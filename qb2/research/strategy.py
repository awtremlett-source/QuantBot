"""The Strategy contract, and the look-ahead check every scoring path runs.

PORTED, NOT IMPORTED, from v1's research/strategy.py (SHA-256 at copy time,
2026-10-10: c2db335a8bef704997bd4ba74eacb30c1a37bf6e2182c51cf41f9767ac73f10b).
v1 asked a strategy one bar at a time (``decide(history)``), which costs a full
re-read of history per bar: fine on 2 years of daily bars, hopeless on 5-minute
bars inside a 200-run Monte Carlo. qb2 asks once for the whole series --
``weights(bars)`` -- and then PROVES the answer is causal by re-asking on cut-off
copies: if removing the future changes any past weight, the strategy was reading
the future, and it is refused before it is scored.

Long-only, all-in or flat: a weight is 0.0 (cash) or 1.0 (held). Sizing is S7's.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np
import pandas as pd

CUTS = (0.25, 0.5, 0.75)                 # where the look-ahead check cuts the series


class LookAhead(RuntimeError):
    """The strategy's past weights changed when the future was removed."""


class Strategy(Protocol):
    """``weights(bars)``: the target decided at each bar's CLOSE, from that bar and
    earlier ones only. The fill timing is the backtester's job, not the strategy's."""

    name: str

    def weights(self, bars: pd.DataFrame) -> pd.Series: ...


class Flat:
    """Never invests. The trivial null."""

    name = "flat"

    def weights(self, bars: pd.DataFrame) -> pd.Series:
        return pd.Series(0.0, index=bars.index)


def checked_weights(strategy: Strategy, bars: pd.DataFrame) -> np.ndarray:
    """The weights as an array, refused if non-binary or if they read the future."""
    full = strategy.weights(bars)
    if len(full) != len(bars):
        raise ValueError(f"{strategy.name}: {len(full)} weights for {len(bars)} bars")
    values = np.asarray(full, dtype=float)
    if not np.isin(values, (0.0, 1.0)).all():
        raise ValueError(f"{strategy.name}: weights must be 0.0 or 1.0 (long or flat)")
    for share in CUTS:
        cut = int(len(bars) * share)
        if cut < 2:
            continue
        early = np.asarray(strategy.weights(bars.iloc[:cut]), dtype=float)
        if not np.array_equal(early, values[:cut]):
            raise LookAhead(f"{strategy.name}: weights before bar {cut} changed when "
                            "later bars were removed -- it reads the future")
    return values
