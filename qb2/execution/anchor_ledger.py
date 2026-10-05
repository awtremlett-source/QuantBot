"""The anchor ledger -- what the anchor buyer meant to do, and what became of it.

PLAN_V3 P20 holds a small "anchor" of every bot name on the practice account so
Trading 212 prices all 50. The buyer lives in ``anchors.py``; THIS file only reads
and appends its ledger, and it has no way to reach the broker. That split is the
point: the bot's flatten has to know how much of a position is anchor (so it never
sells one), but the bot must never be able to import the module that can place an
order. So the bot imports this, and only this.

One JSON object per line in ``data/anchors/ledger.jsonl``, append-only, five kinds:

* ``INTENT``     -- written BEFORE an order is sent. A crash after this line and
  before the next leaves an intent with no outcome, which reads as UNRESOLVED,
  never as "nothing happened".
* ``OUTCOME``    -- what the broker said: ACCEPTED (with its order id) or UNRESOLVED
  (timeout, error, anything else). Orders are not idempotent (docs/t212/FACTS.md
  row e), so an UNRESOLVED intent blocks its ticker until it is reconciled.
* ``RECONCILED`` -- what the broker's own order history later showed: FILLED,
  NOT_FILLED (rejected or cancelled with nothing filled) or NOT_PLACED (no trace of
  it anywhere, long enough afterwards to be sure).
* ``PRE_EXISTING`` -- a holding that was already in the account, bought by hand,
  NOT by the program. Fenced like an anchor (never in the bot's pot, never sold by
  flatten) but it spends nothing from the anchor caps and is not an order.

* ``RETRY_AUTHORISED`` -- the operator's words lifting ONE refusal, once.

An OUTCOME may also be REFUSED: the broker definitely rejected the order and
created nothing. That name is never retried automatically -- a person decides,
and a RETRY_AUTHORISED line records that they did.

A line that is not valid JSON is never skipped: a ledger we cannot read is a
ledger whose blocking intents we cannot see, so reading it raises.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LEDGER_PATH = REPO_ROOT / "data" / "anchors" / "ledger.jsonl"

INTENT = "INTENT"
OUTCOME = "OUTCOME"
RECONCILED = "RECONCILED"
PRE_EXISTING = "PRE_EXISTING"
# The operator's recorded words lifting ONE refusal, once (QT-12 fix, 2026-10-05).
RETRY_AUTHORISED = "RETRY_AUTHORISED"
KINDS = frozenset({INTENT, OUTCOME, RECONCILED, PRE_EXISTING, RETRY_AUTHORISED})

ACCEPTED = "ACCEPTED"
UNRESOLVED = "UNRESOLVED"
FILLED = "FILLED"
NOT_FILLED = "NOT_FILLED"
NOT_PLACED = "NOT_PLACED"
REFUSED = "REFUSED"

# An intent in one of these states may still become (or already be) a real order.
BLOCKING = frozenset({ACCEPTED, UNRESOLVED})
# These are settled as "no money left the account".
SETTLED_EMPTY = frozenset({NOT_FILLED, NOT_PLACED, REFUSED})
# Not orders the program made, so not counted against the caps or the day.
NOT_AN_ORDER = frozenset({PRE_EXISTING})


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
    retry_authorised: str = ""      # the operator's words, if this refusal is lifted

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
        if self.state == PRE_EXISTING:
            return self.quantity
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

    def unusable(self) -> str:
        """Why --live must not trust this ledger, or "" (anchors.py F13)."""
        try:
            return "" if self.records() else (
                "empty" if self.path.is_file() else "missing")
        except LedgerCorrupt as exc:
            return f"unreadable ({exc})"

    def states(self) -> dict[str, IntentState]:
        """Every intent, with its latest known state."""
        folded: dict[str, IntentState] = {}
        for row in self.records():
            intent_id = str(row["intent_id"])
            kind = row["kind"]
            if kind in (PRE_EXISTING, INTENT):
                pre = kind == PRE_EXISTING        # a holding, not an order
                folded[intent_id] = IntentState(
                    intent_id=intent_id,
                    ticker=str(row.get("ticker", "")),
                    at_utc=str(row.get("at_utc", "")),
                    quantity=_float(row.get("quantity")),
                    est_gbp=0.0 if pre else _float(row.get("est_gbp")),
                    state=PRE_EXISTING if pre else UNRESOLVED,
                    detail=str(row.get("detail", "")) if pre else "")
                continue
            known = folded.get(intent_id)
            if known is None:
                raise LedgerCorrupt(
                    f"{kind} for intent {intent_id} has no INTENT before it")
            if kind == RETRY_AUTHORISED:
                if known.state != REFUSED:
                    raise LedgerCorrupt(f"retry authorised for intent {intent_id}, "
                                        f"which is {known.state}, not REFUSED")
                folded[intent_id] = replace(
                    known, retry_authorised=str(row.get("operator_words", "")))
                continue
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
                   if s.state not in SETTLED_EMPTY | NOT_AN_ORDER)

    def orders_on(self, day: date) -> int:
        """Intents dated that UTC day, whatever became of them."""
        return sum(1 for s in self.states().values()
                   if s.day == day and s.state not in NOT_AN_ORDER)

    def refused(self) -> dict[str, str]:
        """Names the broker definitely refused, with why. Never retried by the
        program; only a RETRY_AUTHORISED line (the operator's words) lifts one."""
        return {s.ticker: s.detail for s in self.refusals() if not s.retry_authorised}

    def refusals(self) -> list[IntentState]:
        """Every refusal, lifted or not -- the broker's words carry its rules."""
        return [s for s in self.states().values() if s.state == REFUSED]

    def anchor_quantities(self) -> dict[str, float]:
        quantities: dict[str, float] = {}
        for state in self.states().values():
            amount = state.anchor_quantity
            if amount > 0:
                quantities[state.ticker] = quantities.get(state.ticker, 0.0) + amount
        return quantities


def pre_existing_record(ticker: str, quantity: float, at: datetime,
                        how_placed: str) -> dict[str, object]:
    """The ledger line for a holding the program did NOT buy, fenced as an anchor."""
    if not quantity > 0:
        raise ValueError("a pre-existing holding needs a positive quantity")
    return {"kind": PRE_EXISTING, "intent_id": f"pre-existing-{ticker}",
            "at_utc": at.isoformat(), "ticker": ticker, "quantity": quantity,
            "detail": how_placed}


def retry_record(ledger: AnchorLedger, intent_id: str, operator_words: str,
                 at: datetime) -> dict[str, object]:
    """The ledger line lifting one refusal. Words and a REFUSED intent required."""
    if not operator_words.strip():
        raise ValueError("a retry needs the operator's words")
    state = ledger.states().get(intent_id)
    if state is None or state.state != REFUSED:
        raise ValueError(f"intent {intent_id} is not a refusal -- nothing to lift")
    if state.retry_authorised:
        raise ValueError(f"intent {intent_id} is already lifted")
    return {"kind": RETRY_AUTHORISED, "intent_id": intent_id,
            "at_utc": at.isoformat(), "ticker": state.ticker,
            "operator_words": operator_words}
