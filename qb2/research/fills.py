"""When a decision can really be filled -- delay rule (c), and flat by the close (S4).

PORTED in part from v1's research/backtester.py (SHA-256 at copy time, 2026-10-10:
4ca72b809c37d1eab994ec6feda0b07aa9a4baeb8e1973ffb8d391407ad485ba): its rule that a
decision is never filled on the bar it was made. v1 filled at the NEXT bar's open;
qb2 fills later, at the price we would really have had.

**Delay rule (c), decided 2026-10-09** (operator: *"GO on S4 delay: (c), measure
T212 freshness"*): a signal on a bar acts at the open of the first bar that
STARTS at or after that bar's close plus the market's row-o delay (US 1.25 min,
London 16.66 min). On 5-minute bars that is 2 bars later in the US and 5 bars
later in London; on daily bars, the next session's open. Slippage and spread
are charged on the fill by the cost model (qb2/execution/costs.py).

**Flat by the close (PLAN_V3 P4), intraday only.** A decision whose fill would
land in a later session is never acted on, a session starts flat, and every
position is sold at the open of the first bar starting 15 minutes before the bell
(starting figure) -- or the session's last bar if none does. Nothing is held
overnight. Closes come from the exchange calendars, so a half day closes early.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time, timedelta

import exchange_calendars as xcals  # type: ignore[import-untyped]
import numpy as np
import pandas as pd
from numpy.typing import NDArray

from qb2.execution import xcheck

ROW_O_DELAY_MINUTES = xcheck.ROW_O_DELAY_MINUTES      # one copy of row o, not two
BAR_MINUTES = {"5m": 5}
FLAT_BEFORE_CLOSE = timedelta(minutes=15)            # P4, starting figure
CALENDARS = {"US": "XNYS", "LSE": "XLON"}
EXCHANGE_TZ = {"US": "America/New_York", "LSE": "Europe/London"}
REGULAR_CLOSE = {"US": time(16, 0), "LSE": time(16, 30)}


def fill_index(index: pd.DatetimeIndex, interval: str, market: str) -> NDArray[np.int64]:
    """For each bar, the position of the bar its decision fills at (n = never)."""
    n = len(index)
    if interval == "1d":
        return np.arange(1, n + 1, dtype=np.int64)
    if interval not in BAR_MINUTES:
        raise ValueError(f"no fill rule for interval {interval!r}")
    wait = pd.Timedelta(minutes=BAR_MINUTES[interval] + ROW_O_DELAY_MINUTES[market])
    starts = pd.DatetimeIndex(index).tz_convert("UTC").as_unit("ns")
    found = np.searchsorted(starts.asi8, (starts + wait).asi8, side="left")
    return np.asarray(found, dtype=np.int64)


def _close_ns(day: object, market: str) -> int:
    calendar = xcals.get_calendar(CALENDARS[market])
    stamp = pd.Timestamp(str(day))
    try:
        if calendar.is_session(stamp):
            return int(pd.Timestamp(calendar.session_close(stamp)).as_unit("ns").value)
    except Exception:                         # noqa: BLE001 - outside the calendar range
        pass
    local = pd.Timestamp(f"{day} {REGULAR_CLOSE[market]}", tz=EXCHANGE_TZ[market])
    return int(local.tz_convert("UTC").as_unit("ns").value)


@dataclass(frozen=True, slots=True)
class Schedule:
    """Everything about WHEN, computed once per name; positions() is then pure numpy."""

    n: int
    fills: NDArray[np.int64]
    usable: NDArray[np.bool_]
    session_first: NDArray[np.bool_] | None
    forced_flat: NDArray[np.bool_] | None


def schedule(index: pd.DatetimeIndex, interval: str, market: str) -> Schedule:
    n = len(index)
    fills = fill_index(index, interval, market)
    usable = fills < n
    if interval == "1d":
        return Schedule(n, fills, usable, None, None)
    local = pd.DatetimeIndex(index).tz_convert(EXCHANGE_TZ[market])
    session = np.asarray(local.normalize().tz_localize(None).asi8)
    same = np.zeros(n, dtype=bool)
    ok = np.flatnonzero(usable)
    same[ok] = session[fills[ok]] == session[ok]
    first = np.r_[True, session[1:] != session[:-1]]
    last = np.r_[session[1:] != session[:-1], True]
    days = pd.DatetimeIndex(local.normalize().tz_localize(None)).date
    closes = {d: _close_ns(d, market) for d in sorted(set(days))}
    cutoff = np.array([closes[d] for d in days], dtype=np.int64) - \
        int(FLAT_BEFORE_CLOSE.total_seconds() * 1e9)
    utc = pd.DatetimeIndex(index).tz_convert("UTC").as_unit("ns").asi8
    return Schedule(n, fills, same, first, (utc >= cutoff) | last)


def positions(plan: Schedule, weights: NDArray[np.float64]) -> NDArray[np.float64]:
    """The position held during each bar after the delay and P4 are applied.

    ``weights[i]`` is the target decided at bar i's close. It takes effect from the
    open of bar ``fills[i]``; when two decisions land on one bar, the later wins.
    """
    target = np.asarray(weights, dtype=float)
    if len(target) != plan.n:
        raise ValueError("weights and bars differ in length")
    chosen = np.flatnonzero(plan.usable)
    landing = plan.fills[chosen]
    keep = np.r_[landing[1:] != landing[:-1], True] if len(landing) else landing.astype(bool)
    held = np.full(plan.n, np.nan)
    held[landing[keep]] = target[chosen[keep]]
    if plan.session_first is not None:
        held[plan.session_first & np.isnan(held)] = 0.0      # nothing carried in
    known = np.where(np.isnan(held), 0, np.arange(plan.n))
    held = held[np.maximum.accumulate(known)]
    held = np.nan_to_num(held, nan=0.0)
    if plan.forced_flat is not None:
        held[plan.forced_flat] = 0.0                         # sold before the bell
    return np.asarray(held, dtype=np.float64)
