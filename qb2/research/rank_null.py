"""The advisor's skill-free books: the Deflated Sharpe's luck bar for the monthly slot book
(QT-21 C, the box's fix (i) of QT-19/20).

QT-20 measured why the coin-flip null spread 5-10x too wide on this book: a coin holds
every name half the time, re-flipped daily, eligible or not, so half the coins caught a
broken price the book can never hold. These null books follow the trial's OWN book and
differ from it only in the ranking:

* random ranks: one uniform draw per (seed, bet, month), so a rank changes only from one
  month to the next (the book reads a value only on a month-end decision bar);
* the trial's own everything else (advisor_book.build with its Settings): the same
  month-end decision bars, k = 20% of the eligible names, the 30% buffer, P10 stops with
  VIX, P13, the 1% ceiling and slot weights; the same eligibility -- 90% coverage over the
  rule's lookback AND a finite rule value on that bar (a name the rule cannot rank is
  never in the null either). A-06's market filter is the rule's, not the null's;
* priced by the SAME call as the book: firewall.score hands each null book to
  firewall.portfolio at the stress being judged (costs.py; tests assert the call).

Look-ahead: the ranks read no data; eligibility reads the rule's own values. The first
null book of every scoring is rebuilt on data cut at the book's three cut dates
(advisor_book.causal -- the book's own check) and refused if its past changed.

Advisor slot book only: S6/P19 keep the coin (firewall.score with no ``skill_free``).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from qb2.research import advisor_book, deflation
from qb2.signals import a_rules


def months(bars: pd.DataFrame) -> np.ndarray:
    return np.array([advisor_book.month_of(d) for d in pd.DatetimeIndex(bars.index).date])


def rule_values(rule: a_rules.Rule, names: Sequence[Any]) -> dict[str, np.ndarray]:
    """Each name's registered value at every bar -- the book's input."""
    return {n.symbol: rule.values(n.bars, n.bet, months(n.bars)) for n in names}


def ranks(seed: int, bet: int, month: np.ndarray) -> np.ndarray:
    """One uniform draw per (seed, bet, month), repeated on every bar of that month."""
    draw = {int(m): np.random.default_rng(np.random.SeedSequence([seed, bet, int(m)])).random()
            for m in np.unique(month)}
    return np.array([draw[int(m)] for m in month])


class Nulls:
    """The skill-free books of ONE scoring: ``draw(seed)`` is firewall.score's skill_free."""

    def __init__(self, entry: Mapping[str, Any], data: Sequence[Any], *,
                 vix: pd.Series | None, cuts: Sequence[date]) -> None:
        self.rule = a_rules.of(entry)
        self.settings = advisor_book.Settings.of(entry["parameters"], self.rule.lookback,
                                                 self.rule.ascending)
        self.data, self.vix, self.cuts = list(data), vix, list(cuts)
        self.ok = self.eligible(self.data)
        self.checked = False

    def eligible(self, names: Sequence[Any]) -> dict[str, np.ndarray]:
        return {s: np.isfinite(v) for s, v in rule_values(self.rule, names).items()}

    def book(self, seed: int, names: Sequence[Any],
             ok: Mapping[str, np.ndarray] | None = None) -> advisor_book.Book:
        mask = ok if ok is not None else self.eligible(names)
        values = {n.symbol: np.where(mask[n.symbol], ranks(seed, n.bet, months(n.bars)), np.nan)
                  for n in names}
        return advisor_book.build(self.settings, names, values, vix=self.vix)

    def draw(self, seed: int) -> tuple[Callable[[Any], advisor_book.Held], list[Any]]:
        built = self.book(seed, self.data, self.ok)
        if not self.checked:                          # the book's own look-ahead check
            advisor_book.causal(lambda names: self.book(seed, names), self.data, built, self.cuts)
            self.checked = True
        names = [replace(n, weight=built.weights[n.symbol]) for n in self.data]
        index = {n.symbol: pd.DatetimeIndex(n.bars.index) for n in names}
        return (lambda name: advisor_book.Held(name.symbol, index[name.symbol],
                                               built.decisions[name.symbol])), names


def analytic_sr0(returns: Sequence[float] | np.ndarray, n_trials: int) -> float | None:
    """(ii), DESCRIPTION ONLY: the luck bar from ONE book's own Sharpe noise (its moments,
    Bailey & Lopez de Prado). It differs from (i) by design: (i) measures how far skill-free
    books sit from EACH OTHER on the one shared history; (ii) how far one book's Sharpe sits
    from its true value -- the noise the PSR already charges in its own denominator."""
    try:                                              # None where the moments cannot be made
        sr, skew, kurt, t = deflation.moments(returns)
        var = (1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr * sr) / max(t - 1, 1)
        return deflation.expected_max_sharpe(max(n_trials, 2), var)
    except ValueError:
        return None
