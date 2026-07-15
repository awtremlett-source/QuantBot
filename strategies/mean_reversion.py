"""Challenger #1: RSI dip-buy above trend -- long-only mean-reversion.

The idea, in one sentence: inside an established uptrend, buy the short sharp
dips and sell the bounce. "Uptrend" is the same anchor the champion uses (close
above its long SMA); "dip" and "bounce" are measured with a short RSI.

RSI VARIANT: Cutler's RSI -- SIMPLE averages of gains and losses, NOT Wilder's
exponential smoothing. ``RSI = 100 - 100/(1 + RS)`` where ``RS = mean(gains) /
mean(losses)`` over the last ``rsi_period`` bar-to-bar close changes. Edge
rules, in this order: ``mean(losses) == 0 -> 100`` and ``mean(gains) == 0 -> 0``
(so a perfectly flat window reads 100 -- overbought-ish, never a buy signal).
Cutler's variant is chosen because it is deterministic over a fixed window and
hand-computable in a test; Wilder smoothing depends on where the series starts.

STATUS: validated spare part ONLY. This strategy is NOT wired to the paper
loop; ``execution/config.py`` stays frozen. Any promotion goes through the full
§7 firewall and a PROPOSE->GO decision first.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

import pandas as pd

from research.strategy import Strategy

_FloatArray = NDArray[np.float64]


def _rolling_mean(values: _FloatArray, window: int) -> _FloatArray:
    """Simple rolling mean via cumulative sums; NaN until the window is full.

    ``out[i]`` is the mean of ``values[i - window + 1 : i + 1]`` -- fast enough
    that ``decide`` can recompute indicators from scratch every call (the
    statelessness contract) without dominating a 1,000-trial Monte Carlo run.
    """
    n = len(values)
    out = np.full(n, np.nan)
    if n < window:
        return out
    sums = np.concatenate(([0.0], np.cumsum(values)))
    out[window - 1 :] = (sums[window:] - sums[:-window]) / window
    return out


def cutler_rsi(closes: _FloatArray, period: int) -> _FloatArray:
    """Cutler's RSI of ``closes`` over ``period`` changes, aligned to ``closes``.

    ``rsi[t]`` uses the ``period`` bar-to-bar changes ENDING at bar ``t`` (so the
    first defined value is at index ``period`` -- it needs ``period + 1`` closes);
    earlier entries are NaN. See the module docstring for the exact formula and
    the zero-gain / zero-loss edge rules.
    """
    if period < 1:
        raise ValueError(f"rsi period must be >= 1, got {period}")
    n = len(closes)
    rsi = np.full(n, np.nan)
    if n < period + 1:
        return rsi

    diffs = np.diff(closes)
    avg_gain = _rolling_mean(np.clip(diffs, 0.0, None), period)
    avg_loss = _rolling_mean(np.clip(-diffs, 0.0, None), period)

    # 100 - 100/(1+RS) simplifies to 100*g/(g+l); divide only where the sum is
    # positive so the zero/zero case never hits the division at all.
    total = avg_gain + avg_loss
    safe_total = np.where(total > 0.0, total, np.nan)
    core = 100.0 * avg_gain / safe_total
    # Edge rules IN ORDER: no losses -> 100 (covers the all-flat window too),
    # then no gains -> 0. NaN warmup entries fail both == checks and stay NaN.
    values = np.where(avg_loss == 0.0, 100.0, np.where(avg_gain == 0.0, 0.0, core))

    # diffs[j] ends at close[j+1], so the RSI at bar t is the rolling value at
    # diff index t-1.
    rsi[1:] = values
    return rsi


class MeanReversionStrategy:
    """Buy oversold dips above the trend SMA; exit on the bounce or trend break.

    Implements the :class:`research.strategy.Strategy` protocol: ``decide``
    returns the target weight for the NEXT bar, always exactly 0.0 or 1.0.

    Rules (a stateless replay -- everything is recomputed from the ``history``
    given to each call; the instance holds parameters only, never position):

    * warmup: fewer than ``max(trend_lookback, rsi_period + 1)`` bars -> 0.0
    * ``trend_ok[t]`` = close[t] > SMA(trend_lookback)[t]
    * replay t ascending: ENTER (1.0) when flat AND trend_ok AND
      rsi < entry_threshold; EXIT (0.0) when invested AND (rsi > exit_threshold
      OR not trend_ok)
    * the answer is the position standing at the final bar
    """

    def __init__(
        self,
        rsi_period: int,
        entry_threshold: float,
        exit_threshold: float,
        trend_lookback: int = 200,
    ) -> None:
        if rsi_period < 1:
            raise ValueError(f"rsi_period must be >= 1, got {rsi_period}")
        if trend_lookback < 1:
            raise ValueError(f"trend_lookback must be >= 1, got {trend_lookback}")
        if not 0.0 <= entry_threshold <= 100.0 or not 0.0 <= exit_threshold <= 100.0:
            raise ValueError(
                "RSI thresholds must be in [0, 100], got "
                f"entry={entry_threshold!r} exit={exit_threshold!r}"
            )
        if entry_threshold >= exit_threshold:
            raise ValueError(
                "entry_threshold must be < exit_threshold (hysteresis band), got "
                f"entry={entry_threshold!r} >= exit={exit_threshold!r}"
            )
        self._rsi_period = rsi_period
        self._entry_threshold = float(entry_threshold)
        self._exit_threshold = float(exit_threshold)
        self._trend_lookback = trend_lookback
        # Enough bars for BOTH indicators to be defined at the replay start.
        self._warmup = max(trend_lookback, rsi_period + 1)

    def decide(self, history: pd.DataFrame) -> float:
        n = len(history)
        if n < self._warmup:
            return 0.0

        closes = history["close"].to_numpy(dtype=float)
        rsi = cutler_rsi(closes, self._rsi_period)
        sma = _rolling_mean(closes, self._trend_lookback)
        # NaN warmup values compare False on both signals, and the replay below
        # starts where both indicators are defined anyway.
        trend_ok = closes > sma
        enter_signal = trend_ok & (rsi < self._entry_threshold)
        exit_signal = (rsi > self._exit_threshold) | ~trend_ok

        # Plain-python lists make the O(n) state replay ~10x faster than
        # per-element ndarray indexing; the semantics are the docstring's.
        enters: list[bool] = enter_signal.tolist()
        exits: list[bool] = exit_signal.tolist()
        invested = False
        for t in range(self._warmup - 1, n):
            if invested:
                if exits[t]:
                    invested = False
            elif enters[t]:
                invested = True
        return 1.0 if invested else 0.0


class TunableMeanReversion:
    """Tunable family over a deliberately SMALL grid (12 combos = 12 trials/fold).

    Implements :class:`research.strategy.TunableStrategy`. ``trend_lookback`` is
    fixed at the champion's 200-bar trend anchor rather than searched: fewer
    knobs = fewer lottery tickets for the trial count to deflate.
    """

    _RSI_PERIODS = (2, 3)
    _ENTRIES = (10.0, 20.0, 30.0)
    _EXITS = (65.0, 75.0)

    def __init__(self, trend_lookback: int = 200) -> None:
        if trend_lookback < 1:
            raise ValueError(f"trend_lookback must be >= 1, got {trend_lookback}")
        self._trend_lookback = trend_lookback

    def param_grid(self) -> list[dict[str, Any]]:
        return [
            {"rsi_period": p, "entry_threshold": e, "exit_threshold": x}
            for p in self._RSI_PERIODS
            for e in self._ENTRIES
            for x in self._EXITS
        ]

    def build(self, params: dict[str, Any]) -> Strategy:
        return MeanReversionStrategy(
            rsi_period=int(params["rsi_period"]),
            entry_threshold=float(params["entry_threshold"]),
            exit_threshold=float(params["exit_threshold"]),
            trend_lookback=self._trend_lookback,
        )
