"""Deterministic, fully-OFFLINE tests for the Monte-Carlo known-null gate.

All price data is synthetic, injected as DataFrames -- no DB, no network. This file
IS the firewall's birth certificate: it proves the gate rejects worthless strategies
(a coin-flip, a do-nothing FlatStrategy) AND that it does not reject everything (a
strategy that mechanically harvests a deterministic pattern passes). If the coin-flip
known-null ever passes, the firewall is broken -- see
``test_coin_flip_known_null_does_not_pass``.

Sizes are kept small for speed; the logic under test does not need thousands of trials.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research.monte_carlo import (
    MonteCarloResult,
    RandomStrategy,
    assess_strategy,
    null_distribution,
    p_value,
)
from research.strategy import FlatStrategy

# Test sizing: small enough to be fast, large enough for a stable null.
_N_BARS = 160
_N_TRIALS = 200
_ALPHA = 0.05
# The null's base seed and the observed coin-flip's seed are deliberately DIFFERENT,
# so the strategy under test is not one of the null draws (that would be circular).
_NULL_SEED = 0
_OBSERVED_SEED = 4242


def _frame(opens: Sequence[float], closes: Sequence[float]) -> pd.DataFrame:
    """Build a CLEAN-shaped price frame; event_time position == index (``t00000``...)."""
    n = len(opens)
    assert len(closes) == n
    return pd.DataFrame(
        {
            "event_time": [f"t{i:05d}" for i in range(n)],
            "open": [float(o) for o in opens],
            "high": [float(max(o, c)) + 1.0 for o, c in zip(opens, closes)],
            "low": [float(min(o, c)) - 1.0 for o, c in zip(opens, closes)],
            "close": [float(c) for c in closes],
            "volume": [1_000_000] * n,
            "adj_close": [float(c) for c in closes],
        }
    )


def _random_walk(n: int, seed: int) -> pd.DataFrame:
    """A driftless random walk: no exploitable structure, so null Sharpes straddle 0."""
    rng = np.random.default_rng(seed)
    steps = rng.normal(0.0, 1.0, size=n)
    closes = np.maximum(100.0 + np.cumsum(steps), 1.0)
    opens = np.concatenate([[100.0], closes[:-1]])  # gapless: open == prior close
    return _frame(opens.tolist(), closes.tolist())


def _alternating(n: int) -> pd.DataFrame:
    """A deterministic, obviously-exploitable cycle.

    Even-indexed bars gain intrabar (+5% open->close); odd-indexed bars lose (-2%).
    Gapless (open == prior close), so the ONLY way to profit is to be long during the
    even 'up' bars and flat during the odd 'down' bars -- exactly what
    :class:`_CycleHarvester` does.
    """
    opens: list[float] = []
    closes: list[float] = []
    price = 100.0
    for i in range(n):
        opens.append(price)
        price = price * 1.05 if i % 2 == 0 else price * 0.98
        closes.append(price)
    return _frame(opens, closes)


class _CycleHarvester:
    """Long only when the NEXT bar is an even (up) bar; flat otherwise.

    ``decide`` on bar i sets the weight for bar index ``len(history)`` (== i+1), which
    the backtester fills at that bar's open. Long iff that bar is even -> harvests every
    up bar, sits out every down bar. A trivial exploit of :func:`_alternating`.
    """

    def decide(self, history: pd.DataFrame) -> float:
        next_index = len(history)
        return 1.0 if next_index % 2 == 0 else 0.0


def test_p_value_smoothing_edges() -> None:
    null = [0.0, 1.0, 2.0, 3.0]

    # Observed above every null score -> p at the smoothing floor 1/(n+1), never 0.
    assert p_value(9.0, null) == pytest.approx(1 / 5)
    # Observed below all null scores -> p near 1.0 == (n+1)/(n+1).
    assert p_value(-1.0, null) == pytest.approx(1.0)
    # Ties count as ">=" (2.0 and 3.0 both clear an observed of 2.0).
    assert p_value(2.0, null) == pytest.approx((2 + 1) / 5)


def test_null_distribution_is_deterministic_given_seed() -> None:
    prices = _random_walk(_N_BARS, seed=1)

    d1 = null_distribution(prices, n_trials=40, seed=7, log_path=None)
    d2 = null_distribution(prices, n_trials=40, seed=7, log_path=None)
    d3 = null_distribution(prices, n_trials=40, seed=8, log_path=None)

    assert d1 == d2  # same seed -> identical null distribution
    assert p_value(0.5, d1) == p_value(0.5, d2)  # ...and identical p-value
    assert d1 != d3  # a different seed genuinely changes the draws


def test_coin_flip_known_null_does_not_pass() -> None:
    # BIRTH CERTIFICATE. A coin-flip has NO edge, so the firewall MUST call it luck.
    # If this ever asserts passed is True, the firewall is BROKEN: it would be
    # rubber-stamping pure noise as signal, and nothing downstream could be trusted.
    prices = _random_walk(_N_BARS, seed=3)
    coin_flip = RandomStrategy(prob_long=0.5, seed=_OBSERVED_SEED)  # != null seed

    result = assess_strategy(
        coin_flip,
        prices,
        n_trials=_N_TRIALS,
        alpha=_ALPHA,
        seed=_NULL_SEED,
        log_path=None,
    )

    assert isinstance(result, MonteCarloResult)
    assert result.passed is False
    # Not merely failing -- comfortably indistinguishable from luck.
    assert result.p_value > _ALPHA
    assert result.p_value > 0.1


def test_flat_strategy_does_not_pass() -> None:
    # A do-nothing strategy has Sharpe 0 and no edge -> must not pass.
    prices = _random_walk(_N_BARS, seed=3)

    result = assess_strategy(
        FlatStrategy(),
        prices,
        n_trials=_N_TRIALS,
        alpha=_ALPHA,
        seed=_NULL_SEED,
        log_path=None,
    )

    assert result.observed_metric == 0.0
    assert result.passed is False
    assert result.p_value > _ALPHA


def test_exploitable_pattern_does_pass() -> None:
    # SANITY, the other direction: a mechanically-exploitable deterministic pattern,
    # harvested by a trivial strategy, MUST clear the firewall -- otherwise the gate
    # rejects everything and is useless.
    prices = _alternating(_N_BARS)

    result = assess_strategy(
        _CycleHarvester(),
        prices,
        n_trials=_N_TRIALS,
        alpha=_ALPHA,
        seed=_NULL_SEED,
        log_path=None,
    )

    assert result.passed is True
    assert result.p_value < _ALPHA
    assert result.observed_metric > result.null_mean  # beats the coin-flip null
    assert result.percentile > 90.0  # sits far out in the right tail


def test_assess_strategy_logs_one_monte_carlo_trial(tmp_path: Path) -> None:
    from research.trial_log import read_trials

    prices = _random_walk(80, seed=2)
    path = str(tmp_path / "trials.jsonl")

    assess_strategy(
        RandomStrategy(0.5, seed=5), prices, n_trials=30, seed=0, log_path=path
    )

    records = read_trials(path)
    assert len(records) == 1  # the null batch's own summary is suppressed
    assert records[0]["kind"] == "monte_carlo"
    assert records[0]["n_trials"] == 30
    assert records[0]["metric_name"] == "annualized_sharpe_net"
