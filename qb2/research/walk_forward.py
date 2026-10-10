"""Walk-forward: grade only on bars the fit never saw (S4).

PORTED, NOT IMPORTED, from v1's research/walk_forward.py (SHA-256 at copy time,
2026-10-10: 5db3bd8c4ec1b1245c2f20d768fcce74205daf412d0070445383ffa2231f05de).
Same idea: sequential anchored folds; FIT (choose parameters) on the TRAIN window
only, then grade on the TEST window that follows; the stitched TEST returns are
the out-of-sample (OOS) record.

Adapted for qb2: every run needs a registered token; costs and the delay rule are
inside each grading run (backtest.py); window sizes default per bar size --
daily 252 / 63 bars, 5-minute 10 / 5 sessions of that market (starting figures).

P19's trials and the drills have FIXED parameters (a one-element grid). Nothing
is chosen, so each fold's grade is exactly that bar range of one full run --
which is how it is computed (a test proves the two agree), and it counts as ONE
trial, not one per fold.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import pandas as pd

from qb2.execution import costs
from qb2.research import backtest, fills, preregister, stats, trial_log
from qb2.research.strategy import Strategy


class Tunable(Protocol):
    name: str

    def param_grid(self) -> list[dict[str, Any]]: ...

    def build(self, params: dict[str, Any]) -> Strategy: ...


class Fixed:
    """A fixed-parameter strategy as a one-element grid."""

    def __init__(self, strategy: Strategy) -> None:
        self.strategy = strategy
        self.name = strategy.name

    def param_grid(self) -> list[dict[str, Any]]:
        return [{}]

    def build(self, params: dict[str, Any]) -> Strategy:
        return self.strategy


@dataclass(frozen=True, slots=True)
class Fold:
    train_lo: int
    train_hi: int
    test_lo: int
    test_hi: int


def default_sizes(interval: str, market: str) -> tuple[int, int]:
    if interval == "1d":
        return 252, 63
    per = stats.BARS_PER_SESSION[market]
    return 10 * per, 5 * per


def folds(n: int, train_size: int, test_size: int) -> list[Fold]:
    """Anchored folds; TEST windows are contiguous and never overlap."""
    if train_size < 1 or test_size < 2:
        raise ValueError("train_size must be >= 1 and test_size >= 2")
    out: list[Fold] = []
    hi = train_size
    while hi < n and min(hi + test_size, n) - hi >= 2:
        out.append(Fold(0, hi, hi, min(hi + test_size, n)))
        hi += test_size
    return out


@dataclass(frozen=True, slots=True)
class WalkForwardResult:
    folds: list[Fold]
    oos: pd.DataFrame            # gross, net, marked, entries -- OOS bars only
    total_trials: int
    chosen: list[dict[str, Any]]


def _frame(result: backtest.BacktestResult, lo: int, hi: int) -> pd.DataFrame:
    p = result.paths
    return pd.DataFrame({"gross": p.gross[lo:hi], "net": p.net[lo:hi],
                         "marked": p.marked[lo:hi], "entries": p.entries[lo:hi]},
                        index=result.index[lo:hi])


def walk_forward(token: preregister.Registered, tunable: Tunable, bars: pd.DataFrame, *,
                 instrument: costs.Instrument, interval: str, market: str,
                 stress: float = 1.0, sizes: tuple[int, int] | None = None,
                 plan: fills.Schedule | None = None,
                 log_path: Path | None = trial_log.DEFAULT_TRIAL_LOG) -> WalkForwardResult:
    registered = preregister.check(token)
    train, test = sizes or default_sizes(interval, market)
    windows = folds(len(bars), train, test)
    if not windows:
        return WalkForwardResult([], _empty(), 0, [])
    grid = tunable.param_grid()
    kw: dict[str, Any] = dict(instrument=instrument, interval=interval, market=market,
                              stress=stress, log_path=None)
    if len(grid) == 1:
        full = backtest.run(registered, tunable.build(grid[0]), bars, plan=plan, **kw)
        oos = pd.concat([_frame(full, f.test_lo, f.test_hi) for f in windows])
        total, chosen = 1, [dict(grid[0])] * len(windows)
    else:
        parts, chosen = [], []
        for f in windows:
            best = _fit(registered, tunable, grid, bars.iloc[f.train_lo:f.train_hi], kw)
            graded = backtest.run(registered, tunable.build(best), bars.iloc[:f.test_hi], **kw)
            parts.append(_frame(graded, f.test_lo, f.test_hi))
            chosen.append(best)
        oos, total = pd.concat(parts), len(grid) * len(windows)
    if log_path is not None:
        net = stats.compute(oos["net"], interval, market)
        trial_log.log_trial({
            "utc_time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "kind": trial_log.DRILL if registered.is_drill else trial_log.WALK_FORWARD,
            "candidate_id": registered.id, "register_commit": registered.commit,
            "strategy_name": tunable.name,
            "params": {"train": train, "test": test, "folds": len(windows),
                       "total_trials": total, "stress": stress},
            "metric_name": "oos_sharpe_per_bar_net", "metric_value": net.sharpe_per_bar,
            "n_bars": len(oos)}, path=log_path)
    return WalkForwardResult(windows, oos, total, chosen)


def _fit(token: preregister.Registered, tunable: Tunable, grid: Sequence[dict[str, Any]],
         train_bars: pd.DataFrame, kw: dict[str, Any]) -> dict[str, Any]:
    """TRAIN ONLY. First combo wins ties (deterministic)."""
    best: dict[str, Any] | None = None
    best_score = -math.inf
    for params in grid:
        result = backtest.run(token, tunable.build(params), train_bars, **kw)
        score = stats.compute(result.paths.net, kw["interval"], kw["market"]).sharpe_per_bar
        if best is None or score > best_score:
            best, best_score = dict(params), score
    assert best is not None
    return best


def _empty() -> pd.DataFrame:
    return pd.DataFrame({"gross": np.array([], float), "net": np.array([], float),
                         "marked": np.array([], float), "entries": np.array([], bool)},
                        index=pd.DatetimeIndex([], tz="UTC"))
