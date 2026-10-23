"""The shadows: S-01..S-06 = A2-01..A2-06 unchanged, scored live from the arm date (QT-23 C), and
S-07, the slow trend filter on VWRL, from its own day 0 (QT-24 D).

Each, every processed session: advisor_book.build with its registered Settings and its twin's
rule values on the LIVE store's final bars (live.names), deciding nothing before the arm date
(``start``: cash until its first month-end decision on or after it); fills at the next bar's
open (fills.positions); per-bar returns from simulate.run -- the one trade arithmetic -- in
pounds (P3), costs.py at 1x and 2x, the survivorship mark-down on single shares; slots combined
by bet_groups.combine with the book's weights; compounded from the arm date.
R8: the lookback may read history to DECIDE, never to SCORE -- :func:`score` returns nothing
dated before the arm date (wall: tests/qb2/test_qt23_advisor.py). Counted 0: background scoring,
never shown as advice; a promotion is ADV-0's registered rule, and then only a PROPOSE.
backtest.run is not used: it rightly refuses bars past the holdout seal, and live bars are.
S-07 (registered cd3e863): trend_filter's month-end fills on VWRL's live bars, valued by ADV-0's own
scorecard (scorecard.day: as if sold at each close, 1x and 2x, dividends), from parameters'
scored_from -- never before it (:func:`start`); a row for a session before that never names it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from qb2.advisor import live, scorecard
from qb2.research import (advisor_book, backtest, bet_groups, fills, names, pounds, rank_null, simulate,
                          trend_filter)
from qb2.signals import a_rules

SHADOWS = tuple(f"S-0{j}" for j in range(1, 8))
STRESSES = (1.0, 2.0)


def book(entry: Mapping[str, Any], names: Sequence[names.NameData], vix: pd.Series, arm: date,
         market_on: Mapping[int, bool]) -> advisor_book.Book:
    """The shadow's book on live bars, deciding nothing before the arm date. ``market_on``: the
    A-06 filter (advisor_rules.filter_of) on live closes, read only by a filtered rule (S-06)."""
    rule = a_rules.of(entry)
    s = advisor_book.Settings.of(entry["parameters"], rule.lookback, rule.ascending)
    return advisor_book.build(s, names, rank_null.rule_values(rule, names), vix=vix,
                              market_on=market_on if rule.market_filter else None, start=arm)


def returns(b: advisor_book.Book, names: Sequence[names.NameData], arm: date,
            stress: float) -> pd.Series:
    """The pot's per-bar return from the arm date on: slots combined by the book's weights."""
    parts, weights = {}, {}
    for n in names:
        held = fills.positions(n.plan, np.asarray(b.decisions[n.symbol], dtype=float))
        opens, closes = n.bars["open"].to_numpy(dtype=float), n.bars["close"].to_numpy(dtype=float)
        if n.fx is not None:
            opens, closes = pounds.to_pounds(opens, closes, n.fx)
        paths = simulate.run(opens, closes, held, simulate.leg_fractions(n.instrument, stress),
                             backtest.drag_per_bar(n.instrument, "1d", n.market), n.income)
        on = live.days_of(n.bars.index, n.market) >= arm          # R8: scored from the arm date
        parts[n.symbol] = pd.Series(paths.marked[on], index=n.bars.index[on])
        weights[n.symbol] = b.weights[n.symbol][on]
    return bet_groups.combine(parts, None, weights) if parts else pd.Series(dtype=float)


def start(entry: Mapping[str, Any], arm: date) -> date:
    """The day a shadow's score starts: the arm date, or its own later day 0 (S-07)."""
    since = entry["parameters"].get("scored_from")
    return max(arm, date.fromisoformat(str(since))) if since else arm


def score(entry: Mapping[str, Any], names: Sequence[names.NameData], vix: pd.Series, arm: date,
          market_on: Mapping[int, bool]) -> dict[float, pd.Series]:
    """Each stress's compounded value (1.0 = the pot at the start), bar by bar, from the start."""
    if entry["rule"] == "trend_filter":
        return trend(entry, names, start(entry, arm))
    b = book(entry, names, vix, arm, market_on)
    return {s: (1.0 + returns(b, names, arm, s).fillna(0.0)).cumprod() for s in STRESSES}


def trend(entry: Mapping[str, Any], names: Sequence[names.NameData], since: date) -> dict[float, pd.Series]:
    """S-07 on its one line's live bars: the month-end fills (the history decides), each day's value
    as if sold at that close -- ADV-0's scorecard arithmetic -- from ``since`` only."""
    n = next(x for x in names if x.symbol == entry["parameters"]["line"])
    days = list(live.days_of(n.bars.index, n.market))
    month_end, week_end = trend_filter.calendar_ends(days)
    made = trend_filter.fills(days, month_end, week_end,
                              trend_filter.above(n.bars["close"].to_numpy(dtype=float), month_end), since)
    k0 = next((k for k, d in enumerate(days) if d >= since), len(days))
    book_ = [scorecard.Fill(days[t], side, "") for t, side in made]
    paid = n.income if n.income is not None else np.zeros(len(days))
    values = [scorecard.day(n.bars.iloc[k0:], days[k0:], book_, paid[k0:], n.instrument, k).value
              for k in range(len(days) - k0)]
    return {s: pd.Series([v[s] / scorecard.POT_GBP for v in values], index=n.bars.index[k0:], dtype=float)
            for s in STRESSES}


def row(scored: Mapping[str, Mapping[float, pd.Series]], entries: Mapping[str, Mapping[str, Any]],
        arm: date, d: date) -> dict[str, dict[str, float]]:
    """Each shadow's line for session ``d``, in % from its own start; none before that start."""
    out = {}
    for sid, by in scored.items():
        if d >= start(entries[sid], arm):
            at = {s: v[live.days_of(v.index, "LSE") <= d] for s, v in by.items()}
            out[sid] = {f"pct_{s:g}x": round((float(v.iloc[-1]) - 1) * 100, 4) if len(v) else 0.0
                        for s, v in at.items()}
    return out
