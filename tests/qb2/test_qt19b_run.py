"""QT-19 B1-B3: the register and its order, the resumable runner, the drills' planting."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from qb2.research import (advisor_book, advisor_data, advisor_drills, advisor_run, firewall,
                          preregister, trial_log)
from qb2.research.s6_run import Defect
from qb2.signals.a_rules import SENTINEL_VOLUME

IDS = [f"A-0{j}" for j in range(1, 7)]


def test_six_trials_one_arm_and_the_drills_in_register_order() -> None:
    a = [e for e in preregister.entries().values() if str(e["id"]).startswith("A-")]
    assert [e["id"] for e in a] == IDS
    for e in a:
        p = e["parameters"]
        assert (e["kind"], e["bar_size"], e["side"], p["arm"]) == ("trial", "1d", "long-only", "ALL")
        assert (p["top"], p["buffer"], p["stop_k"], p["risk_per_trade"]) == (0.2, 0.3, 3.0, 0.01)
        assert "N = 48" in e["judged"] and "2025-10-10" in e["holdout"]
        assert "advisor-universe-v1" in e["universe"] and "2014-04-01" in e["universe"]
    assert [e["parameters"]["filter"] is not None for e in a] == [False] * 5 + [True]
    drills = {e["id"]: e["expect"] for e in preregister.entries().values()
              if str(e["id"]).startswith("KN-A-")}
    assert drills == {"KN-A-RANDOM-1d": "FAIL", "KN-A-GAP-1d": "FAIL", "KN-A-PLANT-1d": "PASS",
                      "KN-A-PLANT-v2-1d": "PASS"}


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(preregister.REPO_ROOT), *args], capture_output=True,
                          text=True, check=True).stdout.strip()


def test_the_register_was_committed_alone_before_any_rule_code() -> None:
    """Box B1: the six registered in their own commit, an ancestor of the rule code."""
    preregister.require("A-01")
    registered = _git("log", "--format=%H", "--reverse", '-S"A-01"', "--",
                      preregister.REGISTER_REL).split()[0]
    assert _git("show", "--name-only", "--format=", registered) == preregister.REGISTER_REL
    for path in ("qb2/signals/a_rules.py", "qb2/research/advisor_book.py"):
        for commit in _git("log", "--diff-filter=A", "--format=%H", "--", path).split():
            assert commit != registered
            assert subprocess.run(["git", "-C", str(preregister.REPO_ROOT), "merge-base",
                                   "--is-ancestor", registered, commit]).returncode == 0


def test_trim_keeps_253_bars_before_the_first_out_of_sample_day() -> None:
    days = pd.bdate_range("2012-01-02", "2015-01-01", tz="America/New_York")
    bars = pd.DataFrame({"close": 1.0}, index=days)
    cut = advisor_data.trim(bars)
    first = int(np.flatnonzero(pd.DatetimeIndex(cut.index).date >= date(2014, 4, 1))[0])
    assert first == 253
    short = bars.iloc[-300:]
    assert len(advisor_data.trim(short)) == 300                      # fewer: all of them


# ---------------------------------------------------------------- the runner

@dataclass
class FakeResult:
    verdict: str


def _fake(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, prints: list[dict[str, str]],
          boom: str | None = None) -> list[str]:
    ran: list[str] = []
    entries = [{"id": c, "kind": "trial", "rule": "a_momentum", "name": c} for c in ("A-01", "A-02")]
    monkeypatch.setattr(advisor_run, "trials", lambda root=None: entries)
    monkeypatch.setattr(advisor_run, "code_commit", lambda *a: "c0ffee")
    monkeypatch.setattr(advisor_data, "fingerprints", lambda *a: prints[0])
    monkeypatch.setattr(advisor_data, "load", lambda *a: ([], [], {"credited": 0,
                                                                              "not_ok": 0}))
    monkeypatch.setattr(preregister, "require", lambda cid: type(
        "T", (), {"id": cid, "entry": {"id": cid, "rule": "x"}, "commit": "r"})())
    monkeypatch.setattr(advisor_run, "book_for", lambda entry, data, **kw: (None, []))

    def score(token: Any, *a: Any, **kw: Any) -> Any:
        if token.id == boom:
            raise KeyboardInterrupt
        ran.append(token.id)
        return FakeResult("FAIL")
    monkeypatch.setattr(advisor_run, "score", score)
    monkeypatch.setattr(advisor_run, "summary", lambda token, result, data, book: {
        "id": token.id, "verdict": result.verdict, "p": 0.5, "dsr": 0.0, "trades": 40,
        "vwrp_symbol": "VWRP.L", "sharpe": 0.0, "n_bars": 100, "register_commit": "r"})
    log = tmp_path / "trials.jsonl"
    monkeypatch.setattr(trial_log, "DEFAULT_TRIAL_LOG", log)
    return ran


def test_resumable_skips_finished_and_reruns_the_interrupted(monkeypatch: pytest.MonkeyPatch,
                                                             tmp_path: Path) -> None:
    prints = [{"a": "A", "b": "B"}]
    _fake(monkeypatch, tmp_path, prints, boom="A-02")
    with pytest.raises(KeyboardInterrupt):
        advisor_run.run(run_dir=tmp_path, say=lambda s: None)
    assert (tmp_path / "run1" / "A-01.json").is_file()
    ran = _fake(monkeypatch, tmp_path, prints)
    advisor_run.run(run_dir=tmp_path, say=lambda s: None)
    assert ran == ["A-02"]                                           # A-01 never re-run
    rows = [json.loads(x) for x in (tmp_path / "journal.ndjson").read_text().splitlines()]
    assert any(r["event"] == "interrupted" and r["id"] == "A-02" for r in rows)
    assert rows[-1]["event"] == "fingerprints_end"


def test_a_fingerprint_moving_mid_run_is_a_defect(monkeypatch: pytest.MonkeyPatch,
                                                   tmp_path: Path) -> None:
    prints = [{"a": "A", "b": "B"}]
    _fake(monkeypatch, tmp_path, prints)
    calls = iter([{"a": "A", "b": "B"}, {"a": "A2", "b": "B"}])
    monkeypatch.setattr(advisor_data, "fingerprints", lambda *a: next(calls))
    with pytest.raises(Defect, match="moved"):
        advisor_run.run(run_dir=tmp_path, say=lambda s: None)
    _fake(monkeypatch, tmp_path, [{"a": "OTHER", "b": "B"}])
    with pytest.raises(Defect, match="fingerprint"):                 # restart on other data
        advisor_run.run(run_dir=tmp_path, say=lambda s: None)


# ---------------------------------------------------------------- the drills' planting

def _name(n: int = 300) -> firewall.NameData:
    from qb2.execution import costs
    from qb2.research import fills
    days = pd.DatetimeIndex(advisor_book.sessions("US", date(2015, 1, 1),
                                                              date(2016, 6, 30))[:n]).tz_localize(
        "America/New_York")
    bars = pd.DataFrame({"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0,
                         "volume": 1.0}, index=days)
    return firewall.NameData("X", "US", costs.Instrument("X_US_EQ", "USD", "US", "STOCK"), bars,
                             fills.schedule(days, "1d", "US"), 3)


def test_plant_marks_month_ends_and_moves_prices_only_after_them() -> None:
    name = _name()
    up, down = advisor_drills.marks(name)
    assert up or down
    gap = advisor_drills.plant([name], {"pattern": "gap", "jump": 0.03})[0].bars
    trend = advisor_drills.plant([name], {"pattern": "trend", "delta_per_bar": 0.003,
                                          "trend_bars": 20})[0].bars
    t = (up or down)[0]
    sign = 1 if up and t == up[0] else -1
    before = gap["close"].iloc[t] / gap["close"].iloc[t - 1]
    after = gap["open"].iloc[t + 1] / gap["close"].iloc[t]
    assert before == pytest.approx(1.0) and after == pytest.approx(1.03 ** sign)
    assert trend["close"].iloc[t + 20] / trend["close"].iloc[t] == pytest.approx(1.003 ** (20 * sign))
    marked = set(np.flatnonzero(gap["volume"].to_numpy() == SENTINEL_VOLUME))
    assert marked == set(up)                                          # ANTI carries no marker


def test_same_bar_fill_is_the_broken_one() -> None:
    name = _name()
    broken = advisor_drills.same_bar_fills([name])[0]
    assert list(broken.plan.fills[:3]) == [0, 1, 2] and list(name.plan.fills[:3]) == [1, 2, 3]
