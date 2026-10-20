"""The advisor's pure rules, one copy each, shared by research and the live advisor (QT-23).

* income -- P3: OK payouts / the previous close on the first bar on or after the ex-date, US net of
  withholding (the rule of every back-test here; moved from advisor_data);
* filter_of -- A-06's market filter: D3 above the mean of its last 200 closes (from advisor_data);
* rebuy_signal -- R6: a close at least 10% above the lowest close since the exit (from adv0_describe).
Free of anything that reaches the back-test-only P15 history rule, so the LIVE advisor may import it
(wall: tests/wall/test_p15_history_wall.py); advisor_data and adv0_describe re-export these.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from qb2.ingest import dividends
from qb2.research import advisor_book, total_return

VIX = "^VIX"
FILTER_BARS = 200
REBUY = 0.10                           # R6 (ADV-0 parameters.rebuy_rise): a STARTING FIGURE


def income(symbol: str, market: str, bars: pd.DataFrame, clean_root: Path | None = None,
           ) -> tuple[np.ndarray, dict[str, int]]:
    """Payout / previous close on the first bar on or after each OK ex-date."""
    out = np.zeros(len(bars))
    seen = {"credited": 0, "not_ok": 0}
    rows = dividends.load(symbol, clean_root)
    if rows is None or rows.empty or len(bars) < 2:
        return out, seen
    days = pd.DatetimeIndex(bars.index).date
    close = bars["close"].to_numpy(dtype=float)
    keep = 1.0 - total_return.WITHHOLDING.get(market, 0.0)
    for _, row in rows.iterrows():
        t = int((days < date.fromisoformat(str(row["ex_date"]))).sum())   # first bar on/after
        if not 1 <= t < len(bars):
            continue
        if str(row["verdict"]) != "OK":
            seen["not_ok"] += 1
            continue
        out[t] += float(row["amount"]) / close[t - 1] * keep
        seen["credited"] += 1
    return out, seen


def filter_of(vwrp: pd.Series, vwrl: pd.Series) -> dict[int, bool]:
    """The rule itself, on any two close series: research's, or the advisor's live ones (QT-23)."""
    last = max(pd.DatetimeIndex(vwrp.index).date[-1], pd.DatetimeIndex(vwrl.index).date[-1])
    ends = advisor_book.last_sessions(advisor_book.sessions("LSE", date(2012, 1, 1), last))
    out: dict[int, bool] = {}
    for m, end in ends.items():
        for series in (vwrp, vwrl):
            upto = series[pd.DatetimeIndex(series.index).date <= end]
            if len(upto) >= FILTER_BARS:
                out[m] = bool(upto.iloc[-1] > upto.iloc[-FILTER_BARS:].mean())
                break
    return out


def rebuy_signal(close: float, low: float) -> bool:
    """R6, its ONE copy (the live job's too): a close at least 10% above the lowest close since the
    exit -- compared to the micro-penny, so a 2-decimal price exactly 10% up counts (95.00 -> 104.50)."""
    return round(close, 6) >= round(low * (1 + REBUY), 6)
