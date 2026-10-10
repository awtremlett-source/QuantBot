"""The backtester: one registered strategy on one name's bars, honestly (S4).

PORTED, NOT IMPORTED, from v1's research/backtester.py (SHA-256 at copy time,
2026-10-10: 4ca72b809c37d1eab994ec6feda0b07aa9a4baeb8e1973ffb8d391407ad485ba).
v1's file is split here into four, each under 250 lines: fills.py (when),
simulate.py (how much), stats.py (the figures) and this file (the checks, in
order, and the trial log).

The checks every run makes before a number exists:

1. the candidate is in the COMMITTED register (preregister.check);
2. no bar is inside the holdout seal, unless this is the final run (holdout);
3. the weights are 0/1 and do not read the future (strategy.checked_weights);
4. fills follow delay rule (c) and P4 (fills.py); every fill pays the cost model
   (simulate.py) -- gross AND net are always both reported, 2x is ``stress=2``;
5. single shares are marked down for survivorship before scoring: 1.0% a year
   held (ETFs 0). A STARTING FIGURE taken from published averages of how much
   survivor-only share lists flatter back-tests -- NOT measured on these names.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from qb2.execution import costs
from qb2.research import fills, holdout, preregister, simulate, stats, trial_log
from qb2.research.strategy import Strategy, checked_weights

SURVIVORSHIP_DRAG_PER_YEAR = 0.01        # single shares; ETFs 0 -- starting figure
SURVIVORSHIP_LABEL = ("survivorship mark-down: 1.0%/yr held on single shares, 0 on "
                      "ETFs -- a starting figure from published averages, not measured "
                      "on these names")


def drag_per_bar(instrument: costs.Instrument, interval: str, market: str) -> float:
    if instrument.kind != "STOCK":
        return 0.0
    return SURVIVORSHIP_DRAG_PER_YEAR / stats.periods_per_year(interval, market)


@dataclass(frozen=True, slots=True)
class BacktestResult:
    candidate_id: str
    symbol: str
    interval: str
    market: str
    index: pd.DatetimeIndex
    held: np.ndarray
    paths: simulate.Paths
    legs: simulate.LegFractions
    stress: float

    def series(self, which: str) -> pd.Series:
        return pd.Series(getattr(self.paths, which), index=self.index)

    @property
    def trades(self) -> int:
        return int(self.paths.entries.sum())


def validate(bars: pd.DataFrame) -> None:
    if len(bars) == 0:
        raise ValueError("no bars; nothing to backtest")
    missing = [c for c in ("open", "close") if c not in bars.columns]
    if missing:
        raise ValueError(f"bars missing column(s): {missing}")
    if not isinstance(bars.index, pd.DatetimeIndex) or bars.index.tz is None:
        raise ValueError("bars need a timezone-aware DatetimeIndex (UTC in code, #23)")
    if not bars.index.is_monotonic_increasing:
        raise ValueError("bars must be in ascending time order")


def run(token: preregister.Registered, strategy: Strategy, bars: pd.DataFrame, *,
        instrument: costs.Instrument, interval: str, market: str, stress: float = 1.0,
        final: holdout.HoldoutPass | None = None, plan: fills.Schedule | None = None,
        log_path: Path | None = trial_log.DEFAULT_TRIAL_LOG) -> BacktestResult:
    """One name, one registered strategy. Logs ONE trial unless ``log_path`` is None
    (the firewall passes None and logs one summary for the whole candidate)."""
    registered = preregister.check(token)
    if str(registered.entry["bar_size"]) != interval:
        raise preregister.NotRegistered(
            f"{registered.id} is registered on {registered.entry['bar_size']} bars, "
            f"not {interval}")
    holdout.check_unsealed(bars.index, interval, market, final)
    validate(bars)
    weights = checked_weights(strategy, bars)
    schedule = plan or fills.schedule(bars.index, interval, market)
    held = fills.positions(schedule, weights)
    legs = simulate.leg_fractions(instrument, stress)
    paths = simulate.run(bars["open"].to_numpy(dtype=float),
                         bars["close"].to_numpy(dtype=float), held, legs,
                         drag_per_bar(instrument, interval, market))
    result = BacktestResult(registered.id, instrument.ticker, interval, market,
                            pd.DatetimeIndex(bars.index), held, paths, legs, stress)
    if log_path is not None:
        net = stats.compute(paths.net, interval, market)
        trial_log.log_trial({
            "utc_time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "kind": trial_log.DRILL if registered.is_drill else trial_log.BACKTEST,
            "candidate_id": registered.id, "register_commit": registered.commit,
            "strategy_name": strategy.name,
            "params": {"symbol": instrument.ticker, "stress": stress},
            "metric_name": "sharpe_per_bar_net", "metric_value": net.sharpe_per_bar,
            "n_bars": len(bars)}, path=log_path)
    return result
