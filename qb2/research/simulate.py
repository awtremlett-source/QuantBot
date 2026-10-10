"""The trade arithmetic: positions in, gross / net / marked-down returns out (S4).

PORTED in part from v1's research/backtester.py (SHA-256 at copy time, 2026-10-10:
4ca72b809c37d1eab994ec6feda0b07aa9a4baeb8e1973ffb8d391407ad485ba): marking at the
close, filling at the open, net and gross off the SAME decisions.

What changed, and why. The bot sizes each order at a fixed stake (PLAN_V3: at most
10% of its 30% pot), so returns are measured on that stake, per bar, and add up:

* a trade buys at the fill bar's OPEN; shares = stake / entry price;
* each bar it is held earns (price change) / entry price -- the gap from the last
  close to this open belongs to the position held before this bar's fill, the
  move from open to close to the position held after it;
* every fill pays the cost model's full leg cost (qb2/execution/costs.py: spread,
  slippage, FX 0.15% per leg on non-sterling lines, 0.5% stamp duty on UK share
  buys, PTM levy), as a fraction of the stake. There is no way to ask for zero:
  the stress multiplier is refused below 1.
* the survivorship mark-down is charged per bar HELD on single shares.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from qb2.execution import costs

STAKE_GBP = 300.0          # STARTING FIGURE: 10% of a GBP 3,000 pot (safety.py)


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
    """Per-bar returns on the stake for a 0/1 position path."""
    held = np.asarray(held, dtype=float)
    before = np.r_[0.0, held[:-1]]
    entries = held > before
    exits = held < before
    entry_px = np.where(entries, opens, np.nan)
    known = np.where(np.isnan(entry_px), 0, np.arange(len(held)))
    entry_px = entry_px[np.maximum.accumulate(known)]          # carried while held
    entry_before = np.r_[np.nan, entry_px[:-1]]
    prev_close = np.r_[np.nan, closes[:-1]]
    with np.errstate(invalid="ignore"):
        gap = np.where(before > 0, (opens - prev_close) / entry_before, 0.0)
        body = np.where(held > 0, (closes - opens) / entry_px, 0.0)
    gross = np.nan_to_num(gap) + np.nan_to_num(body)
    if len(held):
        exits[-1] = exits[-1] or held[-1] > 0       # still open at the end: sold there
    net = gross - entries * legs.buy - exits * legs.sell
    return Paths(gross=gross, net=net, marked=net - drag_per_bar * held, entries=entries)
