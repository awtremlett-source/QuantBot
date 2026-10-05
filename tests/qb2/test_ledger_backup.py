"""The anchor ledger survives a machine: backed up after every live run, and a
restored copy is never trusted until the broker agrees with it (F13, stale case).

A backup is a snapshot, so a restored ledger can be missing the newest orders. Every
API order in the broker's history must match a ledger intent before --live sends
anything; a mismatch stops the run, says which orders, and writes nothing. Orders
the operator placed by hand (WEB, IOS) are not anchors and are ignored.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from qb2.execution import ledger_backup
from qb2.execution.anchor_ledger import (ACCEPTED, FILLED, INTENT, OUTCOME,
                                         RECONCILED, AnchorLedger)
from tests.qb2.test_qt12_anchors import MON_OVERLAP, FakeReader, live, seeded

UTC = timezone.utc


def broker_order(order_id: int, ticker: str, *, source: str = "API",
                 at: datetime = MON_OVERLAP - timedelta(hours=2),
                 quantity: float = 0.01) -> dict[str, Any]:
    """Shaped like one item of GET /equity/history/orders (FACTS row y)."""
    return {"order": {"id": order_id, "ticker": ticker, "side": "BUY",
                      "status": "FILLED", "quantity": quantity,
                      "filledQuantity": quantity, "initiatedFrom": source,
                      "createdAt": at.isoformat().replace("+00:00", "Z")},
            "fill": {"quantity": quantity, "walletImpact": {"netValue": -1.0}}}


def ledger_with_filled_anchor(tmp_path: Path, order_id: int = 1001,
                              ticker: str = "OLD_US_EQ") -> AnchorLedger:
    book = seeded(tmp_path / "anchors" / "ledger.jsonl")
    at = (MON_OVERLAP - timedelta(hours=3)).isoformat()
    book.append({"kind": INTENT, "intent_id": "a-old", "at_utc": at,
                 "ticker": ticker, "quantity": "0.01", "est_gbp": 1.0})
    book.append({"kind": OUTCOME, "intent_id": "a-old", "at_utc": at,
                 "status": ACCEPTED, "order_id": order_id})
    book.append({"kind": RECONCILED, "intent_id": "a-old", "at_utc": at,
                 "status": FILLED, "order_id": order_id, "filled_quantity": 0.01,
                 "filled_gbp": 1.0})
    return book


def test_a_stale_ledger_sends_nothing_and_changes_nothing(tmp_path: Path) -> None:
    book = ledger_with_filled_anchor(tmp_path)
    before = book.path.read_bytes()
    history = {"OLD_US_EQ": [broker_order(1001, "OLD_US_EQ")],
               "NEW_US_EQ": [broker_order(1002, "NEW_US_EQ")]}    # not in the copy

    report, _, wire, _ = live(tmp_path, ledger=book,
                              reader=FakeReader(history=history))

    assert wire.posts == 0
    assert "NEW_US_EQ order 1002" in report.halted
    assert "OLD_US_EQ" not in report.halted
    assert "changed nothing" in report.halted
    assert book.path.read_bytes() == before          # reconcile never ran


def test_a_matching_ledger_is_allowed_and_hand_orders_are_ignored(
        tmp_path: Path) -> None:
    book = ledger_with_filled_anchor(tmp_path)
    history = {"OLD_US_EQ": [broker_order(1001, "OLD_US_EQ")],
               "MU_US_EQ": [broker_order(7, "MU_US_EQ", source="WEB"),
                            broker_order(8, "MU_US_EQ", source="IOS")]}

    report, reader, wire, _ = live(tmp_path, ledger=book,
                                   reader=FakeReader(history=history))

    assert "history:None" in reader.calls             # the broker was asked
    assert "changed nothing" not in report.halted
    assert wire.posts > 0


def test_a_lost_reply_counts_as_recorded(tmp_path: Path) -> None:
    """An intent with no order id yet is matched the way reconcile matches it."""
    book = seeded(tmp_path / "anchors" / "ledger.jsonl")
    at = MON_OVERLAP - timedelta(hours=1)
    book.append({"kind": INTENT, "intent_id": "a-lost", "at_utc": at.isoformat(),
                 "ticker": "LOST_US_EQ", "quantity": "0.01", "est_gbp": 1.0})
    order = broker_order(1003, "LOST_US_EQ", at=at + timedelta(seconds=5))
    assert ledger_backup.unrecorded(book, [order], _matches()) == ""


def _matches() -> Any:
    from qb2.execution.anchors import _matches as matches
    return matches


def test_backup_copies_verifies_and_keeps_every_copy(tmp_path: Path) -> None:
    book = ledger_with_filled_anchor(tmp_path)
    dest = tmp_path / "remote"
    first = ledger_backup.backup(book.path, dest, MON_OVERLAP, environ={})
    second = ledger_backup.backup(book.path, dest,
                                  MON_OVERLAP + timedelta(minutes=1), environ={})
    copies = sorted((dest / "anchors").glob("ledger-*.jsonl"))
    assert len(copies) == 2                           # never pruned, never deleted
    digest = hashlib.sha256(book.path.read_bytes()).hexdigest()
    assert all(hashlib.sha256(c.read_bytes()).hexdigest() == digest for c in copies)
    assert "verified" in first and "verified" in second


def test_backup_goes_to_the_operators_folder_and_warns_when_local(
        tmp_path: Path) -> None:
    book = ledger_with_filled_anchor(tmp_path)
    remote = tmp_path / "onedrive"
    said = ledger_backup.backup(book.path, None, MON_OVERLAP,
                                environ={"QUANTBOT_BACKUP_DIR": str(remote)})
    assert list((remote / "anchors").glob("ledger-*.jsonl"))
    assert "LOCAL-ONLY" not in said
    local = ledger_backup.backup(book.path, None, MON_OVERLAP, environ={},
                                 local_dest=tmp_path / "data" / "backups")
    assert "LOCAL-ONLY" in local


def test_backup_of_a_missing_ledger_creates_nothing(tmp_path: Path) -> None:
    dest = tmp_path / "remote"
    said = ledger_backup.backup(tmp_path / "nope.jsonl", dest, MON_OVERLAP,
                                environ={})
    assert "no ledger" in said
    assert not dest.exists()
