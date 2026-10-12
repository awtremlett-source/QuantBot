"""QT-16A: a fair luck test (turnover-matched null) and US returns in pounds. Offline.

Synthetic bars only; the real-store re-proof is ``python -m qb2.research.known_null``
and the session log. Each guard here was seen RED on the code before the fix.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from qb2.research import (backtest, fills, firewall, known_null, matched_null, pounds,
                          report, simulate, verdict)
from tests.qb2.test_qt14b_firewall import (US_STOCK, _bench, _data, _sessions,  # noqa: F401
                                           _token, register_repo)


def _runs(held: np.ndarray) -> list[tuple[int, int]]:
    s, e = matched_null.runs_of(held)
    return list(zip(s.tolist(), e.tolist(), strict=True))


# --------------------------------------------------- A1: the matched null --

def test_the_matched_null_keeps_count_and_lengths_and_never_overlaps() -> None:
    index = _sessions("US", 6)
    plan = fills.schedule(index, "5m", "US")
    held = np.zeros(len(index))
    for a, b in ((80, 92), (100, 101), (170, 200), (250, 252), (330, 345)):
        held[a:b] = 1.0
    prep = matched_null.prepare(held, plan, 78, len(index))
    for seed in range(20):
        new = matched_null.draw(prep, np.random.default_rng(seed))
        before, after = _runs(held[78:]), _runs(new[78:])
        assert sorted(e - s for s, e in before) == sorted(e - s for s, e in after)
        ok, session = matched_null.legal(plan)
        on = np.flatnonzero(new > 0)
        assert ok[on].all()                                     # delay + P4 respected
        for s, e in _runs(new):
            assert len(set(session[s:e])) == 1                  # inside one session
    one = matched_null.draw(prep, np.random.default_rng(3))
    same = matched_null.draw(prep, np.random.default_rng(3))
    other = matched_null.draw(prep, np.random.default_rng(4))
    assert np.array_equal(one, same) and not np.array_equal(one, other)  # seeded; it moves


def test_tightly_packed_sessions_still_fit_every_trade_every_time() -> None:
    index = _sessions("US", 3)
    plan = fills.schedule(index, "5m", "US")
    ok, session = matched_null.legal(plan)
    held = np.zeros(len(index))
    for day in range(3):
        first = np.flatnonzero(ok & (session == session[0] + day))[0]
        for k in range(12):                                     # 12 trades of 5, one gap
            held[first + 6 * k:first + 6 * k + 5] = 1.0
    prep = matched_null.prepare(held, plan, 0, len(index))
    for seed in range(20):
        new = matched_null.draw(prep, np.random.default_rng(seed))
        assert sorted(e - s for s, e in _runs(new)) == [5] * 36 and ok[new > 0].all()


def test_no_trade_lands_before_a_delayed_fill_or_after_the_p4_cut() -> None:
    index = _sessions("LSE", 3)
    plan = fills.schedule(index, "5m", "LSE")
    ok, _ = matched_null.legal(plan)
    assert plan.session_first is not None and plan.forced_flat is not None
    first = np.flatnonzero(plan.session_first)
    assert not ok[first].any() and not ok[first + 4].any() and ok[first + 5].all()
    assert not ok[plan.forced_flat].any()


def test_a_trade_crossing_the_window_edge_stays_where_it_was() -> None:
    plan = fills.schedule(pd.bdate_range("2024-01-02", periods=60, tz="America/New_York"),
                          "1d", "US")
    held = np.zeros(60)
    held[15:25] = 1.0                                           # crosses lo = 20
    held[40:43] = 1.0
    prep = matched_null.prepare(held, plan, 20, 60)
    for seed in range(10):
        new = matched_null.draw(prep, np.random.default_rng(seed))
        assert new[15:25].all() and new[25] == 0.0
        assert len(_runs(new[20:])) == 2


def test_when_placement_keeps_failing_each_trade_keeps_its_own_session(
        monkeypatch: pytest.MonkeyPatch) -> None:
    index = _sessions("US", 3)
    plan = fills.schedule(index, "5m", "US")
    ok, session = matched_null.legal(plan)
    held = np.zeros(len(index))
    for day, (a, b) in enumerate(((3, 40), (10, 12), (50, 70))):
        first = np.flatnonzero(session == session[0] + day)[0]
        held[first + a:first + b] = 1.0
    monkeypatch.setattr(matched_null, "RETRIES", 0)             # force the fallback
    prep = matched_null.prepare(held, plan, 0, len(index))
    new = matched_null.draw(prep, np.random.default_rng(0))
    assert [e - s for s, e in _runs(new)] == [e - s for s, e in _runs(held)]
    assert [session[s] for s, _ in _runs(new)] == [session[s] for s, _ in _runs(held)]
    assert ok[new > 0].all()


def _lazy(register_repo: Path) -> firewall.FirewallResult:  # noqa: F811
    token = _token(register_repo, "KN-LAZY-5m")
    return firewall.score(token, known_null.strategy_for(token.entry), _data("5m"),
                          interval="5m", n_null=30, bench=_bench, log_path=None)


def test_lazy_random_entries_fail_the_matched_luck_test(register_repo: Path) -> None:  # noqa: F811
    result = _lazy(register_repo)
    assert result.verdict.outcome == verdict.FAIL and "luck" in result.verdict.failed
    assert result.coin is not None and result.coin[0] < verdict.ALPHA   # beats the coin
    run = known_null.DrillRun("KN-LAZY-5m", 1.0, "FAIL", result, "luck")
    assert run.green


def test_against_the_old_coin_flip_luck_test_lazy_random_passes_it_red(
        register_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    """The pre-QT-16 firewall, restored: the coin-flip decides the luck test."""
    def coin_as_luck(seen: firewall.Portfolio, data: Any, interval: str,
                     seeds: Any) -> list[tuple[float, int]]:
        token = _token(register_repo, "KN-LAZY-5m")
        return [firewall._draw(firewall.portfolio(token, firewall._coin(s), data,  # noqa: SLF001
                                                  interval, 1.0), interval) for s in seeds]
    monkeypatch.setattr(firewall, "_matched", coin_as_luck)
    result = _lazy(register_repo)
    assert "luck" not in result.verdict.failed                  # RED: luck "beaten"
    assert not known_null.DrillRun("KN-LAZY-5m", 1.0, "FAIL", result, "luck").green


def test_the_report_names_the_luck_test_and_keeps_the_coin_flip_beside_it(
        register_repo: Path) -> None:  # noqa: F811
    text = report.render(_lazy(register_repo))
    assert "Luck test (turnover-matched null" in text and "Coin-flip null (description" in text
    assert "beats the turnover-matched luck test" in text


# ------------------------------------------------------ A2: pounds, not dollars --

def test_share_up_ten_dollar_down_ten_is_minus_one_percent_in_pounds() -> None:
    rates = pounds.Rates(np.array([1.0, 1.0]), np.array([1.0, 1 / 0.9]), np.zeros(2, bool))
    opens, closes = pounds.to_pounds(np.array([100.0, 100.0]), np.array([100.0, 110.0]), rates)
    paths = simulate.run(opens, closes, np.array([0.0, 1.0]), simulate.LegFractions(1e-9, 1e-9))
    assert paths.gross[1] == pytest.approx(-0.01)               # (1.10)(0.90) - 1


class _AlwaysIn:
    name = "always_in"

    def weights(self, bars: pd.DataFrame) -> pd.Series:
        return pd.Series(1.0, index=bars.index)


def test_the_backtest_pays_a_dollar_line_in_pounds(register_repo: Path) -> None:  # noqa: F811
    index = pd.bdate_range("2024-03-04", periods=2, tz="America/New_York")
    bars = pd.DataFrame({"open": [100.0, 100.0], "close": [100.0, 110.0]}, index=index)
    rates = pounds.Rates(np.array([1.0, 1.0]), np.array([1.0, 1 / 0.9]), np.zeros(2, bool))
    token = _token(register_repo, "KN-COIN-1d")
    run = backtest.run(token, _AlwaysIn(), bars, instrument=US_STOCK, interval="1d",
                       market="US", fx=rates, log_path=None)
    assert run.paths.gross[1] == pytest.approx(-0.01)
    with pytest.raises(pounds.NoRate, match="silent dollar"):
        backtest.run(token, _AlwaysIn(), bars, instrument=US_STOCK, interval="1d",
                     market="US", log_path=None)


def test_a_missing_fx_bar_while_held_makes_the_trial_insufficient_and_says_so(
        register_repo: Path) -> None:  # noqa: F811
    token = _token(register_repo, "KN-COIN-5m")
    data = _data("5m")
    aapl = data[0]
    assert aapl.fx is not None
    holed = pounds.Rates(aapl.fx.open.copy(), aapl.fx.close.copy(), aapl.fx.stale)
    holed.close[-200:] = np.nan                                 # inside the graded window
    data[0] = firewall.NameData(aapl.symbol, aapl.market, aapl.instrument, aapl.bars,
                                aapl.plan, aapl.bet, holed)
    result = firewall.score(token, known_null.strategy_for(token.entry), data,
                            interval="5m", n_null=5, bench=_bench, log_path=None)
    assert result.verdict.outcome == verdict.INSUFFICIENT
    assert any("no GBPUSD rate" in r for r in result.verdict.reasons)
    assert result.p_value is None                               # no null was dressed up


def test_rates_take_the_same_bar_then_a_recent_one_then_nothing() -> None:
    index = pd.date_range("2026-08-03 09:30", periods=6, freq="5min", tz="America/New_York")
    fx = pd.DataFrame({"open": [1.30, 1.31, 1.32, 1.33, 1.34, 1.35],
                       "close": [1.301, 1.311, 1.321, 1.331, 1.341, 1.351]},
                      index=index).drop(index[[1, 2, 3, 4]])
    got = pounds.align(index, fx, "5m")
    assert got.open[0] == 1.30 and got.close[0] == 1.301        # same moment
    assert got.open[1] == got.close[1] == 1.301 and got.stale[1]  # 5 min stale: allowed
    assert got.stale[2] and not got.missing[2]                  # 10 min: still allowed
    assert got.missing[3] and np.isnan(got.close[3])            # 15 min: missing
    assert got.open[5] == 1.35 and not got.stale[5]
    days = pd.bdate_range("2025-04-14", periods=3, tz="America/New_York")
    daily_fx = pd.DataFrame({"open": [1.3], "close": [1.31]},
                            index=pd.DatetimeIndex(["2025-04-11"], tz="Europe/London"))
    d = pounds.align(days, daily_fx, "1d")
    assert d.close[0] == 1.31 and d.stale[0] and d.stale[1]     # Fri for Mon and Tue
    assert d.missing[2]                                         # not for Wed (5 days)


def test_a_currency_with_no_rate_is_left_out_by_name(tmp_path: Path) -> None:
    entry = {"yfinance": "XEUR.L", "t212_ticker": "XEURl_EQ", "quote_currency": "EUR",
             "kind": "ETF", "exchange": "LSE"}
    data, skipped = firewall.load("1d", entries=[entry], clean_root=tmp_path)
    assert data == [] and "no EUR->GBP rate" in skipped[0]
    assert pounds.needs_rate("GBX") is False and pounds.needs_rate("USD") is True
