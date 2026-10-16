"""QT-21 C: the advisor's luck bar from random-rank books built by the trial's own rules.

Synthetic London names (offline); the register's real A-01 / A-03 entries. Each test
names the mutant it turns RED (docs/reports/QT-21_redfirst_c.txt): a daily re-flip
instead of monthly, a null without costs, a different k, a null that ignores
eligibility, a null that reads the future -- and S6/P19 keep the coin.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from qb2.execution import costs
from qb2.research import (advisor_book, advisor_data, advisor_run, benchmark, fills, firewall,
                          monte_carlo, preregister, rank_null, trial_log)
from qb2.research.strategy import LookAhead

DAYS = pd.DatetimeIndex(advisor_book.sessions("LSE", date(2014, 1, 1), date(2017, 6, 30))
                        ).tz_localize("Europe/London")


def _name(i: int, close: np.ndarray, days: pd.DatetimeIndex = DAYS) -> firewall.NameData:
    bars = pd.DataFrame({"open": close, "high": close * 1.002, "low": close * 0.998, "close": close,
                         "volume": 1e6}, index=days)
    return firewall.NameData(f"N{i}.L", "LSE", costs.Instrument(f"N{i}l_EQ", "GBP", "LSE", "STOCK"),
                             bars, fills.schedule(days, "1d", "LSE"), i)


def names(n: int = 10) -> list[firewall.NameData]:
    rng = np.random.default_rng(7)
    out = [_name(i, 100.0 * np.exp(np.cumsum(rng.normal(0.0003, 0.004, len(DAYS)))))   # calm: the
           for i in range(n - 2)]                                       # slot, not the 1%, binds
    out.append(_name(n - 2, np.full(len(DAYS), 50.0)))                  # flat: A-03 cannot rank it
    holed = DAYS[np.arange(len(DAYS)) % 4 != 0]                         # 75% coverage: never eligible
    out.append(_name(n - 1, 100.0 * np.exp(np.cumsum(rng.normal(0.001, 0.004, len(holed))))
                     , holed))
    return out


def built(cid: str, data: list[firewall.NameData]) -> tuple[advisor_book.Book, list[Any],
                                                             rank_null.Nulls]:
    token = preregister.require(cid)
    book, weighted = advisor_run.book_for(token.entry, data)
    nulls = rank_null.Nulls(token.entry, weighted, vix=advisor_data.vix(), cuts=advisor_run.cuts(data))
    return book, weighted, nulls


SEEDS = monte_carlo.trial_seeds(0, 4)


def test_null_books_share_the_books_k_slots_and_ceiling() -> None:            # mutant: different k
    book, weighted, nulls = built("A-01", names())
    assert any((~book.capped[n.symbol][300:]).all() for n in weighted)   # k shows in the weights
    for seed in SEEDS:
        null = nulls.book(seed, weighted)
        for n in weighted:
            pd.testing.assert_series_equal(null.weights[n.symbol], book.weights[n.symbol])
        assert null.buys and null.buys != book.buys                       # random, not the rule


def test_null_ranks_change_only_from_one_month_to_the_next() -> None:        # mutant: daily re-flip
    month = rank_null.months(names(1)[0].bars)
    r = rank_null.ranks(SEEDS[0], 3, month)
    for m in np.unique(month):
        assert len(set(r[month == m])) == 1
    assert len(set(r)) == len(np.unique(month))
    _, weighted, nulls = built("A-01", names())
    null = nulls.book(SEEDS[0], weighted)
    for sym, t in null.buys:                                             # bought on month-end bars only
        days = pd.DatetimeIndex(next(n for n in weighted if n.symbol == sym).bars.index).date
        assert t + 1 == len(days) or advisor_book.month_of(days[t + 1]) != advisor_book.month_of(days[t])


def test_null_never_holds_a_name_the_rule_cannot_rank() -> None:            # mutant: ignores eligibility
    _, weighted, nulls = built("A-03", names())
    flat, holed = weighted[-2].symbol, weighted[-1].symbol
    for seed in monte_carlo.trial_seeds(0, 12):
        null = nulls.book(seed, weighted)
        assert not null.decisions[flat].any() and not null.decisions[holed].any()


def test_the_null_is_priced_by_the_same_call_as_the_book(monkeypatch: pytest.MonkeyPatch,
                                                         ) -> None:      # mutants: no costs; the coin
    book, weighted, _ = built("A-01", names())
    calls: list[tuple[Any, ...]] = []
    real = firewall.portfolio

    def spy(token: Any, make: Any, data: Any, interval: str, stress: float, final: Any = None) -> Any:
        calls.append((make, list(data), interval, stress, final))
        return real(token, make, data, interval, stress, final)
    monkeypatch.setattr(firewall, "portfolio", spy)
    monkeypatch.setattr(benchmark, "over", lambda a, b, **kw: benchmark.Benchmark("VWRP.L", "stub", a, b, 0.0))
    advisor_run.score(preregister.require("A-01"), weighted, book, stress=2.0, n_null=3)
    observed, one, *rest = calls
    assert observed[3] == 2.0 and one[3] == 1.0 and len(rest) == 3
    for make, data, interval, stress, final in rest:
        assert (interval, stress, final) == ("1d", 2.0, None)              # the judged stress, costed
        assert [d.instrument for d in data] == [d.instrument for d in weighted]
        assert isinstance(make(data[0]), advisor_book.Held)               # a monthly book, not a coin
        held = sum(make(d).weights(d.bars).to_numpy().sum() for d in data)
        seen = sum(advisor_book.Held(w.symbol, pd.DatetimeIndex(w.bars.index), book.decisions[w.symbol]
                                     ).weights(w.bars).to_numpy().sum() for w in weighted)
        assert held != seen                                               # its own random book


def test_the_first_null_book_is_checked_for_look_ahead() -> None:           # mutant: the null peeks
    _, weighted, nulls = built("A-01", names())
    make, data = nulls.draw(SEEDS[0])
    assert nulls.checked and len(data) == len(weighted)

    class Peeking(rank_null.Nulls):
        def eligible(self, names: Any) -> dict[str, np.ndarray]:
            ok = super().eligible(names)
            return {s: np.r_[v[21:], np.zeros(21, dtype=bool)] for s, v in ok.items()}
    token = preregister.require("A-01")
    peek = Peeking(token.entry, weighted, vix=advisor_data.vix(), cuts=advisor_run.cuts(weighted))
    with pytest.raises(LookAhead):
        peek.draw(SEEDS[0])


def test_s6_and_p19_keep_the_coin(monkeypatch: pytest.MonkeyPatch) -> None:
    data = names(4)[:2]
    calls: list[Any] = []
    real = firewall.portfolio

    def spy(token: Any, make: Any, d: Any, interval: str, stress: float, final: Any = None) -> Any:
        calls.append((make, list(d)))
        return real(token, make, d, interval, stress, final)
    monkeypatch.setattr(firewall, "portfolio", spy)
    token = preregister.require("A-01")
    days = {n.symbol: pd.DatetimeIndex(n.bars.index) for n in data}
    flips = {s: (np.arange(len(i)) // 10 % 2).astype(float) for s, i in days.items()}   # many trades
    firewall.score(token, lambda n: advisor_book.Held(n.symbol, days[n.symbol], flips[n.symbol]),
                   data, interval="1d", n_null=2, log_path=None,
                   bench=lambda a, b: benchmark.Benchmark("VWRP.L", "stub", a, b, 0.0))
    assert len(calls) == 1 + 2                                            # the book, then two nulls
    for make, d in calls[1:]:
        assert isinstance(make(d[0]), monte_carlo.RandomStrategy) and d == data


def test_a_firewall_note_is_logged_and_counted_zero(tmp_path: Path) -> None:
    log = tmp_path / "trials.jsonl"
    trial_log.log_trial({"utc_time": "2026-10-17T00:00:00+00:00", "kind": trial_log.NOTE,
                         "candidate_id": "FIREWALL-QT21", "register_commit": "x",
                         "strategy_name": "firewall change", "params": {}, "metric_name": "n",
                         "metric_value": 42, "n_bars": 0}, path=log)
    n, seen = trial_log.count_selection_trials(log)
    assert n == 0 and seen["notes_excluded"] == 1


def test_the_analytic_bar_is_one_books_own_noise() -> None:
    r = np.random.default_rng(1).normal(0.0005, 0.01, 3000)
    sr0 = rank_null.analytic_sr0(r, 48)
    assert sr0 is not None and 0.03 < sr0 < 0.05                         # ~2.1 sd of a 3,000-bar Sharpe's noise
    assert replace(advisor_book.Settings(252, False), top=0.2).top == 0.2
