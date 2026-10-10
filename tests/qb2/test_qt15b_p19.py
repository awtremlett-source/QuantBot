"""QT-15 B: P19's nine rules as registered, and the resumable trial runner. Offline.

The rules are checked by hand on tiny series; the runner with a stub scorer
(order, the full-count N, resume after an interruption, holdout only on PASS);
the holdout path with the real firewall on synthetic bars spanning the seal.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from qb2.research import (benchmark, fills, firewall, holdout, p19_run, preregister,
                          strategy, trial_log, verdict)
from qb2.signals import indicators, p19_rules
from tests.qb2.test_qt14b_firewall import (NAMES, _bars, _bench, _sessions,  # noqa: F401
                                           _token, register_repo)


def _daily(closes: list[float]) -> pd.DataFrame:
    index = pd.bdate_range("2025-01-02", periods=len(closes), tz="America/New_York")
    c = pd.Series(closes, index=index, dtype=float)
    return pd.DataFrame({"open": c, "high": c + 0.5, "low": c - 0.5, "close": c,
                         "volume": 1.0})


# ------------------------------------------------------------------ the rules --

def test_every_registered_trial_builds_and_a_changed_parameter_is_refused() -> None:
    trials = p19_run.trials()
    assert [t["id"] for t in trials][:2] == ["P19-01-5m", "P19-02-5m"] and len(trials) == 18
    for entry in trials:
        assert p19_rules.build(entry).bar_size == entry["bar_size"]
    with pytest.raises(ValueError, match="not the ones"):
        p19_rules.build(dict(trials[0], parameters={"ema": 10}))


def test_a_cross_up_enters_and_the_mirror_cross_exits() -> None:
    closes = [10.0] * 30 + [12.0, 12.5, 13.0, 9.0, 9.0, 9.0]
    w = p19_rules.P19Rule("price_x_ema9", "1d").weights(_daily(closes))
    assert w.iloc[:30].sum() == 0                   # flat line: no cross, no trade
    assert list(w.iloc[30:]) == [1.0, 1.0, 1.0, 0.0, 0.0, 0.0]


def test_a_new_session_needs_a_fresh_entry() -> None:
    """P4: sold before the bell, so yesterday's cross does not re-enter today."""
    index = _sessions("US", 2)
    close = pd.Series(100.0, index=index)
    close.iloc[60:] = 101.0                          # crosses up on day 1, stays up
    bars = pd.DataFrame({"open": close, "high": close, "low": close, "close": close,
                         "volume": 1.0})
    w = p19_rules.P19Rule("price_x_ema9", "5m").weights(bars)
    assert w.iloc[60:78].eq(1.0).all()              # held to the end of day 1...
    assert w.iloc[78:].eq(0.0).all()                # ...and no re-entry on day 2
    daily = p19_rules.P19Rule("price_x_ema9", "1d").weights(bars)
    assert daily.iloc[78:].eq(1.0).all()            # daily bars carry the state


def test_keltner_reversion_reads_the_bar_touching_the_band() -> None:
    bars = _daily([100.0] * 40)
    lower, _, upper = indicators.keltner(bars)
    bars.loc[bars.index[35], "low"] = float(lower.iloc[35]) - 1.0     # touches...
    w = p19_rules.P19Rule("keltner_reversion", "1d").weights(bars)    # ...closes inside
    assert w.iloc[35] == 1.0 and w.iloc[34] == 0.0
    lower, _, upper = indicators.keltner(bars)
    bars.loc[bars.index[38], "high"] = float(upper.iloc[38]) + 1.0
    w = p19_rules.P19Rule("keltner_reversion", "1d").weights(bars)
    assert list(w.iloc[35:]) == [1.0, 1.0, 1.0, 0.0, 0.0]


def test_the_stacked_rule_holds_while_aligned() -> None:
    closes = [100.0] * 60 + [100 + i for i in range(1, 20)] + [60.0] * 5
    w = p19_rules.P19Rule("stacked_emas", "1d").weights(_daily(closes))
    assert w.iloc[:60].sum() == 0 and w.iloc[62:79].eq(1.0).all() and w.iloc[-1] == 0.0


@pytest.mark.parametrize("rule", sorted(p19_rules.RULES))
def test_no_rule_reads_the_future(rule: str) -> None:
    for size, bars in (("5m", _bars(_sessions("LSE", 4), 3, 0.002)),
                       ("1d", _bars(pd.bdate_range("2024-01-02", periods=300,
                                                   tz="Europe/London"), 4, 0.015))):
        values = strategy.checked_weights(p19_rules.P19Rule(rule, size), bars)
        assert set(np.unique(values)) <= {0.0, 1.0}


# ------------------------------------------------------------- the runner --

def _result(cid: str, outcome: str = verdict.FAIL) -> firewall.FirewallResult:
    index = pd.date_range("2026-08-03 14:00", periods=40, freq="5min", tz="UTC")
    series = pd.Series(0.001, index=index)
    frame = pd.DataFrame({"gross": series, "net": series, "marked": series,
                          "entries": [True] + [False] * 39}, index=index)
    seen = firewall.Portfolio(series, series, series, 40, {"AAPL": frame})
    day = index[0].date()
    return firewall.FirewallResult(
        cid, "c" * 40, "5m", 2.0, 1, 1, [], day, day, seen, seen, 0.5, 0.0, 1.0,
        {"dsr": 0.1, "n_trials": 18.0, "sr0": 0.1},
        benchmark.Benchmark("VWRP.L", "stub", day, day, 0.01), verdict.Verdict(outcome))


class _Stub:
    def __init__(self, passing: str = "", stop_at: int = 0) -> None:
        self.calls: list[tuple[str, int, bool]] = []
        self.passing, self.stop_at = passing, stop_at

    def __call__(self, token: Any, make: Any, data: Any, **kw: Any) -> Any:
        self.calls.append((token.id, kw["n_trials"], kw.get("final") is not None))
        if self.stop_at and len(self.calls) == self.stop_at:
            raise KeyboardInterrupt("planted: the laptop lid closed")
        if kw.get("log_path") is not None:
            trial_log.log_trial({"utc_time": "t", "kind": "firewall", "candidate_id":
                                 token.id, "register_commit": "c", "strategy_name": "s",
                                 "params": {}, "metric_name": "m", "metric_value": 0,
                                 "n_bars": 1}, path=kw["log_path"])
        return _result(token.id, verdict.PASS if token.id == self.passing else verdict.FAIL)


def _run(tmp: Path, root: Path, stub: _Stub, **kw: Any) -> list[dict[str, Any]]:
    finals: list[str] = []

    def opened(token: Any, **_: Any) -> holdout.HoldoutPass:
        finals.append(token.id)
        return holdout.open_final_run(token, spent=tmp / "spent.jsonl",
                                      log_path=tmp / "trials.jsonl")

    out = p19_run.run(run_dir=tmp / "run", log_path=tmp / "trials.jsonl",
                      require=lambda i: _token(root, i), score=stub, open_final=opened,
                      load=lambda interval, **k: ([], []), bench=_bench, n_null=3,
                      say=lambda s: None, **kw)
    (tmp / "finals.json").write_text(json.dumps(finals), encoding="utf-8")
    return out


def test_all_18_in_register_order_each_deflated_over_the_full_count(
        tmp_path: Path, register_repo: Path) -> None:  # noqa: F811
    stub = _Stub(passing="P19-03-1d")
    records = _run(tmp_path, register_repo, stub)
    assert [c[0] for c in stub.calls if not c[2]] == [t["id"] for t in p19_run.trials()]
    assert {c[1] for c in stub.calls} == {18}                 # N = 0 before + 18
    assert len(records) == 18
    assert json.loads((tmp_path / "finals.json").read_text()) == ["P19-03-1d"]
    held = [r for r in records if "holdout" in r]
    assert [r["id"] for r in held] == ["P19-03-1d"]
    kinds = [r["kind"] for r in trial_log.read_trials(tmp_path / "trials.jsonl")]
    assert kinds.count("firewall") == 18 and kinds.count("holdout") == 2   # open + result
    assert trial_log.count_selection_trials(tmp_path / "trials.jsonl")[0] == 18


def test_an_interrupted_run_resumes_and_is_logged(tmp_path: Path,
                                                  register_repo: Path) -> None:  # noqa: F811
    with pytest.raises(KeyboardInterrupt):
        _run(tmp_path, register_repo, _Stub(stop_at=4))
    again = _Stub()
    records = _run(tmp_path, register_repo, again)
    assert len(again.calls) == 15 and again.calls[0][0] == p19_run.trials()[3]["id"]
    events = [json.loads(x) for x in (tmp_path / "run" / "journal.jsonl")
              .read_text(encoding="utf-8").splitlines()]
    assert [e["id"] for e in events if e["event"] == "interrupted"] == ["P19-04-5m"]
    assert len(records) == 18


def test_a_defect_rerun_starts_over_and_keeps_every_trial_counted(
        tmp_path: Path, register_repo: Path) -> None:  # noqa: F811
    _run(tmp_path, register_repo, _Stub())
    second = _Stub()
    _run(tmp_path, register_repo, second, new_batch="planted defect")
    assert len(second.calls) == 18 and {c[1] for c in second.calls} == {36}
    assert p19_run.state(tmp_path / "run")[:2] == (2, 18)


def test_the_holdout_grades_only_the_sealed_bars(tmp_path: Path,
                                                 register_repo: Path) -> None:  # noqa: F811
    token = _token(register_repo, "P19-01-5m")
    index = _sessions("US", 25, start="2026-09-01")
    bars = _bars(index, 7)
    inst = NAMES[0][1]
    name = firewall.NameData("AAPL", "US", inst, bars, fills.schedule(index, "5m", "US"), 0)
    make = (lambda e: lambda n: p19_rules.build(e))(token.entry)
    with pytest.raises(holdout.Sealed):
        firewall.score(token, make, [name], interval="5m", n_null=3, bench=_bench,
                       log_path=None)
    final = holdout.open_final_run(token, spent=tmp_path / "s.jsonl",
                                   log_path=tmp_path / "t.jsonl")
    result = firewall.score(token, make, [name], interval="5m", n_null=3, bench=_bench,
                            log_path=None, final=final, n_trials=18)
    graded = pd.DatetimeIndex(result.observed.marked.index).tz_convert("America/New_York")
    assert graded.min().date() == date(2026, 9, 21)           # the first sealed session
    assert result.start == date(2026, 9, 21)
    with pytest.raises(holdout.Sealed, match="already had"):
        holdout.open_final_run(token, spent=tmp_path / "s.jsonl")
    assert preregister.check(token) is token
