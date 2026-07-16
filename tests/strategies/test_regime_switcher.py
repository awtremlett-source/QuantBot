"""Deterministic, fully-OFFLINE tests for the regime switcher.

The synthetic series are built from ALTERNATING returns (+amp, -amp, +amp, ...):
every 20-bar window then holds ten of each sign, so its mean is ~0 and its
population std is exactly the amplitude -- which makes RV20, the one-year
median, and therefore severity analytically known by hand:

* constant amplitude a for the whole series  -> severity == a/a == 1.0
* last 20 returns at amplitude 2a            -> final severity == 2a/a == 2.0
* dead-flat closes                           -> RV_med == 0 -> severity 0.0

Regime logic is probed through growing PREFIXES of one engineered path (decide
is a stateless replay, so ``decide(prices[:k])`` is the regime standing at bar
``k-1``) with constant stand-in sub-strategies isolating WHO was delegated to:
calm always answers 0.25, stressed always answers 0.75.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
import pytest
from numpy.typing import NDArray

from strategies.regime_switcher import (
    RegimeSwitcherStrategy,
    TunableRegimeSwitcher,
    severity_series,
)

_WARMUP = 273  # 252-bar median window + 20-bar RV window + 1 (the locked spec)


def _frame(closes: Sequence[float]) -> pd.DataFrame:
    """Build a CLEAN-shaped price frame (open == close; event_time ``t0000``...)."""
    values = [float(c) for c in closes]
    n = len(values)
    return pd.DataFrame(
        {
            "event_time": [f"t{i:04d}" for i in range(n)],
            "open": values,
            "high": [c + 1.0 for c in values],
            "low": [c - 1.0 for c in values],
            "close": values,
            "volume": [1_000_000] * n,
            "adj_close": values,
        }
    )


def _alternating_closes(amps: Sequence[float], start: float = 100.0) -> list[float]:
    """Closes whose return ``i`` has magnitude ``amps[i-1]``, alternating sign."""
    closes = [start]
    for i, amp in enumerate(amps, start=1):
        sign = 1.0 if i % 2 == 1 else -1.0
        closes.append(closes[-1] * (1.0 + sign * amp))
    return closes


def _severity(closes: Sequence[float]) -> NDArray[np.float64]:
    return severity_series(np.asarray(closes, dtype=float))


class _ConstantStrategy:
    """Stand-in sub-strategy: fixed answer, records every history length seen."""

    def __init__(self, value: float) -> None:
        self.value = value
        self.calls: list[int] = []

    def decide(self, history: pd.DataFrame) -> float:
        self.calls.append(len(history))
        return self.value


def _switcher(threshold: float = 1.5) -> tuple[
    RegimeSwitcherStrategy, _ConstantStrategy, _ConstantStrategy
]:
    calm = _ConstantStrategy(0.25)
    stressed = _ConstantStrategy(0.75)
    return (
        RegimeSwitcherStrategy(threshold=threshold, calm=calm, stressed=stressed),
        calm,
        stressed,
    )


# ------------------------------------------------------------------ severity

# 280 bars at amplitude 1%, then 20 bars at 2%: severity ends exactly at 2x.
_BASE_AMP = 0.01
_CALM_AMPS = [_BASE_AMP] * 279
_SPIKE_CLOSES = _alternating_closes(_CALM_AMPS + [2 * _BASE_AMP] * 20)


def test_severity_hand_check_normal_is_one_spike_is_two() -> None:
    sev = _severity(_SPIKE_CLOSES)
    assert len(sev) == len(_SPIKE_CLOSES) == 300
    # Undefined until bar 271 (20 returns for RV20, then 252 RV20s for the median).
    assert np.isnan(sev[:271]).all()
    # Constant-amplitude region: RV20 == its own median -> severity 1.0.
    assert sev[271] == pytest.approx(1.0, rel=1e-9)
    assert sev[279] == pytest.approx(1.0, rel=1e-9)
    # Final bar: last 20 returns all at 2a, median still a -> severity 2.0.
    assert sev[299] == pytest.approx(2.0, rel=1e-6)


def test_severity_flat_series_is_zero_not_nan() -> None:
    sev = _severity([100.0] * 300)
    # RV20 == 0 and RV_med == 0: the RV_med==0 rule pins severity at 0.0.
    assert np.all(sev[271:] == 0.0)
    assert np.isnan(sev[:271]).all()


# ----------------------------------------------------- hysteresis + delegation

# One engineered path, probed at 20-bar boundaries (threshold 1.5, exit 1.2):
#   bars   0..279  amplitude a     severity ~1.0      calm
#   bars 280..299  amplitude 2a    severity -> 2.0    crosses 1.5 -> STRESSED
#   bars 300..319  amplitude 1.3a  severity -> 1.3    in (1.2, 1.5) -> STAYS stressed
#   bars 320..339  amplitude a     severity -> 1.0    drops below 1.2 -> calm
_HYST_CLOSES = _alternating_closes(
    _CALM_AMPS
    + [2 * _BASE_AMP] * 20
    + [1.3 * _BASE_AMP] * 20
    + [_BASE_AMP] * 20
)


def test_hysteresis_enter_hold_between_bands_then_exit() -> None:
    strategy, _, _ = _switcher(threshold=1.5)
    assert strategy.decide(_frame(_HYST_CLOSES[:280])) == 0.25  # calm baseline
    assert strategy.decide(_frame(_HYST_CLOSES[:300])) == 0.75  # spike: stressed
    # Severity has fallen to ~1.3 -- BELOW the 1.5 entry line but above the
    # 0.8*1.5=1.2 exit line. Without hysteresis this bar would read calm.
    assert strategy.decide(_frame(_HYST_CLOSES[:320])) == 0.75
    assert strategy.decide(_frame(_HYST_CLOSES)) == 0.25  # below 1.2: calm again


def test_delegation_emits_exactly_the_active_substrategys_answer() -> None:
    calm_frame = _frame(_HYST_CLOSES[:280])
    stressed_frame = _frame(_HYST_CLOSES[:300])

    strategy, calm, stressed = _switcher(threshold=1.5)
    assert strategy.decide(calm_frame) == 0.25
    assert strategy.decide(stressed_frame) == 0.75
    # Both sub-signals are computed on the FULL history every call, as if each
    # strategy always ran -- the regime only picks whose answer is emitted.
    assert calm.calls == [280, 300]
    assert stressed.calls == [280, 300]


def test_warmup_returns_flat_without_consulting_substrategies() -> None:
    strategy, calm, stressed = _switcher(threshold=1.5)
    assert strategy.decide(_frame(_HYST_CLOSES[: _WARMUP - 1])) == 0.0
    assert calm.calls == [] and stressed.calls == []


def test_stateless_same_history_same_answer() -> None:
    strategy, _, _ = _switcher(threshold=1.5)
    stressed_frame = _frame(_HYST_CLOSES[:300])
    calm_frame = _frame(_HYST_CLOSES[:280])
    first = strategy.decide(stressed_frame)
    assert strategy.decide(calm_frame) == 0.25
    assert strategy.decide(stressed_frame) == first == 0.75


def test_constructor_rejects_bad_threshold() -> None:
    for bad in (0.0, -1.5):
        with pytest.raises(ValueError):
            RegimeSwitcherStrategy(threshold=bad)


# ------------------------------------------------------------------ tunable


def test_param_grid_is_exactly_three_thresholds() -> None:
    grid = TunableRegimeSwitcher().param_grid()
    assert grid == [{"threshold": 1.2}, {"threshold": 1.5}, {"threshold": 1.8}]


def test_build_returns_a_working_strategy_with_frozen_defaults() -> None:
    strategy = TunableRegimeSwitcher().build({"threshold": 1.5})
    # Below warmup the answer is flat regardless of the frozen sub-strategies.
    assert strategy.decide(_frame([100.0] * (_WARMUP - 1))) == 0.0
