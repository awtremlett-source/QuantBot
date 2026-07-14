"""Monte-Carlo known-null gate -- the §7 validation firewall, part 3 of 3.

Parts 1 and 2 (backtester, walk-forward) make a track record HONEST. This part asks
the harder question: *is the honest record any better than luck?* It answers with a
coin-flip null. We run many random long/flat "strategies" over the SAME prices to see
what pure chance produces, then place the real strategy's RISK-ADJUSTED score in that
distribution. If the real score is not comfortably out in the right tail, the edge is
indistinguishable from noise and the firewall REJECTS it.

This is the layer that makes the firewall TRUSTWORTHY, so it carries its own birth
certificate (in the tests): a coin-flip fed in here MUST be rejected, and a strategy
that mechanically harvests a deterministic price pattern MUST pass. If a coin-flip
ever passed, the gate would be rubber-stamping noise and nothing downstream could be
believed.

Two locked principles run through it:

* RISK-ADJUSTED judging -- the verdict is built on Sharpe (``annualized_sharpe_net``),
  not raw return, so a lucky high-return/high-variance run cannot buy its way through.
* Honest trial counting -- each batch appends one summary to the append-only trial log
  (:mod:`research.trial_log`), and the underlying backtester counts every run, so the
  Deflated Sharpe later sees every try.

Builds ON TOP of the backtester and walk-forward; it never touches their fill or
no-lookahead logic.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from data_store.timeutils import now_utc_iso
from research import trial_log
from research.backtester import BacktestResult, run_backtest
from research.strategy import Strategy

logger = logging.getLogger(__name__)

# Metric name -> the RISK-ADJUSTED field it reads off a BacktestResult. Sharpe is the
# default and the one the firewall's verdict is built on; total_return is offered for
# diagnostics only.
_METRIC_ATTR: dict[str, str] = {
    "sharpe": "annualized_sharpe_net",
    "total_return": "total_return_net",
}


class RandomStrategy:
    """A coin-flip null: ``decide`` returns 1.0 or 0.0 at random, ignoring the market.

    Each bar draws one Bernoulli(``prob_long``) outcome (1.0 = fully invested next bar,
    0.0 = all cash). The RNG is seeded at construction, so a fresh instance replays an
    identical sequence for a given ``seed`` -- deterministic, which is what lets the
    null distribution be reproduced exactly. It has no signal by design: it is the
    yardstick of "what does pure luck score on these prices?".
    """

    def __init__(self, prob_long: float, seed: int) -> None:
        if not 0.0 <= prob_long <= 1.0:
            raise ValueError(f"prob_long must be in [0, 1], got {prob_long!r}")
        self._prob_long = float(prob_long)
        self._rng = np.random.default_rng(seed)

    def decide(self, history: pd.DataFrame) -> float:
        # One draw per bar; history is deliberately ignored -- a coin has no memory.
        return 1.0 if self._rng.random() < self._prob_long else 0.0


@dataclass(frozen=True, slots=True)
class MonteCarloResult:
    """The verdict of a known-null assessment.

    ``observed_metric`` is the real strategy's RISK-ADJUSTED score; ``null_mean`` /
    ``null_std`` summarise the coin-flip null on the same prices; ``p_value`` is the
    (smoothed) chance a coin-flip matches or beats the observed score; ``percentile``
    is where the observed score sits within the null (0-100); ``passed`` is
    ``p_value < alpha`` -- i.e. "significantly better than luck".
    """

    observed_metric: float
    null_mean: float
    null_std: float
    p_value: float
    percentile: float
    passed: bool
    n_trials: int


def _metric_name(metric: str) -> str:
    """Map a metric key to its BacktestResult field, or raise on an unknown key."""
    try:
        return _METRIC_ATTR[metric]
    except KeyError as exc:
        raise ValueError(
            f"unknown metric {metric!r}; use 'sharpe' or 'total_return'"
        ) from exc


def _metric_value(result: BacktestResult, metric: str) -> float:
    """Pull the risk-adjusted metric off a backtest result."""
    return float(getattr(result, _metric_name(metric)))


def _trial_seeds(seed: int, n_trials: int) -> list[int]:
    """Derive ``n_trials`` decorrelated child seeds from a single base ``seed``.

    Uses NumPy's :class:`~numpy.random.SeedSequence`, so the child seeds are well
    separated (adjacent base seeds do not produce correlated null draws) and fully
    determined by ``seed`` -- the whole null distribution is reproducible.
    """
    if n_trials < 1:
        raise ValueError(f"n_trials must be >= 1, got {n_trials}")
    state = np.random.SeedSequence(seed).generate_state(n_trials)
    return [int(x) for x in state.tolist()]


def null_distribution(
    prices: pd.DataFrame,
    n_trials: int = 1000,
    prob_long: float = 0.5,
    metric: str = "sharpe",
    seed: int = 0,
    log_path: str | None = trial_log.DEFAULT_TRIAL_LOG,
    **backtest_kwargs: Any,
) -> list[float]:
    """Run ``n_trials`` coin-flip backtests over ``prices``; return their metrics.

    Each trial is a :class:`RandomStrategy` with a distinct seed derived from ``seed``,
    backtested over the SAME ``prices`` under the SAME cost model (``backtest_kwargs``),
    scored by the RISK-ADJUSTED ``metric`` (default ``annualized_sharpe_net``). The
    returned list is the null distribution: what pure luck scores on these prices.

    Logging: the individual coin-flip runs are silenced (they would flood the log);
    one summary record (``kind='monte_carlo'``, ``n_trials``) is appended instead. Pass
    ``log_path=None`` to disable.
    """
    metric_name = _metric_name(metric)  # validate the metric before any work
    # Never forward a stray log_path into the per-trial backtests -- they are always
    # silenced; this batch logs a single summary of its own.
    internal_kwargs = {k: v for k, v in backtest_kwargs.items() if k != "log_path"}

    scores: list[float] = []
    for trial_seed in _trial_seeds(seed, n_trials):
        strategy = RandomStrategy(prob_long, seed=trial_seed)
        result = run_backtest(strategy, prices, log_path=None, **internal_kwargs)
        scores.append(_metric_value(result, metric))

    if log_path is not None:
        summary: dict[str, Any] = {
            "utc_time": now_utc_iso(),
            "kind": "monte_carlo",
            "strategy_name": "RandomStrategy",
            "params": {
                "prob_long": float(prob_long),
                "seed": int(seed),
                "metric": metric,
            },
            "metric_name": metric_name,
            "metric_value": float(np.asarray(scores, dtype=float).mean()),
            "n_bars": int(len(prices)),
            "n_trials": int(n_trials),
        }
        trial_log.log_trial(summary, path=log_path)
    return scores


def p_value(observed_metric: float, null_scores: Sequence[float]) -> float:
    """Fraction of null scores ``>=`` observed, with ``+1/+1`` smoothing.

    Higher score = better, so a SMALL p-value means the observed score sat out in the
    right tail (few coin-flips reached it) -- unlikely to be luck. The smoothing,
    ``(count_ge + 1) / (n + 1)``, keeps p strictly positive: even a score above every
    null draw returns ``1/(n+1)``, never a dishonest exactly-zero.
    """
    n = len(null_scores)
    if n == 0:
        raise ValueError("null_scores is empty; cannot compute a p-value")
    count_ge = sum(1 for s in null_scores if s >= observed_metric)
    return (count_ge + 1) / (n + 1)


def assess_strategy(
    strategy: Strategy,
    prices: pd.DataFrame,
    n_trials: int = 1000,
    alpha: float = 0.05,
    metric: str = "sharpe",
    seed: int = 0,
    log_path: str | None = trial_log.DEFAULT_TRIAL_LOG,
    **backtest_kwargs: Any,
) -> MonteCarloResult:
    """Assess ``strategy`` against a coin-flip null on ``prices``; return the verdict.

    Backtests the real ``strategy`` for its RISK-ADJUSTED ``metric``, builds the null
    distribution of the same metric from ``n_trials`` coin-flips over the same prices,
    then reports the p-value, the percentile-vs-null, and ``passed = p_value < alpha``.

    One ``kind='monte_carlo'`` summary (observed metric, p-value, verdict) is appended
    to ``log_path``; the null batch's own summary is suppressed so exactly one record
    is written per assessment. Pass ``log_path=None`` to disable.
    """
    metric_name = _metric_name(metric)
    internal_kwargs = {k: v for k, v in backtest_kwargs.items() if k != "log_path"}

    observed = _metric_value(
        run_backtest(strategy, prices, log_path=None, **internal_kwargs), metric
    )
    # Build the coin-flip null on the SAME prices; suppress its summary so this
    # assessment emits exactly one (richer) record below.
    null_scores = null_distribution(
        prices,
        n_trials=n_trials,
        prob_long=0.5,
        metric=metric,
        seed=seed,
        log_path=None,
        **internal_kwargs,
    )

    pv = p_value(observed, null_scores)
    null_arr = np.asarray(null_scores, dtype=float)
    null_mean = float(null_arr.mean())
    null_std = float(null_arr.std())
    percentile = float((null_arr < observed).mean() * 100.0)
    passed = pv < alpha

    if log_path is not None:
        summary: dict[str, Any] = {
            "utc_time": now_utc_iso(),
            "kind": "monte_carlo",
            "strategy_name": type(strategy).__name__,
            "params": {
                "alpha": float(alpha),
                "metric": metric,
                "seed": int(seed),
                "prob_long": 0.5,
                "null_mean": null_mean,
                "null_std": null_std,
                "p_value": pv,
                "percentile": percentile,
                "passed": passed,
            },
            "metric_name": metric_name,
            "metric_value": observed,
            "n_bars": int(len(prices)),
            "n_trials": int(n_trials),
        }
        trial_log.log_trial(summary, path=log_path)

    logger.info(
        "monte_carlo: strategy=%s observed=%.3f null_mean=%.3f p=%.4f passed=%s",
        type(strategy).__name__,
        observed,
        null_mean,
        pv,
        passed,
    )
    return MonteCarloResult(
        observed_metric=observed,
        null_mean=null_mean,
        null_std=null_std,
        p_value=pv,
        percentile=percentile,
        passed=passed,
        n_trials=n_trials,
    )
