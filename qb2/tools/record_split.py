"""Record Trading 212's own share-split bookings in the anchor ledger, only on the operator's words (QT-32D).

**Why** (QT-31 C5). On 27 Oct 2026 Trading 212 split CSH2 (one share became 250) and booked it as two
orders the anchor ledger lacks: 0.0008 out and 0.2 in, fill type STOCK_SPLIT, with no ``initiatedFrom``.
F13's stale check reads them as API orders the ledger never made, so every ``--live`` run halts, and the
ledger says CSH2's anchor is 0.0008 while the broker holds 0.2. Fixing the ledger is his decision
(DECISION REQUESTED 1, QT-31 and QT-32); QT-32 built this tool and ran its dry run only.

    python -m qb2.tools.record_split --instrument CSH2l_EQ                  # dry run: writes nothing
    python -m qb2.tools.record_split --instrument CSH2l_EQ --words "<GO>"   # appends, once

* It reads the broker with the READ-ONLY client (GET only, practice host) and imports no order client: it
  can place, amend or cancel nothing (tests/qb2/test_qt32d_record_split.py holds that).
* It takes only the instrument's bookings that are FILLED with fill type STOCK_SPLIT and whose order id
  the ledger lacks. Any other booking of that instrument the ledger lacks refuses the whole run.
* Append-only: one SPLIT line per broker order id (anchor_ledger.SPLIT), oldest id first; nothing is
  deleted or rewritten, and a second run finds nothing to record.
* It writes only when ``--words`` equals GO_WORDS character for character, after a verified ledger
  backup, and only if F13 would then pass. Either way it prints the lines, the anchor before and after,
  and F13's verdict on the ledger with those lines, by the very check ``--live`` runs
  (ledger_backup.unrecorded with ledger_backup.matches, on the broker's newest history page).
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol

from qb2.execution import ledger_backup
from qb2.execution.anchor_ledger import SPLIT, AnchorLedger

GO_WORDS = ("GO on the CSH2 split: record Trading 212's 27 Oct CSH2 split bookings in the anchor ledger "
            "from its order history, so the stale check passes and CSH2's anchor reads 0.2.")
SPLIT_FILL = "STOCK_SPLIT"
DETAIL = "Trading 212's own booking of a share split (fill type STOCK_SPLIT), from its order history"


class SplitRefused(RuntimeError):
    """Nothing was written, and why."""


class Broker(Protocol):
    def history_orders(self, ticker: str | None = None) -> list[dict[str, Any]]: ...
    def positions(self) -> list[dict[str, Any]]: ...


def bookings(history: Sequence[Mapping[str, Any]], book: AnchorLedger, instrument: str) -> list[dict[str, Any]]:
    """The SPLIT lines to append: the instrument's split bookings the ledger lacks, oldest order id first."""
    known = {s.order_id for s in book.states().values() if s.order_id is not None}
    lines, other = [], []
    for item in history:
        order, fill = dict(item.get("order") or {}), dict(item.get("fill") or {})
        if order.get("ticker") != instrument or order.get("id") in known:
            continue
        quantity, side = order.get("filledQuantity"), order.get("side")
        number = float(quantity) if isinstance(quantity, (int, float)) else 0.0
        signed = number != 0 and (number > 0) == (side == "BUY")
        if fill.get("type") != SPLIT_FILL or order.get("status") != "FILLED" or not signed \
                or type(order.get("id")) is not int:
            other.append(f"order {order.get('id')} ({order.get('status')}, fill {fill.get('type')}, {side} {quantity})")
            continue
        lines.append({"kind": SPLIT, "intent_id": f"split-{order['id']}", "order_id": order["id"],
                      "at_utc": str(order.get("createdAt")).replace("Z", "+00:00"), "ticker": instrument,
                      "side": side, "quantity": number, "price": fill.get("price"),
                      "fill_id": fill.get("id"), "detail": DETAIL})
    if other:
        raise SplitRefused(f"{instrument}: the ledger lacks booking(s) that are not splits: {'; '.join(other)} "
                           "-- nothing recorded; a person must look first")
    return sorted(lines, key=lambda line: int(line["order_id"]))


def with_lines(book: AnchorLedger, lines: Sequence[Mapping[str, Any]], folder: Path) -> AnchorLedger:
    """A copy of the ledger with ``lines`` appended, in a scratch folder: what the ledger WOULD read."""
    copy = AnchorLedger(folder / "ledger.jsonl")
    if book.path.is_file():
        shutil.copyfile(book.path, copy.path)
    for line in lines:
        copy.append(line)
    return copy


def held(positions: Sequence[Mapping[str, Any]], instrument: str) -> float | None:
    found = [p for p in positions if (p.get("instrument") or {}).get("ticker", p.get("ticker")) == instrument]
    return float(found[0]["quantity"]) if found else None


def run(instrument: str, words: str | None, broker: Broker, book: AnchorLedger,
        backup: Callable[[Path], str] = ledger_backup.backup, say: Callable[[str], None] = print) -> int:
    """0: dry run shown, or recorded, or nothing to record. 2: refused, nothing written."""
    try:
        lines = bookings(broker.history_orders(ticker=instrument), book, instrument)
        page = broker.history_orders()                                       # F13 reads the newest page
        say(f"broker holds {instrument}: {held(broker.positions(), instrument)} (read-only key)")
        if not lines:
            say(f"nothing to record: the ledger already holds every split booking of {instrument}")
            return 0
        with tempfile.TemporaryDirectory() as folder:
            after = with_lines(book, lines, Path(folder))
            verdict = ledger_backup.unrecorded(after, page, ledger_backup.matches)
            anchors = (book.anchor_quantities().get(instrument), after.anchor_quantities().get(instrument))
        for line in lines:
            say(f"append: {line}")
        say(f"{instrument} anchor in the ledger: {anchors[0]} -> {anchors[1]}; spent from the caps: nothing")
        say(f"F13 would then {'pass: no API order in the newest history page is missing' if not verdict else 'STILL FAIL: ' + verdict}")
        if words is None:
            say("DRY RUN: nothing written. Recording it needs the operator's GO words, exactly.")
            return 0
        if words != GO_WORDS:
            raise SplitRefused("--words is not the CSH2 GO line, character for character -- nothing written")
        if verdict:
            raise SplitRefused("F13 would still fail after these lines -- nothing written; a person must look")
        say(backup(book.path))                                               # verified, or it raises
        for line in lines:
            book.append(line)
        left = ledger_backup.unrecorded(book, page, ledger_backup.matches)
        say(f"recorded {len(lines)} line(s); F13 now {'passes' if not left else 'FAILS: ' + left}")
        return 0 if not left else 2
    except (SplitRefused, OSError) as why:
        say(f"REFUSED: {why}")
        return 2


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record the broker's split bookings in the anchor ledger.")
    parser.add_argument("--instrument", required=True, help="Trading 212's ticker, e.g. CSH2l_EQ")
    parser.add_argument("--words", default=None, help="the operator's GO line, exactly; omitted = dry run")
    args = parser.parse_args(argv)
    from qb2.execution.t212_client import T212DemoClient          # the READ-ONLY client: GET only

    return run(args.instrument, args.words, T212DemoClient(), AnchorLedger())


if __name__ == "__main__":
    sys.exit(main())
