"""The coin-flip null: what does pure luck score on these same bars? (S4)

PORTED, NOT IMPORTED, from v1's research/monte_carlo.py (SHA-256 at copy time,
2026-10-10: eb4c1677be68498ab1ac45234ae6926e16db56a6d40ee05ad250942f3586ede7).
Same principles: a seeded coin-flip strategy run many times over the SAME bars
under the SAME costs and delay; the real result placed in that distribution;
judged on the risk-adjusted (per-bar Sharpe) figure, never raw return; the p-value
smoothed so it is never a dishonest zero.

What moved: running the null through the whole candidate pipeline (every name,
bet groups, walk-forward OOS windows) is the firewall's job (firewall.py), so the
null sees exactly what the candidate saw. This file keeps the pieces.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

DEFAULT_TRIALS = 200             # STARTING FIGURE: enough for p down to 1/201
ALPHA = 0.05


class RandomStrategy:
    """Long or flat at random each bar, ignoring the market. Seeded, so a fresh
    instance replays the same draws -- and a shorter series gets the same prefix,
    which is what lets it pass the look-ahead check honestly."""

    def __init__(self, prob_long: float, seed: int) -> None:
        if not 0.0 <= prob_long <= 1.0:
            raise ValueError(f"prob_long must be in [0, 1], got {prob_long!r}")
        self.prob_long = float(prob_long)
        self.seed = int(seed)
        self.name = f"coin_flip(p={prob_long:g},seed={seed})"

    def weights(self, bars: pd.DataFrame) -> pd.Series:
        draws = np.random.default_rng(self.seed).random(len(bars))
        return pd.Series((draws < self.prob_long).astype(float), index=bars.index)


def trial_seeds(seed: int, n_trials: int) -> list[int]:
    """Decorrelated child seeds, fully determined by ``seed`` (SeedSequence)."""
    if n_trials < 1:
        raise ValueError(f"n_trials must be >= 1, got {n_trials}")
    return [int(x) for x in np.random.SeedSequence(seed).generate_state(n_trials).tolist()]


def p_value(observed: float, null_scores: Sequence[float]) -> float:
    """(count of null >= observed + 1) / (n + 1): small = out in the right tail."""
    if not null_scores:
        raise ValueError("null_scores is empty; cannot compute a p-value")
    count = sum(1 for s in null_scores if s >= observed)
    return (count + 1) / (len(null_scores) + 1)


def percentile(observed: float, null_scores: Sequence[float]) -> float:
    return float((np.asarray(null_scores, dtype=float) < observed).mean() * 100.0)
