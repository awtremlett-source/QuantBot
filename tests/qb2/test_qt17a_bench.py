"""QT-17A: the seal's one door, a losing rule cannot beat luck, hourly bars testable. Offline.

Synthetic bars only; the real-store re-proofs are in the session log and
docs/research/known_null_2026-10-12_QT17_1h.md. Each guard was seen RED first.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import exchange_calendars as xcals  # type: ignore[import-untyped]
import numpy as np
import pandas as pd
import pytest

from qb2.execution import costs
from qb2.guard import earnings_window
from qb2.research import (benchmark, fills, firewall, holdout, matched_null, p15, pounds,
                          preregister, stats, trial_log, verdict, walk_forward)
from tests.qb2.test_qt14b_firewall import (_bench, _flat_fx, _sessions, _token,  # noqa: F401
                                           register_repo)

MSFT = costs.Instrument("MSFT_US_EQ", "USD", "US", "STOCK")


# ------------------------------------------- A2: a losing rule cannot beat luck --

class InTheStorm:
    """Long through each session's wild stretch (bars 30-39 once the delay lands)."""

    name = "in_the_storm"

    def weights(self, bars: pd.DataFrame) -> pd.Series:
        local = bars.index.tz_convert("America/New_York")
        place = pd.Series(local.date).groupby(local.date).cumcount().to_numpy()
        return pd.Series(((place >= 28) & (place < 38)).astype(float), index=bars.index)


def _clustered_losses() -> list[firewall.NameData]:
    """Calm bars, and in every session ten wild bars (+/-1.5% in turn, drifting down
    0.02% a bar): the rule holds exactly those, so it loses its costs and the drift
    every session -- clustered losses, very noisy returns. Random timing with the
    same trades mostly lands on calm bars: the same costs, far less noise, so a
    WORSE (more negative) Sharpe. The losing rule "beats luck" on p alone."""
    index = _sessions("US", 40)
    local = index.tz_convert("America/New_York")
    place = pd.Series(local.date).groupby(local.date).cumcount().to_numpy()
    rng = np.random.default_rng(17)
    storm = (place >= 30) & (place < 40)
    swing = np.where(place % 2 == 0, 0.015, -0.015) - 0.0002
    step = np.where(storm, swing, rng.normal(0, 0.0002, len(index)))
    close = 100 * np.exp(np.cumsum(step))
    opens = np.r_[100.0, close[:-1]]
    bars = pd.DataFrame({"open": opens, "high": np.maximum(opens, close) * 1.0001,
                         "low": np.minimum(opens, close) * 0.9999, "close": close,
                         "volume": 1000.0}, index=index)
    return [firewall.NameData("MSFT", "US", MSFT, bars, fills.schedule(index, "5m", "US"),
                              0, _flat_fx(len(bars)))]


def test_a_losing_rule_whose_losses_cluster_cannot_pass_the_luck_gate(
        register_repo: Path) -> None:  # noqa: F811
    token = _token(register_repo, "KN-LAZY-5m")              # any registered 5m drill
    result = firewall.score(token, lambda name: InTheStorm(), _clustered_losses(),
                            interval="5m", n_null=30, bench=_bench, log_path=None)
    mean = float(result.observed.marked.mean())
    assert mean < 0 and stats.compute(result.observed.marked, "5m").total_return < 0
    assert result.p_value is not None and result.p_value < verdict.ALPHA   # old Gate 1: "beats luck"
    assert result.verdict.outcome == verdict.FAIL
    assert "positive" in result.verdict.failed                             # new Gate 1: it cannot
    assert any("positive net mean per bar" in r for r in result.verdict.reasons)


def _judge(p: float, mean: float | None) -> verdict.Verdict:
    return verdict.judge(oos_trades=30, oos_bars=500, p_value=p, mean_per_bar=mean, dsr=0.99,
                         strategy_return=0.5, benchmark_return=0.0)


def test_the_luck_gate_needs_both_halves() -> None:
    assert _judge(0.001, 0.0001).passed
    losing = _judge(0.001, -0.0001)
    assert losing.failed == ("positive",) and not losing.passed
    assert "positive" in _judge(0.001, 0.0).failed                         # zero is not positive
    assert _judge(0.2, 0.0001).failed == ("luck",)
    assert _judge(0.001, None).outcome == verdict.INSUFFICIENT


# ------------------------------------------------------- A1: one door, logged --

def test_bars_through_refuses_the_seal_without_the_final_pass() -> None:
    with pytest.raises(holdout.Sealed):
        holdout.bars_through("VWRP.L", "1d", "LSE", through=date(2025, 10, 10))
    with pytest.raises(holdout.Sealed):
        holdout.bars_through("AAPL", "1h", "US", through=date(2026, 7, 13))
    with pytest.raises(holdout.Sealed):
        holdout.research_bars("AAPL", "1h", "US", through=date(2026, 8, 3))


def test_a_sealed_look_is_logged_and_counts_no_trial(tmp_path: Path) -> None:
    log = tmp_path / "trials.jsonl"
    trial_log.log_trial({"utc_time": "2026-10-12T21:00:00+00:00", "kind": trial_log.SEAL_VIEWED,
                         "candidate_id": "QT16-C2-stop-description", "register_commit": "none",
                         "strategy_name": "stop_description", "params": {},
                         "metric_name": "sealed_daily_year_viewed", "metric_value": 1,
                         "n_bars": 0}, path=log)
    n, seen = trial_log.count_selection_trials(log)
    assert n == 0 and seen["seal_viewed_excluded"] == 1


# ------------------------------------------------- A3: hourly bars, honestly --

def _hours(market: str, days: list[str], extra_after_close: bool = False) -> pd.DatetimeIndex:
    """1h bars as the store holds them: from each session's open, one an hour, while
    the hour starts before the close (US 09:30...15:30, London 08:00...16:00)."""
    cal = xcals.get_calendar(fills.CALENDARS[market])
    parts = []
    for day in days:
        opened, closed = cal.session_open(day), cal.session_close(day)
        starts = pd.date_range(opened, closed, freq="1h", inclusive="left")
        if extra_after_close:                    # a stray bar past the bell
            starts = starts.append(pd.DatetimeIndex([starts[-1] + pd.Timedelta(hours=1)]))
        parts.append(starts.tz_convert(fills.EXCHANGE_TZ[market]))
    return parts[0].append(parts[1:])


def _held_all_day(index: pd.DatetimeIndex, market: str,
                  may_enter: np.ndarray | None = None) -> np.ndarray:
    plan = fills.schedule(index, "1h", market, may_enter=may_enter)
    return fills.positions(plan, np.ones(len(index)))


def test_an_hourly_entry_fills_two_hours_later_never_at_the_decision_time() -> None:
    for market, first_fill in (("US", "11:30"), ("LSE", "10:00")):
        index = _hours(market, ["2026-06-02"])
        held = _held_all_day(index, market)
        # The decision at the first bar's close (10:30 NY / 09:00 London) cannot fill on
        # the bar opening at that very moment: the price is only seen after the delay.
        assert held[1] == 0.0, f"{market}: filled at the decision time"
        assert index[np.flatnonzero(held)[0]].strftime("%H:%M") == first_fill
        assert list(fills.fill_index(index, "1h", market)[:3]) == [2, 3, 4]


def test_hourly_p4_sells_at_the_last_bar_starting_by_the_cut() -> None:
    us, lse = _hours("US", ["2026-06-02"]), _hours("LSE", ["2026-06-02"])
    held_us, held_lse = _held_all_day(us, "US"), _held_all_day(lse, "LSE")
    assert [t.strftime("%H:%M") for t in us[held_us > 0]] == ["11:30", "12:30", "13:30",
                                                             "14:30"]
    assert held_us[-1] == 0.0 and us[-1].strftime("%H:%M") == "15:30"     # sold at 15:30 open
    assert lse[held_lse > 0][-1].strftime("%H:%M") == "15:00" and held_lse[-1] == 0.0


@pytest.mark.parametrize("market,day,last_held", [("US", "2025-11-28", "11:30"),
                                                   ("LSE", "2025-12-24", "11:00")])
def test_nothing_is_held_past_the_cut_on_a_half_day(market: str, day: str,
                                                    last_held: str) -> None:
    """Half days close early (13:00 New York, 12:30 London) from the exchange
    calendar; a stray bar after the bell must not keep the 12:xx hour held."""
    index = _hours(market, [day], extra_after_close=True)
    held = _held_all_day(index, market)
    cut = (pd.Timestamp(xcals.get_calendar(fills.CALENDARS[market]).session_close(day))
           - fills.FLAT_BEFORE_CLOSE)
    ends = pd.DatetimeIndex(index).tz_convert("UTC") + pd.Timedelta(hours=1)
    assert (ends[held > 0] <= cut).all(), "a bar held past the P4 cut-off"
    assert index[held > 0][-1].strftime("%H:%M") == last_held


def test_the_5m_cut_is_unchanged_by_the_hourly_rule() -> None:
    for market, cut in (("US", "15:45"), ("LSE", "16:15")):
        index = _sessions(market, 2)
        plan = fills.schedule(index, "5m", market)
        assert plan.forced_flat is not None
        local = np.asarray(index.tz_convert(fills.EXCHANGE_TZ[market]).strftime("%H:%M"))
        last = np.r_[local[1:] < local[:-1], True]
        assert (plan.forced_flat == ((local >= cut) | last)).all()


# ---------------------------------------------- A3: P15 inside the back-test --

def _earnings(known: list[str], day: str = "2026-06-04") -> pd.DataFrame:
    """Snapshots as the clean store keeps them: each fetch (knowable_time) lists this
    date and the next one, as the provider does -- the sender needs a NEXT date known
    after each announcement, or it blocks (fail closed)."""
    rows = [(d, k) for k in known for d in (day, "2026-09-03")]
    return pd.DataFrame({"symbol": "MSFT", "earnings_date": [d for d, _ in rows],
                         "knowable_time": [k for _, k in rows]})


SESSIONS = ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04", "2026-06-05",
            "2026-06-08", "2026-06-09"]
WINDOW = np.array([date(2026, 6, 3), date(2026, 6, 4), date(2026, 6, 5)])  # 4 June +/- 1 session


def test_the_backtest_asks_the_senders_own_earnings_check() -> None:
    """Bar by bar, the mask is exactly earnings_window.bot_verdict at the send moment."""
    index = _hours("US", SESSIONS)
    frame = _earnings(["2026-06-01T18:00:00+00:00", "2026-06-03T15:00:00+00:00"])
    got = p15.mask("MSFT", "STOCK", index, "1h", "US", frame)
    sent = pd.DatetimeIndex(index).tz_convert("UTC") + pd.Timedelta(minutes=61.25)
    want = [not earnings_window.bot_verdict("MSFT", "STOCK", "US", t.to_pydatetime(),
                                            frame).blocked for t in sent]
    assert got.tolist() == want
    day = pd.DatetimeIndex(index).date
    # unknown until 18:00 UTC on 1 June (fail closed); then the window 3-5 June blocks
    assert not got[day == date(2026, 6, 1)][:3].any() and got[day == date(2026, 6, 2)].all()
    assert not got[np.isin(day, WINDOW)].any() and got[day == date(2026, 6, 8)].all()
    assert p15.mask("ISF.L", "ETF", index, "1h", "US", None).all()       # ETF: N/A
    once = _earnings(["2026-05-01T00:00:00+00:00"]).query("earnings_date == '2026-06-04'")
    after = p15.mask("MSFT", "STOCK", index, "1h", "US", once)
    assert not after[day == date(2026, 6, 8)].any()          # no next date known: blocked


def test_no_entry_inside_an_earnings_window_and_sells_are_never_blocked() -> None:
    index = _hours("US", SESSIONS)
    frame = _earnings(["2026-05-01T00:00:00+00:00"])
    held = _held_all_day(index, "US", p15.mask("MSFT", "STOCK", index, "1h", "US", frame))
    window = np.isin(pd.DatetimeIndex(index).date, WINDOW)
    assert held[~window].any() and not held[window].any(), "traded inside the window"
    # A block that starts mid-session: the held position is not forced out, its sale
    # lands, and the next buy is refused.
    one = _hours("US", ["2026-06-02"])
    may = np.array([True, True, True, False, False, False, False])
    plan = fills.schedule(one, "1h", "US", may_enter=may)
    weights = np.array([1, 1, 1, 0, 1, 1, 1], dtype=float)
    assert fills.positions(plan, weights).tolist() == [0, 0, 1, 1, 1, 0, 0]


def test_the_matched_null_trades_only_where_an_entry_was_allowed() -> None:
    index = _hours("US", SESSIONS)
    allowed = p15.mask("MSFT", "STOCK", index, "1h", "US",
                       _earnings(["2026-05-01T00:00:00+00:00"]))
    ok, _ = matched_null.legal(fills.schedule(index, "1h", "US", may_enter=allowed))
    day = pd.DatetimeIndex(index).date
    assert not ok[np.isin(day, WINDOW)].any()
    assert ok[day == date(2026, 6, 8)].sum() == 4                         # 11:30 ... 14:30


# --------------------------------------------- A3: the 1h seal, FX, benchmark --

def _store(root: Path, symbol: str, index: pd.DatetimeIndex, close: np.ndarray) -> None:
    folder = root / "bars" / "1h" / symbol
    folder.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"open": close, "high": close, "low": close, "close": close,
                  "volume": 1.0}, index=index).to_parquet(folder / "2026-07.parquet")


def test_hourly_research_stops_before_2026_07_13(tmp_path: Path) -> None:
    index = _hours("US", ["2026-07-09", "2026-07-10", "2026-07-13", "2026-07-14"])
    _store(tmp_path, "AAPL", index, np.linspace(100, 101, len(index)))
    got = holdout.research_bars("AAPL", "1h", "US", clean_root=tmp_path)
    assert pd.DatetimeIndex(got.index).date.max() == date(2026, 7, 10) and len(got) == 14
    with pytest.raises(holdout.Sealed):
        holdout.check_unsealed(index, "1h", "US")
    with pytest.raises(holdout.Sealed):
        holdout.bars_through("AAPL", "1h", "US", through=date(2026, 7, 13), clean_root=tmp_path)


def test_hourly_fx_takes_the_last_rate_known_at_each_moment() -> None:
    shares = _hours("US", ["2026-06-02"])                         # 09:30 ... 15:30 NY
    hours = pd.date_range("2026-06-02 08:00", "2026-06-02 17:00", freq="1h",
                          tz="America/New_York")
    fx = pd.DataFrame({"open": np.arange(len(hours), dtype=float) + 1.0,
                       "close": np.arange(len(hours), dtype=float) + 1.5}, index=hours)
    fx = fx.drop(hours[[4, 5, 6, 7]])                             # 12:00-15:00 missing
    rates = pounds.align(shares, fx, "1h")
    assert rates.open[0] == 2.0 and rates.close[0] == 3.0          # 09:00 open, 10:00 open
    assert rates.stale[2] and not rates.stale[0]                   # 11:30 bar ends 12:30
    assert np.isnan(rates.close[4]) and np.isnan(rates.open[5])    # > 3 hours past 11:00


def test_the_hourly_benchmark_is_vwrp_hourly_through_the_door(tmp_path: Path) -> None:
    index = _hours("LSE", ["2026-06-01", "2026-06-02", "2026-06-03"])
    close = np.r_[[100.0] * 9, [101.0] * 9, [110.0] * 8, [111.1]]
    _store(tmp_path, "VWRP.L", index, close)
    got = benchmark.over(date(2026, 6, 2), date(2026, 6, 3), interval="1h",
                         chosen=("VWRP.L", "stub"), clean_root=tmp_path)
    assert got.total_return == pytest.approx(111.1 / 100.0 - 1.0)
    with pytest.raises(benchmark.MissingBenchmark):
        benchmark.over(date(2026, 6, 2), date(2026, 6, 3), interval="1h",
                       chosen=("VWRL.L", "stub"), clean_root=tmp_path)
    with pytest.raises(holdout.Sealed):
        benchmark.over(date(2026, 7, 1), date(2026, 7, 13), interval="1h",
                       chosen=("VWRP.L", "stub"), clean_root=tmp_path)
    # QT-14..16's 5m benchmark read DAILY VWRP inside the daily seal: refused now
    with pytest.raises(holdout.Sealed):
        benchmark.over(date(2026, 7, 21), date(2026, 9, 18), interval="1d",
                       chosen=("VWRP.L", "stub"), clean_root=tmp_path)


def test_hourly_walk_forward_is_a_quarter_then_months() -> None:
    assert walk_forward.default_sizes("1h", "US") == (63 * 7, 21 * 7)
    assert walk_forward.default_sizes("1h", "LSE") == (63 * 9, 21 * 9)
    assert stats.periods_per_year("1h", "LSE") == 252 * 9
    assert "1h" in preregister.BAR_SIZES


def test_the_firewall_loads_hourly_bars_with_the_p15_mask(tmp_path: Path) -> None:
    """Wired at the loader: a share whose earnings dates were first recorded AFTER the
    bars (the real store's case: every snapshot is from 2026-10-02 on). QT-17: blocked
    on every bar. QT-18 A1 (operator GO, 2026-10-16): the history rule -- 4 June is
    the first date on record, never known early, so blocked through its window (to
    5 June); 3 Sep is known from 4 June's close, so 8-9 June may trade. An ETF: N/A."""
    index = _hours("US", SESSIONS)
    _store(tmp_path, "MSFT", index, np.linspace(100, 101, len(index)))
    _store(tmp_path, "ISF.L", _hours("LSE", SESSIONS), np.linspace(5, 5.1, 9 * 7))
    (tmp_path / "earnings").mkdir()
    _earnings(["2026-10-02T17:50:45+00:00"]).to_parquet(tmp_path / "earnings" / "MSFT.parquet")
    entries = [{"yfinance": "MSFT", "t212_ticker": "MSFT_US_EQ", "quote_currency": "USD",
                "kind": "STOCK", "exchange": "NASDAQ"},
               {"yfinance": "ISF.L", "t212_ticker": "ISFl_EQ", "quote_currency": "GBX",
                "kind": "ETF", "exchange": "London Stock Exchange"}]
    data, skipped = firewall.load("1h", entries=entries, clean_root=tmp_path)
    assert skipped == [] and [d.symbol for d in data] == ["MSFT", "ISF.L"]
    share, fund = data
    assert share.plan.may_enter is not None
    day = pd.DatetimeIndex(index).date
    assert not share.plan.may_enter[day <= date(2026, 6, 5)].any()
    assert share.plan.may_enter[day >= date(2026, 6, 8)].all()
    assert fund.plan.may_enter is not None and fund.plan.may_enter.all()
    held = fills.positions(share.plan, np.ones(len(index)))
    assert not held[day <= date(2026, 6, 5)].any() and held[day >= date(2026, 6, 8)].any()
