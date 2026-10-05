"""QT-12 fix: size each anchor to its instrument's own rules, retry the refused.

Operator verbatim (2026-10-05): *"Size each anchor order to its instrument's
rules: round quantity UP to the allowed decimal places and to at least the
minimum quantity, then re-run live (practice only) for the 18 refused names
during the London+NY overlap. Report any name over £1.10 before buying it.
Lifetime cap stays £100."*

The rules come from the broker's own refusals (it publishes them nowhere else):
"must trade at least 0.01121443" and "invalid quantity precision 3". A refused
name is still never retried by itself -- only an operator's recorded words lift
ONE refusal, once.
"""

from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from qb2.execution import anchors, costs
from qb2.execution.anchor_ledger import (INTENT, OUTCOME, REFUSED, AnchorLedger,
                                         LedgerCorrupt, retry_record)
from qb2.execution.anchors import InstrumentRule, WOULD_BUY, SKIP
from qb2.execution.t212_client import Response
from tests.qb2.test_qt12_anchors import (AZN, FAKE, MON_OVERLAP, FakeReader,
                                         OrderWire, calendar, frozen_throttle,
                                         fx_on, live, plan, quotes_on)

WORDS = "re-run live (practice only) for the 18 refused names"


def reply(type_: str, detail: str) -> str:
    return "HTTP 400: " + json.dumps(
        {"type": f"/api-errors/{type_}", "title": "Error while placing the order",
         "status": 400, "detail": detail, "traceId": "t"})


PRECISION_3 = reply("quantity-precision-mismatch", "invalid quantity precision 3")
PRECISION_2 = reply("quantity-precision-mismatch", "invalid quantity precision 2")
MIN_QTY = reply("min-quantity-exceeded", "must trade at least 0.01121443")


def refuse(book: AnchorLedger, ticker: str, detail: str, n: int = 1) -> str:
    at = MON_OVERLAP - timedelta(hours=1, minutes=n)
    intent_id = f"i-{ticker}-{n}"
    book.append({"kind": INTENT, "intent_id": intent_id, "at_utc": at.isoformat(),
                 "ticker": ticker, "quantity": "0.0084", "est_gbp": 1.0})
    book.append({"kind": OUTCOME, "intent_id": intent_id, "at_utc": at.isoformat(),
                 "status": REFUSED, "http_status": 400, "detail": detail})
    return intent_id


# ============================================ the rules, from the broker's words ===

def test_the_rules_are_read_from_the_brokers_refusals() -> None:
    assert anchors.parse_rule(PRECISION_3) == InstrumentRule(decimals=3)
    assert anchors.parse_rule(PRECISION_2) == InstrumentRule(decimals=2)
    assert anchors.parse_rule(MIN_QTY) == InstrumentRule(
        min_quantity=Decimal("0.01121443"))
    assert anchors.parse_rule("HTTP 400: something else") == InstrumentRule()


def test_rules_from_several_refusals_of_one_name_combine(tmp_path: Path) -> None:
    book = AnchorLedger(tmp_path / "ledger.jsonl")
    refuse(book, "AZNl_EQ", PRECISION_3, 1)
    refuse(book, "AZNl_EQ", MIN_QTY, 2)
    assert anchors.instrument_rules(book)["AZNl_EQ"] == InstrumentRule(
        decimals=3, min_quantity=Decimal("0.01121443"))


# ================================================== sizing rounds UP to the rule ===

def test_precision_rounds_up_to_the_allowed_places() -> None:
    inst = costs.Instrument(ticker="X", currency="GBP", market="LSE",
                                    kind="STOCK", aim=False)
    s = anchors.size_anchor(118.7, 118.48, inst, InstrumentRule(decimals=3))
    assert s.quantity == Decimal("0.009"), s.quantity        # 1/118.7 = 0.00842..
    assert -s.quantity.as_tuple().exponent <= 3              # type: ignore[operator]
    assert s.quantity * Decimal("118.7") >= 1


def test_the_minimum_quantity_is_met_rounded_up() -> None:
    inst = costs.Instrument(ticker="X", currency="USD", market="US",
                                    kind="STOCK", aim=False)
    s = anchors.size_anchor(89.5, 89.5, inst,
                            InstrumentRule(min_quantity=Decimal("0.01121443")))
    assert s.quantity == Decimal("0.0113"), s.quantity
    assert s.quantity >= Decimal("0.01121443")


def test_both_rules_together() -> None:
    inst = costs.Instrument(ticker="X", currency="GBP", market="LSE",
                                    kind="STOCK", aim=False)
    s = anchors.size_anchor(4.0, 4.0, inst, InstrumentRule(
        decimals=2, min_quantity=Decimal("0.301")))
    assert s.quantity == Decimal("0.31"), s.quantity


def test_a_name_with_no_rule_is_sized_as_before() -> None:
    inst = costs.Instrument(ticker="X", currency="GBP", market="LSE",
                                    kind="STOCK", aim=False)
    assert (anchors.size_anchor(118.7, 118.48, inst).quantity
            == anchors.size_anchor(118.7, 118.48, inst, InstrumentRule()).quantity
            == Decimal("0.0085"))


# ================================== a refusal is lifted only by recorded words ===

def test_a_refused_name_stays_refused_without_the_operators_words(
        tmp_path: Path) -> None:
    book = AnchorLedger(tmp_path / "ledger.jsonl")
    refuse(book, "AZNl_EQ", PRECISION_3)
    p = plan(tmp_path, ledger=book)
    azn = next(r for r in p.rows if r.t212_ticker == "AZNl_EQ")
    assert azn.decision == SKIP and "refused by the broker" in azn.reason


def test_the_operators_words_lift_one_refusal_and_size_to_the_rule(
        tmp_path: Path) -> None:
    book = AnchorLedger(tmp_path / "ledger.jsonl")
    intent_id = refuse(book, "AZNl_EQ", PRECISION_3)
    book.append(retry_record(book, intent_id, WORDS, MON_OVERLAP))
    assert "AZNl_EQ" not in book.refused()
    p = plan(tmp_path, ledger=book)
    azn = next(r for r in p.rows if r.t212_ticker == "AZNl_EQ")
    assert azn.decision == WOULD_BUY, azn.reason
    assert azn.quantity == Decimal("0.009")


def test_a_retry_needs_words_and_a_refusal(tmp_path: Path) -> None:
    book = AnchorLedger(tmp_path / "ledger.jsonl")
    intent_id = refuse(book, "AZNl_EQ", PRECISION_3)
    with pytest.raises(ValueError):
        retry_record(book, intent_id, "  ", MON_OVERLAP)
    with pytest.raises(ValueError):
        retry_record(book, "no-such-intent", WORDS, MON_OVERLAP)
    at = MON_OVERLAP.isoformat()
    book.append({"kind": INTENT, "intent_id": "i-ok", "at_utc": at,
                 "ticker": "VUAGl_EQ", "quantity": "0.009", "est_gbp": 1.0})
    with pytest.raises(ValueError):
        retry_record(book, "i-ok", WORDS, MON_OVERLAP)
    # A hand-written retry line for an intent that was not refused is corrupt.
    book.append({"kind": "RETRY_AUTHORISED", "intent_id": "i-ok", "at_utc": at,
                 "operator_words": WORDS})
    with pytest.raises(LedgerCorrupt):
        book.states()


def test_the_retry_is_sent_once_at_the_rule_and_a_second_refusal_sticks(
        tmp_path: Path) -> None:
    book = AnchorLedger(tmp_path / "anchors" / "ledger.jsonl")
    intent_id = refuse(book, "AZNl_EQ", PRECISION_3)
    book.append(retry_record(book, intent_id, WORDS, MON_OVERLAP))

    def on_post(n: int, body: bytes) -> Response:
        return Response(400, {}, PRECISION_2[len("HTTP 400: "):].encode())

    report, _, wire, _ = live(tmp_path, ledger=book, identities=[AZN],
                              wire=OrderWire(on_post=on_post))
    sent = wire.posted()
    assert [p["ticker"] for p in sent] == ["AZNl_EQ"]
    assert str(sent[0]["quantity"]) == "0.009"
    assert report.halted == "" and [r[0] for r in report.refused] == ["AZNl_EQ"]
    later = MON_OVERLAP + timedelta(minutes=30)
    _, _, wire2, _ = live(tmp_path, ledger=book, identities=[AZN], now=later,
                          reader=FakeReader(exchanges=calendar(later.date())))
    assert wire2.posted() == [], "a second refusal was retried by itself"


# ============================================== names over GBP 1.10 wait for him ===

def test_names_over_the_review_line_are_held_and_reported(tmp_path: Path) -> None:
    book = AnchorLedger(tmp_path / "ledger.jsonl")
    # AZN at 2 dp: 0.01 x GBP 118.7 = GBP 1.19, over GBP 1.10.
    book.append(retry_record(book, refuse(book, "AZNl_EQ", PRECISION_2), WORDS,
                             MON_OVERLAP))
    p = anchors.build_plan(
        identities=[AZN],
        quotes=quotes_on(MON_OVERLAP.date() - timedelta(days=3)),
        fx=fx_on(MON_OVERLAP.date() - timedelta(days=3)),
        positions=[], pending=[], ledger=book, now=MON_OVERLAP,
        schedules=anchors.parse_schedules(calendar(MON_OVERLAP.date())),
        killswitch_on=False, hold_above_gbp=1.10)
    azn = p.rows[0]
    assert azn.decision == SKIP and "over GBP 1.10" in azn.reason, azn.reason
    assert azn.est_gbp is not None and azn.est_gbp > 1.10


def test_the_live_run_never_sends_a_held_name(tmp_path: Path) -> None:
    book = AnchorLedger(tmp_path / "anchors" / "ledger.jsonl")
    book.append(retry_record(book, refuse(book, "AZNl_EQ", PRECISION_2), WORDS,
                             MON_OVERLAP))
    reader = FakeReader(exchanges=calendar(MON_OVERLAP.date()))
    wire = OrderWire()
    report = anchors.run_live(
        inputs=anchors.Inputs([AZN], quotes_on(MON_OVERLAP.date()),
                              fx_on(MON_OVERLAP.date())),
        reader=reader,
        orderer=anchors.AnchorOrderClient(FAKE, transport=wire,
                                          throttle=frozen_throttle()),
        ledger=book, now_fn=lambda: MON_OVERLAP, root=tmp_path,
        sleep=lambda s: None, hold_above_gbp=1.10)
    assert wire.posted() == [], "a name over GBP 1.10 was bought before review"
    assert report.halted == ""
