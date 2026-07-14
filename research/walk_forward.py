"""Walk-forward validation -- the §7 firewall, part 2 of 3.

Grades a strategy ONLY on data it was never fitted on. The price series is split
into sequential folds; for each fold we FIT (search the parameter grid) on a TRAIN
window, then grade the chosen strategy on the FOLLOWING TEST window the fit never
saw, and roll forward. The stitched TEST-window returns are the honest out-of-
sample (OOS) record.

Two leaks, two guards. The backtester's next-open fill blocks INTRABAR lookahead
(a decision is never filled on the bar it was made). Walk-forward blocks the subtler
leak of FITTING on the data you then grade on: parameters are chosen in exactly ONE
place -- :func:`fit_best`, which only ever receives TRAIN bars. The OOS grading run
legitimately replays full history up to and INCLUDING the test window so indicators
warm up on real prior prices, but only test-window returns are counted and the
parameters came solely from train.

Stats reuse :func:`research.backtester.compute_stats`, so the OOS numbers are defined
identically to a plain backtest and cannot drift.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

import pandas as pd

from data_store.timeutils import now_utc_iso
from research import trial_log
from research.backtester import (
    BacktestResult,
    Stats,
    compute_stats,
    run_backtest,
)
from research.strategy import Strategy, TunableStrategy

logger = logging.getLogger(__name__)

# Matches run_backtest's default; used only to scale the reported OOS equity curve.
_DEFAULT_STARTING_EQUITY = 10000.0
_VALID_MODES = ("anchored", "rolling")
_VALID_METRICS = ("sharpe", "total_return")


@dataclass(frozen=True, slots=True)
class FitResult:
    """The outcome of one parameter search on a single TRAIN window.

    ``in_sample_score`` is the winning candidate's score on TRAIN under the chosen
    metric (this is an IN-SAMPLE number and must NOT be read as a track record).
    ``trials_evaluated`` is how many parameter combinations were tried.
    """

    best_params: dict[str, Any]
    best_strategy: Strategy
    in_sample_score: float
    trials_evaluated: int


@dataclass(frozen=True, slots=True)
class WalkForwardFold:
    """One TRAIN->TEST fold: what was fitted, and how it did out-of-sample.

    Range fields are ``event_time`` values (inclusive endpoints). ``oos_returns`` is
    the per-bar returns over just this fold's TEST window; ``oos_stats`` grades that
    slice on its own.
    """

    train_start: str
    train_end: str
    test_start: str
    test_end: str
    best_params: dict[str, Any]
    in_sample_score: float
    oos_returns: pd.Series
    oos_stats: Stats
    trials_evaluated: int


@dataclass(frozen=True, slots=True)
class WalkForwardResult:
    """The stitched out-of-sample record across every fold.

    ``oos_returns`` concatenates each fold's TEST-window returns in chronological
    order (contiguous + non-overlapping by the ``step >= test_size`` rule);
    ``oos_equity_curve`` compounds them from the starting equity. The headline
    ``oos_*`` figures are :func:`research.backtester.compute_stats` over the stitched
    series. ``total_trials`` is the honest count of parameter combinations tried
    across all folds -- the input to a Deflated Sharpe later.
    """

    folds: list[WalkForwardFold]
    oos_returns: pd.Series
    oos_equity_curve: pd.Series
    oos_total_return: float
    oos_annualized_sharpe: float
    oos_max_drawdown: float
    num_folds: int
    total_trials: int


def _score(result: BacktestResult, selection_metric: str) -> float:
    """Pull the selection metric off a backtest result (net figures only)."""
    if selection_metric == "sharpe":
        return result.annualized_sharpe_net
    if selection_metric == "total_return":
        return result.total_return_net
    raise ValueError(
        f"unknown selection_metric {selection_metric!r}; use 'sharpe' or 'total_return'"
    )


def fit_best(
    tunable: TunableStrategy,
    train_prices: pd.DataFrame,
    selection_metric: str = "sharpe",
    **backtest_kwargs: Any,
) -> FitResult:
    """Search ``tunable``'s grid on TRAIN ONLY and return the best-scoring fit.

    Every candidate is backtested on ``train_prices`` (never any later bar -- this
    is the sole place parameters are chosen, and the walk-forward birth certificate
    checks it) and scored by ``selection_metric`` (``'sharpe'`` ->
    ``annualized_sharpe_net``, ``'total_return'`` -> ``total_return_net``). Cost
    kwargs are forwarded so fitting uses the SAME cost model as grading.

    Deterministic tie-break: on equal scores the FIRST (grid-order) combo wins.
    """
    grid = tunable.param_grid()
    if not grid:
        raise ValueError("tunable.param_grid() is empty; nothing to fit")

    best_params: dict[str, Any] | None = None
    best_strategy: Strategy | None = None
    best_score = -math.inf
    for params in grid:
        strategy = tunable.build(params)
        # log_path=None: grid-search candidates are counted via total_trials, not
        # written to the trial log one-by-one (walk_forward logs a single summary).
        result = run_backtest(strategy, train_prices, log_path=None, **backtest_kwargs)
        score = _score(result, selection_metric)
        # Strictly-greater replaces, so the FIRST combo at the top score keeps it.
        # The `is None` guard also seeds the first iteration even if its score is
        # -inf/NaN, so we never return an empty fit on a non-empty grid.
        if best_strategy is None or score > best_score:
            best_params, best_strategy, best_score = dict(params), strategy, score

    assert best_params is not None and best_strategy is not None  # grid is non-empty
    return FitResult(
        best_params=best_params,
        best_strategy=best_strategy,
        in_sample_score=best_score,
        trials_evaluated=len(grid),
    )


def _validate_prices(prices: pd.DataFrame, train_size: int) -> None:
    """Reject input walk-forward cannot honestly split into folds."""
    if "event_time" not in prices.columns:
        raise ValueError("prices missing required column 'event_time'")
    if len(prices) == 0:
        raise ValueError("prices is empty; nothing to walk forward over")
    if not prices["event_time"].is_monotonic_increasing:
        raise ValueError("prices.event_time must be in ascending order")
    if len(prices) <= train_size + 2:
        raise ValueError(
            f"too little data: need more than train_size+2 ({train_size + 2}) bars "
            f"for even one fold, got {len(prices)}"
        )


def walk_forward(
    tunable: TunableStrategy,
    prices: pd.DataFrame,
    train_size: int = 252,
    test_size: int = 63,
    step: int | None = None,
    mode: str = "anchored",
    selection_metric: str = "sharpe",
    log_path: str | None = trial_log.DEFAULT_TRIAL_LOG,
    **backtest_kwargs: Any,
) -> WalkForwardResult:
    """Roll a fit/grade window over ``prices`` and return the stitched OOS record.

    For each fold: fit the grid on the TRAIN window (``mode='anchored'`` = expanding
    ``prices[0:train_end]``; ``'rolling'`` = the last ``train_size`` bars), then grade
    the chosen strategy on ``prices[:test_end]`` and keep only the TEST-window
    returns. ``step`` defaults to ``test_size`` and MUST be ``>= test_size`` so TEST
    windows never overlap. ``**backtest_kwargs`` (costs, starting equity) flow into
    BOTH the fit and the grade so they share one cost model.

    One summary record is appended to the trial log at ``log_path`` per run (the
    RISK-ADJUSTED out-of-sample Sharpe, plus the honest ``total_trials`` count);
    the many internal grid-search backtests are silenced (they log ``None``). Pass
    ``log_path=None`` to disable logging entirely.
    """
    if train_size < 1:
        raise ValueError(f"train_size must be >= 1, got {train_size}")
    if test_size < 2:
        raise ValueError(f"test_size must be >= 2, got {test_size}")
    if mode not in _VALID_MODES:
        raise ValueError(f"unknown mode {mode!r}; use 'anchored' or 'rolling'")
    if selection_metric not in _VALID_METRICS:
        raise ValueError(
            f"unknown selection_metric {selection_metric!r}; use 'sharpe' or 'total_return'"
        )
    step_size = test_size if step is None else step
    if step_size < test_size:
        raise ValueError(
            f"step ({step_size}) must be >= test_size ({test_size}) so TEST windows "
            "never overlap"
        )
    _validate_prices(prices, train_size)

    n = len(prices)
    event_time = prices["event_time"]
    starting_equity = float(
        backtest_kwargs.get("starting_equity", _DEFAULT_STARTING_EQUITY)
    )

    folds: list[WalkForwardFold] = []
    train_hi = train_size  # exclusive end of the train window / start of the test one
    while train_hi < n:
        test_lo = train_hi
        test_hi = min(train_hi + test_size, n)
        # Stop once the (possibly shorter, final) test window has fewer than 2 bars:
        # a single bar yields no genuine bar-to-bar return.
        if test_hi - test_lo < 2:
            break
        train_lo = 0 if mode == "anchored" else train_hi - train_size

        # FIT on TRAIN ONLY -- fit_best must never see a bar at/after test_lo. This
        # slice is the ONE input to the parameter search (see the birth certificate).
        train_prices = prices.iloc[train_lo:train_hi]
        fit = fit_best(tunable, train_prices, selection_metric, **backtest_kwargs)

        # GRADE OUT-OF-SAMPLE: replay full history up to and INCLUDING the test
        # window so indicators warm up on real prior bars (the next-open fill still
        # blocks intrabar lookahead), then keep only the test-window per-bar returns.
        # log_path=None: this grading run is folded into the single walk-forward
        # summary logged below, not counted as a standalone backtest trial.
        graded = run_backtest(
            fit.best_strategy, prices.iloc[:test_hi], log_path=None, **backtest_kwargs
        )
        oos_returns = graded.returns.iloc[test_lo:test_hi]

        folds.append(
            WalkForwardFold(
                train_start=str(event_time.iloc[train_lo]),
                train_end=str(event_time.iloc[train_hi - 1]),
                test_start=str(event_time.iloc[test_lo]),
                test_end=str(event_time.iloc[test_hi - 1]),
                best_params=fit.best_params,
                in_sample_score=fit.in_sample_score,
                oos_returns=oos_returns,
                oos_stats=compute_stats(oos_returns),
                trials_evaluated=fit.trials_evaluated,
            )
        )
        train_hi += step_size

    if not folds:
        # Validation guarantees at least one fold; never emit an empty result quietly.
        raise ValueError("no walk-forward folds produced; check window sizes")

    # STITCH: the fold TEST windows are contiguous + non-overlapping (step>=test_size),
    # so a plain chronological concat is the honest OOS return series.
    stitched = pd.concat([f.oos_returns for f in folds])
    stitched.name = "oos_return"
    equity_curve = starting_equity * (1.0 + stitched).cumprod()
    equity_curve.name = "oos_equity"
    oos_stats = compute_stats(stitched)

    result = WalkForwardResult(
        folds=folds,
        oos_returns=stitched,
        oos_equity_curve=equity_curve,
        oos_total_return=oos_stats.total_return,
        oos_annualized_sharpe=oos_stats.annualized_sharpe,
        oos_max_drawdown=oos_stats.max_drawdown,
        num_folds=len(folds),
        total_trials=sum(f.trials_evaluated for f in folds),
    )
    logger.info(
        "walk_forward: mode=%s folds=%d oos_total=%.4f oos_sharpe=%.2f "
        "oos_max_dd=%.4f trials=%d",
        mode,
        result.num_folds,
        result.oos_total_return,
        result.oos_annualized_sharpe,
        result.oos_max_drawdown,
        result.total_trials,
    )

    if log_path is not None:
        # One summary trial per walk-forward run. metric_value is the RISK-ADJUSTED
        # out-of-sample Sharpe; params carry total_trials so the deflation count
        # includes every grid combination tried across all folds.
        trial_record: dict[str, Any] = {
            "utc_time": now_utc_iso(),
            "kind": "walk_forward",
            "strategy_name": type(tunable).__name__,
            "params": {
                "mode": mode,
                "train_size": train_size,
                "test_size": test_size,
                "step": step_size,
                "selection_metric": selection_metric,
                "num_folds": result.num_folds,
                "total_trials": result.total_trials,
            },
            "metric_name": "oos_annualized_sharpe",
            "metric_value": result.oos_annualized_sharpe,
            "n_bars": int(len(stitched)),
        }
        trial_log.log_trial(trial_record, path=log_path)

    return result
