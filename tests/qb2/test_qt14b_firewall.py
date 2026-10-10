"""QT-14B: firewall v2 -- pre-registration, honest fills, benchmark, known-null. Offline.

Synthetic bars only (the real-store gate is run by ``python -m
qb2.research.known_null`` and recorded in the session log). The known-null tests
here also prove each gate goes RED on the breakage it guards: the delay removed
(Gate 1) and costs switched off (Gate 2).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

import exchange_calendars as xcals  # type: ignore[import-untyped]
import numpy as np
import pandas as pd
import pytest

from qb2.execution import costs, ledger_backup
from qb2.ingest import verify_universe
from qb2.research import (backtest, bet_groups, benchmark, fills, firewall, holdout,
                          known_null, monte_carlo, preregister, report, simulate,
                          strategy, trial_log, verdict, walk_forward)

REPO = Path(__file__).resolve().parents[2]
PLAN = REPO / "docs" / "plan" / "PLAN_V3.md"
US_STOCK = costs.Instrument("AAPL_US_EQ", "USD", "US", "STOCK")
UK_SHARE = costs.Instrument("AZNl_EQ", "GBX", "LSE", "STOCK")
UK_ETF = costs.Instrument("ISFl_EQ", "GBX", "LSE", "ETF")


# ------------------------------------------------------------------ helpers --

def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t",
                    *args], check=True, capture_output=True)


@pytest.fixture(scope="module")
def register_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A git repo holding a COMMITTED copy of the real register."""
    root = tmp_path_factory.mktemp("reg")
    (root / "docs" / "research").mkdir(parents=True)
    shutil.copy(REPO / preregister.REGISTER_REL, root / preregister.REGISTER_REL)
    _git(root, "init", "-q")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "register")
    return root


def _token(root: Path, cid: str) -> preregister.Registered:
    return preregister.require(cid, root=root)


def _sessions(market: str, days: int, start: str = "2026-06-01") -> pd.DatetimeIndex:
    tz, opens = fills.EXCHANGE_TZ[market], ("09:30" if market == "US" else "08:00")
    per = 78 if market == "US" else 102
    parts = [pd.date_range(f"{d.date()} {opens}", periods=per, freq="5min", tz=tz)
             for d in pd.bdate_range(start, periods=days)]
    return parts[0].append(parts[1:])


def _bars(index: pd.DatetimeIndex, seed: int, vol: float = 0.001) -> pd.DataFrame:
    close = 100 * np.exp(np.cumsum(np.random.default_rng(seed).normal(0, vol, len(index))))
    opens = np.r_[100.0, close[:-1]]
    return pd.DataFrame({"open": opens, "high": np.maximum(opens, close) * 1.0005,
                         "low": np.minimum(opens, close) * 0.9995, "close": close,
                         "volume": 1000.0}, index=index)


NAMES = [("AAPL", US_STOCK), ("GOOG", costs.Instrument("GOOG_US_EQ", "USD", "US", "STOCK")),
         ("GOOGL", costs.Instrument("GOOGL_US_EQ", "USD", "US", "STOCK")), ("AZN.L", UK_SHARE),
         ("VUAG.L", costs.Instrument("VUAGl_EQ", "GBP", "LSE", "ETF")),
         ("VUSA.L", costs.Instrument("VUSAl_EQ", "GBP", "LSE", "ETF")), ("ISF.L", UK_ETF),
         ("MSFT", costs.Instrument("MSFT_US_EQ", "USD", "US", "STOCK"))]


def _data(interval: str) -> list[firewall.NameData]:
    groups = bet_groups.load()
    bets = sorted({bet_groups.group_of(s, groups) for s, _ in NAMES})
    out = []
    for i, (symbol, inst) in enumerate(NAMES):
        index = (_sessions(inst.market, 40) if interval == "5m" else
                 pd.bdate_range("2023-10-02", periods=500, tz=fills.EXCHANGE_TZ[inst.market]))
        bars = _bars(index, 100 + i, 0.001 if interval == "5m" else 0.012)
        out.append(firewall.NameData(symbol, inst.market, inst, bars,
                                     fills.schedule(bars.index, interval, inst.market),
                                     bets.index(bet_groups.group_of(symbol, groups))))
    return out


def _bench(start: date, end: date) -> benchmark.Benchmark:
    return benchmark.Benchmark("VWRP.L", "synthetic stub", start, end, 0.02)


# ------------------------------------------------------ B2: pre-registration --

def test_an_unregistered_candidate_cannot_be_scored(register_repo: Path) -> None:
    with pytest.raises(preregister.NotRegistered, match="not in"):
        preregister.require("P19-99-5m", root=register_repo)
    bars = _bars(_sessions("US", 3), 1)
    for call in (lambda: backtest.run(object(), strategy.Flat(), bars,  # type: ignore[arg-type]
                                      instrument=US_STOCK, interval="5m", market="US"),
                 lambda: firewall.score(object(), lambda n: strategy.Flat(), [],  # type: ignore[arg-type]
                                        interval="5m", log_path=None),
                 lambda: walk_forward.walk_forward(object(), walk_forward.Fixed(  # type: ignore[arg-type]
                     strategy.Flat()), bars, instrument=US_STOCK, interval="5m", market="US"),
                 lambda: holdout.open_final_run(object())):  # type: ignore[arg-type]
        with pytest.raises(preregister.NotRegistered):
            call()
    with pytest.raises(preregister.NotRegistered):
        preregister.Registered(entry={}, commit="x", committed_at="y")


def test_registered_but_uncommitted_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "docs" / "research").mkdir(parents=True)
    register = root / preregister.REGISTER_REL
    entry = json.loads((REPO / preregister.REGISTER_REL).read_text(encoding="utf-8"))
    first = dict(entry, entries=entry["entries"][:1])
    register.write_text(json.dumps(first), encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "one entry")
    register.write_text(json.dumps(dict(entry, entries=entry["entries"][:2])), encoding="utf-8")
    assert preregister.require(entry["entries"][0]["id"], root=root).commit
    with pytest.raises(preregister.NotRegistered, match="NOT committed"):
        preregister.require(entry["entries"][1]["id"], root=root)
    changed = dict(entry["entries"][0], parameters={"ema": 10})
    register.write_text(json.dumps(dict(entry, entries=[changed])), encoding="utf-8")
    with pytest.raises(preregister.NotRegistered, match="changed after"):
        preregister.require(entry["entries"][0]["id"], root=root)


def test_p19s_eighteen_trials_are_registered_exactly_as_the_plan_lists_them() -> None:
    entries = preregister.entries()
    trials = [e for e in entries.values() if e["kind"] == "trial"]
    assert len(trials) == 18
    assert {(e["bar_size"]) for e in trials} == {"5m", "1d"}
    table = [line for line in PLAN.read_text(encoding="utf-8").splitlines()
             if line.startswith("| ") and line.split("|")[1].strip().isdigit()]
    plan_rules = {int(r.split("|")[1]): (r.split("|")[2].strip(), r.split("|")[3].strip())
                  for r in table[:9]}
    for bar in ("5m", "1d"):
        for n, (name, entry_rule) in plan_rules.items():
            e = entries[f"P19-{n:02d}-{bar}"]
            assert (e["name"], e["entry_rule"]) == (name, entry_rule)
            assert e["date"] == "2026-10-10" and "mirror of the entry" in e["exit_rule"]
            assert e["side"] == "long-only" and e["holdout"]
    keltner = entries["P19-08-5m"]["parameters"]
    assert keltner == {"middle": "EMA 21", "atr": "Wilder ATR(14)", "multiple": 2.0}
    assert all("(P4)" in e["exit_rule"] for e in trials if e["bar_size"] == "5m")


# ------------------------------------------------------------- B2: holdout --

def test_the_holdout_dates_are_the_ones_fixed() -> None:
    assert holdout.SEALED_FROM == {"1d": date(2025, 10, 10), "5m": date(2026, 9, 21)}
    for code in ("XNYS", "XLON"):
        sessions = xcals.get_calendar(code).sessions_in_range("2026-08-01", "2026-10-09")
        assert sessions[-15].date() == holdout.SEALED_FROM["5m"]


def test_any_read_of_sealed_data_is_refused(register_repo: Path, tmp_path: Path) -> None:
    with pytest.raises(holdout.Sealed):
        holdout.research_bars("AAPL", "5m", "US", through=date(2026, 9, 21))
    sealed = _bars(_sessions("US", 2, start="2026-09-21"), 3)
    with pytest.raises(holdout.Sealed):
        holdout.check_unsealed(sealed.index, "5m", "US")
    token = _token(register_repo, "P19-01-5m")
    with pytest.raises(holdout.Sealed):
        backtest.run(token, strategy.Flat(), sealed, instrument=US_STOCK, interval="5m",
                     market="US", log_path=None)
    once = holdout.open_final_run(token, spent=tmp_path / "s.jsonl",
                                  log_path=tmp_path / "t.jsonl")
    holdout.check_unsealed(sealed.index, "5m", "US", once)        # the one look
    with pytest.raises(holdout.Sealed, match="already"):
        holdout.open_final_run(token, spent=tmp_path / "s.jsonl", log_path=tmp_path / "t.jsonl")
    with pytest.raises(holdout.Sealed):
        holdout.HoldoutPass("P19-01-5m", "now")


# ------------------------------------------------ B4: delay rule (c), P4 ------

def test_fills_land_where_hand_arithmetic_says() -> None:
    us = _sessions("US", 1)
    lse = _sessions("LSE", 1)
    # US: 10:00 bar closes 10:05, +1.25 min -> 10:06:15 -> first start 10:10 = 2 bars on
    assert fills.fill_index(us, "5m", "US")[6] == 8
    # London: 09:00 bar closes 09:05, +16.66 min -> 09:21:40 -> first start 09:25 = 5 on
    assert fills.fill_index(lse, "5m", "LSE")[12] == 17
    days = pd.bdate_range("2024-01-02", periods=5, tz="Europe/London")
    assert list(fills.fill_index(days, "1d", "LSE")) == [1, 2, 3, 4, 5]


def test_nothing_is_held_overnight_and_late_signals_never_carry() -> None:
    index = _sessions("US", 2)
    plan = fills.schedule(index, "5m", "US")
    held = fills.positions(plan, np.ones(len(index)))
    day = pd.DatetimeIndex(index).tz_convert("America/New_York")
    assert held[0] == 0 and held[1] == 0 and held[2] == 1           # 2 bars to fill
    late = (day.hour == 15) & (day.minute >= 45)
    assert (held[late] == 0).all()                                   # sold by 15:45
    assert held[78] == 0 and held[79] == 0 and held[80] == 1         # day 2 starts flat
    only_last = np.zeros(len(index))
    only_last[70:78] = 1.0                                           # signals at 15:20+
    assert fills.positions(plan, only_last)[78:].sum() == 0


# ------------------------------------------------- B4: costs inside, gross/net --

def test_there_is_no_zero_cost_path() -> None:
    for stress in (0.0, 0.5, 0.99):
        with pytest.raises(ValueError, match="never below 1x"):
            simulate.leg_fractions(US_STOCK, stress)
    from qb2.data import universe
    for entry in universe.bot_entries():
        legs = simulate.leg_fractions(firewall.instrument_of(entry), 1.0)
        assert legs.buy > 0 and legs.sell > 0


def test_stamp_duty_on_uk_share_buys_and_fx_on_us_legs() -> None:
    uk, etf, us = (simulate.leg_fractions(i, 1.0) for i in (UK_SHARE, UK_ETF, US_STOCK))
    assert uk.buy - uk.sell == pytest.approx(costs.STAMP_DUTY_RATE)
    assert etf.buy == pytest.approx(etf.sell)
    bp = costs.BASIS_POINT
    assert us.buy == pytest.approx((3 + costs.SLIPPAGE_BPS) * bp + costs.FX_FEE_RATE)
    assert us.sell == pytest.approx(us.buy)                         # FX on BOTH legs
    assert etf.buy == pytest.approx((8 + costs.SLIPPAGE_BPS) * bp)  # sterling ETF: no FX
    two = simulate.leg_fractions(UK_SHARE, 2.0)
    assert two.buy == pytest.approx(2 * uk.buy)


def test_the_trade_arithmetic_by_hand() -> None:
    opens = np.array([100.0, 101.0, 102.0, 104.0])
    closes = np.array([100.5, 101.5, 103.0, 104.5])
    held = np.array([0.0, 1.0, 1.0, 0.0])
    legs = simulate.LegFractions(0.001, 0.002)
    out = simulate.run(opens, closes, held, legs)
    assert out.gross[1] == pytest.approx((101.5 - 101.0) / 101.0)
    assert out.gross[2] == pytest.approx((102 - 101.5) / 101 + (103 - 102) / 101)
    assert out.gross[3] == pytest.approx((104 - 103) / 101)          # gap, then sold
    assert out.net[1] == pytest.approx(out.gross[1] - 0.001)
    assert out.net[3] == pytest.approx(out.gross[3] - 0.002)
    assert out.gross.sum() == pytest.approx((104 - 101) / 101)


def test_gross_and_net_both_reported_and_net_is_lower(register_repo: Path) -> None:
    bars = _bars(_sessions("LSE", 5), 9)
    token = _token(register_repo, "KN-COIN-5m")
    one = backtest.run(token, monte_carlo.RandomStrategy(0.5, 1), bars, instrument=UK_SHARE,
                       interval="5m", market="LSE", log_path=None)
    two = backtest.run(token, monte_carlo.RandomStrategy(0.5, 1), bars, instrument=UK_SHARE,
                       interval="5m", market="LSE", stress=2.0, log_path=None)
    assert one.trades > 0
    assert one.paths.net.sum() < one.paths.gross.sum()
    assert two.paths.net.sum() < one.paths.net.sum()
    assert one.paths.gross.sum() == pytest.approx(two.paths.gross.sum())


def test_survivorship_mark_down_hits_single_shares_only() -> None:
    assert backtest.drag_per_bar(UK_ETF, "1d", "LSE") == 0.0
    assert backtest.drag_per_bar(US_STOCK, "1d", "US") == pytest.approx(0.01 / 252)
    assert "not measured on these names" in backtest.SURVIVORSHIP_LABEL


# ------------------------------------------------------- the strategy contract --

class _Peeker:
    name = "peeker"

    def weights(self, bars: pd.DataFrame) -> pd.Series:
        return (bars["close"].shift(-1) > bars["close"]).astype(float)


def test_a_strategy_that_reads_the_future_is_refused(register_repo: Path) -> None:
    bars = _bars(_sessions("US", 3), 4)
    with pytest.raises(strategy.LookAhead):
        backtest.run(_token(register_repo, "KN-COIN-5m"), _Peeker(), bars,
                     instrument=US_STOCK, interval="5m", market="US", log_path=None)


class _Twice:
    """Two identical grid entries: forces walk-forward's fitting path."""

    def __init__(self, inner: strategy.Strategy) -> None:
        self.inner, self.name = inner, inner.name

    def param_grid(self) -> list[dict[str, Any]]:
        return [{"a": 1}, {"a": 2}]

    def build(self, params: dict[str, Any]) -> strategy.Strategy:
        return self.inner


def test_walk_forward_fast_path_equals_fold_by_fold_grading(register_repo: Path) -> None:
    bars = _bars(_sessions("US", 25), 5)
    token = _token(register_repo, "KN-COIN-5m")
    coin = monte_carlo.RandomStrategy(0.5, 7)
    kw: dict[str, Any] = dict(instrument=US_STOCK, interval="5m", market="US", log_path=None)
    fast = walk_forward.walk_forward(token, walk_forward.Fixed(coin), bars, **kw)
    slow = walk_forward.walk_forward(token, _Twice(coin), bars, **kw)
    assert len(fast.folds) == len(slow.folds) >= 2 and fast.total_trials == 1
    np.testing.assert_allclose(fast.oos["net"].to_numpy(), slow.oos["net"].to_numpy())


# --------------------------------------------------------------- B3: trials --

def test_drills_are_logged_but_never_counted(tmp_path: Path) -> None:
    log = tmp_path / "trials.jsonl"
    base = {"utc_time": "t", "candidate_id": "x", "register_commit": "c",
            "strategy_name": "s", "params": {"total_trials": 3}, "metric_name": "m",
            "metric_value": 0.0, "n_bars": 1}
    for kind in ("drill", "drill", "firewall", "backtest", "walk_forward", "monte_carlo"):
        trial_log.log_trial({**base, "kind": kind}, path=log)
    n, seen = trial_log.count_selection_trials(log)
    assert n == 1 + 1 + 3 and seen["drills_excluded"] == 2
    assert trial_log.DEFAULT_TRIAL_LOG.as_posix().endswith("data/qb2/trials.jsonl")
    with pytest.raises(ValueError):
        trial_log.log_trial({**base, "kind": "mystery"}, path=log)


def test_the_trial_log_is_backed_up_and_staleness_is_seen(tmp_path: Path) -> None:
    log = tmp_path / "trials.jsonl"
    log.write_text('{"a": 1}\n', encoding="utf-8")
    dest = tmp_path / "remote"
    assert "never been backed up" in ledger_backup.stale(log, dest=dest, environ={})
    assert "verified" in ledger_backup.backup(log, dest=dest, folder=ledger_backup.TRIALS_FOLDER)
    assert ledger_backup.stale(log, dest=dest, environ={}) == ""
    log.write_text('{"a": 1}\n{"b": 2}\n', encoding="utf-8")
    assert "changed since" in ledger_backup.stale(log, dest=dest, environ={})


# ----------------------------------------------------------- B4: bet groups --

def test_the_bet_group_file_covers_both_pairs() -> None:
    groups = bet_groups.load()
    assert groups["GOOG"] == groups["GOOGL"] and groups["VUAG.L"] == groups["VUSA.L"]
    assert groups["GOOG"] != groups["VUAG.L"]
    doc = json.loads(bet_groups.GROUPS_FILE.read_text(encoding="utf-8"))
    assert doc["version"] == "v1"
    assert bet_groups.effective_n(["GOOG", "GOOGL", "VUAG.L", "VUSA.L", "AAPL"]) == 3


def test_one_bet_is_averaged_before_bets_are_averaged() -> None:
    idx = pd.date_range("2024-01-01", periods=2, freq="D", tz="UTC")
    combined = bet_groups.combine({"GOOG": pd.Series([0.02, 0.0], idx),
                                   "GOOGL": pd.Series([0.0, 0.0], idx),
                                   "AAPL": pd.Series([0.04, 0.0], idx)})
    assert combined.iloc[0] == pytest.approx((0.01 + 0.04) / 2)


# ---------------------------------------------------- B5: benchmark and report --

def test_d3_is_vwrp_when_t212_lists_its_gbp_accumulating_line() -> None:
    good = [verify_universe.Resolved(
        "VWRP.L", "LSE", t212_ticker="VWRPl_EQ", isin=benchmark.D3_ISIN, currency="GBP",
        name="Vanguard FTSE All-World (Acc)")]
    symbol, why = benchmark.choose(lambda entries: good)
    assert symbol == "VWRP.L" and "VWRPl_EQ" in why
    bad = [verify_universe.Resolved("VWRP.L", "LSE", ok=False, reason="absent")]
    assert benchmark.choose(lambda entries: bad)[0] == "VWRL.L"


def test_a_report_without_the_benchmark_refuses_to_render(register_repo: Path) -> None:
    token = _token(register_repo, "KN-COIN-5m")
    data = _data("5m")[:2]
    result = firewall.score(token, known_null.strategy_for(token.entry), data,
                            interval="5m", n_null=5, bench=_bench, log_path=None)
    assert "benchmark VWRP.L" in report.render(result)
    assert "gross" in report.render(result) and "net at 1x" in report.render(result)
    result.benchmark = None
    with pytest.raises(benchmark.MissingBenchmark):
        report.render(result)
    result.benchmark = benchmark.Benchmark("VWRP.L", "x", date(2020, 1, 1),
                                           date(2020, 2, 1), 0.0)
    with pytest.raises(benchmark.MissingBenchmark, match="covers"):
        report.render(result)


# -------------------------------------------------------------- B6: verdicts --

def test_insufficient_is_its_own_answer_and_never_pass() -> None:
    few = verdict.judge(oos_trades=29, oos_bars=500, p_value=0.001, dsr=0.99,
                        strategy_return=0.5, benchmark_return=0.0)
    assert few.outcome == verdict.INSUFFICIENT and not few.passed
    assert "29 out-of-sample trades" in few.line()
    good = verdict.judge(oos_trades=30, oos_bars=500, p_value=0.001, dsr=0.99,
                         strategy_return=0.5, benchmark_return=0.0)
    assert good.passed
    behind = verdict.judge(oos_trades=30, oos_bars=500, p_value=0.001, dsr=0.99,
                           strategy_return=0.01, benchmark_return=0.02)
    assert behind.outcome == verdict.FAIL and "benchmark" in behind.line()


# ------------------------------------------- B6: the known-null gate, both ways --

@pytest.fixture(scope="module")
def synthetic_base() -> dict[str, list[firewall.NameData]]:
    return {"5m": _data("5m"), "1d": _data("1d")}


def _gate(register_repo: Path, base: dict[str, list[firewall.NameData]],
          tmp: Path) -> dict[str, list[known_null.DrillRun]]:
    return known_null.run_gate(base=base, require=lambda i: _token(register_repo, i),
                               n_null=30, bench=_bench, log_path=tmp / "trials.jsonl")


def test_the_known_null_gate_is_green_on_honest_code(
        register_repo: Path, synthetic_base: dict[str, list[firewall.NameData]],
        tmp_path: Path) -> None:
    runs = _gate(register_repo, synthetic_base, tmp_path)
    assert known_null.colour(runs["gate1"]) == "GREEN", \
        [(r.drill_id, r.result.verdict.line()) for r in runs["gate1"]]
    assert known_null.colour(runs["gate2"]) == "GREEN", \
        [(r.drill_id, r.result.verdict.line()) for r in runs["gate2"]]
    coin = runs["gate1"][0].result
    assert coin.verdict.outcome == verdict.FAIL                      # rejected, not "too few"
    logged = trial_log.read_trials(tmp_path / "trials.jsonl")
    assert len(logged) == 8 and {r["kind"] for r in logged} == {"drill"}
    assert trial_log.count_selection_trials(tmp_path / "trials.jsonl")[0] == 0


def _one(register_repo: Path, drill: str, base: list[firewall.NameData]) -> str:
    token = _token(register_repo, drill)
    data = known_null.with_pattern(base, "5m", token.entry["parameters"])
    return firewall.score(token, known_null.strategy_for(token.entry), data, interval="5m",
                          n_null=30, bench=_bench, log_path=None).verdict.outcome


def test_gate_one_goes_red_when_the_delay_is_removed(
        register_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fills, "ROW_O_DELAY_MINUTES", {"US": 0.0, "LSE": 0.0})
    assert _one(register_repo, "KN-INSTANT-5m", _data("5m")) == verdict.PASS   # RED


def test_gate_two_goes_red_when_costs_are_switched_off(
        register_repo: Path, monkeypatch: pytest.MonkeyPatch,
        synthetic_base: dict[str, list[firewall.NameData]]) -> None:
    monkeypatch.setattr(simulate, "leg_fractions",
                        lambda inst, stress: simulate.LegFractions(1e-12, 1e-12))
    assert _one(register_repo, "KN-PLANT-SMALL-5m", synthetic_base["5m"]) == verdict.PASS
