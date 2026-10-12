"""P15 inside the back-test: the sender's earnings check, asked exactly as the sender asks it.

PLAN_V3 P15: the bot never buys into a results announcement. Live, sender check 8
refuses a BUY when qb2/guard/earnings_window.py ``bot_verdict`` says blocked --
from the session before an announcement through the session after it, a share
with no knowable date blocked too (fail closed), an ETF N/A. QT-17 A3 runs that
same function inside the back-test, on the same earnings file, at the moment the
order would really be sent: the deciding bar's close plus the market's row-o
delay. ``bot_verdict`` itself keeps only rows whose knowable_time is at or before
that moment, so a date first recorded later is never known earlier.

The answer becomes the fill schedule's ``may_enter`` (fills.py): a blocked BUY
decision never lands, so a flat position stays flat and a held one stays held;
selling is never blocked, as the sender's sells skip checks 6-9. The matched null
places its trades only where an entry was allowed (matched_null.legal).

Intraday (bot) bars only: on daily bars, the advisor's, P15 warns and never blocks.

Asked once per (session, newest snapshot) pair: the verdict depends on nothing
else, so the cache is exact.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from qb2.guard import earnings_window
from qb2.ingest import earnings
from qb2.research import fills


def mask(symbol: str, kind: str, index: pd.DatetimeIndex, interval: str, market: str,
         frame: pd.DataFrame | None) -> NDArray[np.bool_]:
    """For each bar: may a BUY decided at its close be sent? (``frame``: the earnings file)"""
    n = len(index)
    if kind == earnings_window.ETF:
        return np.ones(n, dtype=bool)
    wait = pd.Timedelta(minutes=fills.BAR_MINUTES[interval] + fills.ROW_O_DELAY_MINUTES[market])
    sent = (pd.DatetimeIndex(index).tz_convert("UTC") + wait).floor("us").as_unit("ns")
    days = sent.tz_convert(fills.EXCHANGE_TZ[market]).date
    known = (np.sort(pd.DatetimeIndex(pd.to_datetime(frame["knowable_time"], utc=True))
                     .unique().as_unit("ns").asi8)     # one unit with ``sent``, or the order lies
             if frame is not None and not frame.empty else np.array([], dtype=np.int64))
    snapshots = np.searchsorted(known, sent.asi8, side="right")
    out = np.empty(n, dtype=bool)
    asked: dict[tuple[object, int], bool] = {}
    for i in range(n):
        key = (days[i], int(snapshots[i]))
        if key not in asked:
            moment: datetime = sent[i].to_pydatetime()
            asked[key] = not earnings_window.bot_verdict(symbol, kind, market, moment,
                                                         frame).blocked
        out[i] = asked[key]
    return out


def schedule(symbol: str, kind: str, index: pd.DatetimeIndex, interval: str, market: str,
             clean_root: Path | None = None) -> fills.Schedule:
    """The fill schedule, with P15's entry mask on intraday bars."""
    if interval == "1d":
        return fills.schedule(index, interval, market)
    allowed = mask(symbol, kind, index, interval, market, earnings.load(symbol, clean_root))
    return fills.schedule(index, interval, market, may_enter=allowed)
