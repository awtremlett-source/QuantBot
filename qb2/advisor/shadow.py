"""The six shadows, S-01..S-06 = A2-01..A2-06 unchanged, scored live from the arm date (QT-23 C).

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
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from qb2.advisor import live
from qb2.research import advisor_book, backtest, bet_groups, fills, names, pounds, rank_null, simulate
from qb2.signals import a_rules

SHADOWS = tuple(f"S-0{j}" for j in range(1, 7))
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


def score(entry: Mapping[str, Any], names: Sequence[names.NameData], vix: pd.Series, arm: date,
          market_on: Mapping[int, bool]) -> dict[float, pd.Series]:
    """Each stress's compounded value (1.0 = the pot at the arm date), bar by bar, from the arm."""
    b = book(entry, names, vix, arm, market_on)
    return {s: (1.0 + returns(b, names, arm, s).fillna(0.0)).cumprod() for s in STRESSES}
