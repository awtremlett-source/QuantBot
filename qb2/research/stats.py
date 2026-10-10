"""Headline statistics, one definition for every path (S4).

PORTED from v1's research/backtester.py ``compute_stats`` (SHA-256 at copy time,
2026-10-10: 4ca72b809c37d1eab994ec6feda0b07aa9a4baeb8e1973ffb8d391407ad485ba),
adapted to more than one bar size.

**Returns compound (QT-15 A1).** Each per-bar return is earned on the pot as it
stands at that bar's start, so equity is the running product of (1 + r), the total
return is equity at the end - 1 (it can never read below -100%), and drawdown is
measured on that same compounded line -- the basis the benchmark is measured on.
QT-14's port added them up (equity = 1 + cumsum), which let a coin-flip read -369%.

The verdict uses the PER-BAR Sharpe (mean / standard deviation) of the simple
per-bar returns, unchanged by QT-15, as is the Deflated Sharpe's input: the Monte Carlo
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
    total_return: float          # compounded: prod(1 + r) - 1, never below -1
    sharpe_per_bar: float
    sharpe_annualised: float
    max_drawdown: float          # worst fall from a peak of compounded equity, <= 0
    bars: int


def compounded(returns: pd.Series | np.ndarray) -> np.ndarray:
    """Equity from 1.0: the running product of (1 + r). A pot cannot fall below
    nothing, so a bar that would take it below zero leaves it at zero."""
    growth = np.maximum(1.0 + np.asarray(returns, dtype=float), 0.0)
    return np.concatenate([[1.0], np.cumprod(growth)])


def compute(returns: pd.Series | np.ndarray, interval: str, market: str = "US") -> Stats:
    values = np.asarray(returns, dtype=float)
    if len(values) == 0:
        return Stats(0.0, 0.0, 0.0, 0.0, 0)
    std = float(values.std(ddof=1)) if len(values) > 1 else 0.0
    per_bar = float(values.mean()) / std if std > 1e-15 and math.isfinite(std) else 0.0
    equity = compounded(values)
    peaks = np.maximum.accumulate(equity)
    drawdown = float((equity / peaks - 1.0).min())
    return Stats(total_return=float(equity[-1] - 1.0), sharpe_per_bar=per_bar,
                 sharpe_annualised=per_bar * math.sqrt(periods_per_year(interval, market)),
                 max_drawdown=drawdown, bars=len(values))
