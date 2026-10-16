"""QT-18 B2-B3: the S6 runner -- every trial once, resumable, the data and code pinned. Offline.

The scoring itself is stubbed (it is firewall.score, proven in QT-14..17); what is
tested here is the run's bookkeeping: register order, save-then-count, restart,
interrupted trials, DEFECT on a moved commit or fingerprint, the single holdout.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from qb2.research import firewall, holdout, p19_results, p19_run, s6_run, trial_log
from qb2.signals import s6_rules

PASSER = "S6-03-US"


class Stub:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []
        self.opened: list[str] = []


@pytest.fixture()
def stub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Stub:
    s = Stub()
    monkeypatch.setattr(trial_log, "DEFAULT_TRIAL_LOG", tmp_path / "trials.jsonl")
    monkeypatch.setattr(s6_run, "code_commit", lambda: "commit-1")
    monkeypatch.setattr(s6_run, "fingerprints", lambda: {"a": "A", "b": "B"})
    monkeypatch.setattr(firewall, "load", lambda interval, entries: ([], []))
    monkeypatch.setattr(s6_rules, "maker", lambda entry, data: None)
    monkeypatch.setattr(p19_run, "sealed_names", lambda data, interval, final: [])

    def score(token: Any, make: Any, data: Any, **kw: Any) -> Any:
        s.calls.append((token.id, kw.get("final") is not None))
        return SimpleNamespace(id=token.id, final=kw.get("final") is not None)

    def summarise(result: Any, names: Any) -> dict[str, Any]:
        verdict = "PASS" if result.id == PASSER else "FAIL"
        return {"id": result.id, "verdict": verdict, "p": 0.01, "dsr": 0.5, "trades": 40,
                "vwrp_symbol": "VWRP.L", "sharpe": 0.1, "n_bars": 100, "bars": "1h",
                "reasons": []}

    def opened(token: Any, **kw: Any) -> object:
        if token.id in s.opened:
            raise holdout.Sealed(f"{token.id} has already had its final holdout run")
        s.opened.append(token.id)
        return object()

    monkeypatch.setattr(firewall, "score", score)
    monkeypatch.setattr(p19_results, "summarise", summarise)
    monkeypatch.setattr(holdout, "open_final_run", opened)
    return s


def _firewall_lines() -> list[dict[str, Any]]:
    return [r for r in trial_log.read_trials() if r["kind"] == "firewall"]


def test_all_24_run_in_register_order_each_saved_then_counted_once(stub: Stub,
                                                                    tmp_path: Path) -> None:
    s6_run.run(run_dir=tmp_path / "runs", say=lambda _: None)
    ids = [e["id"] for e in s6_run.trials()]
    assert len(ids) == 24 and [c[0] for c in stub.calls if not c[1]] == ids
    assert stub.calls.count((PASSER, True)) == 1 and stub.opened == [PASSER]
    assert sorted(p.stem for p in (tmp_path / "runs" / "run1").glob("S6-*.json")) == \
        sorted(ids + [f"{PASSER}.holdout"])
    assert [r["candidate_id"] for r in _firewall_lines()] == ids
    assert trial_log.count_selection_trials()[0] == 24
    assert not list((tmp_path / "runs").rglob("*.tmp"))
    done = json.loads((tmp_path / "runs" / "run1" / f"{PASSER}.json").read_text(encoding="utf-8"))
    assert done["holdout"]["verdict"] == "PASS" and done["code_commit"] == "commit-1"


def test_a_restart_skips_finished_trials_and_never_repeats_the_holdout(stub: Stub,
                                                                       tmp_path: Path) -> None:
    s6_run.run(run_dir=tmp_path / "runs", say=lambda _: None)
    first = len(stub.calls)
    s6_run.run(run_dir=tmp_path / "runs", say=lambda _: None)
    assert len(stub.calls) == first and len(_firewall_lines()) == 24


def test_an_interrupted_trial_is_rerun_once_and_logged_with_no_result(stub: Stub,
                                                                      tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    s6_run.run(run_dir=runs, limit=3, say=lambda _: None)
    fourth = s6_run.trials()[3]["id"]
    s6_run.note(runs, event="started", run=1, id=fourth)          # the PC went off mid-trial
    s6_run.run(run_dir=runs, limit=1, say=lambda _: None)
    events = [(r["event"], r.get("id")) for r in s6_run.journal(runs)]
    assert ("interrupted", fourth) in events
    assert [c[0] for c in stub.calls].count(fourth) == 1
    assert len(_firewall_lines()) == 4 == trial_log.count_selection_trials()[0]


def test_a_result_saved_but_not_yet_counted_is_counted_on_restart(stub: Stub,
                                                                  tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    s6_run.run(run_dir=runs, limit=2, say=lambda _: None)
    log = trial_log.DEFAULT_TRIAL_LOG
    lines = log.read_text(encoding="utf-8").splitlines()
    log.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")   # crash before the line
    s6_run.run(run_dir=runs, limit=0, say=lambda _: None)
    assert len(_firewall_lines()) == 2 and len(stub.calls) == 2


@pytest.mark.parametrize("moved", ["code", "a", "b"])
def test_a_moved_commit_or_fingerprint_is_a_defect(stub: Stub, tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch,
                                                   moved: str) -> None:
    runs = tmp_path / "runs"
    s6_run.run(run_dir=runs, limit=1, say=lambda _: None)
    if moved == "code":
        monkeypatch.setattr(s6_run, "code_commit", lambda: "commit-2")
    else:
        monkeypatch.setattr(s6_run, "fingerprints",
                            lambda: {"a": "A", "b": "B", moved: "moved"})
    with pytest.raises(s6_run.Defect):
        s6_run.run(run_dir=runs, say=lambda _: None)
    assert s6_run.journal(runs)[-1]["event"] == "defect" and len(stub.calls) == 1


def test_a_holdout_opened_without_a_saved_result_is_never_repeated(stub: Stub,
                                                                   tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    stub.opened.append(PASSER)                     # opened before; its file never written
    s6_run.run(run_dir=runs, say=lambda _: None)
    done = json.loads((runs / "run1" / f"{PASSER}.json").read_text(encoding="utf-8"))
    assert done["holdout"]["verdict"] == "NOT RUN" and (PASSER, True) not in stub.calls


def test_the_code_commit_is_refused_when_the_code_is_dirty(tmp_path: Path) -> None:
    import subprocess
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "qb2").mkdir()
    (tmp_path / "qb2" / "x.py").write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(s6_run.Defect, match="uncommitted"):
        s6_run.code_commit(tmp_path)


def test_a_trial_whose_result_was_never_saved_is_never_counted(stub: Stub, tmp_path: Path,
                                                              monkeypatch: pytest.MonkeyPatch) -> None:
    real = s6_run.atomic_write

    def failing(path: Path, record: Any) -> None:
        if path.stem == s6_run.trials()[1]["id"]:
            raise OSError("disk full")              # the PC dies as the result is written
        real(path, record)

    monkeypatch.setattr(s6_run, "atomic_write", failing)
    with pytest.raises(OSError):
        s6_run.run(run_dir=tmp_path / "runs", say=lambda _: None)
    assert [r["candidate_id"] for r in _firewall_lines()] == [s6_run.trials()[0]["id"]]
