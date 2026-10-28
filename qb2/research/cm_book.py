"""Batch 2's book: the target the model learns, the trade rule, the strategy the firewall scores
and the graded window (QT-27 D1; register commit 6be96dad, CM-*: clarifications 1, 2, 4, 6, 7).

The trade plumbing is batch 1's own, unchanged: ``CMRule`` is s6_rules.Rule with one new
trigger -- buy at bar 1's close on the (name, day) pairs the trade rule chose -- so the fill (two
bars later, same session), the exit at E's open, P15 at the decision bar and the S6-04/05 stop
(entry - 3 x Wilder ATR(14) of the bar before the entry, crossed on a close at or below it, else
raised to close - 3 x ATR, never lowered) are the code batch 1 was judged with.

* TARGET: that same trade's gross return, fill to exit, in the instrument's own currency
  (fills.positions + simulate.run gross, compounded over the session). P15 changes no price, so
  the target ignores it; a P15-refused day keeps its training row and is ranked, not bought.
* TRADE RULE per (market, session): a bet's prediction = the mean of its eligible lines', its cost
  = the mean of its lines' own 1x round trips at GBP 300; it QUALIFIES above 2 x cost; the top 3
  by prediction - cost (ties by bet name) are chosen, every eligible line of a chosen bet bought.
* ELIGIBLE needs the entry to land before E -- read from the exchange calendar, so it is known at
  the decision moment whatever bars come later (``entry_possible``).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from qb2.execution import costs
from qb2.model import features
from qb2.research import bet_groups, fills, simulate, walk_forward
from qb2.research.names import NameData
from qb2.signals import s6_rules

STAKE_GBP = simulate.STAKE_GBP
QUALIFY, TOP = 2.0, 3
BAR = timedelta(hours=1)


def rule_entry(cid: str) -> dict[str, Any]:
    """What s6_rules.Rule reads from an entry: the stop is on every trade, k = 3."""
    return {"id": cid, "rule": "cm", "parameters": {"stop": True, "stop_k": 3.0}}


class CMRule(s6_rules.Rule):
    """s6_rules.Rule, triggered at bar 1's close on the chosen (name, day) pairs only."""

    def _trigger(self, s0: int, e: int, n: int, o: np.ndarray, h: np.ndarray, lo: np.ndarray,
                 c: np.ndarray, atr: np.ndarray, prior: float | None, day: date) -> int | None:
        return s0 if prior is not None and s0 < n and (self.symbol, day) in self.chosen else None


def maker(cid: str, chosen: set[tuple[str, date]]) -> Callable[[NameData], CMRule]:
    entry = rule_entry(cid)
    return lambda name: CMRule(entry, name, chosen)


def round_trip(name: NameData) -> float:
    """The name's own 1x round-trip cost at GBP 300, as a fraction (the one cost model)."""
    return float(costs.round_trip(name.instrument, STAKE_GBP).fraction)


def entry_possible(day: date, market: str) -> bool:
    """From the calendar alone: does a fill two bars after bar 1 land before E (the P4 cut bar)?"""
    sched = features.exchange_schedule([day], market)
    if day not in sched.index:
        return False
    open_, close = (pd.Timestamp(sched.loc[day, k]) for k in ("open", "close"))
    starts = pd.date_range(open_, close - pd.Timedelta(seconds=1), freq="1h")
    cut = close - fills.FLAT_BEFORE_CLOSE
    exit_at = next((i for i, t in enumerate(starts) if t + BAR > cut), len(starts) - 1)
    wait = BAR + pd.Timedelta(minutes=fills.ROW_O_DELAY_MINUTES[market])
    fill_at = next((i for i, t in enumerate(starts) if t >= open_ + wait), len(starts))
    return fill_at < exit_at


def targets(cid: str, name: NameData, days: set[date]) -> dict[date, float]:
    """Each chosen day's trade return, fill to exit after the stop, gross, own currency."""
    plan = replace(name.plan, may_enter=None)                     # P15 changes no price
    rule = CMRule(rule_entry(cid), replace(name, plan=plan), {(name.symbol, d) for d in days})
    held = fills.positions(plan, rule.weights(name.bars).to_numpy(dtype=float))
    o, c = name.bars["open"].to_numpy(dtype=float), name.bars["close"].to_numpy(dtype=float)
    gross = simulate.run(o, c, held, simulate.LegFractions(0.0, 0.0)).gross
    out = {}
    for s0, s1, day in s6_rules.sessions(pd.DatetimeIndex(name.bars.index), name.market):
        if day in days and held[s0:s1].any():
            out[day] = float(np.prod(1.0 + gross[s0:s1]) - 1.0)
    return out


def choose(preds: pd.DataFrame, cost: Mapping[str, float], *, groups: Mapping[str, str] | None = None,
           top: int = TOP) -> set[tuple[str, date]]:
    """The (symbol, day) pairs bought: per (market, session), bets above 2 x cost, top 3 by
    prediction - cost, ties by bet name; ``preds`` holds symbol, market, day, prediction."""
    known = bet_groups.load() if groups is None else groups
    if preds.empty:
        return set()
    frame = preds.assign(bet=[bet_groups.group_of(s, known) for s in preds["symbol"]],
                         cost=[float(cost[s]) for s in preds["symbol"]])
    chosen: set[tuple[str, date]] = set()
    for (_, day), group in frame.groupby(["market", "day"], sort=True):
        bets = group.groupby("bet").agg(prediction=("prediction", "mean"), cost=("cost", "mean"))
        bets = bets[bets["prediction"] > QUALIFY * bets["cost"]]
        bets = bets.assign(key=bets["prediction"] - bets["cost"]).reset_index()
        picked = set(bets.sort_values(["key", "bet"], ascending=[False, True]).head(top)["bet"])
        chosen |= {(str(s), day) for s, b in zip(group["symbol"], group["bet"]) if b in picked}
    return chosen


def graded(name: NameData, first_oos: date) -> NameData:
    """The name's bars from one firewall training window (63 sessions' worth) before its first
    bar dated on or after ``first_oos``, so the unchanged firewall grades from exactly that bar;
    unchanged when it has fewer bars before it (graded from its own mark, as in batch 1)."""
    days = pd.DatetimeIndex(name.bars.index).date
    start = int((days < first_oos).sum()) - walk_forward.default_sizes("1h", name.market)[0]
    if start <= 0:
        return name
    p = name.plan
    first = None if p.session_first is None else np.r_[True, p.session_first[start + 1:]]
    plan = fills.Schedule(p.n - start, p.fills[start:] - start, p.usable[start:], first,
                          None if p.forced_flat is None else p.forced_flat[start:],
                          None if p.may_enter is None else p.may_enter[start:])
    fx = None if name.fx is None else type(name.fx)(name.fx.open[start:], name.fx.close[start:],
                                                    name.fx.stale[start:])
    return replace(name, bars=name.bars.iloc[start:], plan=plan, fx=fx,
                   income=None if name.income is None else name.income[start:],
                   weight=None if name.weight is None else name.weight.iloc[start:])
