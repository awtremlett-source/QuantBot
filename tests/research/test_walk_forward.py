"""Deterministic, fully-OFFLINE tests for the walk-forward validator.

All price data is synthetic, injected as DataFrames -- no DB, no network. The
central invariant is NO FIT ON TEST: parameters are chosen only inside fit_best,
which only ever receives TRAIN bars. The birth-certificate spy below proves that a
candidate strategy never sees a test bar during the fit phase -- leaking test data
into the fit MUST fail that test.

event_time is encoded as zero-padded ``t0000, t0001, ...`` so lexicographic order
matches bar position, and a fold's index range can be recovered with ``int(et[1:])``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pandas as pd
import pytest

from research.strategy import BuyAndHold, SmaTrendStrategy, Strategy
from research.walk_forward import fit_best, walk_forward


def _frame(closes: Sequence[float], opens: Sequence[float] | None = None) -> pd.DataFrame:
    """Build a CLEAN-shaped price frame; event_time position == index (``t0000``...)."""
    the_opens = list(closes) if opens is None else list(opens)
    the_closes = list(closes)
    n = len(the_closes)
    assert len(the_opens) == n
    event_time = [f"t{i:04d}" for i in range(n)]
    return pd.DataFrame(
        {
            "event_time": event_time,
            "open": [float(o) for o in the_opens],
            "high": [float(max(o, c)) + 1.0 for o, c in zip(the_opens, the_closes)],
            "low": [float(min(o, c)) - 1.0 for o, c in zip(the_opens, the_closes)],
            "close": [float(c) for c in the_closes],
            "volume": [1_000_000] * n,
            "adj_close": [float(c) for c in the_closes],
        }
    )


def _rising(n: int, start: float = 100.0) -> pd.DataFrame:
    """A strictly rising series of length ``n`` (close == open == start + i)."""
    return _frame([start + i for i in range(n)])


def _pos(event_time: str) -> int:
    """Recover the bar index encoded in a ``t0000``-style event_time."""
    return int(event_time[1:])


class _ConstantTunable:
    """A trivial tunable: one param, ignored -- build() always returns BuyAndHold."""

    def param_grid(self) -> list[dict[str, Any]]:
        return [{"unused": 0}]

    def build(self, params: dict[str, Any]) -> Strategy:
        return BuyAndHold()


class _MaxTimeStrategy:
    """Flat strategy that records the max event_time it is ever shown.

    Used by the birth certificate: after a walk-forward run, a candidate used only
    during the FIT phase must have ``max_seen`` strictly before its fold's test start.
    """

    def __init__(self) -> None:
        self.max_seen: str | None = None

    def decide(self, history: pd.DataFrame) -> float:
        seen = str(history["event_time"].iloc[-1])
        if self.max_seen is None or seen > self.max_seen:
            self.max_seen = seen
        return 0.0


class _SpyTunable:
    """Records every strategy it builds, in grid-then-fold order.

    All candidates are flat (score 0.0), so fit_best's first-highest tie-break always
    picks the FIRST candidate per fold -- the one that then gets the OOS grading run.
    """

    def __init__(self, lookbacks: Sequence[int]) -> None:
        self._lookbacks = list(lookbacks)
        self.built: list[_MaxTimeStrategy] = []

    def param_grid(self) -> list[dict[str, Any]]:
        return [{"lookback": lb} for lb in self._lookbacks]

    def build(self, params: dict[str, Any]) -> Strategy:
        spy = _MaxTimeStrategy()
        self.built.append(spy)
        return spy


def test_fold_partition_anchored_and_rolling() -> None:
    # 10 bars, train_size=4, test_size=2, step=2 -> 3 folds.
    prices = _rising(10)

    anchored = walk_forward(
        _ConstantTunable(), prices, train_size=4, test_size=2, step=2, mode="anchored"
    )
    rolling = walk_forward(
        _ConstantTunable(), prices, train_size=4, test_size=2, step=2, mode="rolling"
    )

    assert anchored.num_folds == 3
    assert rolling.num_folds == 3

    def ranges(res_folds: list[Any]) -> list[tuple[int, int, int, int]]:
        return [
            (
                _pos(f.train_start),
                _pos(f.train_end),
                _pos(f.test_start),
                _pos(f.test_end),
            )
            for f in res_folds
        ]

    # Anchored train window expands from bar 0; rolling keeps a fixed 4-bar window.
    assert ranges(anchored.folds) == [(0, 3, 4, 5), (0, 5, 6, 7), (0, 7, 8, 9)]
    assert ranges(rolling.folds) == [(0, 3, 4, 5), (2, 5, 6, 7), (4, 7, 8, 9)]

    # Test windows are identical across modes, contiguous and non-overlapping.
    for res in (anchored, rolling):
        windows = [(_pos(f.test_start), _pos(f.test_end)) for f in res.folds]
        assert windows == [(4, 5), (6, 7), (8, 9)]
        for (_s0, e0), (s1, _e1) in zip(windows, windows[1:]):
            assert s1 == e0 + 1  # contiguous: next test starts right after prior ends


def test_final_shorter_test_window_is_included() -> None:
    # 12 bars, train_size=4, test_size=3, step=3. Folds at train_hi 4, 7, 10.
    # The last window [10,12) is only 2 bars (< test_size) but still >= 2 -> included.
    prices = _rising(12)
    res = walk_forward(
        _ConstantTunable(), prices, train_size=4, test_size=3, step=3, mode="anchored"
    )

    windows = [(_pos(f.test_start), _pos(f.test_end)) for f in res.folds]
    assert windows == [(4, 6), (7, 9), (10, 11)]  # last one is a 2-bar partial
    assert res.num_folds == 3


def test_no_fit_on_test_birth_certificate() -> None:
    # THE walk-forward birth certificate. A candidate strategy built during a fold's
    # FIT phase must never see an event_time at/after that fold's TEST start. If
    # walk_forward ever fit on prices[:test_end] (a leak), the non-selected candidates
    # would see test bars and the `< test_start` assertion below would fail.
    lookbacks = [2, 3, 4]  # need >= 2 candidates so non-selected ones exist to inspect
    k = len(lookbacks)
    spy = _SpyTunable(lookbacks)
    prices = _rising(10)

    res = walk_forward(spy, prices, train_size=4, test_size=2, step=2, mode="anchored")

    # fit builds k candidates per fold; grading reuses (does not rebuild) the winner.
    assert len(spy.built) == k * res.num_folds
    assert res.total_trials == k * res.num_folds

    for fold_idx, fold in enumerate(res.folds):
        candidates = spy.built[fold_idx * k : (fold_idx + 1) * k]
        winner, others = candidates[0], candidates[1:]

        # The winner (first, by tie-break) is re-run OOS and legitimately sees up to
        # the test end -- that is allowed.
        assert winner.max_seen == fold.test_end

        # Every OTHER candidate was touched ONLY during the fit and must have stopped
        # strictly before this fold's test window began.
        assert others, "need non-selected candidates to check the fit phase"
        for cand in others:
            assert cand.max_seen is not None
            assert cand.max_seen < fold.test_start


def test_fit_best_never_sees_test_bars_directly() -> None:
    # Belt-and-braces on the same invariant, exercised at the fit_best boundary: given
    # only a TRAIN slice, no candidate can record an event_time inside the test window.
    prices = _rising(10)
    train = prices.iloc[0:4]
    test_start = str(prices["event_time"].iloc[4])

    spy = _SpyTunable([2, 3, 4])
    fit_best(spy, train)

    assert spy.built  # candidates were actually evaluated
    for cand in spy.built:
        assert cand.max_seen is not None
        assert cand.max_seen < test_start


def test_step_smaller_than_test_size_raises() -> None:
    prices = _rising(20)
    with pytest.raises(ValueError, match="step"):
        walk_forward(_ConstantTunable(), prices, train_size=4, test_size=3, step=2)


def test_too_little_data_raises() -> None:
    # len == train_size + 2 is NOT enough (need strictly more).
    prices = _rising(6)
    with pytest.raises(ValueError, match="too little data"):
        walk_forward(_ConstantTunable(), prices, train_size=4, test_size=2)


def test_total_trials_equals_grid_size_times_folds() -> None:
    lookbacks = [2, 3, 4, 5]
    tunable = SmaTrendStrategy(lookbacks)
    prices = _rising(12)

    res = walk_forward(tunable, prices, train_size=4, test_size=2, step=2)

    assert all(f.trials_evaluated == len(lookbacks) for f in res.folds)
    assert res.total_trials == sum(len(lookbacks) for _ in res.folds)
    assert res.total_trials == len(lookbacks) * res.num_folds


def test_oos_returns_are_chronological_stitch_of_folds() -> None:
    tunable = SmaTrendStrategy([2, 3])
    prices = _rising(12)

    res = walk_forward(tunable, prices, train_size=4, test_size=2, step=2)

    # The stitched OOS returns are exactly each fold's test-slice returns, concatenated.
    expected = pd.concat([f.oos_returns for f in res.folds])
    pd.testing.assert_series_equal(
        res.oos_returns, expected, check_names=False
    )

    # Chronological + non-overlapping: the index is strictly increasing.
    positions = [_pos(str(t)) for t in res.oos_returns.index]
    assert positions == sorted(positions)
    assert len(set(positions)) == len(positions)

    # Equity compounds the stitched returns from the starting equity.
    expected_equity = 10000.0 * (1.0 + res.oos_returns).cumprod()
    pd.testing.assert_series_equal(
        res.oos_equity_curve, expected_equity, check_names=False
    )

    # Cross-check one headline stat by hand: total return == prod(1+r) - 1.
    hand_total = float((1.0 + res.oos_returns).prod()) - 1.0
    assert res.oos_total_return == pytest.approx(hand_total, rel=1e-12)


def test_plumbing_buy_and_hold_on_rising_series_is_positive() -> None:
    # A trivial tunable (single param, ignored) that always buys and holds, on a
    # strictly rising series, must produce a positive stitched OOS return.
    prices = _rising(12)

    res = walk_forward(_ConstantTunable(), prices, train_size=4, test_size=2, step=2)

    # 12 bars, train 4 / test 2 / step 2 -> test windows [4,6),[6,8),[8,10),[10,12).
    assert res.num_folds == 4
    windows = [(_pos(f.test_start), _pos(f.test_end)) for f in res.folds]
    assert windows == [(4, 5), (6, 7), (8, 9), (10, 11)]
    assert res.total_trials == 4  # one param per fold
    assert res.oos_total_return > 0.0
    assert res.oos_equity_curve.iloc[-1] > 10000.0
