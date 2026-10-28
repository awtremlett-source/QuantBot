"""The combined model's two fixed fits and its walk-forward (QT-27 D1; register commit 6be96dad).

* CM-L (``ridge``): StandardScaler fit on the training fold only, then Ridge(alpha=1.0).
* CM-G (``gbt``): HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05,
  max_leaf_nodes=15, min_samples_leaf=50, l2_regularization=1.0, early_stopping=False,
  random_state=0); scikit-learn 1.8.0's defaults otherwise; no scaling.

No tuning, ever. Before each fit the targets are clipped at the TRAINING fold's own 1st and 99th
percentiles; predictions are used as they come.

Walk-forward (expanding): the first out-of-sample session t0 is the first session dated on or
after 2024-02-01 with at least 126 sessions holding training rows at or before position t0 - 2;
refit at t0 and every 21 sessions after it; the model for sessions [t_k, t_k+1) is fit only on
rows dated at or before position t_k - 2 (one session of embargo). ``train_last`` is that
boundary, kept as its own function so the red-first can move it. Each (market, session) is
predicted as its own batch -- the decision moment's -- because a matrix product's last binary
digit can depend on how many rows go through it together (QT-27: the look-ahead test, which
compares bytes, caught a 4e-19 difference between a 105-row and a 30-row batch).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor  # type: ignore[import-untyped]
from sklearn.linear_model import Ridge  # type: ignore[import-untyped]
from sklearn.pipeline import make_pipeline  # type: ignore[import-untyped]
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]

MODELS = ("ridge", "gbt")
CLIP = (1.0, 99.0)
OOS_FROM, OOS_END = date(2024, 2, 1), date(2026, 7, 10)
MIN_TRAIN_SESSIONS, REFIT_EVERY, EMBARGO = 126, 21, 1
GBT = {"max_iter": 200, "learning_rate": 0.05, "max_leaf_nodes": 15, "min_samples_leaf": 50,
       "l2_regularization": 1.0, "early_stopping": False, "random_state": 0}


def estimator(model: str) -> Any:
    """A fresh, unfitted copy of one registered model -- nothing else is accepted."""
    if model == "ridge":
        return make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    if model == "gbt":
        return HistGradientBoostingRegressor(**GBT)
    raise ValueError(f"model {model!r} is not registered (only {MODELS})")


@dataclass(frozen=True, slots=True)
class Fitted:
    model: str
    est: Any
    clip: tuple[float, float]
    rows: int


def fit(model: str, x: np.ndarray, y: np.ndarray) -> Fitted:
    """Clip at this fold's own percentiles, then fit -- on these rows and nothing else."""
    lo, hi = (float(v) for v in np.percentile(y, CLIP))
    est = estimator(model).fit(x, np.clip(y, lo, hi))
    return Fitted(model, est, (lo, hi), len(y))


def predict(fitted: Fitted, x: np.ndarray) -> np.ndarray:
    return np.asarray(fitted.est.predict(x), dtype=float)


@dataclass(frozen=True, slots=True)
class Block:
    first: int          # position of the block's first test session
    stop: int           # one past its last
    train_last: int     # the last session position its model may train on


def blocks(sessions: Sequence[date], trained: Sequence[bool], *, oos_from: date = OOS_FROM,
           oos_end: date = OOS_END, min_train: int = MIN_TRAIN_SESSIONS,
           every: int = REFIT_EVERY, embargo: int = EMBARGO) -> list[Block]:
    """The refit schedule over the arm's sessions (``trained``: the session holds training rows)."""
    held = np.cumsum(np.asarray(trained, dtype=int))
    gap = embargo + 1
    start = next((i for i, d in enumerate(sessions)
                  if d >= oos_from and i - gap >= 0 and held[i - gap] >= min_train), None)
    end = sum(1 for d in sessions if d <= oos_end)
    if start is None or start >= end:
        return []
    return [Block(k, min(k + every, end), k - gap) for k in range(start, end, every)]


def train_last(block: Block) -> int:
    """The fold boundary: the last session a block's model may see (QT-27 E3 moves it)."""
    return block.train_last


def walk_forward(rows: pd.DataFrame, model: str, columns: Sequence[str], sessions: Sequence[date],
                 plan: Sequence[Block]) -> tuple[pd.Series, list[dict[str, Any]]]:
    """Out-of-sample predictions for ``rows`` (``day``, ``target``, the columns), and each fit's record."""
    pos = rows["day"].map({d: i for i, d in enumerate(sessions)})
    preds = pd.Series(np.nan, index=rows.index, dtype=float)
    log: list[dict[str, Any]] = []
    cols = list(columns)
    for block in plan:
        last = train_last(block)
        train = rows[(pos <= last) & rows["target"].notna()]
        test = rows[(pos >= block.first) & (pos < block.stop)]
        if test.empty or train.empty:
            continue
        fitted = fit(model, train[cols].to_numpy(dtype=float), train["target"].to_numpy(dtype=float))
        for _, part in test.groupby([k for k in ("market", "day") if k in test.columns], sort=False):
            preds.loc[part.index] = predict(fitted, part[cols].to_numpy(dtype=float))
        log.append({"first": sessions[block.first], "last": sessions[block.stop - 1],
                    "train_last": sessions[last], "train_max_day": max(train["day"]),
                    "train_rows": len(train), "test_rows": len(test), "clip": fitted.clip})
    return preds, log
