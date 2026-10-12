"""The turnover-matched null: the rule's own trades, placed at random (QT-16 A1).

QT-15 found the coin-flip null unfair to slow rules. A fresh 50% coin every bar
churns, pays costs on almost every other bar, and so ANY slow rule "beats" it on
costs alone -- all 18 P19 trials did (p 0.005) while losing to VWRP. This null
asks the fair question: is the rule's TIMING better than random timing with the
same turnover? It decides the verdict's luck test (p < 0.05); the coin-flip stays
in the report as a description, and still feeds the Deflated Sharpe's variance.

For each name the candidate's own held path in the graded window is cut into its
trades (runs of held bars). The same number of trades, with the same holding
lengths, is then placed at random start times inside that same window:

* never overlapping, with at least one flat bar between two trades, so the count
  of trades -- and so every cost leg -- is exactly the candidate's;
* only on bars a real fill could hold (the delay and P4): daily from the second
  bar; on 5-minute bars from the first bar a delayed fill reaches in a session to
  the bar before the P4 cut-off, inside ONE session;
* a trade that crosses the window's edge stays where it is (it was half graded);
* seeded per bet, so both lines of one bet draw from the same seed, as the coin.

The new path is priced exactly as the candidate's was: the same prices (in
pounds), cost legs, survivorship drag and bet groups (simulate.run, combine).

Placement: trades go to free stretches at random, longest first, each to a
stretch chosen in proportion to the room left in it; inside a stretch they take a
random order and random gaps (stars and bars). If the room runs out -- only when
the candidate fills its sessions nearly full -- it retries with the same
generator, and after RETRIES failures each trade keeps its own stretch with a
random start inside it, which always fits because the candidate's trades did.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from qb2.research import backtest, fills, simulate

RETRIES = 20                     # placements tried before the in-stretch fallback

Ints = NDArray[np.int64]


@dataclass(frozen=True, slots=True)
class Graded:
    """One name's full candidate run and the bar range [lo, hi) that is graded."""

    full: backtest.BacktestResult
    lo: int
    hi: int


def runs_of(held: NDArray[np.float64]) -> tuple[Ints, Ints]:
    """Start and end (exclusive) of every run of held bars."""
    on = np.r_[0, (np.asarray(held) > 0).astype(np.int8), 0]
    edges = np.diff(on)
    return np.flatnonzero(edges == 1).astype(np.int64), np.flatnonzero(edges == -1).astype(np.int64)


def legal(plan: fills.Schedule) -> tuple[NDArray[np.bool_], Ints]:
    """Bars a delayed fill can hold, and each bar's session (all 0 on daily bars)."""
    landed = np.zeros(plan.n, dtype=bool)
    landed[plan.fills[plan.usable]] = True
    session = (np.zeros(plan.n, dtype=np.int64) if plan.session_first is None
               else np.cumsum(plan.session_first).astype(np.int64))
    first = pd.Series(np.where(landed, np.arange(plan.n), plan.n)).groupby(session).transform("min")
    ok = np.arange(plan.n) >= first.to_numpy()
    if plan.forced_flat is not None:
        ok &= ~plan.forced_flat
    return ok, session


def stretches(free: NDArray[np.bool_], session: Ints) -> tuple[Ints, Ints]:
    """Maximal runs of free bars that stay inside one session."""
    cut = np.r_[True, session[1:] != session[:-1]]
    starts = np.flatnonzero(free & (cut | ~np.r_[False, free[:-1]]))
    ends = np.flatnonzero(free & (np.r_[cut[1:], True] | ~np.r_[free[1:], False])) + 1
    return starts.astype(np.int64), ends.astype(np.int64)


def _assign(lengths: Ints, room: Ints, rng: np.random.Generator) -> Ints | None:
    """Each trade's stretch, longest first; None if the room ran out."""
    room = room.copy()
    out = np.empty(len(lengths), dtype=np.int64)
    for i in np.lexsort((rng.random(len(lengths)), -lengths)):
        need = int(lengths[i]) + 1                    # the trade plus its gap
        weight = np.clip(room - need + 1, 0, None).astype(float)
        if weight.sum() <= 0:
            return None
        pick = int(np.searchsorted(np.cumsum(weight), rng.random() * weight.sum(), "right"))
        out[i], room[pick] = pick, room[pick] - need
    return out


def _lay(lo: int, size: int, lengths: Ints, rng: np.random.Generator) -> tuple[Ints, Ints]:
    """Random order, random gaps (stars and bars) for trades sharing one stretch."""
    order = rng.permutation(lengths)
    slack = size - int(order.sum()) - (len(order) - 1)
    cuts = np.sort(rng.choice(slack + len(order), len(order), replace=False))
    return lo + cuts + np.r_[0, np.cumsum(order)[:-1]], order


@dataclass(frozen=True, slots=True)
class Prepared:
    """Everything about one name that does not depend on the draw, built once."""

    base: NDArray[np.float64]          # the candidate's path with its movable trades removed
    lo: Ints                           # free stretches [lo, hi)
    hi: Ints
    lengths: Ints                      # the movable trades' holding lengths
    home: Ints                         # each trade's own stretch (the fallback)


def prepare(held: NDArray[np.float64], plan: fills.Schedule, lo: int, hi: int) -> Prepared:
    held = np.asarray(held, dtype=float)
    starts, ends = runs_of(held)
    move = (starts >= lo) & (ends <= hi)
    base = held.copy()
    for s, e in zip(starts[move], ends[move], strict=True):
        base[s:e] = 0.0
    ok, session = legal(plan)
    taken = base > 0                                   # outside bars and edge trades
    blocked = taken | np.r_[False, taken[:-1]] | np.r_[taken[1:], False]
    inside = np.zeros(len(held), dtype=bool)
    inside[lo:hi] = True
    a, b = stretches(ok & ~blocked & inside, session)
    home = np.searchsorted(a, starts[move], "right").astype(np.int64) - 1
    return Prepared(base, a, b, (ends[move] - starts[move]).astype(np.int64), home)


def draw(prep: Prepared, rng: np.random.Generator) -> NDArray[np.float64]:
    """One random placement of the candidate's trades (see the module docstring)."""
    out = prep.base.copy()
    if not len(prep.lengths):
        return out
    where = None
    for _ in range(RETRIES):
        where = _assign(prep.lengths, prep.hi - prep.lo + 1, rng)
        if where is not None:
            break
    if where is None:                                  # each keeps its own stretch
        where = prep.home
    for k in np.unique(where):
        firsts, order = _lay(int(prep.lo[k]), int(prep.hi[k] - prep.lo[k]),
                             prep.lengths[where == k], rng)
        for s, n in zip(firsts, order, strict=True):
            out[s:s + n] = 1.0
    return out


def frames(graded: Mapping[str, Graded], prepared: Mapping[str, Prepared],
           bets: Mapping[str, int], seed: int) -> dict[str, pd.DataFrame]:
    """One matched-null draw: every name's graded frame, priced like the candidate."""
    out: dict[str, pd.DataFrame] = {}
    for symbol, g in graded.items():
        rng = np.random.default_rng(np.random.SeedSequence([seed, bets[symbol]]))
        held = draw(prepared[symbol], rng)
        paths = simulate.run(g.full.opens, g.full.closes, held, g.full.legs, g.full.drag)
        out[symbol] = backtest.frame(g.full, g.lo, g.hi, paths, held)
    return out
