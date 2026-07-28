"""Tests for research.deflation -- the Deflated Sharpe machinery (rubric 2)."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from scipy import stats

from research.deflation import (
    count_selection_trials,
    deflated_sharpe,
    expected_max_sharpe,
    moments,
    psr,
)

# A fixed, slightly-skewed returns sample (seeded once; values are then frozen by
# the seed, so every assertion below is deterministic).
_RNG = np.random.default_rng(42)
_SAMPLE = _RNG.normal(0.0005, 0.01, 500)


# ---------------------------------------------------------------- moments


def test_moments_match_scipy_and_hand_values() -> None:
    sr, skew, kurt = moments(_SAMPLE)
    assert sr == pytest.approx(_SAMPLE.mean() / _SAMPLE.std(ddof=1))
    assert skew == pytest.approx(float(stats.skew(_SAMPLE)))
    assert kurt == pytest.approx(float(stats.kurtosis(_SAMPLE, fisher=False)))
    # Raw (Pearson) kurtosis: a normal sample sits near 3, never near 0.
    assert 2.0 < kurt < 4.0


def test_moments_rejects_short_series() -> None:
    with pytest.raises(ValueError, match="at least 30"):
        moments([0.01] * 29)


def test_moments_rejects_zero_std() -> None:
    with pytest.raises(ValueError, match="zero or non-finite std"):
        moments([0.01] * 100)


def test_moments_rejects_nan() -> None:
    bad = _SAMPLE.copy()
    bad[10] = math.nan
    with pytest.raises(ValueError, match="NaN or infinite"):
        moments(bad)


# ---------------------------------------------------------------- psr


def test_psr_of_exactly_zero_mean_noise_is_half() -> None:
    # De-mean the sample so its per-bar Sharpe is exactly 0: the probability its
    # true Sharpe exceeds the 0 benchmark must then be exactly Phi(0) = 0.5.
    centered = _SAMPLE - _SAMPLE.mean()
    assert psr(centered, 0.0) == pytest.approx(0.5)


def test_psr_increases_with_track_length_for_fixed_positive_sr() -> None:
    # Tiling repeats the identical distribution, so sr/skew/kurt are (near)
    # unchanged while T grows -- confidence must rise with the longer record.
    short = _SAMPLE
    long = np.tile(_SAMPLE, 4)
    assert moments(short)[0] > 0.0
    assert psr(long, 0.0) > psr(short, 0.0)


def test_psr_rejects_pathological_moments(monkeypatch: pytest.MonkeyPatch) -> None:
    # For genuine data the variance term is bounded below by (1 - skew*sr/2)^2
    # >= 0 (Pearson's kurt >= 1 + skew^2), so the guard can only fire on
    # degenerate/injected moments -- inject them to prove the raise happens.
    import research.deflation as deflation

    # var_term = 1 - 3*1 + ((3-1)/4)*1 = -1.5
    monkeypatch.setattr(deflation, "moments", lambda r: (1.0, 3.0, 3.0))
    with pytest.raises(ValueError, match="pathological moments"):
        deflation.psr(_SAMPLE, 0.0)


# ---------------------------------------------------------------- expected_max_sharpe


def test_expected_max_sharpe_spot_value() -> None:
    # Hand-checked at n=100, var=1: (1-g)*PhiInv(0.99) + g*PhiInv(1 - 1/(100e))
    # = 0.42278*2.32635 + 0.57722*2.68021 = 2.5306 (verified against scipy).
    assert expected_max_sharpe(100, 1.0) == pytest.approx(2.5306, abs=1e-3)


def test_expected_max_sharpe_monotonic_in_trials_and_variance() -> None:
    assert expected_max_sharpe(1000, 1.0) > expected_max_sharpe(100, 1.0)
    assert expected_max_sharpe(100, 2.0) > expected_max_sharpe(100, 1.0)
    # Variance enters as sqrt: 4x the variance = exactly 2x the ceiling.
    assert expected_max_sharpe(100, 4.0) == pytest.approx(
        2.0 * expected_max_sharpe(100, 1.0)
    )


def test_expected_max_sharpe_rejects_bad_inputs() -> None:
    with pytest.raises(ValueError, match="n_trials"):
        expected_max_sharpe(1, 1.0)
    with pytest.raises(ValueError, match="var_trials"):
        expected_max_sharpe(100, 0.0)


# ---------------------------------------------------------------- deflated_sharpe


def test_deflated_sharpe_shrinks_as_trials_grow() -> None:
    var_trials = 1e-4
    d10 = deflated_sharpe(_SAMPLE, 10, var_trials)
    d100 = deflated_sharpe(_SAMPLE, 100, var_trials)
    d1000 = deflated_sharpe(_SAMPLE, 1000, var_trials)
    # The luck ceiling rises with N...
    assert d10["sr0"] < d100["sr0"] < d1000["sr0"]
    # ...so the deflated verdict strictly falls, and never exceeds PSR@0.
    assert d10["dsr"] > d100["dsr"] > d1000["dsr"]
    assert d1000["dsr"] < d1000["psr_at_0"]
    # T and the undeflated PSR are N-independent.
    assert d10["T"] == len(_SAMPLE)
    assert d10["psr_at_0"] == pytest.approx(d1000["psr_at_0"])


# ---------------------------------------------------------------- count_selection_trials


def _write_log(path: Path, records: list[dict[str, Any]]) -> str:
    with open(path, "w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record) + "\n")
    return str(path)


def test_count_selection_trials_policy_branches(tmp_path: Path) -> None:
    base = {
        "utc_time": "2026-01-01T00:00:00Z",
        "strategy_name": "X",
        "metric_name": "m",
        "metric_value": 0.0,
        "n_bars": 100,
    }
    log = _write_log(
        tmp_path / "trials.jsonl",
        [
            # counted: 45 + 27 grid combinations
            {**base, "kind": "walk_forward", "params": {"total_trials": 45}},
            {**base, "kind": "walk_forward", "params": {"total_trials": 27}},
            # counted: 1 each
            {**base, "kind": "backtest", "params": {}},
            {**base, "kind": "backtest", "params": {"slippage_pct": 0.0005}},
            # excluded: the measuring stick
            {**base, "kind": "monte_carlo", "params": {"alpha": 0.05}},
            # excluded: cross-ticker tapes, REGARDLESS of kind
            {
                **base,
                "kind": "backtest",
                "params": {"context": "cross_ticker_generalization"},
            },
            {
                **base,
                "kind": "monte_carlo",
                "params": {"context": "cross_ticker_generalization"},
            },
        ],
    )
    n, breakdown = count_selection_trials(log)
    assert n == 45 + 27 + 2
    assert breakdown == {
        "walk_forward_records": 2,
        "walk_forward_trials": 72,
        "backtest_records": 2,
        "monte_carlo_records_excluded": 1,
        "cross_ticker_records_excluded": 2,
    }


def test_count_selection_trials_empty_log(tmp_path: Path) -> None:
    n, breakdown = count_selection_trials(str(tmp_path / "absent.jsonl"))
    assert n == 0
    assert breakdown["walk_forward_trials"] == 0


def test_count_selection_trials_rejects_unknown_kind(tmp_path: Path) -> None:
    log = _write_log(
        tmp_path / "trials.jsonl",
        [{"kind": "mystery", "params": {}}],
    )
    with pytest.raises(ValueError, match="unknown trial kind"):
        count_selection_trials(log)
