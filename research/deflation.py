"""Deflated Sharpe -- the formal multiple-testing penalty (§7; graduation rubric 2).

The trial log records every time we pulled the slot-machine lever (every backtest
and every walk-forward grid combination). With enough tries, the BEST result looks
good by pure luck: the expected maximum Sharpe among N noise strategies grows like
sqrt(V * 2 ln N). The Deflated Sharpe Ratio (Bailey & Lopez de Prado) penalises a
result by that luck ceiling: instead of asking "is the Sharpe above zero?" it asks
"is the Sharpe above what the LUCKIEST of our N tries would have shown by chance?".

Pieces, in order:

* :func:`moments` -- per-bar Sharpe (mean/std, ddof=1) plus skewness and raw
  kurtosis of the returns. Everything downstream is built on these.
* :func:`psr` -- the Probabilistic Sharpe Ratio: the probability that the TRUE
  Sharpe exceeds a benchmark, given the estimate's sampling error (which widens
  with skew/fat tails and narrows with track length T).
* :func:`expected_max_sharpe` -- the luck ceiling SR0: the expected best per-bar
  Sharpe among ``n_trials`` skill-free strategies whose Sharpe estimates have
  variance ``var_trials``.
* :func:`deflated_sharpe` -- DSR = PSR evaluated at SR0. DSR >= 0.95 means the
  record is unlikely (at 5%) to be the product of our own multiple testing.
* :func:`count_selection_trials` -- the honest N, read from the append-only log.

UNITS: every Sharpe in this module is PER-BAR (daily bars here), NOT annualized --
the PSR formula's ``sqrt(T - 1)`` scaling assumes per-bar units. Annualize only
for display (multiply by ``sqrt(252)``).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any, TypeAlias

import numpy as np
from numpy.typing import NDArray

import pandas as pd
from scipy import stats

from research import trial_log

# Fewer bars than this and the third/fourth moments are noise dressed as numbers.
_MIN_BARS = 30

# Euler-Mascheroni constant, used by the expected-maximum formula.
_EULER_GAMMA = float(np.euler_gamma)

# Trial-log records carrying this context tag are OTHER TICKERS' tapes (the
# cross-ticker generalization test). They are excluded from the NVDA deflation
# count and will be counted when cross-ticker claims are themselves deflated.
_CROSS_TICKER_CONTEXT = "cross_ticker_generalization"

ReturnsLike: TypeAlias = Sequence[float] | NDArray[np.float64] | pd.Series


def _as_returns_array(returns: ReturnsLike) -> NDArray[np.float64]:
    """Validate and convert a returns input to a 1-D float array."""
    arr = np.asarray(returns, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"returns must be 1-dimensional, got shape {arr.shape}")
    if len(arr) < _MIN_BARS:
        raise ValueError(
            f"need at least {_MIN_BARS} returns for stable moments, got {len(arr)}"
        )
    if not np.isfinite(arr).all():
        raise ValueError("returns contain NaN or infinite values")
    return arr


def moments(returns: ReturnsLike) -> tuple[float, float, float]:
    """Per-bar Sharpe, skewness, and RAW kurtosis of ``returns``.

    ``sr`` is ``mean / std`` with ``ddof=1`` and is NON-annualized (per-bar).
    ``skew`` is :func:`scipy.stats.skew`; ``kurt`` is raw (Pearson) kurtosis,
    :func:`scipy.stats.kurtosis` with ``fisher=False``, so a normal distribution
    scores 3.0. Raises on fewer than 30 returns or a zero/non-finite std -- a
    flat series has no defined Sharpe and must fail loudly, not return 0.
    """
    arr = _as_returns_array(returns)
    mean = float(arr.mean())
    std = float(arr.std(ddof=1))
    # A constant series leaves float dust (~1e-18), not an exact 0 -- compare
    # against a tolerance relative to the mean's magnitude, never against 0.0.
    if not math.isfinite(std) or std <= 1e-12 * max(1.0, abs(mean)):
        raise ValueError(f"returns have zero or non-finite std ({std!r})")
    sr = mean / std
    skew = float(stats.skew(arr))
    kurt = float(stats.kurtosis(arr, fisher=False))
    return sr, skew, kurt


def psr(returns: ReturnsLike, sr_benchmark: float) -> float:
    """Probabilistic Sharpe Ratio: P(true Sharpe > ``sr_benchmark``).

    ``Phi( (sr - sr*) * sqrt(T - 1) / sqrt(1 - skew*sr + ((kurt-1)/4) * sr^2) )``
    where ``sr*`` is the benchmark and T the number of returns. The denominator
    is the sampling error of a Sharpe ESTIMATE: negative skew and fat tails
    (kurt > 3) widen it, long records (the sqrt(T-1)) shrink it. All Sharpe
    units are per-bar. Raises if the variance expression is non-positive
    (pathological moments -- the normal approximation has broken down).
    """
    sr, skew, kurt = moments(returns)
    t = len(_as_returns_array(returns))
    var_term = 1.0 - skew * sr + ((kurt - 1.0) / 4.0) * sr**2
    if var_term <= 0.0:
        raise ValueError(
            f"pathological moments: sampling-variance term {var_term!r} <= 0 "
            f"(sr={sr!r}, skew={skew!r}, kurt={kurt!r})"
        )
    z = (sr - sr_benchmark) * math.sqrt(t - 1.0) / math.sqrt(var_term)
    return float(stats.norm.cdf(z))


def expected_max_sharpe(n_trials: int, var_trials: float) -> float:
    """The luck ceiling SR0: expected MAX per-bar Sharpe among skill-free trials.

    ``sqrt(var_trials) * ((1-g) * PhiInv(1 - 1/N) + g * PhiInv(1 - 1/(N*e)))``
    with g the Euler-Mascheroni constant -- the expected maximum of N draws from
    a zero-mean normal with variance ``var_trials`` (Bailey & Lopez de Prado's
    approximation). Grows with BOTH the number of trials and the spread of trial
    outcomes: more tries, or noisier tries, raise the bar a real record must clear.
    """
    if n_trials < 2:
        raise ValueError(f"n_trials must be >= 2, got {n_trials}")
    if var_trials <= 0.0:
        raise ValueError(f"var_trials must be > 0, got {var_trials!r}")
    g = _EULER_GAMMA
    hi = float(stats.norm.ppf(1.0 - 1.0 / n_trials))
    lo = float(stats.norm.ppf(1.0 - 1.0 / (n_trials * math.e)))
    return math.sqrt(var_trials) * ((1.0 - g) * hi + g * lo)


def deflated_sharpe(
    returns: ReturnsLike, n_trials: int, var_trials: float
) -> dict[str, float]:
    """Deflated Sharpe verdict for one track record against N logged trials.

    Returns a dict of per-bar figures: ``sr``/``skew``/``kurt``/``T`` (the
    moments), ``sr0`` (the luck ceiling from :func:`expected_max_sharpe`),
    ``psr_at_0`` (P(true Sharpe > 0) -- the UNdeflated question), and ``dsr``
    (P(true Sharpe > SR0) -- the deflated one). ``dsr >= 0.95`` is the pass bar.
    """
    sr, skew, kurt = moments(returns)
    sr0 = expected_max_sharpe(n_trials, var_trials)
    return {
        "sr": sr,
        "skew": skew,
        "kurt": kurt,
        "T": float(len(_as_returns_array(returns))),
        "sr0": sr0,
        "psr_at_0": psr(returns, 0.0),
        "dsr": psr(returns, sr0),
    }


def count_selection_trials(
    log_path: str = trial_log.DEFAULT_TRIAL_LOG,
) -> tuple[int, dict[str, int]]:
    """The honest N for deflation, from the append-only trial log.

    POLICY (what counts as a SELECTION trial -- a lever pull that could have
    influenced which strategy we kept):

    * ``kind == 'walk_forward'``: contributes ``params['total_trials']`` -- every
      grid combination tried across every fold was a chance to get lucky.
    * ``kind == 'backtest'``: contributes 1 -- each standalone backtest was a look.
    * ``kind == 'monte_carlo'``: contributes 0 -- the null batches are the
      measuring stick pointed at a result we already had, not new tries.
    * Records whose ``params.context == 'cross_ticker_generalization'``:
      contribute 0 REGARDLESS of kind -- they are other tickers' tapes, and will
      be counted when cross-ticker claims are deflated, not NVDA's.

    Returns ``(n, breakdown)`` where ``breakdown`` reports what was counted and
    what was excluded, so the tally can be audited line by line.
    """
    breakdown = {
        "walk_forward_records": 0,
        "walk_forward_trials": 0,
        "backtest_records": 0,
        "monte_carlo_records_excluded": 0,
        "cross_ticker_records_excluded": 0,
    }
    for record in trial_log.read_trials(log_path):
        params: dict[str, Any] = record.get("params") or {}
        if params.get("context") == _CROSS_TICKER_CONTEXT:
            breakdown["cross_ticker_records_excluded"] += 1
            continue
        kind = record.get("kind")
        if kind == "walk_forward":
            breakdown["walk_forward_records"] += 1
            breakdown["walk_forward_trials"] += int(params["total_trials"])
        elif kind == "backtest":
            breakdown["backtest_records"] += 1
        elif kind == "monte_carlo":
            breakdown["monte_carlo_records_excluded"] += 1
        else:
            raise ValueError(f"unknown trial kind {kind!r} in {log_path}")
    n = breakdown["walk_forward_trials"] + breakdown["backtest_records"]
    return n, breakdown
