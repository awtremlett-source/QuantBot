"""The trade arithmetic: positions in, gross / net / marked-down returns out (S4).

PORTED in part from v1's research/backtester.py (SHA-256 at copy time, 2026-10-10:
4ca72b809c37d1eab994ec6feda0b07aa9a4baeb8e1973ffb8d391407ad485ba): marking at the
close, filling at the open, net and gross off the SAME decisions.

What changed, and why (QT-15 A1: v1 compounded, QT-14's port added). The bot's
pot is split equally per BET (bet_groups.combine), and each bet's slot is re-sized
to the pot as it stands at every bar, so returns COMPOUND (stats.compounded):

* a trade buys at the fill bar's OPEN;
* each bar it is held earns its price move on the slot as it stands at that bar's
  start -- the gap from the last close to this open belongs to the position held
  before this bar's fill, the move from open to close to the position held after
  it; over one trade the bars multiply to exit / entry;
* every fill pays the cost model's full leg cost (qb2/execution/costs.py: spread,
  slippage, FX 0.15% per leg on non-sterling lines, 0.5% stamp duty on UK share
  buys, PTM levy) as a fraction of the slot. There is no way to ask for zero: the
  stress multiplier is refused below 1.
* the survivorship mark-down is charged per bar HELD on single shares.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from qb2.execution import costs

# STARTING FIGURE: 10% of a GBP 3,000 pot (safety.py). Used for the COST arithmetic
# only (a fixed fee is a bigger share of a small order); returns are per slot.
STAKE_GBP = 300.0


@dataclass(frozen=True, slots=True)
class LegFractions:
    buy: float
    sell: float


def leg_fractions(instrument: costs.Instrument, stress: float) -> LegFractions:
    """Each leg's cost as a share of the stake, from the ONE cost model."""
    if not stress >= 1.0:
        raise ValueError(f"cost stress {stress!r} refused: costs are never below 1x")
    buy = costs.leg_cost(instrument, STAKE_GBP, "BUY", stress=stress)
    sell = costs.leg_cost(instrument, STAKE_GBP, "SELL", stress=stress)
    out = LegFractions(buy.fraction_of_consideration, sell.fraction_of_consideration)
    if out.buy <= 0 or out.sell <= 0:
        raise ValueError(f"{instrument.ticker}: a zero-cost leg is not a real fill")
    return out


@dataclass(frozen=True, slots=True)
class Paths:
    gross: NDArray[np.float64]
    net: NDArray[np.float64]
    marked: NDArray[np.float64]
    entries: NDArray[np.bool_]


def run(opens: NDArray[np.float64], closes: NDArray[np.float64],
        held: NDArray[np.float64], legs: LegFractions,
        drag_per_bar: float = 0.0) -> Paths:
    """Per-bar returns on the slot, re-sized every bar, for a 0/1 position path."""
    held = np.asarray(held, dtype=float)
    before = np.r_[0.0, held[:-1]]
    entries = held > before
    exits = held < before
    prev_close = np.r_[np.nan, closes[:-1]]
    with np.errstate(invalid="ignore", divide="ignore"):
        gap = np.where(before > 0, opens / prev_close - 1.0, 0.0)
        body = np.where(held > 0, closes / opens - 1.0, 0.0)
    gross = (1.0 + np.nan_to_num(gap)) * (1.0 + np.nan_to_num(body)) - 1.0
    if len(held):
        exits[-1] = exits[-1] or held[-1] > 0       # still open at the end: sold there
    net = (1.0 + gross) * (1.0 - entries * legs.buy) * (1.0 - exits * legs.sell) - 1.0
    marked = (1.0 + net) * (1.0 - drag_per_bar * held) - 1.0
    return Paths(gross=gross, net=net, marked=marked, entries=entries)
