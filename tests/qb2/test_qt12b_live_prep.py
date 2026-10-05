"""QT-12 Part B, before the first live buy: the three changes the operator asked for.

Operator verbatim (2026-10-05): *"A definite refusal from Trading 212 (order
rejected, nothing created) skips that name, records the reason, and the run
continues. Only a lost or unclear reply stops the run. Never auto-retry a refused
name; list them all in the report."* -- *"Before the first buy, prove the order
key and the read-only key see the same account (same account id, practice, GBP).
Mismatch -> stop, buy nothing."* -- *"Record the 5 bot names among them (MU, SNDK,
TSLA, GEV, SGLN) in the ledger as PRE-EXISTING holdings, fenced like anchors
(never in the bot's results or pot, never sold by flatten) but not bought by the
program."*
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from qb2.execution import safety
from qb2.execution.anchor_ledger import (NOT_PLACED, PRE_EXISTING, REFUSED,
                                         UNRESOLVED, AnchorLedger,
                                         pre_existing_record)
from qb2.execution.t212_client import Response
from tests.qb2.test_qt12_anchors import (MON_OVERLAP, FakeReader, OrderWire, orders,
                                         calendar, live, plan)

UTC = timezone.utc


def rejected(code: str = "InsufficientFreeForStocksBuy") -> Response:
    """A definite refusal: HTTP 400 with the broker's JSON error, no order id."""
    return Response(400, {}, json.dumps({"code": code,
                                         "message": "planted"}).encode())


# ====================================== 1: a definite refusal skips one name ===

def test_a_refused_name_is_skipped_and_the_run_continues(tmp_path: Path) -> None:
    def on_post(n: int, body: bytes) -> Response:
        if json.loads(body)["ticker"] == "MU_US_EQ":
            return rejected()
        return Response(200, {}, json.dumps({"id": 900 + n, "status": "NEW"}).encode())

    report, _, wire, book = live(tmp_path, wire=OrderWire(on_post=on_post))
    assert report.halted == "", f"a definite refusal halted the run: {report.halted}"
    assert {p["ticker"] for p in wire.posted()} == {"MU_US_EQ", "AZNl_EQ", "VUAGl_EQ"}
    assert report.accepted == ["AZNl_EQ", "VUAGl_EQ"]
    assert [r[0] for r in report.refused] == ["MU_US_EQ"]
    assert "InsufficientFreeForStocksBuy" in report.refused[0][1]
    mu = next(s for s in book.states().values() if s.ticker == "MU_US_EQ")
    assert mu.state == REFUSED and "HTTP 400" in mu.detail
    assert "MU_US_EQ" not in book.blocking_tickers()
    assert book.committed_gbp() < 3 * 1.1, "a refusal spent nothing"
    assert any("REFUSED" in line and "MU_US_EQ" in line for line in report.lines)


def test_a_refused_name_is_never_retried(tmp_path: Path) -> None:
    report, _, _, book = live(tmp_path, wire=OrderWire(on_post=lambda n, b: rejected()))
    assert len(report.refused) == 3
    later = MON_OVERLAP + timedelta(minutes=30)
    report2, _, wire2, _ = live(tmp_path, now=later, ledger=book,
                                reader=FakeReader(exchanges=calendar(later.date())))
    assert wire2.posted() == [], "a refused name was sent again"
    p = plan(tmp_path, ledger=book)
    assert all("refused by the broker" in r.reason for r in p.rows), (
        [r.reason for r in p.rows])


def test_an_unclear_refusal_still_halts(tmp_path: Path) -> None:
    """A 400 that is not the broker's JSON could be anything: unclear -> stop."""
    report, _, wire, book = live(tmp_path, wire=OrderWire(
        on_post=lambda n, b: Response(400, {}, b"<html>proxy</html>")))
    assert wire.posts == 1 and report.halted
    [state] = orders(book)
    assert state.state == UNRESOLVED


def test_a_server_error_still_halts(tmp_path: Path) -> None:
    report, _, wire, book = live(tmp_path, wire=OrderWire(
        on_post=lambda n, b: Response(503, {}, b'{"code": "busy"}')))
    assert wire.posts == 1 and report.halted
    assert orders(book)[0].state == UNRESOLVED


def test_a_refused_key_stops_the_run_without_blaming_the_name(tmp_path: Path) -> None:
    """401/403 refuse the KEY, not the name: nothing was created, so the run
    stops (every name would fail the same way) and the name is NOT marked
    refused -- once the key is fixed it may be bought."""
    report, _, wire, book = live(tmp_path, wire=OrderWire(
        on_post=lambda n, b: Response(403, {}, b'{"code": "Forbidden"}')))
    assert wire.posts == 1 and "403" in report.halted
    [state] = orders(book)
    assert state.state == NOT_PLACED
    assert report.refused == []


# ============================================ 2: both keys, one account ======

class MismatchReader(FakeReader):
    def __init__(self, summary: dict[str, Any]) -> None:
        super().__init__(exchanges=calendar(MON_OVERLAP.date()))
        self._summary = summary

    def account_summary(self) -> dict[str, Any]:
        self.calls.append("summary")
        return self._summary


def test_a_different_account_id_buys_nothing(tmp_path: Path) -> None:
    report, reader, wire, _ = live(
        tmp_path, reader=MismatchReader({"id": 2, "currency": "GBP"}))
    assert wire.posted() == [] and "same account" in report.halted
    assert "summary" in reader.calls


def test_a_read_only_account_not_in_pounds_buys_nothing(tmp_path: Path) -> None:
    report, _, wire, _ = live(
        tmp_path, reader=MismatchReader({"id": 1, "currency": "EUR"}))
    assert wire.posted() == [] and report.halted


def test_a_missing_account_id_buys_nothing(tmp_path: Path) -> None:
    report, _, wire, _ = live(tmp_path, reader=MismatchReader({"currency": "GBP"}))
    assert wire.posted() == [] and report.halted


def test_matching_accounts_are_reported(tmp_path: Path) -> None:
    report, _, wire, _ = live(tmp_path)
    assert wire.posted()
    assert any("same account" in line for line in report.lines)


# ========================== 3: pre-existing holdings, fenced, not bought ====

AT = datetime(2026, 10, 5, 14, 0, tzinfo=UTC)


def test_a_pre_existing_holding_is_fenced_like_an_anchor(tmp_path: Path) -> None:
    book = AnchorLedger(tmp_path / "ledger.jsonl")
    book.append(pre_existing_record("MU_US_EQ", 12.5711224, AT,
                                    "placed by hand: WEB 2026-09-16, IOS 2026-09-29"))
    assert book.anchor_quantities() == {"MU_US_EQ": 12.5711224}
    # Never in the bot's pot, never sold by flatten.
    assert safety.bot_view({"MU_US_EQ": 12.5711224},
                           book.anchor_quantities()) == {"MU_US_EQ": 0.0}
    # Not bought by the program: no spend, no order today, nothing blocking.
    assert book.committed_gbp() == 0.0
    assert book.orders_on(AT.date()) == 0
    assert book.blocking() == []
    [state] = book.states().values()
    assert state.state == PRE_EXISTING


def test_a_pre_existing_record_needs_a_positive_quantity(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(ValueError):
        pre_existing_record("MU_US_EQ", 0.0, AT, "x")


# ==================== found live, 2026-10-05 13:42Z: the broker's real format ===
#
# The first live run halted on INTC with this reply. It IS a definite refusal --
# Trading 212 answers in "problem details" form (type/title/status/detail), not
# the code/message shape the classifier first looked for -- so the run stopped
# instead of skipping one name. Failing safe, but not what the operator asked for.

INTC_REPLY = (b'{"type":"/api-errors/min-quantity-exceeded","title":"Error while '
              b'placing the order","status":400,"detail":"must trade at least '
              b'0.01121443","traceId":"feac44ad92f3012fac34eea71003fada"}')


def test_the_brokers_problem_details_reply_is_a_definite_refusal(
        tmp_path: Path) -> None:
    def on_post(n: int, body: bytes) -> Response:
        if json.loads(body)["ticker"] == "MU_US_EQ":
            return Response(400, {}, INTC_REPLY)
        return Response(200, {}, json.dumps({"id": 900 + n, "status": "NEW"}).encode())

    report, _, wire, book = live(tmp_path, wire=OrderWire(on_post=on_post))
    assert report.halted == "", report.halted
    assert [r[0] for r in report.refused] == ["MU_US_EQ"]
    assert "min-quantity-exceeded" in report.refused[0][1]
    assert len(wire.posted()) == 3


def test_a_stored_definite_refusal_settles_as_refused_not_retried(
        tmp_path: Path) -> None:
    """An earlier run recorded the refusal as UNRESOLVED (the old classifier).

    Left alone, reconcile would call it NOT_PLACED after ten minutes and the
    next run would send it again -- an automatic retry of a refused name.
    """
    from qb2.execution.anchor_ledger import INTENT, OUTCOME

    book = AnchorLedger(tmp_path / "anchors" / "ledger.jsonl")
    at = MON_OVERLAP - timedelta(minutes=1)
    book.append({"kind": INTENT, "intent_id": "i-mu", "at_utc": at.isoformat(),
                 "ticker": "MU_US_EQ", "quantity": "0.0111", "est_gbp": 1.0})
    book.append({"kind": OUTCOME, "intent_id": "i-mu", "at_utc": at.isoformat(),
                 "status": UNRESOLVED, "http_status": 400,
                 "detail": "HTTP 400: " + INTC_REPLY.decode()})

    report, _, wire, _ = live(tmp_path, ledger=book)
    mu = next(s for s in book.states().values() if s.ticker == "MU_US_EQ")
    assert mu.state == REFUSED, mu
    assert "MU_US_EQ" not in {p["ticker"] for p in wire.posted()}
    assert report.halted == "", report.halted
