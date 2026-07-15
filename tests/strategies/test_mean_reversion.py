"""Deterministic, fully-OFFLINE tests for the mean-reversion challenger.

All price data is synthetic DataFrames -- no DB, no network. The RSI checks are
HAND-COMPUTED (Cutler's variant: simple averages over the window, so a human can
redo every number below with a pencil -- that is why the variant was chosen).

Strategy behaviour is probed through ``decide`` on growing prefixes of one price
path: because ``decide`` is a stateless full replay, ``decide(prices[:k])`` IS
the position standing at bar ``k-1``, so a sequence of prefix calls traces the
enter/hold/exit path without touching any internals.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
import pytest
from numpy.typing import NDArray

from strategies.mean_reversion import (
    MeanReversionStrategy,
    TunableMeanReversion,
    cutler_rsi,
)


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


def _rsi(closes: Sequence[float], period: int) -> NDArray[np.float64]:
    return cutler_rsi(np.asarray(closes, dtype=float), period)


# ---------------------------------------------------------------- Cutler RSI


def test_rsi_hand_computed_values() -> None:
    # closes -> diffs [1, 2, -1, 3]
    rsi = _rsi([100.0, 101.0, 103.0, 102.0, 105.0], period=3)
    # Warmup: needs period+1 closes, so the first defined value is at index 3.
    assert np.isnan(rsi[:3]).all()
    # rsi[3]: diffs [1, 2, -1] -> gains mean 1.0, losses mean 1/3, RS = 3
    #   -> 100 - 100/4 = 75.
    assert rsi[3] == pytest.approx(75.0)
    # rsi[4]: diffs [2, -1, 3] -> gains mean 5/3, losses mean 1/3, RS = 5
    #   -> 100 - 100/6 = 83.333...
    assert rsi[4] == pytest.approx(100.0 - 100.0 / 6.0)


def test_rsi_hand_computed_period_two() -> None:
    rsi = _rsi([100.0, 101.0, 103.0, 102.0, 105.0], period=2)
    assert rsi[2] == pytest.approx(100.0)  # diffs [1, 2]: no losses -> 100
    # rsi[3]: diffs [2, -1] -> gains mean 1.0, losses mean 0.5, RS = 2
    #   -> 100 - 100/3 = 66.667
    assert rsi[3] == pytest.approx(100.0 - 100.0 / 3.0)
    # rsi[4]: diffs [-1, 3] -> gains mean 1.5, losses mean 0.5, RS = 3 -> 75.
    assert rsi[4] == pytest.approx(75.0)


def test_rsi_all_gains_is_100_all_losses_is_0() -> None:
    up = _rsi([1.0, 2.0, 3.0, 4.0, 5.0], period=2)
    assert np.all(up[2:] == 100.0)
    down = _rsi([5.0, 4.0, 3.0, 2.0, 1.0], period=2)
    assert np.all(down[2:] == 0.0)


def test_rsi_flat_window_reads_100_by_edge_rule_order() -> None:
    # Both means are zero; the mean(losses)==0 rule is checked FIRST -> 100
    # (overbought-ish: a dead-flat market is never a buy signal).
    flat = _rsi([7.0, 7.0, 7.0, 7.0], period=2)
    assert np.all(flat[2:] == 100.0)


def test_rsi_rejects_bad_period() -> None:
    with pytest.raises(ValueError):
        _rsi([1.0, 2.0], period=0)


def test_rsi_too_short_series_is_all_nan() -> None:
    assert np.isnan(_rsi([1.0, 2.0], period=3)).all()


# ------------------------------------------------------- strategy behaviour
# All behaviour tests use small windows so every number is hand-checkable:
# rsi_period=2, entry 30, exit 70, trend_lookback=4 -> warmup = max(4, 3) = 4.


def _strategy() -> MeanReversionStrategy:
    return MeanReversionStrategy(
        rsi_period=2, entry_threshold=30.0, exit_threshold=70.0, trend_lookback=4
    )


def test_warmup_returns_flat() -> None:
    # 3 bars < warmup 4 -> 0.0 no matter how tradeable the shape looks.
    assert _strategy().decide(_frame([100.0, 90.0, 80.0])) == 0.0


def test_below_trend_stays_flat_even_when_oversold() -> None:
    # Straight decline: RSI(2) is 0 (maximally oversold) at every decidable bar,
    # but the close sits below SMA-4 throughout -> the trend filter vetoes entry.
    frame = _frame([130.0, 120.0, 110.0, 100.0, 90.0, 80.0])
    assert _strategy().decide(frame) == 0.0


def test_oversold_above_trend_enters() -> None:
    # Uptrend, then a two-bar dip that stays above SMA-4:
    #   t=5: SMA4 = (120+130+127+126)/4 = 125.75 < close 126 (trend ok) and
    #   diffs [-3, -1] -> RSI 0 < entry 30 -> enter.
    frame = _frame([100.0, 110.0, 120.0, 130.0, 127.0, 126.0])
    assert _strategy().decide(frame) == 1.0


# One engineered path traces the full enter -> hold -> exit hysteresis:
#   bar 4 (close 396): SMA4 323.5 ok; diffs [-2,-2] -> RSI 0    -> ENTER
#   bar 5 (close 400): SMA4 398.5 ok; diffs [-2,+4] -> RSI 66.7 -> HOLD (30<RSI<70)
#   bar 6 (close 410): SMA4 401   ok; diffs [+4,+10] -> RSI 100 -> EXIT (>70)
_HYSTERESIS_CLOSES = [100.0, 100.0, 400.0, 398.0, 396.0, 400.0, 410.0]


def test_hysteresis_enter_hold_exit() -> None:
    strategy = _strategy()
    closes = _HYSTERESIS_CLOSES
    assert strategy.decide(_frame(closes[:4])) == 0.0  # before the dip: flat
    assert strategy.decide(_frame(closes[:5])) == 1.0  # oversold dip: enter
    assert strategy.decide(_frame(closes[:6])) == 1.0  # RSI 66.7: hold the band
    assert strategy.decide(_frame(closes[:7])) == 0.0  # RSI 100 > exit: out


def test_trend_break_exits_mid_position() -> None:
    # Same entry as above, then a crash bar: close 200 < SMA4 348.5. RSI reads 0
    # (deeply oversold) but the trend veto fires first -> exit, not re-enter.
    frame = _frame([100.0, 100.0, 400.0, 398.0, 396.0, 200.0])
    assert _strategy().decide(frame) == 0.0


def test_stateless_same_history_same_answer() -> None:
    strategy = _strategy()
    invested = _frame(_HYSTERESIS_CLOSES[:5])
    exited = _frame(_HYSTERESIS_CLOSES)
    # Interleave prefixes: earlier calls must leave no residue in the instance.
    first = strategy.decide(invested)
    assert strategy.decide(exited) == 0.0
    assert strategy.decide(invested) == first == 1.0


def test_constructor_rejects_inverted_thresholds() -> None:
    with pytest.raises(ValueError):
        MeanReversionStrategy(
            rsi_period=2, entry_threshold=70.0, exit_threshold=30.0, trend_lookback=4
        )
    with pytest.raises(ValueError):
        MeanReversionStrategy(
            rsi_period=0, entry_threshold=30.0, exit_threshold=70.0, trend_lookback=4
        )


# ------------------------------------------------------------------ tunable


def test_param_grid_is_exactly_the_locked_12_combos() -> None:
    grid = TunableMeanReversion().param_grid()
    assert len(grid) == 12
    unique = {tuple(sorted(params.items())) for params in grid}
    assert len(unique) == 12
    assert grid[0] == {
        "rsi_period": 2,
        "entry_threshold": 10.0,
        "exit_threshold": 65.0,
    }
    for params in grid:
        assert params["rsi_period"] in (2, 3)
        assert params["entry_threshold"] in (10.0, 20.0, 30.0)
        assert params["exit_threshold"] in (65.0, 75.0)


def test_build_returns_a_working_strategy() -> None:
    tunable = TunableMeanReversion(trend_lookback=4)
    strategy = tunable.build(
        {"rsi_period": 2, "entry_threshold": 30.0, "exit_threshold": 70.0}
    )
    assert strategy.decide(_frame([100.0, 110.0, 120.0, 130.0, 127.0, 126.0])) == 1.0
