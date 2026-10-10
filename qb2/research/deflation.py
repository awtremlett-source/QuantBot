"""Deflated Sharpe -- the penalty for having tried many things (S4).

PORTED, NOT IMPORTED, from v1's research/deflation.py (SHA-256 at copy time,
2026-10-10: f0d9d46d19909e02adb85008fad02b9db805c17fb3f40d92244478e59fa9e6a6).
The maths is unchanged (Bailey & Lopez de Prado): PSR is the probability the true
Sharpe beats a benchmark given the estimate's sampling error; SR0 is the expected
BEST per-bar Sharpe among N skill-free tries; DSR = PSR at SR0, and 0.95 passes.

What changed: N comes from qb2's OWN trial log (trial_log.count_selection_trials:
drills excluded), and ``var_trials`` -- the spread of Sharpe among skill-free
strategies on these bars -- is measured directly as the variance of the coin-flip
null, which is exactly that. All Sharpes here are PER BAR. No scipy (not a
pinned qb2 dependency): the normal curve is the standard library's NormalDist,
and skew / raw kurtosis are the same biased moment estimators scipy uses.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from statistics import NormalDist

import numpy as np

MIN_BARS = 30
PASS = 0.95
_EULER_GAMMA = float(np.euler_gamma)
_NORMAL = NormalDist()


def moments(returns: Sequence[float] | np.ndarray) -> tuple[float, float, float, int]:
    """(per-bar Sharpe, skew, RAW kurtosis, T). Refuses short or flat series."""
    arr = np.asarray(returns, dtype=float)
    if arr.ndim != 1 or len(arr) < MIN_BARS:
        raise ValueError(f"need at least {MIN_BARS} returns, got {arr.shape}")
    if not np.isfinite(arr).all():
        raise ValueError("returns contain NaN or infinite values")
    mean, std = float(arr.mean()), float(arr.std(ddof=1))
    if not math.isfinite(std) or std <= 1e-12 * max(1.0, abs(mean)):
        raise ValueError(f"returns have zero or non-finite std ({std!r})")
    centred = arr - mean
    m2, m3, m4 = (float((centred**k).mean()) for k in (2, 3, 4))
    return mean / std, m3 / m2**1.5, m4 / m2**2, len(arr)


def psr(returns: Sequence[float] | np.ndarray, sr_benchmark: float) -> float:
    sr, skew, kurt, t = moments(returns)
    var_term = 1.0 - skew * sr + ((kurt - 1.0) / 4.0) * sr**2
    if var_term <= 0.0:
        raise ValueError(f"pathological moments: variance term {var_term!r} <= 0")
    return _NORMAL.cdf((sr - sr_benchmark) * math.sqrt(t - 1.0) / math.sqrt(var_term))


def expected_max_sharpe(n_trials: int, var_trials: float) -> float:
    """SR0: the expected best per-bar Sharpe among ``n_trials`` skill-free tries."""
    if n_trials < 2:
        raise ValueError(f"n_trials must be >= 2, got {n_trials}")
    if var_trials <= 0.0:
        raise ValueError(f"var_trials must be > 0, got {var_trials!r}")
    hi = _NORMAL.inv_cdf(1.0 - 1.0 / n_trials)
    lo = _NORMAL.inv_cdf(1.0 - 1.0 / (n_trials * math.e))
    return math.sqrt(var_trials) * ((1.0 - _EULER_GAMMA) * hi + _EULER_GAMMA * lo)


def deflated_sharpe(returns: Sequence[float] | np.ndarray, n_trials: int,
                    var_trials: float) -> dict[str, float]:
    sr, skew, kurt, t = moments(returns)
    sr0 = expected_max_sharpe(n_trials, var_trials)
    return {"sr": sr, "skew": skew, "kurt": kurt, "T": float(t), "sr0": sr0,
            "n_trials": float(n_trials), "psr_at_0": psr(returns, 0.0),
            "dsr": psr(returns, sr0)}
