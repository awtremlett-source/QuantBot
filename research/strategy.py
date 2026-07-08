"""The Strategy contract and two reference strategies.

A strategy's only job is to answer one question, bar by bar: *given everything
known up to and including now, what fraction of the portfolio should be invested
on the NEXT bar?* That answer is a TARGET WEIGHT in ``[0.0, 1.0]`` (0 = all cash,
1 = fully invested). Long-only: weights never go negative (no shorting) and never
exceed 1 (no leverage).

The backtester -- not the strategy -- owns timing and execution: it calls
:meth:`Strategy.decide` with history through the current bar and fills the
resulting weight at the NEXT bar's open. A strategy therefore CANNOT see the
future; it only ever receives past-and-current bars.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

import pandas as pd


class Strategy(Protocol):
    """Structural contract for a long-only strategy.

    Any object with a matching ``decide`` method satisfies this -- no base class
    or registration needed (it is a :class:`typing.Protocol`).
    """

    def decide(self, history: pd.DataFrame) -> float:
        """Return the target weight in ``[0, 1]`` to hold on the NEXT bar.

        ``history`` is every bar up to AND INCLUDING the current one (same column
        layout as the CLEAN series: ``event_time, open, high, low, close, volume,
        adj_close``) -- never any future bar. The returned weight should be in
        ``[0, 1]``; the backtester clamps defensively and rejects non-finite
        values, but a well-behaved strategy returns a value already in range.
        """
        ...


class FlatStrategy:
    """Never invests -- always 100% cash. The trivial null track record."""

    def decide(self, history: pd.DataFrame) -> float:
        return 0.0


class BuyAndHold:
    """Fully invested from the first available fill onward (weight 1.0).

    Returns 1.0 as soon as there is any history (there always is -- ``decide`` is
    called with at least the current bar), so the backtester buys in at the first
    NEXT-bar open and then holds.
    """

    def decide(self, history: pd.DataFrame) -> float:
        return 1.0 if len(history) >= 1 else 0.0


class TunableStrategy(Protocol):
    """A family of strategies parameterised by a small grid, for fitting.

    ``param_grid`` enumerates every parameter combination to try; ``build`` turns
    one combination into a concrete :class:`Strategy`. Walk-forward fitting searches
    ``param_grid`` on TRAIN data ONLY, then grades the chosen ``build`` result on
    unseen TEST data -- so the grid is the only place parameters are ever chosen.
    """

    def param_grid(self) -> list[dict[str, Any]]:
        """Return every parameter combination to evaluate, in a fixed order."""
        ...

    def build(self, params: dict[str, Any]) -> Strategy:
        """Return a concrete :class:`Strategy` for one parameter combination."""
        ...


class _SmaTrendRule:
    """Long (weight 1) while the last close sits above its ``lookback``-bar SMA.

    Needs at least ``lookback`` bars to form the average; before that it stays flat
    (weight 0). Uses only past-and-current closes, so it is lookahead-free like every
    :class:`Strategy`.
    """

    def __init__(self, lookback: int) -> None:
        if lookback < 1:
            raise ValueError(f"lookback must be >= 1, got {lookback}")
        self._lookback = lookback

    def decide(self, history: pd.DataFrame) -> float:
        if len(history) < self._lookback:
            return 0.0
        closes = history["close"]
        sma = float(closes.iloc[-self._lookback :].mean())
        last_close = float(closes.iloc[-1])
        return 1.0 if last_close > sma else 0.0


class SmaTrendStrategy:
    """Tunable SMA-trend family over a set of candidate ``lookback`` windows.

    Reference :class:`TunableStrategy` for the walk-forward tests: ``param_grid``
    ranges over the ``lookbacks`` supplied at construction and ``build`` returns the
    matching moving-average rule.
    """

    def __init__(self, lookbacks: Sequence[int]) -> None:
        chosen = list(lookbacks)
        if not chosen:
            raise ValueError("SmaTrendStrategy needs at least one lookback")
        self._lookbacks = chosen

    def param_grid(self) -> list[dict[str, Any]]:
        return [{"lookback": lb} for lb in self._lookbacks]

    def build(self, params: dict[str, Any]) -> Strategy:
        return _SmaTrendRule(int(params["lookback"]))
