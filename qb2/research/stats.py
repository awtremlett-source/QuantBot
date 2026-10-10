"""Headline statistics, one definition for every path (S4).

PORTED from v1's research/backtester.py ``compute_stats`` (SHA-256 at copy time,
2026-10-10: 4ca72b809c37d1eab994ec6feda0b07aa9a4baeb8e1973ffb8d391407ad485ba),
adapted to returns on a fixed stake, which ADD rather than compound, and to more
than one bar size.

The verdict uses the PER-BAR Sharpe (mean / standard deviation): the Monte Carlo
null and the Deflated Sharpe are both in per-bar units. The annualised figure is
for reading only: daily bars x sqrt(252); 5-minute bars x sqrt(252 x bars per
session), 78 in New York and 102 in London.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

TRADING_DAYS = 252
BARS_PER_SESSION = {"US": 78, "LSE": 102}


def periods_per_year(interval: str, market: str = "US") -> float:
    if interval == "1d":
        return float(TRADING_DAYS)
    if interval == "5m":
        return float(TRADING_DAYS * BARS_PER_SESSION[market])
    raise ValueError(f"no annualisation for interval {interval!r}")


@dataclass(frozen=True, slots=True)
class Stats:
    total_return: float          # sum of per-bar returns on the stake
    sharpe_per_bar: float
    sharpe_annualised: float
    max_drawdown: float          # worst fall from a peak of (1 + cumulative), <= 0
    bars: int


def compute(returns: pd.Series | np.ndarray, interval: str, market: str = "US") -> Stats:
    values = np.asarray(returns, dtype=float)
    if len(values) == 0:
        return Stats(0.0, 0.0, 0.0, 0.0, 0)
    std = float(values.std(ddof=1)) if len(values) > 1 else 0.0
    per_bar = float(values.mean()) / std if std > 1e-15 and math.isfinite(std) else 0.0
    equity = 1.0 + np.concatenate([[0.0], np.cumsum(values)])
    peaks = np.maximum.accumulate(equity)
    drawdown = float((equity / peaks - 1.0).min())
    return Stats(total_return=float(values.sum()), sharpe_per_bar=per_bar,
                 sharpe_annualised=per_bar * math.sqrt(periods_per_year(interval, market)),
                 max_drawdown=drawdown, bars=len(values))
