"""An append-only record of what we meant to do and what actually happened.

Two lines per trade, never one:

* **INTENT**, written BEFORE anything is sent -- the price we expected, how old
  that price was, and what we thought it would cost.
* **OUTCOME**, written after -- the real fill, the quantity, the time.

Why both, and why in that order: if the program dies between them, the file says
so. An intent with no outcome means "we may have sent an order and we do not know
what happened", which is exactly the state a reconcile needs to find and a
single-line log would hide. The order endpoints are not idempotent
(docs/t212/FACTS.md row e), so "we do not know" must never be answered by
sending again.

Nothing is ever rewritten or deleted. The file only grows, so a line once written
is evidence.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEDGER = REPO_ROOT / "data" / "qb2" / "fills.jsonl"

INTENT = "INTENT"
OUTCOME = "OUTCOME"


@dataclass(frozen=True, slots=True)
class OpenIntent:
    """An intent with no outcome: we do not know what happened. Reconcile, never resend."""

    intent_id: str
    ticker: str
    side: str
    quantity: float
    expected_price: float
    at: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _as_float(value: object) -> float:
    """A number out of a JSON line, or 0.0 -- never a crash on a bad file."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


class FillRecorder:
    """Append-only JSONL. The only write it performs is 'add a line at the end'."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path if path is not None else DEFAULT_LEDGER
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------- writing ---

    def _append(self, record: dict[str, object]) -> None:
        """One line, flushed to the operating system before we go on.

        The flush matters: an intent still sitting in a buffer when the power
        goes is an intent that was never recorded, which is the one failure this
        file exists to prevent.
        """
        line = json.dumps(record, sort_keys=True) + "\n"
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())

    def record_intent(self, *, intent_id: str, ticker: str, side: str,
                      quantity: float, expected_price: float,
                      quote_age_seconds: float, estimated_cost_gbp: float,
                      note: str = "") -> str:
        """Write down what we are about to do, BEFORE we do it."""
        self._append({"kind": INTENT, "intent_id": intent_id, "at": _now(),
                      "ticker": ticker, "side": side, "quantity": quantity,
                      "expected_price": expected_price,
                      "quote_age_seconds": quote_age_seconds,
                      "estimated_cost_gbp": estimated_cost_gbp, "note": note})
        return intent_id

    def record_outcome(self, *, intent_id: str, ticker: str, side: str,
                       filled_quantity: float, fill_price: float,
                       broker_reference: str = "", note: str = "") -> None:
        """Write down what really happened. Never edits the intent line."""
        self._append({"kind": OUTCOME, "intent_id": intent_id, "at": _now(),
                      "ticker": ticker, "side": side,
                      "filled_quantity": filled_quantity,
                      "fill_price": fill_price,
                      "broker_reference": broker_reference, "note": note})

    def record_refusal(self, *, intent_id: str, ticker: str, side: str,
                       reason: str) -> None:
        """A refused order still gets an outcome, so nothing looks unresolved.

        Without this, every blocked trade would look identical to a crash.
        """
        self._append({"kind": OUTCOME, "intent_id": intent_id, "at": _now(),
                      "ticker": ticker, "side": side, "filled_quantity": 0.0,
                      "fill_price": 0.0, "broker_reference": "",
                      "note": f"REFUSED: {reason}"})

    # ------------------------------------------------------------- reading ---

    def lines(self) -> Iterator[dict[str, object]]:
        if not self.path.is_file():
            return
        for raw in self.path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                # A half-written last line means the power went mid-append.
                # Report it; never silently drop it (SCARS #12).
                print(f"fill recorder: unreadable line in {self.path.name} "
                      f"-- treat as an unresolved intent and reconcile")
                continue
            if isinstance(parsed, dict):
                yield parsed

    def open_intents(self) -> list[OpenIntent]:
        """Intents with no outcome. Each one means: go and ask the broker."""
        intents: dict[str, dict[str, object]] = {}
        answered: set[str] = set()
        for record in self.lines():
            identifier = str(record.get("intent_id", ""))
            if record.get("kind") == INTENT:
                intents[identifier] = record
            elif record.get("kind") == OUTCOME:
                answered.add(identifier)
        return [
            OpenIntent(intent_id=identifier, ticker=str(row.get("ticker", "")),
                       side=str(row.get("side", "")),
                       quantity=_as_float(row.get("quantity")),
                       expected_price=_as_float(row.get("expected_price")),
                       at=str(row.get("at", "")))
            for identifier, row in intents.items() if identifier not in answered
        ]

    def has_open_intent(self, ticker: str) -> bool:
        """Used before sending: never send while a previous one is unresolved."""
        return any(intent.ticker == ticker for intent in self.open_intents())

    def fill_gap(self, intent_id: str) -> float | None:
        """How far the fill was from what we expected, as a fraction.

        This is the number that feeds the cost model's spread and slippage
        figures once real fills exist, replacing today's starting figures.
        """
        expected: float | None = None
        for record in self.lines():
            if str(record.get("intent_id", "")) != intent_id:
                continue
            if record.get("kind") == INTENT:
                expected = _as_float(record.get("expected_price"))
            elif record.get("kind") == OUTCOME and expected:
                actual = _as_float(record.get("fill_price"))
                if actual <= 0:
                    return None
                return (actual - expected) / expected
        return None
