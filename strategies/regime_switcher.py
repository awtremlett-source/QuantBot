"""Regime switcher: champion in calm markets, dip-buyer in stressed ones.

EXPERIMENT (graduation-rubric condition 4) -- NOT live. Adopt ONLY if it beats
the always-on SMA-200 champion out-of-sample; otherwise the rejection gets
recorded and the champion stands. ``execution/config.py`` stays frozen either way.

SEVERITY, in plain language: "how turbulent is today compared with this ticker's
own one-year normal?" Per bar t:

* ``RV20[t]`` = standard deviation (population, ddof=0) of the last 20 daily
  close-to-close returns -- recent realized volatility.
* ``RV_med[t]`` = median of the RV20 series over the last 252 bars -- the
  one-year "normal" level of that same volatility.
* ``severity[t] = RV20[t] / RV_med[t]`` (0.0 if ``RV_med == 0``). 1.0 means
  "exactly normal"; 2.0 means "twice as turbulent as normal".

REGIME, via a stateless hysteresis replay (recomputed from the given history on
every call -- the instance holds parameters only): start calm; calm -> stressed
when ``severity > threshold``; stressed -> calm when ``severity < 0.8 *
threshold``. The 0.8 re-entry factor is FIXED, not a parameter: the gap between
the two lines is what stops the regime flapping when severity hovers near the
threshold.

DELEGATION: both sub-strategies' decisions are computed on the full history
independently, exactly as if each ran alone; the switcher only selects WHOSE
decision is emitted (calm bar -> calm strategy's, stressed bar -> stressed
strategy's). Sub-strategies are FROZEN at their validated shapes: calm =
SMA-200 trend (the champion's fit), stressed = mean-reversion 2/20/75 (the
challenger's modal walk-forward fit).
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

import pandas as pd

from research.strategy import SmaTrendStrategy, Strategy
from strategies.mean_reversion import MeanReversionStrategy

_FloatArray = NDArray[np.float64]

_RV_WINDOW = 20
_MEDIAN_WINDOW = 252
# First bar with a defined severity: 20 returns for the first RV20 value (bar 20),
# then 252 RV20 values for the first median (bar 20 + 252 - 1).
_SEVERITY_START = _RV_WINDOW + _MEDIAN_WINDOW - 1
_WARMUP = _RV_WINDOW + _MEDIAN_WINDOW + 1  # 273 bars, per the locked spec
_HYSTERESIS = 0.8  # FIXED re-entry factor -- deliberately not tunable
_TREND_LOOKBACK = 200


def _rolling_mean(values: _FloatArray, window: int) -> _FloatArray:
    """Simple rolling mean via cumulative sums; NaN until the window is full.

    Local copy of the helper in :mod:`strategies.mean_reversion` -- existing
    strategy files are frozen validated artifacts, so nothing is refactored out
    of them here.
    """
    n = len(values)
    out = np.full(n, np.nan)
    if n < window:
        return out
    sums = np.concatenate(([0.0], np.cumsum(values)))
    out[window - 1 :] = (sums[window:] - sums[:-window]) / window
    return out


def severity_series(closes: _FloatArray) -> _FloatArray:
    """Severity per bar, aligned to ``closes``; NaN where not yet defined.

    See the module docstring for the plain-language definition. The rolling
    variance uses the identity ``var = E[x^2] - E[x]^2`` (population, ddof=0),
    clipped at zero against floating-point negatives.
    """
    n = len(closes)
    out = np.full(n, np.nan)
    if n < 2:
        return out

    returns = np.diff(closes) / closes[:-1]
    mean = _rolling_mean(returns, _RV_WINDOW)
    mean_sq = _rolling_mean(returns * returns, _RV_WINDOW)
    rv = np.sqrt(np.clip(mean_sq - mean * mean, 0.0, None))

    # returns[j] ends at bar j+1, so the RV20 value at diff index j belongs to
    # bar j+1; re-align to the bar axis before taking the one-year median.
    rv_bars = np.full(n, np.nan)
    rv_bars[1:] = rv
    med = pd.Series(rv_bars).rolling(_MEDIAN_WINDOW).median().to_numpy()

    # 0/0 and x/0 are handled by the RV_med==0 rule below, so the division may
    # be evaluated blind; NaN warmup entries fail the == check and stay NaN.
    with np.errstate(divide="ignore", invalid="ignore"):
        severity = rv_bars / med
    result: _FloatArray = np.where(med == 0.0, 0.0, severity)
    return result


def regime_series(history: pd.DataFrame, threshold: float) -> list[str]:
    """Per-bar regime labels (``'calm'`` | ``'stressed'``) for ``history``.

    THE hysteresis replay -- :meth:`RegimeSwitcherStrategy.decide` delegates to
    this function, so the labels a monitor reads and the regime the live
    strategy trades can never diverge. Stateless: recomputed from the given
    history on every call, exactly like ``decide``. Bars before the first
    defined severity (the 271-bar warmup) are ``'calm'`` (the replay's start
    state); a NaN severity leaves the regime unchanged, as in ``decide``.
    """
    if not threshold > 0.0:
        raise ValueError(f"threshold must be > 0, got {threshold!r}")
    exit_threshold = _HYSTERESIS * threshold
    closes = history["close"].to_numpy(dtype=float)
    severity: list[float] = severity_series(closes).tolist()

    labels: list[str] = []
    stressed_now = False
    for t in range(len(closes)):
        if t >= _SEVERITY_START:
            s = severity[t]
            if stressed_now:
                if s < exit_threshold:
                    stressed_now = False
            elif s > threshold:
                stressed_now = True
        labels.append("stressed" if stressed_now else "calm")
    return labels


class RegimeSwitcherStrategy:
    """Emit the calm strategy's decision in calm regimes, the stressed one's
    in stressed regimes (see module docstring for severity and hysteresis).

    Implements the :class:`research.strategy.Strategy` protocol. Warmup: fewer
    than 273 bars (252-bar median window + 20-bar RV window + 1) -> 0.0.
    """

    def __init__(
        self,
        threshold: float,
        calm: Strategy | None = None,
        stressed: Strategy | None = None,
    ) -> None:
        if not threshold > 0.0:
            raise ValueError(f"threshold must be > 0, got {threshold!r}")
        self._threshold = float(threshold)
        self._exit_threshold = _HYSTERESIS * self._threshold
        # Defaults are the FROZEN validated shapes (module docstring); built
        # here rather than as default arguments so instances never share state.
        self._calm: Strategy = (
            calm
            if calm is not None
            else SmaTrendStrategy([_TREND_LOOKBACK]).build(
                {"lookback": _TREND_LOOKBACK}
            )
        )
        self._stressed: Strategy = (
            stressed
            if stressed is not None
            else MeanReversionStrategy(
                rsi_period=2,
                entry_threshold=20.0,
                exit_threshold=75.0,
                trend_lookback=_TREND_LOOKBACK,
            )
        )

    def decide(self, history: pd.DataFrame) -> float:
        n = len(history)
        if n < _WARMUP:
            return 0.0

        # THE regime replay lives in regime_series (shared with monitors);
        # only the final bar's label selects whose signal is emitted.
        stressed_now = regime_series(history, self._threshold)[-1] == "stressed"

        # Both sub-signals are computed on the full history, exactly as if each
        # strategy always ran; the regime only selects whose signal is USED.
        calm_signal = self._calm.decide(history)
        stressed_signal = self._stressed.decide(history)
        return stressed_signal if stressed_now else calm_signal


class TunableRegimeSwitcher:
    """Tunable family over the switching threshold ONLY (3 combos).

    Implements :class:`research.strategy.TunableStrategy`. The sub-strategies
    are frozen validated shapes and are deliberately NOT searched here -- the
    experiment tunes when to switch, not what it switches between (3 combos =
    3 trials/fold of honest counting, not 3 x their grids).
    """

    _THRESHOLDS = (1.2, 1.5, 1.8)

    def param_grid(self) -> list[dict[str, Any]]:
        return [{"threshold": t} for t in self._THRESHOLDS]

    def build(self, params: dict[str, Any]) -> Strategy:
        return RegimeSwitcherStrategy(threshold=float(params["threshold"]))
