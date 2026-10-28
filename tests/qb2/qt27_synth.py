"""Synthetic 1-hour bars and names for the QT-27 tests: offline, seeded, on the real calendars."""

from __future__ import annotations

from collections.abc import Sequence

import exchange_calendars as xcals  # type: ignore[import-untyped]
import numpy as np
import pandas as pd

from qb2.execution import costs
from qb2.research import fills
from qb2.research.names import NameData

CALENDAR = {"US": "XNYS", "LSE": "XLON"}
TZ = fills.EXCHANGE_TZ


def bars(market: str, start: str, sessions: int, seed: int, drift: float = 0.0) -> pd.DataFrame:
    """Hourly bars from each session's open to its close, a seeded random walk."""
    cal = xcals.get_calendar(CALENDAR[market])
    days = cal.sessions_in_range(start, pd.Timestamp(start) + pd.Timedelta(days=sessions * 2))[:sessions]
    rng = np.random.default_rng(seed)
    stamps, price, rows = [], 100.0 + seed, []
    for day in days:
        open_, close = cal.session_open(day), cal.session_close(day)
        t = open_
        while t < close:
            stamps.append(t.tz_convert(TZ[market]))
            o = price * (1 + rng.normal(0, 0.002))
            c = o * (1 + rng.normal(drift, 0.004))
            rows.append((o, max(o, c) * (1 + abs(rng.normal(0, 0.001))),
                         min(o, c) * (1 - abs(rng.normal(0, 0.001))), c, float(rng.integers(1_000, 9_000))))
            price = c
            t = t + pd.Timedelta(hours=1)
    frame = pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"],
                         index=pd.DatetimeIndex(stamps, name="ts"))
    return frame


def name(symbol: str, market: str, frame: pd.DataFrame, bet: int, kind: str = "ETF",
         may_enter: np.ndarray | None = None) -> NameData:
    currency = "GBP" if market == "LSE" else "USD"
    inst = costs.Instrument(symbol, currency, market, kind, False)
    plan = fills.schedule(frame.index, "1h", market,
                          may_enter=np.ones(len(frame), dtype=bool) if may_enter is None else may_enter)
    return NameData(symbol, market, inst, frame, plan, bet)


def london_arm(n: int = 5, sessions: int = 200, start: str = "2023-11-01") -> list[NameData]:
    return [name(f"SYN{i}.L", "LSE", bars("LSE", start, sessions, seed=i), bet=i) for i in range(n)]


def vix(start: str = "2023-11-01", sessions: int = 220) -> pd.DataFrame:
    return bars("US", start, sessions, seed=99)


def cut(names: Sequence[NameData], moment: pd.Timestamp) -> list[NameData]:
    """Every bar that ENDS after ``moment`` deleted, schedules rebuilt on what is left."""
    out = []
    for d in names:
        keep = (pd.DatetimeIndex(d.bars.index).tz_convert("UTC") + pd.Timedelta(hours=1)) <= moment
        frame = d.bars[keep]
        may = None if d.plan.may_enter is None else d.plan.may_enter[keep]
        out.append(name(d.symbol, d.market, frame, d.bet, d.instrument.kind, may))
    return out
