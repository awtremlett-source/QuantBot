"""The combined model's 17 features (QT-27 D1; register commit 6be96dad, CM-*: parameters.features).

Every feature of a (name, session) row is known at the CLOSE of that session's bar 1 -- the
decision moment. It is computed from the name's own bars up to bar 1, the other names' bar 1 of
the same market that session (F12-F14), ^VIX closes of EARLIER US sessions (F15) and the exchange
calendar (F16-F17), which is known in advance. The look-ahead test deletes every bar after the
decision moment and gets the same row, byte for byte.

Bar 1 = the session's first stored bar, and only if it starts at the exchange's open (US 09:30,
London 08:00); Pk = the close of the name's last bar of its k-th previous session in the store
(P1 = batch 1's "prior close"). EMA, ATR and Keltner are qb2/signals/indicators.py's, over the
name's 1h bars from its first stored bar. A row with any feature missing is dropped, train and
live alike, and counted (``complete``). No feature is ever added: a new one is a new trial.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

import exchange_calendars as xcals  # type: ignore[import-untyped]
import numpy as np
import pandas as pd

from qb2.research import fills
from qb2.signals import indicators, s6_rules

FEATURES = tuple(f"F{i}" for i in range(1, 18))
CALENDARS = fills.CALENDARS
VOLUME_SESSIONS, VOLUME_MIN_SESSIONS = 20, 10       # F7: the previous 20 sessions, at least 10 with a bar 1
VIX_MAX_WEEKDAYS = 5                                # F15: missing if the latest earlier close is older
TURN_FIRST, TURN_LAST = 3, 1                        # F17: first 3 and last 1 sessions of the month


def exchange_schedule(days: Iterable[date], market: str) -> pd.DataFrame:
    cal = xcals.get_calendar(CALENDARS[market])
    wanted = sorted(set(days))
    if not wanted:
        return pd.DataFrame(columns=["open", "close"])
    frame = cal.schedule.loc[str(wanted[0]):str(wanted[-1]), ["open", "close"]]
    return frame.set_axis(pd.DatetimeIndex(frame.index).date)


def session_opens(days: Iterable[date], market: str) -> dict[date, pd.Timestamp]:
    """Each exchange session's opening moment (UTC); a day the exchange was shut is absent."""
    return {d: pd.Timestamp(t) for d, t in exchange_schedule(days, market)["open"].items()}


def turn_of_month(days: Iterable[date], market: str) -> dict[date, int]:
    """F17: 1 for the last, or one of the first 3, sessions of a calendar month (exchange calendar)."""
    wanted = sorted(set(days))
    if not wanted:
        return {}
    first = date(wanted[0].year, wanted[0].month, 1)
    last = (pd.Timestamp(wanted[-1]) + pd.offsets.MonthEnd(0)).date()
    sessions = list(exchange_schedule([first, last], market).index)
    months: dict[tuple[int, int], list[date]] = {}
    for d in sessions:
        months.setdefault((d.year, d.month), []).append(d)
    flag: dict[date, int] = {}
    for days_in in months.values():
        for i, d in enumerate(days_in):
            flag[d] = int(i < TURN_FIRST or i >= len(days_in) - TURN_LAST)
    return {d: flag.get(d, 0) for d in wanted}


def vix_closes(vix_bars: pd.DataFrame) -> pd.Series:
    """^VIX's close per US session date: the close of that date's last stored 1h bar (16:00)."""
    if vix_bars.empty:
        return pd.Series(dtype=float)
    days = pd.DatetimeIndex(vix_bars.index).tz_convert(fills.EXCHANGE_TZ["US"]).date
    return vix_bars["close"].astype(float).groupby(days).last().sort_index()


def vix_before(day: date, closes: pd.Series) -> float:
    """F15: the latest ^VIX close dated BEFORE ``day`` (never the same date), if recent enough."""
    at = int(closes.index.searchsorted(day, side="left"))        # closes are in date order
    if at == 0:
        return float("nan")
    last = closes.index[at - 1]
    if int(np.busday_count(last, day)) > VIX_MAX_WEEKDAYS:
        return float("nan")
    return float(closes[last])


def name_rows(symbol: str, market: str, bars: pd.DataFrame, vix: pd.Series) -> pd.DataFrame:
    """One row per session that has a bar 1 and a previous session: the per-name features
    (F1-F11, F15-F17) and where bar 1 sits (``s0``). F12-F14 come from ``cross_section``."""
    index = pd.DatetimeIndex(bars.index)
    spans = s6_rules.sessions(index, market)
    if len(spans) < 2:
        return pd.DataFrame(columns=["symbol", "market", "day", "s0", *FEATURES])
    o, h, lo, c, v = (bars[col].to_numpy(dtype=float) for col in ("open", "high", "low", "close", "volume"))
    atr = indicators.atr_wilder(bars, indicators.KELTNER_ATR).to_numpy(dtype=float)
    ema = {n: indicators.ema(bars["close"].astype(float), n).to_numpy(dtype=float) for n in (9, 21, 50)}
    lower, _, upper = (x.to_numpy(dtype=float) for x in indicators.keltner(bars))
    days = [d for _, _, d in spans]
    opens = session_opens(days, market)
    turn = turn_of_month(days, market)
    utc = index.tz_convert("UTC")
    bar1 = np.array([d in opens and utc[a] == opens[d] for a, _, d in spans])
    last = np.array([c[b - 1] for _, b, _ in spans])
    vol1 = np.where(bar1, np.array([v[a] for a, _, _ in spans]), np.nan)

    def p(i: int, k: int) -> float:
        return float(last[i - k]) if i - k >= 0 else float("nan")

    rows = []
    with np.errstate(divide="ignore", invalid="ignore"):
        for i, (s0, _, day) in enumerate(spans):
            if i == 0 or not bar1[i]:
                continue
            seen = vol1[max(0, i - VOLUME_SESSIONS):i]
            seen = seen[np.isfinite(seen)]
            mean_v = float(seen.mean()) if len(seen) >= VOLUME_MIN_SESSIONS else float("nan")
            width = upper[s0] - lower[s0]
            rows.append({
                "symbol": symbol, "market": market, "day": day, "s0": s0,
                "F1": c[s0] / o[s0] - 1, "F2": o[s0] / p(i, 1) - 1, "F3": p(i, 1) / p(i, 2) - 1,
                "F4": p(i, 1) / p(i, 6) - 1, "F5": p(i, 1) / p(i, 21) - 1,
                "F6": (h[s0] - lo[s0]) / atr[s0 - 1] if s0 >= 1 else float("nan"),
                "F7": v[s0] / mean_v if mean_v > 0 else float("nan"),
                "F8": c[s0] / ema[9][s0] - 1, "F9": c[s0] / ema[21][s0] - 1, "F10": c[s0] / ema[50][s0] - 1,
                "F11": (c[s0] - lower[s0]) / width if width > 0 else float("nan"),
                "F15": vix_before(day, vix), "F16": float(day.weekday()), "F17": float(turn[day])})
    return pd.DataFrame(rows, columns=["symbol", "market", "day", "s0", *FEATURES[:11], *FEATURES[14:]])


def cross_section(rows: pd.DataFrame) -> pd.DataFrame:
    """F12-F14 per (market, session) over the names with that value: F1's and F2's ranks
    (average rank of ties / count) and the mean F1 -- the market that hour."""
    out = rows.copy()
    by = out.groupby(["market", "day"])
    out["F12"] = by["F1"].rank(method="average") / by["F1"].transform("count")
    out["F13"] = by["F2"].rank(method="average") / by["F2"].transform("count")
    out["F14"] = by["F1"].transform("mean")
    return out


def complete(rows: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """The rows with all 17 features finite, and how many were dropped."""
    ok = np.isfinite(rows[list(FEATURES)].to_numpy(dtype=float)).all(axis=1)
    return rows[ok], int((~ok).sum())
