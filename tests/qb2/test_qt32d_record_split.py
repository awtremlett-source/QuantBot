"""QT-32D: the CSH2 split recorder -- BUILT and dry-run only; applying it needs the operator's words.

Operator, 2026-11-10 18:08 (verbatim): "QT-32, no GO" -- so the CSH2 split is NOT recorded in the ledger.
The two bookings are copied from Trading 212's order history, read with the read-only key at 06:30 UTC on
11 Nov 2026 (docs/reports/QT-32.md, D1). Offline: a fake read-only broker, tmp ledgers, no socket.
"""

from __future__ import annotations

import ast
import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest

from qb2.execution import anchor_ledger, ledger_backup
from qb2.execution.anchor_ledger import AnchorLedger
from qb2.tools import record_split

ROOT = Path(__file__).resolve().parents[2]
CSH2 = "CSH2l_EQ"
ANCHOR = {"order": {"id": 56050885915, "ticker": CSH2, "side": "BUY", "status": "FILLED", "quantity": 0.0008,
                    "filledQuantity": 0.0008, "createdAt": "2026-10-05T13:49:56.000Z", "initiatedFrom": "API"},
          "fill": {"id": 56050887696, "type": "TRADE", "quantity": 0.0008, "price": 125480.0}}
SPLIT_IN = {"order": {"id": 57101251395, "ticker": CSH2, "side": "BUY", "status": "FILLED", "quantity": 0.2,
                      "filledQuantity": 0.2, "createdAt": "2026-10-27T07:52:06.000Z"},   # no initiatedFrom, as served
            "fill": {"id": 57101251399, "type": "STOCK_SPLIT", "quantity": 0.2, "price": 501.9}}
SPLIT_OUT = {"order": {"id": 57101251392, "ticker": CSH2, "side": "SELL", "status": "FILLED", "quantity": -0.0008,
                       "filledQuantity": -0.0008, "createdAt": "2026-10-27T07:52:06.000Z"},
             "fill": {"id": 57101251394, "type": "STOCK_SPLIT", "quantity": -0.0008, "price": 125475.0}}
OTHER = {"order": {"id": 56050880001, "ticker": "VUSAl_EQ", "side": "BUY", "status": "FILLED", "quantity": 0.02,
                   "filledQuantity": 0.02, "createdAt": "2026-10-05T13:40:00.000Z", "initiatedFrom": "API"},
         "fill": {"id": 1, "type": "TRADE"}}
CSH2_LINES = [  # data/anchors/ledger.jsonl's three CSH2 lines, as written on 5 Oct
    {"at_utc": "2026-10-05T13:49:46.118203+00:00", "est_gbp": 1.0048, "intent_id": "anchor-CSH2", "kind": "INTENT",
     "quantity": "0.0008", "ticker": CSH2},
    {"at_utc": "2026-10-05T13:49:56.096755+00:00", "intent_id": "anchor-CSH2", "kind": "OUTCOME",
     "order_id": 56050885915, "status": "ACCEPTED"},
    {"at_utc": "2026-10-05T14:26:47.931087+00:00", "filled_gbp": 1.0, "filled_quantity": 0.0008,
     "intent_id": "anchor-CSH2", "kind": "RECONCILED", "order_id": 56050885915, "status": "FILLED"},
    {"at_utc": "2026-10-05T13:39:50+00:00", "est_gbp": 1.01, "intent_id": "anchor-VUSA", "kind": "INTENT",
     "quantity": 0.02, "ticker": "VUSAl_EQ"},
    {"at_utc": "2026-10-05T13:40:01+00:00", "filled_gbp": 1.0, "filled_quantity": 0.02, "intent_id": "anchor-VUSA",
     "kind": "RECONCILED", "order_id": 56050880001, "status": "FILLED"}]


class Broker:
    """The read-only broker as the tool sees it: GET reads only, every one counted."""

    def __init__(self, history: list[dict[str, Any]] | None = None) -> None:
        self.history = history if history is not None else [SPLIT_IN, SPLIT_OUT, ANCHOR, OTHER]
        self.reads: list[str] = []

    def history_orders(self, ticker: str | None = None) -> list[dict[str, Any]]:
        self.reads.append(f"history {ticker}")
        return [h for h in self.history if ticker is None or h["order"]["ticker"] == ticker]

    def positions(self) -> list[dict[str, Any]]:
        self.reads.append("positions")
        return [{"instrument": {"ticker": CSH2}, "quantity": 0.2}]


def ledger(tmp: Path) -> AnchorLedger:
    book = AnchorLedger(tmp / "anchors" / "ledger.jsonl")
    for line in CSH2_LINES:
        book.append(line)
    return book


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def go(tmp: Path, words: str | None, broker: Broker | None = None) -> tuple[int, list[str], AnchorLedger]:
    book, said = ledger(tmp), list[str]()
    backups: list[Path] = []

    def backup(path: Path) -> str:
        backups.append(path)
        return ledger_backup.backup(path, dest=tmp / "backups")
    code = record_split.run(CSH2, words, broker or Broker(), book, backup=backup, say=said.append)
    return code, said, book


def test_it_refuses_unless_the_words_match_exactly(tmp_path: Path) -> None:
    near = [record_split.GO_WORDS[:-1], record_split.GO_WORDS + " ", " " + record_split.GO_WORDS,
            record_split.GO_WORDS.lower(), record_split.GO_WORDS.replace("'", "’"),
            record_split.GO_WORDS.replace("0.2", "0.20"), "GO", "QT-32, no GO", ""]
    for n, words in enumerate(near):
        code, said, book = go(tmp_path / str(n), words)
        assert code == 2 and said[-1].startswith("REFUSED: --words is not the CSH2 GO line"), words
        assert len(book.records()) == len(CSH2_LINES)                       # nothing written
        assert not (tmp_path / str(n) / "backups").exists()                 # not even a backup
    code, said, book = go(tmp_path / "exact", record_split.GO_WORDS)
    assert code == 0 and said[-1] == "recorded 2 line(s); F13 now passes"


def test_the_go_words_are_the_decision_requested_line_verbatim() -> None:
    assert record_split.GO_WORDS in " ".join((ROOT / "docs" / "reports" / "QT-31.md").read_text(
        encoding="utf-8").split())


def test_the_dry_run_writes_nothing_and_shows_f13_would_pass(tmp_path: Path) -> None:
    book = ledger(tmp_path)
    before = sha(book.path)
    assert ledger_backup.unrecorded(book, Broker().history_orders(), ledger_backup.matches).startswith(
        "anchor ledger is stale: the broker holds 2 API order(s)")              # today's F13 halt
    said: list[str] = []
    assert record_split.run(CSH2, None, Broker(), book, say=said.append) == 0
    assert sha(book.path) == before and len(said) == 6
    assert said[0] == "broker holds CSH2l_EQ: 0.2 (read-only key)"
    assert "'order_id': 57101251392" in said[1] and "'quantity': -0.0008" in said[1]   # oldest id first
    assert "'order_id': 57101251395" in said[2] and "'quantity': 0.2" in said[2]
    assert said[3] == "CSH2l_EQ anchor in the ledger: 0.0008 -> 0.2; spent from the caps: nothing"
    assert said[4] == "F13 would then pass: no API order in the newest history page is missing"
    assert said[5].startswith("DRY RUN: nothing written")


def test_it_appends_only_and_never_twice(tmp_path: Path) -> None:
    code, _, book = go(tmp_path, record_split.GO_WORDS)
    after = book.path.read_bytes()
    lines = [json.loads(x) for x in after.decode("utf-8").splitlines()]
    assert code == 0 and lines[:len(CSH2_LINES)] == [json.loads(json.dumps(x, sort_keys=True)) for x in CSH2_LINES]
    assert [(x["kind"], x["order_id"]) for x in lines[len(CSH2_LINES):]] == [
        ("SPLIT", 57101251392), ("SPLIT", 57101251395)]
    said: list[str] = []
    assert record_split.run(CSH2, record_split.GO_WORDS, Broker(), book, say=said.append) == 0
    assert book.path.read_bytes() == after                                   # the second run adds nothing
    assert said[-1] == "nothing to record: the ledger already holds every split booking of CSH2l_EQ"


def test_a_booking_that_is_not_a_split_is_refused(tmp_path: Path) -> None:
    odd = {"order": {**SPLIT_IN["order"], "id": 57101251400}, "fill": {**SPLIT_IN["fill"], "type": "TRADE"}}
    for history in ([SPLIT_IN, SPLIT_OUT, ANCHOR, odd], [odd]):
        code, said, book = go(tmp_path / str(len(history)), record_split.GO_WORDS, Broker(history))
        assert code == 2 and "not splits: order 57101251400" in said[-1]
        assert len(book.records()) == len(CSH2_LINES)
    wrong_sign = {"order": {**SPLIT_OUT["order"], "side": "BUY"}, "fill": SPLIT_OUT["fill"]}
    code, said, _ = go(tmp_path / "sign", record_split.GO_WORDS, Broker([SPLIT_IN, wrong_sign, ANCHOR]))
    assert code == 2 and "not splits" in said[-1]


def test_it_takes_a_verified_backup_first_and_writes_nothing_without_one(tmp_path: Path) -> None:
    book, said = ledger(tmp_path), list[str]()
    before = sha(book.path)

    def broken(path: Path) -> str:
        raise OSError("planted: the backup did not verify")
    assert record_split.run(CSH2, record_split.GO_WORDS, Broker(), book, backup=broken, say=said.append) == 2
    assert sha(book.path) == before and said[-1] == "REFUSED: planted: the backup did not verify"
    code, said, book = go(tmp_path / "ok", record_split.GO_WORDS)
    copies = list((tmp_path / "ok" / "backups" / "anchors").glob("ledger-*.jsonl"))
    assert code == 0 and len(copies) == 1 and len(AnchorLedger(copies[0]).records()) == len(CSH2_LINES)
    assert any(x.startswith("ledger backup verified: ") for x in said)


def test_once_recorded_csh2_reads_0_2_spends_nothing_and_f13_passes(tmp_path: Path) -> None:
    book = ledger(tmp_path)
    spent, orders = book.committed_gbp(), book.orders_on(date(2026, 10, 27))
    assert book.anchor_quantities() == {CSH2: 0.0008, "VUSAl_EQ": 0.02}
    go_code, _, book = go(tmp_path / "go", record_split.GO_WORDS)
    assert go_code == 0
    assert book.anchor_quantities() == {CSH2: 0.2, "VUSAl_EQ": 0.02}
    assert book.committed_gbp() == spent and book.orders_on(date(2026, 10, 27)) == orders == 0
    assert book.blocking() == [] and book.refused() == {}
    assert ledger_backup.unrecorded(book, Broker().history_orders(), ledger_backup.matches) == ""
    assert {s.state for s in book.states().values() if s.ticker == CSH2} == {"FILLED", anchor_ledger.SPLIT}


def test_a_ledger_with_no_split_line_folds_exactly_as_before(tmp_path: Path) -> None:
    """The new kind is inert until a SPLIT line exists: the other five fold as they always did."""
    book = ledger(tmp_path)
    book.append(anchor_ledger.pre_existing_record("RRl_EQ", 0.05, datetime(2026, 10, 6), "bought by hand"))
    book.append({"kind": "INTENT", "intent_id": "open", "ticker": "SGLNl_EQ", "at_utc": "2026-10-06T10:00:00+00:00",
                 "quantity": 0.03, "est_gbp": 1.5})
    assert book.anchor_quantities() == {CSH2: 0.0008, "VUSAl_EQ": 0.02, "RRl_EQ": 0.05, "SGLNl_EQ": 0.03}
    assert book.committed_gbp() == pytest.approx(1.0048 + 1.01 + 1.5)
    assert [s.order_id for s in book.states().values()] == [56050885915, 56050880001, None, None]


def test_it_imports_no_order_client_and_reads_only(tmp_path: Path) -> None:
    """It can place, amend or cancel nothing: no order doorway, no sender, no POST, only the read-only client."""
    source = (ROOT / "qb2" / "tools" / "record_split.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    modules = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert modules <= {"__future__", "argparse", "shutil", "sys", "tempfile", "collections.abc", "pathlib", "typing",
                       "qb2.execution", "qb2.execution.anchor_ledger", "qb2.execution.t212_client"}
    names = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
    assert names <= {"annotations", "Callable", "Mapping", "Sequence", "Path", "Any", "Protocol", "ledger_backup",
                     "SPLIT", "AnchorLedger", "T212DemoClient"}
    assert "POST" not in source and "orders/" not in source and "ARMED" not in source
    broker = Broker()
    record_split.run(CSH2, None, broker, ledger(tmp_path), say=lambda _: None)
    assert broker.reads == [f"history {CSH2}", "history None", "positions"]          # reads, nothing else
