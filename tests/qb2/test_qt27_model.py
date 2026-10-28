"""QT-27 D2: the two fixed models, their folds, fold-only scaling and clipping, determinism."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd
import pytest

from qb2.model import combined

COLS = ["a", "b", "c"]


def _rows(sessions: int = 300, per: int = 8, seed: int = 0) -> tuple[pd.DataFrame, list[date]]:
    rng = np.random.default_rng(seed)
    days = [date(2023, 12, 1) + timedelta(days=i) for i in range(sessions)]
    frame = pd.DataFrame({"day": [d for d in days for _ in range(per)]})
    for c in COLS:
        frame[c] = rng.normal(size=len(frame))
    frame["target"] = 0.002 * frame["a"] + rng.normal(0, 0.01, len(frame))
    frame.loc[frame.index % 13 == 0, "target"] = np.nan          # rows with no trade: no target
    return frame, days


def _violations(rows: pd.DataFrame, days: list[date], log: list[dict[str, Any]]) -> list[str]:
    pos = {d: i for i, d in enumerate(days)}
    return [f"block from {e['first']}: trained through {e['train_max_day']}" for e in log
            if pos[e["train_max_day"]] > pos[e["first"]] - 2]


def test_blocks_start_at_126_trained_sessions_not_before_the_date_and_refit_every_21() -> None:
    days = [date(2024, 1, 1) + timedelta(days=i) for i in range(400)]
    trained = [i >= 10 for i in range(400)]                         # rows from session 10 on
    out = combined.blocks(days, trained, oos_from=date(2024, 2, 1), oos_end=days[-1])
    first = out[0].first
    assert sum(trained[:first - 1]) >= 126 > sum(trained[:first - 2])
    assert all(b.first - a.first == 21 for a, b in zip(out, out[1:]))
    assert all(b.train_last == b.first - 2 for b in out) and out[-1].stop == len(days)
    late = combined.blocks(days, [True] * 400, oos_from=date(2024, 9, 1), oos_end=days[-1])
    assert days[late[0].first] == date(2024, 9, 1)


def test_every_model_was_fit_only_on_sessions_at_or_before_first_test_minus_two(
        monkeypatch: pytest.MonkeyPatch) -> None:
    rows, days = _rows()
    blocks = combined.blocks(days, [True] * len(days), oos_from=days[0], oos_end=days[-1])
    preds, log = combined.walk_forward(rows, "ridge", COLS, days, blocks)
    assert preds.notna().sum() > 0 and _violations(rows, days, log) == []
    monkeypatch.setattr(combined, "train_last", lambda block: block.first)   # a test session in training
    _, leaked = combined.walk_forward(rows, "ridge", COLS, days, blocks)
    assert _violations(rows, days, leaked) != []


@pytest.mark.parametrize("model", combined.MODELS)
def test_scaling_and_clipping_use_the_training_fold_only(model: str) -> None:
    rows, days = _rows()
    blocks = combined.blocks(days, [True] * len(days), oos_from=days[0], oos_end=days[-1])
    preds, log = combined.walk_forward(rows, model, COLS, days, blocks)
    block = blocks[2]
    pos = rows["day"].map({d: i for i, d in enumerate(days)})
    train = rows[(pos <= block.train_last) & rows["target"].notna()]
    test = rows[(pos >= block.first) & (pos < block.stop)]
    alone = combined.fit(model, train[COLS].to_numpy(float), train["target"].to_numpy(float))
    assert alone.clip == tuple(np.percentile(train["target"].to_numpy(float), [1.0, 99.0]))
    assert log[2]["clip"] == alone.clip and log[2]["train_rows"] == len(train)
    if model == "ridge":
        assert np.allclose(alone.est[0].mean_, train[COLS].to_numpy(float).mean(axis=0), rtol=0, atol=1e-12)
    for _, part in test.groupby("day"):                  # one batch per session, as walk_forward does
        assert np.array_equal(preds.loc[part.index].to_numpy(), combined.predict(alone, part[COLS].to_numpy(float)))


def test_two_runs_of_one_fold_give_identical_predictions() -> None:
    rows, days = _rows(seed=5)
    blocks = combined.blocks(days, [True] * len(days), oos_from=days[0], oos_end=days[-1])[:2]
    first, _ = combined.walk_forward(rows, "gbt", COLS, days, blocks)
    second, _ = combined.walk_forward(rows, "gbt", COLS, days, blocks)
    assert first.notna().sum() > 0 and np.array_equal(first.to_numpy(), second.to_numpy(), equal_nan=True)


def test_the_settings_are_the_registered_ones_and_nothing_else_is_accepted() -> None:
    ridge, gbt = combined.estimator("ridge"), combined.estimator("gbt")
    assert ridge.steps[1][1].alpha == 1.0
    p = gbt.get_params()
    assert (p["max_iter"], p["learning_rate"], p["max_leaf_nodes"], p["min_samples_leaf"],
            p["l2_regularization"], p["early_stopping"], p["random_state"]) == (200, 0.05, 15, 50, 1.0, False, 0)
    with pytest.raises(ValueError):
        combined.estimator("lasso")
