"""P19's nine rules as strategies, exactly as registered (QT-15 B).

docs/research/preregistered.json (commit 21b154b) is the authority; PLAN_V3 P19
fixed the settings on 2026-10-03. Each rule is long-only, all-in or flat, and its
exit is the mirror of its entry. The indicators are qb2/signals/indicators.py's
(EMA adjust=False; Keltner = EMA 21 +/- 2.0 x the codebase's Wilder ATR(14)).

Two readings, fixed here BEFORE any trial ran (they are wording, not tuning):

* **Keltner reversion.** The registered exit is "the bar touches the upper band
  and closes back inside", and the exit is the entry's mirror, so the entry reads
  the same way: the bar's LOW touches the lower band (low <= lower) and its close
  is back inside (close > lower). The exit: high >= upper and close < upper.
  Should both happen on one bar, the exit wins (the cautious side).
* **A session starts flat (P4, 5-minute bars).** Every position is sold before
  the bell, so a new session needs a FRESH entry signal: a cross made yesterday
  does not re-enter this morning. Daily bars carry the state from bar to bar.

A "cross" is a change of side between the previous bar and this one: up when
``a > b`` now and ``a <= b`` before; down when ``a < b`` now and ``a >= b`` before.
Every series here uses only the bar it is on and earlier ones (the look-ahead
check in strategy.checked_weights proves it on every run).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import numpy as np
import pandas as pd

from qb2.signals import indicators

Signals = Callable[[pd.DataFrame], tuple[pd.Series, pd.Series]]


def cross_up(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a > b) & (a.shift(1) <= b.shift(1))


def cross_down(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a < b) & (a.shift(1) >= b.shift(1))


def _crossing(fast: Callable[[pd.DataFrame], pd.Series],
              slow: Callable[[pd.DataFrame], pd.Series]) -> Signals:
    def signals(bars: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        a, b = fast(bars), slow(bars)
        return cross_up(a, b), cross_down(a, b)
    return signals


def _close(bars: pd.DataFrame) -> pd.Series:
    return bars["close"].astype(float)


def _ema(span: int) -> Callable[[pd.DataFrame], pd.Series]:
    return lambda bars: indicators.ema(_close(bars), span)


def _stacked(bars: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    e9, e21, e50 = (indicators.ema(_close(bars), n) for n in (9, 21, 50))
    aligned = (e9 > e21) & (e21 > e50)
    before = aligned.shift(1, fill_value=False).astype(bool)
    return aligned & ~before, ~aligned & before


def _keltner_breakout(bars: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    _, _, upper = indicators.keltner(bars)
    return cross_up(_close(bars), upper), cross_down(_close(bars), upper)


def _keltner_reversion(bars: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    lower, _, upper = indicators.keltner(bars)
    close = _close(bars)
    enter = (bars["low"] <= lower) & (close > lower)
    leave = (bars["high"] >= upper) & (close < upper)
    return enter, leave


RULES: dict[str, Signals] = {
    "price_x_ema9": _crossing(_close, _ema(9)),
    "price_x_ema21": _crossing(_close, _ema(21)),
    "price_x_ema50": _crossing(_close, _ema(50)),
    "ema9_x_ema21": _crossing(_ema(9), _ema(21)),
    "ema9_x_ema50": _crossing(_ema(9), _ema(50)),
    "ema21_x_ema50": _crossing(_ema(21), _ema(50)),
    "stacked_emas": _stacked,
    "keltner_breakout": _keltner_breakout,
    "keltner_reversion": _keltner_reversion,
}
EXPECTED_PARAMETERS: dict[str, dict[str, Any]] = {
    "price_x_ema9": {"ema": 9}, "price_x_ema21": {"ema": 21}, "price_x_ema50": {"ema": 50},
    "ema9_x_ema21": {"fast": 9, "slow": 21}, "ema9_x_ema50": {"fast": 9, "slow": 50},
    "ema21_x_ema50": {"fast": 21, "slow": 50}, "stacked_emas": {"emas": [9, 21, 50]},
    "keltner_breakout": {"middle": "EMA 21", "atr": "Wilder ATR(14)", "multiple": 2.0},
    "keltner_reversion": {"middle": "EMA 21", "atr": "Wilder ATR(14)", "multiple": 2.0},
}


def hold(enter: pd.Series, leave: pd.Series, sessions: pd.Index | None) -> pd.Series:
    """0/1: long from an entry until an exit (the exit wins a tie); a new session
    starts flat when ``sessions`` is given."""
    state = pd.Series(np.nan, index=enter.index)
    state[enter.fillna(False).to_numpy(bool)] = 1.0
    state[leave.fillna(False).to_numpy(bool)] = 0.0
    if sessions is None:
        return state.ffill().fillna(0.0)
    first = np.r_[True, np.asarray(sessions[1:] != sessions[:-1])]
    state[first & state.isna().to_numpy()] = 0.0
    return state.ffill().fillna(0.0)


class P19Rule:
    """One registered rule on one bar size, as a Strategy (weights decided at close)."""

    def __init__(self, rule: str, bar_size: str) -> None:
        if rule not in RULES:
            raise ValueError(f"{rule!r} is not one of P19's nine rules")
        self.rule, self.bar_size = rule, bar_size
        self.name = f"{rule}({bar_size})"

    def weights(self, bars: pd.DataFrame) -> pd.Series:
        enter, leave = RULES[self.rule](bars)
        sessions = (pd.Index(pd.DatetimeIndex(bars.index).date)
                    if self.bar_size == "5m" else None)
        return hold(enter, leave, sessions)


def build(entry: Mapping[str, Any]) -> P19Rule:
    """The strategy for one register entry -- refused if its parameters differ."""
    rule = str(entry["rule"])
    if rule not in EXPECTED_PARAMETERS or dict(entry["parameters"]) != \
            EXPECTED_PARAMETERS[rule]:
        raise ValueError(f"{entry.get('id')}: parameters {entry.get('parameters')} are "
                         f"not the ones this code implements for {rule!r}")
    return P19Rule(rule, str(entry["bar_size"]))
