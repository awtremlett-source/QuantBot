"""QT-21 B: the bench guard -- one bar carrying > 25% of a result's variance is INSUFFICIENT.

Red-on-broken (SCARS #9), on real books saved from the OLD (uncleaned) store
(tests/qb2/fixtures/qt21/guard_books_old_data.csv, made before Part A): the QT-19
coin book that held SMEA.L into its broken 2023-11-27 open (that bar: ~90% of its
variance) and a random-rank book on the same data (~1.5%). The mutant record (guard
removed -> RED) is docs/reports/QT-21_redfirst_b.txt.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from qb2.execution import costs
from qb2.research import advisor_book, advisor_run, benchmark, fills, firewall, preregister, verdict

BOOKS = Path(__file__).parent / "fixtures" / "qt21" / "guard_books_old_data.csv"
GOOD: dict[str, Any] = {"oos_trades": 500, "oos_bars": 5815, "p_value": 0.005, "mean_per_bar": 0.001,
        "dsr": 0.99, "strategy_return": 3.0, "benchmark_return": 2.0}   # every check met


def book(column: str) -> np.ndarray:
    out: np.ndarray = pd.read_csv(BOOKS, index_col=0)[column].to_numpy(dtype=float)
    return out


def test_the_qt19_coin_book_on_the_old_data_is_insufficient() -> None:
    share = verdict.top_bar_share(book("coin_old_data"))
    assert share == pytest.approx(0.905, abs=0.005)
    got = verdict.judge(**GOOD, top_share=share)
    assert got.outcome == verdict.INSUFFICIENT and not got.passed
    assert "one bar carries 90%" in got.reasons[0]


def test_a_clean_book_is_judged() -> None:
    share = verdict.top_bar_share(book("rank_old_data"))
    assert share == pytest.approx(0.015, abs=0.005)
    assert verdict.judge(**GOOD, top_share=share).outcome == verdict.PASS
    worse = {**GOOD, "dsr": 0.10}
    assert verdict.judge(**worse, top_share=share).outcome == verdict.FAIL


def test_the_share_is_one_bars_squared_deviation_over_the_total() -> None:
    r = np.array([0.0, 0.0, 0.0, 1.0])                  # mean 0.25: 0.5625 of 0.75
    assert verdict.top_bar_share(r) == pytest.approx(0.75)
    assert verdict.top_bar_share(np.zeros(5)) == 0.0 and verdict.top_bar_share([]) == 0.0
    assert verdict.judge(**GOOD, top_share=0.25).outcome == verdict.PASS     # > 25%, not >=


def test_the_firewall_hands_the_judged_series_to_the_guard() -> None:
    days = pd.DatetimeIndex(advisor_book.sessions("LSE", date(2015, 1, 1), date(2016, 6, 30))
                            ).tz_localize("Europe/London")
    close = np.full(len(days), 100.0)
    close[200:] = 300.0                                  # one bar triples the price
    bars = pd.DataFrame({"open": close, "high": close, "low": close, "close": close,
                         "volume": 1e6}, index=days)
    name = firewall.NameData("X.L", "LSE", costs.Instrument("Xl_EQ", "GBP", "LSE", "STOCK"), bars,
                             fills.schedule(days, "1d", "LSE"), 0)
    token = preregister.require("KN-A-RANDOM-1d")
    result = firewall.score(token, lambda n: advisor_run.Held("X.L", days, np.ones(len(days))),
                            [name], interval="1d", n_null=2, log_path=None,
                            bench=lambda a, b: benchmark.Benchmark("VWRP.L", "stub", a, b, 0.0))
    assert result.verdict.outcome == verdict.INSUFFICIENT
    assert any(r.startswith("one bar carries") for r in result.verdict.reasons)
