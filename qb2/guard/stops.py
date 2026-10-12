"""The stop ledger: one stop per open position, raised only (PLAN_V3 P10; QT-16 B1).

Trading 212 has no trailing-stop order and no amend endpoint (FACTS d1, d2), so OUR
code holds every stop, checks it while running, and acts when it is crossed.

* **Set at entry:** entry - k x Wilder ATR(14) on the position's own bars (bot 5m,
  advisor and manual daily), k = 3, a STARTING FIGURE: a jumpy share gets more room.
* **Raised only:** every level goes through :meth:`Ledger.raise_to`, which refuses
  (Blocked) and LOGS a lower one; a file showing a stop lowered is not trusted.
* **Tightened when unsettled** (the pot's 10% brake on, or VIX closed above 30;
  no VIX figure counts as unsettled): k = 2, level = max(old, price - 2 x ATR).
* **Crossed:** BOT -> a SELL through the sender (sender.sell_crossed; disarmed
  today). ADVISOR or MANUAL -> an URGENT-EXIT alert, never a sale: P1's one
  automatic act on his holdings is raising their stop. No price -> UNCHECKED.
* **Catch-up on waking** checks every open stop, logged; the **daily sync** lists
  any held position with no stop -- above all his own.

Append-only JSON lines in data/qb2/stops.jsonl; the state is the replay of them.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from qb2.execution.safety import ADVISOR, BOT, MANUAL, Blocked, Holding

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEDGER = REPO_ROOT / "data" / "qb2" / "stops.jsonl"

STOP_K = 3.0                 # STARTING FIGURE: entry - 3 x Wilder ATR(14)
TIGHT_K = 2.0                # STARTING FIGURE: when unsettled
VIX_UNSETTLED = 30.0         # STARTING FIGURE: a VIX close above this is unsettled
ATR_PERIOD = 14              # Wilder ATR(14): qb2/signals/indicators.atr_wilder
BAR_OF = {BOT: "5m", ADVISOR: "1d", MANUAL: "1d"}

SELL = "SELL"                # bot: a sell intent through the sender
URGENT_EXIT = "URGENT-EXIT"  # advisor / manual: an alert, never a sale
UNCHECKED = "UNCHECKED"      # no price to check against


@dataclass(frozen=True, slots=True)
class Change:
    at: str
    level: float
    reason: str


@dataclass(frozen=True, slots=True)
class Stop:
    position_id: str
    pot: str
    ticker: str
    market: str
    opened_at: str
    entry: float
    atr: float
    k: float
    bar: str
    history: tuple[Change, ...]

    @property
    def level(self) -> float:
        return self.history[-1].level


@dataclass(frozen=True, slots=True)
class StopPlan:
    """What a BUY carries to the sender (check 9): the stop it will open with."""

    ticker: str
    entry: float
    atr: float
    k: float
    level: float


@dataclass(frozen=True, slots=True)
class Action:
    kind: str                    # SELL, URGENT_EXIT or UNCHECKED
    position_id: str
    ticker: str
    pot: str
    price: float | None
    level: float
    message: str


def _finite(value: float | None, what: str) -> float:
    if value is None or not math.isfinite(value) or value <= 0:
        raise Blocked(f"no usable {what} ({value!r}) -- no figure, no stop, no buy")
    return float(value)


def plan(ticker: str, entry: float | None, atr: float | None, k: float = STOP_K) -> StopPlan:
    level = _finite(entry, "entry price") - k * _finite(atr, "ATR")
    if level <= 0:
        raise Blocked(f"{ticker}: entry - {k:g} x ATR is {level:.4f}; a stop at or "
                      "below zero protects nothing")
    return StopPlan(ticker, float(entry or 0), float(atr or 0), k, level)


def check_plan(ticker: str, stop_plan: StopPlan | None, expected_price: float) -> None:
    """Sender check 9: no plan, a plan for another name, or a level not below the
    price is no plan at all -- and no buy."""
    if stop_plan is None:
        raise Blocked(f"no stop plan came with the buy of {ticker}: every position "
                      "opens with a stop (P10)")
    if stop_plan.ticker != ticker:
        raise Blocked(f"the stop plan is for {stop_plan.ticker}, not {ticker}")
    if not (math.isfinite(stop_plan.level) and 0 < stop_plan.level < expected_price):
        raise Blocked(f"{ticker}: a stop at {stop_plan.level} against a price of "
                      f"{expected_price} is not a stop")


def unsettled(brake_on: bool, vix_close: float | None) -> bool:
    if brake_on or vix_close is None or not math.isfinite(vix_close):
        return True
    return vix_close > VIX_UNSETTLED


class Ledger:
    """Append-only JSON lines; :meth:`stops` replays them into the open stops."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DEFAULT_LEDGER

    def _write(self, row: dict[str, Any]) -> None:
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"at": stamp, **row}, sort_keys=True) + "\n")

    def _rows(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        rows = []
        for n, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            try:
                rows.append(dict(json.loads(line)))
            except json.JSONDecodeError as exc:
                raise Blocked(f"stop ledger line {n} is unreadable -- refusing to guess "
                              "what the stops are") from exc
        return rows

    def stops(self) -> dict[str, Stop]:
        held: dict[str, Stop] = {}
        for n, row in enumerate(self._rows(), 1):
            pid, event = str(row.get("position_id")), row.get("event")
            if event == "open":
                if pid in held:
                    raise Blocked(f"stop ledger line {n}: {pid} opened twice")
                held[pid] = Stop(pid, row["pot"], row["ticker"], row["market"],
                                 row["opened_at"], row["entry"], row["atr"], row["k"],
                                 row["bar"], (Change(row["at"], row["level"], row["reason"]),))
            elif event == "raise" and pid in held:
                old = held[pid]
                if not row["level"] > old.level:
                    raise Blocked(f"stop ledger line {n} shows {old.ticker}'s stop LOWERED "
                                  f"from {old.level} to {row['level']} -- not trusted")
                held[pid] = replace(old, history=(*old.history, Change(
                    row["at"], row["level"], row["reason"])))
            elif event == "close":
                held.pop(pid, None)
        return held

    def get(self, position_id: str) -> Stop:
        stop = self.stops().get(position_id)
        if stop is None:
            raise Blocked(f"no open stop for position {position_id}")
        return stop

    def open(self, *, position_id: str, pot: str, ticker: str, market: str, opened_at: str,
             entry: float | None, atr: float | None, reason: str, k: float = STOP_K) -> Stop:
        if pot not in BAR_OF:
            raise Blocked(f"unknown pot {pot!r}: a stop belongs to bot, advisor or manual")
        if position_id in self.stops():
            raise Blocked(f"{position_id} already has a stop; a held position is never "
                          "re-opened (past 12 months: age.rebuy makes a NEW record)")
        made = plan(ticker, entry, atr, k)
        self._write({"event": "open", "position_id": position_id, "pot": pot,
                     "ticker": ticker, "market": market, "opened_at": opened_at,
                     "entry": made.entry, "atr": made.atr, "k": k, "bar": BAR_OF[pot],
                     "level": made.level, "reason": reason})
        return self.get(position_id)

    def raise_to(self, position_id: str, level: float, reason: str) -> Stop:
        """THE one path that moves a level. Lower = refused and logged."""
        stop = self.get(position_id)
        if not math.isfinite(level) or level < stop.level:
            self._write({"event": "refused", "position_id": position_id,
                         "attempted": level if math.isfinite(level) else str(level),
                         "level": stop.level, "reason": reason})
            raise Blocked(f"refused: {stop.ticker}'s stop is {stop.level:.4f}; {level} "
                          "would lower it, and a stop is only ever raised (P10)")
        if level == stop.level:
            return stop
        self._write({"event": "raise", "position_id": position_id, "level": level,
                     "old": stop.level, "reason": reason})
        return self.get(position_id)

    def trail(self, position_id: str, price: float, atr: float, *, unsettled: bool,
              reason: str = "trail") -> Stop:
        """max(old, price - k x ATR): k = 2 when unsettled, else 3. Never lower."""
        k = TIGHT_K if unsettled else STOP_K
        candidate = _finite(price, "price") - k * _finite(atr, "ATR")
        stop = self.get(position_id)
        if candidate <= stop.level:
            return stop
        return self.raise_to(position_id, candidate, f"{reason}: {price:g} - {k:g} x ATR {atr:g}")

    def close(self, position_id: str, reason: str) -> None:
        self.get(position_id)
        self._write({"event": "close", "position_id": position_id, "reason": reason})

    def check(self, prices: Mapping[str, float | None], *, waking: bool = False) -> list[Action]:
        """Every open stop against its latest price, logged (``waking``: the catch-up)."""
        actions = []
        for stop in self.stops().values():
            price = prices.get(stop.ticker)
            if price is None or not math.isfinite(price) or price <= 0:
                actions.append(Action(UNCHECKED, stop.position_id, stop.ticker, stop.pot,
                                      None, stop.level, f"{stop.ticker}: no price, stop "
                                      "NOT checked -- look now"))
            elif price <= stop.level:
                kind = SELL if stop.pot == BOT else URGENT_EXIT
                actions.append(Action(kind, stop.position_id, stop.ticker, stop.pot, price,
                                      stop.level, f"{stop.ticker} at {price:g} crossed its "
                                      f"stop {stop.level:.4f} ({stop.pot})"))
        self._write({"event": "catch_up" if waking else "checked",
                     "open": len(self.stops()), "actions": [a.message for a in actions]})
        return actions

    def catch_up(self, prices: Mapping[str, float | None]) -> list[Action]:
        return self.check(prices, waking=True)

    def unprotected(self, holdings: Sequence[Holding]) -> list[str]:
        """The daily sync's list: every held position with no stop yet."""
        covered = {(s.pot, s.ticker) for s in self.stops().values()}
        missing = [f"{h.owner} {h.ticker}" for h in holdings
                   if h.quantity > 0 and (h.owner, h.ticker) not in covered]
        if missing:
            self._write({"event": "unprotected", "positions": missing})
        return missing
