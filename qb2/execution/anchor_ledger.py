"""The anchor ledger -- what the anchor buyer meant to do, and what became of it.

PLAN_V3 P20 holds a small "anchor" of every bot name on the practice account so
Trading 212 prices all 50. The buyer lives in ``anchors.py``; THIS file only reads
and appends its ledger, and it has no way to reach the broker. That split is the
point: the bot's flatten has to know how much of a position is anchor (so it never
sells one), but the bot must never be able to import the module that can place an
order. So the bot imports this, and only this.

One JSON object per line in ``data/anchors/ledger.jsonl``, append-only, three kinds:

* ``INTENT``     -- written BEFORE an order is sent. A crash after this line and
  before the next leaves an intent with no outcome, which reads as UNRESOLVED,
  never as "nothing happened".
* ``OUTCOME``    -- what the broker said: ACCEPTED (with its order id) or UNRESOLVED
  (timeout, error, anything else). Orders are not idempotent (docs/t212/FACTS.md
  row e), so an UNRESOLVED intent blocks its ticker until it is reconciled.
* ``RECONCILED`` -- what the broker's own order history later showed: FILLED,
  NOT_FILLED (rejected or cancelled with nothing filled) or NOT_PLACED (no trace of
  it anywhere, long enough afterwards to be sure).

A line that is not valid JSON is never skipped: a ledger we cannot read is a
ledger whose blocking intents we cannot see, so reading it raises.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LEDGER_PATH = REPO_ROOT / "data" / "anchors" / "ledger.jsonl"

INTENT = "INTENT"
OUTCOME = "OUTCOME"
RECONCILED = "RECONCILED"
KINDS = frozenset({INTENT, OUTCOME, RECONCILED})

ACCEPTED = "ACCEPTED"
UNRESOLVED = "UNRESOLVED"
FILLED = "FILLED"
NOT_FILLED = "NOT_FILLED"
NOT_PLACED = "NOT_PLACED"

# An intent in one of these states may still become (or already be) a real order.
BLOCKING = frozenset({ACCEPTED, UNRESOLVED})
# These are settled as "no money left the account".
SETTLED_EMPTY = frozenset({NOT_FILLED, NOT_PLACED})


class LedgerCorrupt(RuntimeError):
    """A line could not be read. Refusing beats guessing what it said."""


@dataclass(frozen=True, slots=True)
class IntentState:
    """One intended buy, folded together with everything later said about it."""

    intent_id: str
    ticker: str
    at_utc: str
    quantity: float
    est_gbp: float
    state: str
    order_id: int | None = None
    filled_quantity: float = 0.0
    filled_gbp: float = 0.0
    detail: str = ""

    @property
    def day(self) -> date:
        return datetime.fromisoformat(self.at_utc).date()

    @property
    def anchor_quantity(self) -> float:
        """How much of the position to treat as anchor.

        FILLED counts what filled. ACCEPTED and UNRESOLVED count what was ASKED
        for, because the order may exist: over-protecting an anchor costs the bot
        a sliver it could have sold, under-protecting it sells measuring kit.
        """
        if self.state == FILLED:
            return self.filled_quantity
        if self.state in BLOCKING:
            return self.quantity
        return 0.0


def _float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


class AnchorLedger:
    """Append and fold. No network, no order method, nothing that can trade."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or LEDGER_PATH

    # --------------------------------------------------------------- write ---

    def append(self, record: Mapping[str, object]) -> None:
        """One line, flushed and synced before returning.

        The INTENT must be on disk before the order leaves, or a crash in between
        would forget an order that may exist.
        """
        kind = record.get("kind")
        if kind not in KINDS:
            raise ValueError(f"unknown ledger kind {kind!r}")
        if not record.get("intent_id"):
            raise ValueError("every ledger line needs an intent_id")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(dict(record), sort_keys=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    # ---------------------------------------------------------------- read ---

    def records(self) -> list[dict[str, object]]:
        if not self.path.is_file():
            return []
        out: list[dict[str, object]] = []
        for number, raw in enumerate(
                self.path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise LedgerCorrupt(
                    f"{self.path.name} line {number} is not valid JSON ({exc.msg}); "
                    "a ledger we cannot read may hide an order -- look before "
                    "anything else runs") from None
            if not isinstance(row, dict) or row.get("kind") not in KINDS:
                raise LedgerCorrupt(
                    f"{self.path.name} line {number} is not a ledger record")
            out.append(row)
        return out

    def states(self) -> dict[str, IntentState]:
        """Every intent, with its latest known state."""
        folded: dict[str, IntentState] = {}
        for row in self.records():
            intent_id = str(row["intent_id"])
            kind = row["kind"]
            if kind == INTENT:
                folded[intent_id] = IntentState(
                    intent_id=intent_id,
                    ticker=str(row.get("ticker", "")),
                    at_utc=str(row.get("at_utc", "")),
                    quantity=_float(row.get("quantity")),
                    est_gbp=_float(row.get("est_gbp")),
                    state=UNRESOLVED)
                continue
            known = folded.get(intent_id)
            if known is None:
                raise LedgerCorrupt(
                    f"{kind} for intent {intent_id} has no INTENT before it")
            state = str(row.get("status", UNRESOLVED))
            order_id = row.get("order_id")
            folded[intent_id] = IntentState(
                intent_id=intent_id,
                ticker=known.ticker,
                at_utc=known.at_utc,
                quantity=known.quantity,
                est_gbp=known.est_gbp,
                state=state,
                order_id=(int(order_id) if isinstance(order_id, int)
                          and not isinstance(order_id, bool) else known.order_id),
                filled_quantity=_float(row.get("filled_quantity",
                                               known.filled_quantity)),
                filled_gbp=_float(row.get("filled_gbp", known.filled_gbp)),
                detail=str(row.get("detail", "")))
        return folded

    def blocking(self) -> list[IntentState]:
        """Intents that may be, or may become, a real order."""
        return [s for s in self.states().values() if s.state in BLOCKING]

    def blocking_tickers(self) -> set[str]:
        return {s.ticker for s in self.blocking()}

    def committed_gbp(self) -> float:
        """Spent or possibly spent, for the lifetime cap.

        Everything except an intent settled as empty counts, at the larger of the
        estimate and what actually filled -- the cap errs towards stopping.
        """
        return sum(max(s.est_gbp, s.filled_gbp) for s in self.states().values()
                   if s.state not in SETTLED_EMPTY)

    def orders_on(self, day: date) -> int:
        """Intents dated that UTC day, whatever became of them."""
        return sum(1 for s in self.states().values() if s.day == day)

    def anchor_quantities(self) -> dict[str, float]:
        quantities: dict[str, float] = {}
        for state in self.states().values():
            amount = state.anchor_quantity
            if amount > 0:
                quantities[state.ticker] = quantities.get(state.ticker, 0.0) + amount
        return quantities
