"""QT-31: VWRL's anchor, on its own pinned one-name list beside the agreed 50.

PLAN_V3 P20, addendum of 2026-11-10. The operator's words, verbatim, 2026-11-09:
"Yes, write it" (his answer to "Shall I write the box for a VWRL anchor at a London
session?"). The GO for the buy itself, still needed: "GO on VWRL anchor: add VWRL to
a separate pinned anchor list and buy one practice-account anchor of about £1
through the anchor buyer, inside the £100 cap."

Fake London-hours clock, fake broker, fake order wire: no socket is ever opened.
"""

from __future__ import annotations

import ast
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from qb2.execution import anchor_extras, anchors, safety
from qb2.execution.anchor_extras import ExtrasRefused
from qb2.execution.anchor_ledger import (FILLED, INTENT, OUTCOME, REFUSED,
                                         UNRESOLVED, AnchorLedger, retry_record)
from qb2.execution.anchors import (NATIVE, SKIP, WAIT, WOULD_BUY, AnchorOrderClient,
                                   AnchorRefused, Identity, Inputs, Quote,
                                   Quotes, UniverseTampered)
from qb2.execution.t212_client import Response
from qb2.guard import pots
from tests.qb2.test_qt12_anchors import (FAKE, FakeReader, OrderWire,
                                         _settled_intent, calendar, frozen_throttle,
                                         planted_live_url, position, seeded)
from tests.qb2.test_qt12b_live_prep import rejected

REPO_ROOT = Path(__file__).resolve().parents[2]
UTC = timezone.utc
ADVISOR_FILE = REPO_ROOT / "docs" / "universe" / "advisor-universe-v1-2026-10-01.json"
TUE_OPEN = datetime(2026, 11, 10, 10, 0, tzinfo=UTC)      # 10:00 London (GMT): open
MON = date(2026, 11, 9)
COMMITTED_AT_QT30 = 46.59                                   # data/anchors/ledger.jsonl
# Trading 212's own instrument row for VWRL (data/raw/t212/instruments-2026-10-01.json).
VWRL_ROW: dict[str, Any] = {
    "ticker": "VWRLl_EQ", "type": "ETF", "workingScheduleId": 70,
    "isin": "IE00B3RBWM25", "currencyCode": "GBP",
    "name": "Vanguard FTSE All-World (Dist)", "shortName": "VWRL",
    "maxOpenQuantity": 50000000.0, "extendedHours": False}
LSE_NAMES = {70: "London Stock Exchange"}


def advisor_vwrl() -> dict[str, Any]:
    doc = json.loads(ADVISOR_FILE.read_text(encoding="utf-8"))
    [entry] = [e for e in doc["entries"] if e["yfinance"] == "VWRL.L"]
    return dict(entry)


def vwrl() -> Identity:
    """VWRL as the anchor buyer resolves it from the agreed extras file."""
    [found] = anchors.resolve_identities(anchor_extras.load(), [VWRL_ROW], LSE_NAMES)
    assert isinstance(found, Identity)
    return found


def lse70(day: date) -> list[dict[str, Any]]:
    """The fake broker calendar, with London on VWRL's own schedule id (70)."""
    cal = calendar(day)
    for exchange in cal:
        if exchange["name"] == "London Stock Exchange":
            exchange["workingSchedules"][0]["id"] = 70
    return cal


def quotes(day: date = MON) -> dict[str, Quotes]:
    """Monday's store close and the newest raw bar, as read on 2026-11-10."""
    return {"VWRL.L": Quotes(Quote(133.69, "GBP", "clean daily close", day),
                             Quote(135.05, NATIVE, "raw 1m bar", day))}


def ledger(tmp_path: Path, committed: float = COMMITTED_AT_QT30) -> AnchorLedger:
    book = seeded(tmp_path / "anchors" / "ledger.jsonl")
    _settled_intent(book, "VWRPl_EQ", committed, TUE_OPEN - timedelta(days=30), FILLED, 1)
    return book


def plan(tmp_path: Path, *, now: datetime = TUE_OPEN,
         book: AnchorLedger | None = None) -> anchors.Plan:
    return anchors.build_plan(
        identities=[vwrl()], quotes=quotes(), fx=Quote(1.3386, "RATE", "clean daily close", MON),
        positions=[], pending=[], ledger=book or ledger(tmp_path), now=now,
        schedules=anchors.parse_schedules(lse70(now.date())), killswitch_on=False)


def live(tmp_path: Path, *, now: datetime = TUE_OPEN, wire: OrderWire | None = None,
         book: AnchorLedger | None = None,
         reader: FakeReader | None = None) -> tuple[anchors.LiveReport, OrderWire, AnchorLedger]:
    wire = wire or OrderWire()
    book = book or ledger(tmp_path)
    report = anchors.run_live(
        inputs=Inputs([vwrl()], quotes(), Quote(1.3386, "RATE", "clean daily close", MON)),
        reader=reader or FakeReader(exchanges=lse70(now.date())),
        orderer=AnchorOrderClient(FAKE, transport=wire, throttle=frozen_throttle()),
        ledger=book, now_fn=lambda: now, root=tmp_path, sleep=lambda s: None)
    return report, wire, book


def extras_doc() -> dict[str, Any]:
    return dict(json.loads(anchor_extras.EXTRAS_FILE.read_text(encoding="utf-8")))


def written(tmp_path: Path, doc: dict[str, Any]) -> tuple[Path, str]:
    """A planted extras file, and its own hash -- so only the content checks refuse it."""
    path = tmp_path / "extras.json"
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return path, anchor_extras.sha256_lf(path.read_bytes())


# ===================================================== C1, C2: the list ===

def test_the_extras_file_is_pinned_and_holds_vwrl_alone_as_the_advisor_list_has_it() -> None:
    raw = anchor_extras.EXTRAS_FILE.read_bytes()
    assert anchor_extras.sha256_lf(raw) == anchor_extras.EXTRAS_SHA256
    doc = extras_doc()
    assert doc["status"] == "AGREED" and doc["list"] == "anchor-extras"
    assert anchor_extras.load() == [advisor_vwrl()] == doc["entries"]
    assert vwrl().t212_ticker == "VWRLl_EQ" and vwrl().schedule_id == 70


def test_a_changed_extras_file_is_refused(tmp_path: Path) -> None:
    for change in (b" ", b"\n"):
        path = tmp_path / "changed.json"
        path.write_bytes(anchor_extras.EXTRAS_FILE.read_bytes() + change)
        with pytest.raises(ExtrasRefused, match="hash changed"):
            anchor_extras.load(path)
    with pytest.raises(ExtrasRefused, match="cannot be read"):
        anchor_extras.load(tmp_path / "missing.json")


def test_a_second_name_is_refused_even_with_its_own_hash(tmp_path: Path) -> None:
    doc = extras_doc()
    second = dict(advisor_vwrl(), yfinance="VWRP.L", t212_ticker="VWRPl_EQ",
                  isin="IE00BK5BQT80")
    doc["entries"] = [advisor_vwrl(), second]
    path, digest = written(tmp_path, doc)
    with pytest.raises(ExtrasRefused, match="exactly one name"):
        anchor_extras.load(path, digest)


def test_any_other_single_name_is_refused(tmp_path: Path) -> None:
    for key, value in (("yfinance", "VWRP.L"), ("t212_ticker", "VWRL_US_EQ"),
                       ("isin", "IE00BK5BQT80"), ("exchange", "NYSE"),
                       ("quote_currency", "USD")):
        doc = extras_doc()
        doc["entries"] = [dict(advisor_vwrl(), **{key: value})]
        path, digest = written(tmp_path, doc)
        with pytest.raises(ExtrasRefused, match="other than VWRL"):
            anchor_extras.load(path, digest)
    doc = extras_doc()
    doc["status"] = "DRAFT"
    path, digest = written(tmp_path, doc)
    with pytest.raises(ExtrasRefused):
        anchor_extras.load(path, digest)


# ========================================== C3: the 50 plus the extras ===

def test_load_inputs_reads_the_50_plus_vwrl(tmp_path: Path,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(anchors, "load_verified_lists",
                        lambda *a, **k: ([dict(VWRL_ROW)], dict(LSE_NAMES)))
    inputs = anchors.load_inputs(clean_root=tmp_path, raw_root=tmp_path)
    resolved = [i for i in inputs.identities if isinstance(i, Identity)]
    assert len(inputs.identities) == 51 and resolved == [vwrl()]
    assert "VWRL.L" in inputs.quotes and len(inputs.quotes) == 51


def test_a_changed_extras_file_stops_the_run_before_any_broker_read(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
        tmp_path: Path) -> None:
    tampered = tmp_path / "tampered.json"
    tampered.write_bytes(anchor_extras.EXTRAS_FILE.read_bytes() + b" ")
    monkeypatch.setattr(anchor_extras, "EXTRAS_FILE", tampered)
    monkeypatch.setattr(anchors, "refuse_host_overrides", lambda *a, **k: None)
    monkeypatch.setattr(anchors, "load_verified_lists",
                        lambda *a, **k: ([dict(VWRL_ROW)], dict(LSE_NAMES)))

    def no_broker(*args: object, **kwargs: object) -> None:
        raise AssertionError("the broker was read after a refused extras file")

    monkeypatch.setattr(anchors, "BrokerReader", no_broker)
    monkeypatch.setattr(anchors, "AnchorOrderClient", no_broker)
    for argv in ([], ["--live"]):
        assert anchors.main(argv) == 2
        assert "REFUSED" in capsys.readouterr().out


def test_the_50_name_pin_still_holds(tmp_path: Path) -> None:
    assert anchors.UNIVERSE_FILE.name == "bot-universe-v1-2026-10-01.json"
    assert anchors.UNIVERSE_SHA256 == (
        "b229811dedd54aef4a87e8bff9a8ee4fc61522d035ac29457d7f547fe2b26e44")
    entries = anchors.load_universe()
    assert len(entries) == 50 and "VWRL.L" not in {e["yfinance"] for e in entries}
    doc = json.loads(anchors.UNIVERSE_FILE.read_text(encoding="utf-8"))
    doc["entries"].append(advisor_vwrl())                  # 51, with its own hash
    path = tmp_path / "bot-51.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(UniverseTampered):
        anchors.load_universe(path, anchors.sha256_lf(path))


# ============================================== C4: the fences, for VWRL ===

def test_vwrl_is_planned_as_one_buy_of_about_a_pound(tmp_path: Path) -> None:
    p = plan(tmp_path)
    [row] = p.rows
    assert (row.decision, row.t212_ticker) == (WOULD_BUY, "VWRLl_EQ")
    assert row.quantity == Decimal("0.0079")              # GBP 1 / 133.69 x 1.05, up
    assert row.est_gbp is not None and 1.00 <= row.est_gbp <= 1.10
    assert p.to_buy() == [row]
    assert "names to buy: 1 (1 now, 0 when their market opens)" in anchors.render(p)


def test_a_non_practice_host_is_refused_before_any_socket(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert anchors.DEMO_BASE_URL == "https://demo.trading212.com/api/v0"
    with pytest.raises(anchors.LiveServerRefused):
        AnchorOrderClient(FAKE, base_url=planted_live_url())
    monkeypatch.setenv("T212_BASE_URL", planted_live_url())

    def must_not_run(*args: object, **kwargs: object) -> None:
        raise AssertionError("reached past the refused host")

    for name in ("load_inputs", "BrokerReader", "AnchorOrderClient", "order_transport"):
        monkeypatch.setattr(anchors, name, must_not_run)
    monkeypatch.setattr(anchor_extras, "load", must_not_run)
    assert anchors.main(["--live"]) == 2


def test_the_lifetime_cap_holds_on_the_new_path(tmp_path: Path) -> None:
    [row] = plan(tmp_path, book=ledger(tmp_path / "a", committed=99.50)).rows
    assert row.decision == SKIP and row.reason.startswith("lifetime cap")
    report, wire, _ = live(tmp_path / "b", book=ledger(tmp_path / "b", committed=99.50))
    assert wire.posted() == [] and report.accepted == []
    [row] = plan(tmp_path, book=ledger(tmp_path / "c", committed=98.90)).rows
    assert row.decision == WOULD_BUY                     # 98.90 + about 1.07 <= 100


def test_three_pounds_per_order_holds_for_vwrl(tmp_path: Path) -> None:
    book = ledger(tmp_path)
    book.append({"kind": INTENT, "intent_id": "anchor-test-min", "ticker": "VWRLl_EQ",
                 "at_utc": (TUE_OPEN - timedelta(days=1)).isoformat(),
                 "quantity": "0.0079", "est_gbp": 1.07})
    book.append({"kind": OUTCOME, "intent_id": "anchor-test-min", "status": REFUSED,
                 "at_utc": (TUE_OPEN - timedelta(days=1)).isoformat(),
                 "detail": "HTTP 400: must trade at least 0.05"})
    book.append(retry_record(book, "anchor-test-min", "test words", TUE_OPEN))
    [row] = plan(tmp_path, book=book).rows
    assert row.decision == SKIP and row.reason.startswith("over GBP 3 cap")
    wire = OrderWire()
    client = AnchorOrderClient(FAKE, transport=wire, throttle=frozen_throttle())
    with pytest.raises(AnchorRefused, match="may not exceed"):
        client.buy("VWRLl_EQ", Decimal("0.0225"), 3.01)
    assert wire.calls == []


@pytest.mark.parametrize("now", [
    datetime(2026, 11, 10, 7, 0, tzinfo=UTC),            # before London opens
    datetime(2026, 11, 10, 8, 5, tzinfo=UTC),            # inside the opening margin
    datetime(2026, 11, 10, 16, 20, tzinfo=UTC),          # inside the closing margin
    datetime(2026, 11, 14, 12, 0, tzinfo=UTC)])          # a Saturday
def test_outside_the_session_it_does_not_buy(tmp_path: Path, now: datetime) -> None:
    [row] = plan(tmp_path, now=now).rows
    assert row.decision == WAIT
    report, wire, _ = live(tmp_path / "live", now=now)
    assert wire.posted() == [] and report.accepted == []


def test_an_unknown_outcome_blocks_vwrl_halts_and_is_never_resent(tmp_path: Path) -> None:
    def timeout(n: int, body: bytes) -> Response:
        raise TimeoutError("no reply")

    report, wire, book = live(tmp_path, wire=OrderWire(on_post=timeout))
    assert wire.posts == 1 and "unknown" in report.halted
    [state] = [s for s in book.states().values() if s.ticker == "VWRLl_EQ"]
    assert state.state == UNRESOLVED
    report2, wire2, _ = live(tmp_path, now=TUE_OPEN + timedelta(minutes=1), book=book)
    assert wire2.posted() == [] and "no confirmed outcome" in report2.halted
    [row] = plan(tmp_path, book=book).rows
    assert row.decision == SKIP and row.reason.startswith("unresolved order")


def test_exactly_one_attempt_per_run_and_no_retry(tmp_path: Path) -> None:
    report, wire, book = live(tmp_path / "r", wire=OrderWire(on_post=lambda n, b: rejected()))
    assert wire.posts == 1 and [t for t, _ in report.refused] == ["VWRLl_EQ"]
    _, wire2, _ = live(tmp_path / "r", book=book)
    assert wire2.posts == 0                                # a refusal is never retried
    report3, wire3, book3 = live(tmp_path / "a")
    assert wire3.posts == 1 and report3.accepted == ["VWRLl_EQ"]
    assert wire3.posted()[0] == {"ticker": "VWRLl_EQ", "quantity": 0.0079,
                                 "extendedHours": False}
    filled = {"order": {"id": 1001, "ticker": "VWRLl_EQ", "side": "BUY",
                        "status": "FILLED", "initiatedFrom": "API", "quantity": 0.0079,
                        "filledQuantity": 0.0079, "createdAt": TUE_OPEN.isoformat()},
              "fill": {"walletImpact": {"currency": "GBP", "netValue": -1.07}}}
    held = FakeReader(exchanges=lse70(TUE_OPEN.date()), history={"VWRLl_EQ": [filled]},
                      positions=[position("VWRLl_EQ", 0.0079)])
    report4, wire4, _ = live(tmp_path / "a", book=book3, reader=held,
                             now=TUE_OPEN + timedelta(hours=1))
    assert any("settled FILLED" in line for line in report4.lines)
    assert wire4.posts == 0 and report4.plan is not None   # held: never a second buy
    assert [r.reason for r in report4.plan.rows] == ["held: the broker already prices it"]


def test_vwrl_is_in_neither_pot(tmp_path: Path) -> None:
    anchor = pots.Line("VWRLl_EQ", pots.ANCHOR, 5_000.0)
    assert pots.used(safety.ADVISOR, [anchor]) == 0 == pots.used(safety.BOT, [anchor])
    view = pots.View(account_total_gbp=10_000.0, lines=(anchor,))
    pots.check(safety.ADVISOR, 6_999.0, view)                # the anchor takes no room
    pots.check(safety.BOT, 2_999.0, view)


def test_flatten_leaves_vwrl_alone(tmp_path: Path) -> None:
    book = AnchorLedger(tmp_path / "ledger.jsonl")
    _settled_intent(book, "VWRLl_EQ", 1.07, TUE_OPEN, FILLED, 7)
    held = book.anchor_quantities()
    broker = {"VWRLl_EQ": held["VWRLl_EQ"]}
    assert safety.bot_view(broker, held) == {"VWRLl_EQ": 0.0}
    wrongly_absorbed = [safety.Holding("VWRLl_EQ", held["VWRLl_EQ"], safety.BOT)]
    assert safety.flatten_bot(wrongly_absorbed, "close", broker_quantities=broker,
                              anchor_quantities=held) == []


ANCHOR_BOOKS = ("qb2/execution/anchors.py", "qb2/execution/anchor_extras.py",
                "qb2/execution/anchor_ledger.py", "qb2/execution/ledger_backup.py",
                "qb2/execution/safety.py",
                "qb2/tools/record_split.py")    # QT-32D: appends split lines on his words; no order client


def test_only_the_anchor_books_can_see_vwrls_anchor_and_nothing_imports_the_buyer() -> None:
    """No result, pot or advisor module reads the extras list or the anchor ledger."""
    seen: list[str] = []
    for path in sorted((REPO_ROOT / "qb2").rglob("*.py")):
        name = path.relative_to(REPO_ROOT).as_posix()
        if "__pycache__" in path.parts or name in ANCHOR_BOOKS:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(
                node, (ast.Import, ast.ImportFrom)) else []
            if isinstance(node, ast.ImportFrom):
                names.append(node.module or "")
            text = node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else ""
            if any("anchor_extras" in n or "anchor_ledger" in n for n in names) \
                    or "anchor-extras" in text:
                seen.append(f"{name}:{getattr(node, 'lineno', '?')}")
    assert seen == []
    from tests.wall.test_broker_readonly import doorway_importers
    assert doorway_importers() == []


def test_the_operators_words_are_in_the_list_and_the_plan_verbatim() -> None:
    doc = extras_doc()
    assert doc["agreed_words_verbatim"] == "Yes, write it"
    plan_text = (REPO_ROOT / "docs" / "plan" / "PLAN_V3.md").read_text(encoding="utf-8")
    flat = " ".join(plan_text.split())
    for words in ("Yes, write it", "change this for 6am",
                  "Do not ask for permission to do things, i will be gone after i paste it",
                  "GO on VWRL anchor: add VWRL to a separate pinned anchor list and buy one "
                  "practice-account anchor of about £1 through the anchor buyer, inside the "
                  "£100 cap."):
        assert words in flat
