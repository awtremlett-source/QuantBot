"""P9's scorecard for ADV-0: every suggestion as if it had been followed (QT-23 C).

* AS IF FOLLOWED: an allowed BUY or SELL fills at the open of the first London session that
  opens after it was issued (:func:`fill_session`); a refused one is not followed.
* VALUE: simulate.run -- the one trade arithmetic -- on VWRL's final bars from the arm date:
  costs.py on every fill (a London ETF in GBP: spread and slippage, no stamp duty, no FX), 1x
  with 2x beside; dividends (P3) as in every back-test here (advisor_rules.income: OK payouts /
  the previous close, on the first bar on or after the ex-date); compounded from the arm date
  and marked as if sold at THAT day's close. In % with a notional pound figure beside: the pot
  is 70% of a notional GBP 10,000 account = GBP 7,000 (a display scale, a STARTING FIGURE).
* RECONCILED DAILY: the whole record is recomputed from the suggestions and the bars every run
  and must equal every line written before, to the penny (:func:`reconcile`); a difference is
  RED and names the day -- a revised price or dividend, never silently absorbed.
P9's three sizing shadows are N/A while the advisor holds one name (deferred until a pick
survives).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime

import numpy as np
import pandas as pd

from qb2.execution import costs
from qb2.research import fills, simulate

POT_GBP = 7_000.0                       # STARTING FIGURE: 70% of a notional GBP 10,000 account
STRESSES = (1.0, 2.0)
BUY, SELL = "BUY", "SELL"


@dataclass(frozen=True, slots=True)
class Fill:
    session: date                       # the London session whose OPEN it filled at
    side: str                           # BUY or SELL
    issued: str                         # the suggestion's issue time (UTC, ISO)


@dataclass(frozen=True, slots=True)
class Day:
    session: date
    held: bool                          # held at this close
    close: float
    value: dict[float, float]           # stress -> pounds, marked as if sold at this close

    def pct(self, stress: float = 1.0) -> float:
        return self.value[stress] / POT_GBP - 1.0


def fill_session(issued: datetime, sessions: Sequence[date],
                 opens_at: Callable[[date], datetime]) -> date | None:
    """The first London session that OPENS after the suggestion was issued (None: not yet)."""
    return next((s for s in sessions if opens_at(s) > issued), None)


def xlon(day: date, which: str = "open") -> datetime:
    """The London session's open (or close), in UTC, from the exchange's own calendar."""
    import exchange_calendars as xcals  # type: ignore[import-untyped]
    cal = xcals.get_calendar(fills.CALENDARS["LSE"])
    at = cal.session_open if which == "open" else cal.session_close
    out: datetime = pd.Timestamp(at(pd.Timestamp(day))).to_pydatetime()
    return out


def xlon_open(day: date) -> datetime:
    return xlon(day, "open")


def as_if(suggestions: Sequence[Mapping[str, object]], sessions: Sequence[date],
          opens_at: Callable[[date], datetime] = xlon_open) -> list[Fill]:
    """The allowed BUYs and SELLs, in order, as fills -- one position at a time."""
    out: list[Fill] = []
    for row in suggestions:
        side = str(row.get("action"))
        if not row.get("allowed") or side not in (BUY, SELL):
            continue
        if (side == BUY) == bool(out and out[-1].side == BUY):
            continue                    # a BUY while held, or a SELL while out, follows nothing
        when = fill_session(datetime.fromisoformat(str(row["at"])), sessions, opens_at)
        if when is not None:
            out.append(Fill(when, side, str(row["at"])))
    return out


def held_path(sessions: Sequence[date], book: Sequence[Fill]) -> np.ndarray:
    """1.0 for each session held through its CLOSE: bought at or before its open, not sold."""
    held, on, k = np.zeros(len(sessions)), False, 0
    for i, day in enumerate(sessions):
        while k < len(book) and book[k].session <= day:
            on = book[k].side == BUY
            k += 1
        held[i] = 1.0 if on else 0.0
    return held


def day(bars: pd.DataFrame, sessions: Sequence[date], book: Sequence[Fill], income: np.ndarray,
        instrument: costs.Instrument, k: int) -> Day:
    """Session k's as-if value, 1x and 2x: the one arithmetic on the record cut at k, so it is
    marked as if sold at THAT close (simulate.run sells a position still open at its end)."""
    held = held_path(sessions[:k + 1], book)
    opens, closes = bars["open"].to_numpy(dtype=float), bars["close"].to_numpy(dtype=float)
    value = {s: POT_GBP * float(np.prod(1.0 + simulate.run(
        opens[:k + 1], closes[:k + 1], held, simulate.leg_fractions(instrument, s), 0.0,
        income[:k + 1]).net)) for s in STRESSES}
    return Day(sessions[k], bool(held[k]), float(closes[k]), value)


def record(bars: pd.DataFrame, sessions: Sequence[date], book: Sequence[Fill],
           income: np.ndarray, instrument: costs.Instrument) -> list[Day]:
    """Every session's as-if day, recomputed from scratch (the daily reconciliation)."""
    return [day(bars, sessions, book, income, instrument, k) for k in range(len(sessions))]


def reconcile(written: Sequence[Mapping[str, object]], fresh: Sequence[Day]) -> list[str]:
    """Every line written before must match today's recomputation to the penny."""
    now = {d.session.isoformat(): d for d in fresh}
    out = []
    for row in written:
        day = now.get(str(row["session"]))
        if day is None:
            out.append(f"{row['session']}: written before, missing now (a bar removed?)")
            continue
        for s in STRESSES:
            was, is_ = round(float(row[f"value_{s:g}x"]), 2), round(day.value[s], 2)  # type: ignore[arg-type]
            if was != is_:
                out.append(f"{row['session']}: £{was:,.2f} at {s:g}x written, £{is_:,.2f} now "
                           "(a revised price or dividend)")
    return out


def line(day: Day) -> dict[str, object]:
    """The day's line for days.jsonl."""
    return {"session": day.session.isoformat(), "held": day.held, "close": day.close,
            **{f"value_{s:g}x": round(day.value[s], 2) for s in STRESSES},
            **{f"pct_{s:g}x": round(day.pct(s) * 100, 4) for s in STRESSES}}
