"""The stop ledger: one stop per open position, raised only (PLAN_V3 P10; QT-16 B1; QT-23 B).

Each pot's rule (RULE_OF): BOT and MANUAL entry - k x Wilder ATR(14) (R4); the ADVISOR's big-fall
stop, whose ONE copy is :func:`fall_level`, shared with advisor_book (GO 2026-10-19; R3, R5).
Levels move only through :meth:`Ledger.raise_to`: lower is refused and LOGGED; a file showing one
lowered (a raise, or a re-justified advisor record opening below the one it replaces) is not
trusted. Figures and crossed-stop actions: qb2/guard/__init__.py. Append-only JSON lines in
data/qb2/stops.jsonl; the state is the replay of them."""

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
FALLS = {False: 0.15, True: 0.10}       # the ADVISOR's f, by unsettled: S5's crash tests (R3)
ATR_RULE, FALL_RULE = "atr", "fall"
BAR_OF = {BOT: "5m", ADVISOR: "1d", MANUAL: "1d"}
RULE_OF = {BOT: ATR_RULE, ADVISOR: FALL_RULE, MANUAL: ATR_RULE}     # R4: bot, manual unchanged

SELL, URGENT_EXIT, UNCHECKED = "SELL", "URGENT-EXIT", "UNCHECKED"   # his: an alert, never a sale


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
    atr: float                   # 0 for a big-fall stop
    k: float                     # the ATR multiple, or the f it opened with
    bar: str
    history: tuple[Change, ...]
    rule: str = ATR_RULE         # a ledger written before QT-23 holds only ATR stops

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


def fall_level(price: float, f: float, floor: float | None = None) -> float:
    """THE big-fall rule, its one copy (R5): f below the price -- computed as price - f x price,
    the back-tests' own arithmetic, bit for bit -- and never below ``floor``."""
    level = price - f * price
    return level if floor is None else max(floor, level)


def plan(ticker: str, entry: float | None, atr: float | None, k: float = STOP_K, *,
         f: float | None = None, floor: float | None = None) -> StopPlan:
    """entry - k x ATR; with ``f`` (the advisor) the big fall, never below ``floor``."""
    price = _finite(entry, "entry price")
    level = price - k * _finite(atr, "ATR") if f is None else fall_level(price, f, floor)
    if not 0 < level < price:
        raise Blocked(f"{ticker}: a stop at {level:.4f} against an entry of {price:g} protects nothing")
    return StopPlan(ticker, price, float(atr or 0) if f is None else 0.0, k if f is None else f, level)


def plan_for(pot: str, ticker: str, entry: float | None, atr: float | None, *,
             unsettled: bool | None, k: float = STOP_K, floor: float | None = None) -> StopPlan:
    """The pot's own rule (RULE_OF). The advisor's must be told whether markets are unsettled."""
    if (fall := RULE_OF.get(pot) == FALL_RULE) and unsettled is None:
        raise Blocked(f"{ticker}: the advisor's stop needs to know whether markets are unsettled "
                      "(VIX, the brake) -- no figure, no stop")
    return plan(ticker, entry, atr, k, f=FALLS[bool(unsettled)] if fall else None, floor=floor)


def check_plan(ticker: str, stop_plan: StopPlan | None, expected_price: float) -> None:
    """Sender check 9: no plan, another name's plan, or a level not below the price -> no buy."""
    if stop_plan is None:
        raise Blocked(f"no stop plan came with the buy of {ticker}: every position opens with a stop (P10)")
    if stop_plan.ticker != ticker:
        raise Blocked(f"the stop plan is for {stop_plan.ticker}, not {ticker}")
    if not (math.isfinite(stop_plan.level) and 0 < stop_plan.level < expected_price):
        raise Blocked(f"{ticker}: a stop at {stop_plan.level} against a price of {expected_price} is not a stop")


def unsettled(brake_on: bool, vix_close: float | None) -> bool:
    return brake_on or vix_close is None or not math.isfinite(vix_close) or vix_close > VIX_UNSETTLED


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
        rows, text = [], self.path.read_text(encoding="utf-8") if self.path.is_file() else ""
        for n, line in enumerate(text.splitlines(), 1):
            try:
                rows.append(dict(json.loads(line)))
            except json.JSONDecodeError as exc:
                raise Blocked(f"stop ledger line {n} is unreadable -- refusing to guess "
                              "what the stops are") from exc
        return rows

    def stops(self) -> dict[str, Stop]:
        held, last = dict[str, Stop](), dict[str, float]()       # last: each closed record's final level
        for n, row in enumerate(self._rows(), 1):
            pid, event = str(row.get("position_id")), row.get("event")
            if event == "open":
                if pid in held:
                    raise Blocked(f"stop ledger line {n}: {pid} opened twice")
                was, rule = row.get("replaces"), row.get("rule", ATR_RULE)
                if rule == FALL_RULE and was is not None and row["level"] < last.get(was, 0.0):
                    raise Blocked(f"stop ledger line {n} re-opens {row['ticker']}'s stop LOWER "
                                  f"than {was}'s {last[was]} -- not trusted")
                held[pid] = Stop(pid, row["pot"], row["ticker"], row["market"],
                                 row["opened_at"], row["entry"], row["atr"], row["k"],
                                 row["bar"], (Change(row["at"], row["level"], row["reason"]),), rule)
            elif event == "raise" and pid in held:
                old = held[pid]
                if not row["level"] > old.level:
                    raise Blocked(f"stop ledger line {n} shows {old.ticker}'s stop LOWERED "
                                  f"from {old.level} to {row['level']} -- not trusted")
                held[pid] = replace(old, history=(*old.history, Change(row["at"], row["level"], row["reason"])))
            elif event == "close" and pid in held:
                last[pid] = held.pop(pid).level
        return held

    def get(self, position_id: str) -> Stop:
        if (stop := self.stops().get(position_id)) is None:
            raise Blocked(f"no open stop for position {position_id}")
        return stop

    def open(self, *, position_id: str, pot: str, ticker: str, market: str, opened_at: str,
             entry: float | None, atr: float | None, reason: str, k: float = STOP_K,
             unsettled: bool | None = None, floor: float | None = None, replaces: str | None = None) -> Stop:
        if pot not in BAR_OF:
            raise Blocked(f"unknown pot {pot!r}: a stop belongs to bot, advisor or manual")
        if position_id in self.stops():
            raise Blocked(f"{position_id} already has a stop; a held position is never "
                          "re-opened (past 12 months: age.rebuy makes a NEW record)")
        made = plan_for(pot, ticker, entry, atr, unsettled=unsettled, k=k, floor=floor)
        self._write({"event": "open", "position_id": position_id, "pot": pot, "ticker": ticker,
                     "market": market, "opened_at": opened_at, "entry": made.entry, "atr": made.atr,
                     "k": made.k, "bar": BAR_OF[pot], "level": made.level, "reason": reason,
                     "rule": RULE_OF[pot], **({"replaces": replaces} if replaces else {})})
        return self.get(position_id)

    def raise_to(self, position_id: str, level: float, reason: str) -> Stop:
        """THE one path that moves a level. Lower = refused and logged."""
        stop = self.get(position_id)
        if not math.isfinite(level) or level < stop.level:
            self._write({"event": "refused", "position_id": position_id, "level": stop.level,
                         "attempted": level if math.isfinite(level) else str(level), "reason": reason})
            raise Blocked(f"refused: {stop.ticker}'s stop is {stop.level:.4f}; {level} "
                          "would lower it, and a stop is only ever raised (P10)")
        if level == stop.level:
            return stop
        self._write({"event": "raise", "position_id": position_id, "level": level,
                     "old": stop.level, "reason": reason})
        return self.get(position_id)

    def trail(self, position_id: str, price: float, atr: float | None, *, unsettled: bool,
              reason: str = "trail") -> Stop:
        """The stop's own rule at this close, never lower: the big fall, or k x ATR."""
        stop, f, k = self.get(position_id), FALLS[unsettled], TIGHT_K if unsettled else STOP_K
        fall, close = stop.rule == FALL_RULE, _finite(price, "price")
        candidate = fall_level(close, f) if fall else close - k * _finite(atr, "ATR")
        if candidate <= stop.level:
            return stop
        why = f"{close:g} x (1 - {f:g})" if fall else f"{close:g} - {k:g} x ATR {atr:g}"
        return self.raise_to(position_id, candidate, f"{reason}: {why}")

    def close(self, position_id: str, reason: str) -> None:
        self.get(position_id)
        self._write({"event": "close", "position_id": position_id, "reason": reason})

    def check(self, prices: Mapping[str, float | None], *, waking: bool = False) -> list[Action]:
        """Every open stop against its latest price, logged (``waking``: the catch-up)."""
        actions, held = [], self.stops()
        for s in held.values():
            if (price := prices.get(s.ticker)) is None or not math.isfinite(price) or price <= 0:
                actions.append(Action(UNCHECKED, s.position_id, s.ticker, s.pot, None, s.level,
                                      f"{s.ticker}: no price, stop NOT checked -- look now"))
            elif price <= s.level:
                actions.append(Action(SELL if s.pot == BOT else URGENT_EXIT, s.position_id,
                                      s.ticker, s.pot, price, s.level, f"{s.ticker} at "
                                      f"{price:g} crossed its stop {s.level:.4f} ({s.pot})"))
        self._write({"event": "catch_up" if waking else "checked", "open": len(held),
                     "actions": [a.message for a in actions]})
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
