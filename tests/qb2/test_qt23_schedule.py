"""QT-23 D: the advisor's jobs ride the existing after-hours step, inside the cap, loud when broken.

* The scheduled entry points (QB2-Recorder -> record_now, QB2-StatusPush -> status_push) start
  Python directly, so each first re-runs itself through qb2.tools.capped when outside the cap --
  everything QuantBot runs stays inside it (operator, 2026-10-20) -- and never loops.
* earnings_step.after_daily runs the advisor after the daily top-up and earnings. A STOP, a RED or
  an UNCHECKED stop is RAISED, so the recorder's run is NOT CLEAN; a refusal (a SystemExit) cannot
  end the recorder's run.
* status_push pushes logs/advisor/advisor.md beside its status page, through the same secret scan.
Red-on-broken: each job broken once on purpose here, seen to fail, then restored.
"""

from __future__ import annotations

import ast
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from qb2.advisor import engine, state
from qb2.data import daily_step, earnings_step
from qb2.execution.safety import Blocked
from qb2.tools import capped, governor, status_push
from tests.qb2.test_qt23_advisor import DAYS, _run, at

ROOT = Path(__file__).resolve().parents[2]


# ------------------------------------------------ scheduled starts wrap themselves

def test_inside_the_cap_a_scheduled_start_carries_on() -> None:
    assert governor.run_capped("qb2.tools.record_now", [], verify=lambda: []) is None


def test_outside_it_runs_again_through_the_launcher_and_returns_its_code(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(capped.ENV, raising=False)
    seen: list[list[str]] = []

    def launcher(args: list[str], check: bool) -> subprocess.CompletedProcess[str]:
        seen.append(args)
        return subprocess.CompletedProcess(args, 7)
    code = governor.run_capped("qb2.tools.record_now", ["--no-catchup"], verify=lambda: ["not inside"],
                               run=launcher)
    assert code == 7
    assert seen[0][1:4] == ["-m", "qb2.tools.capped", "--"] and seen[0][-3:] == [
        "-m", "qb2.tools.record_now", "--no-catchup"]


def test_started_by_the_launcher_but_not_inside_is_refused_never_a_loop(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(capped.ENV, "Local\\QuantBot-cap")
    monkeypatch.setattr(capped, "LOG", tmp_path / "cap.log")
    with pytest.raises(governor.NotCapped, match="never a loop"):
        governor.run_capped("qb2.tools.record_now", [], verify=lambda: ["not inside"],
                            run=lambda *a, **k: pytest.fail("looped"))


@pytest.mark.parametrize("module", ["qb2/tools/record_now.py", "qb2/tools/status_push.py"])
def test_each_scheduled_entry_point_wraps_itself_first(module: str) -> None:
    tree = ast.parse((ROOT / module).read_text(encoding="utf-8"))
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    first = main.body[1] if isinstance(main.body[0], ast.Expr) else main.body[0]   # after the docstring
    assert "governor.run_capped(" in ast.unparse(first), ast.unparse(first)[:120]


# ------------------------------------------------------ the after-hours hook

def test_the_hook_runs_the_advisor_after_the_top_up_and_says_what_it_did(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(daily_step, "run_if_due", lambda now, clean_root=None: "Daily store: x")
    monkeypatch.setattr(earnings_step, "run_if_due", lambda now, clean_root=None: "Earnings: y")   # offline
    told = earnings_step.after_daily(datetime.now(timezone.utc), clean_root=tmp_path, digest_dir=tmp_path,
                                     advisor=lambda now, root: "Advisor: 1 session · reconciled: OK")
    assert told.split(" · ")[-2:] == ["Advisor: 1 session", "reconciled: OK"]
    assert earnings_step.after_daily(datetime.now(timezone.utc), clean_root=tmp_path,
                                     digest_dir=tmp_path).endswith("Advisor: not run against a test store")


def test_red_on_broken_the_daily_job(tmp_path: Path) -> None:
    _run(tmp_path, [100.0], DAYS[0], at(DAYS[0], 19), first=True)
    paths, clean = state.Paths.under(tmp_path), tmp_path / "clean"
    assert earnings_step.advise(at(DAYS[0], 20), clean, paths).startswith("Advisor: ")   # green
    days = paths.log("days")
    kept = days.read_text(encoding="utf-8")
    days.write_text(kept + "{half a line\n", encoding="utf-8")                          # broken
    with pytest.raises(RuntimeError, match="ADVISOR STOPPED: days.jsonl line 2 is unreadable"):
        earnings_step.advise(at(DAYS[0], 20), clean, paths)
    days.write_text(kept, encoding="utf-8")                                              # restored
    assert earnings_step.advise(at(DAYS[0], 20), clean, paths).startswith("Advisor: ")


def test_red_on_broken_the_weekly_review(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _run(tmp_path, [100.0], DAYS[0], at(DAYS[0], 19), first=True)
    paths, clean = state.Paths.under(tmp_path), tmp_path / "clean"
    _run(tmp_path, [100.0] * 4, DAYS[3], at(DAYS[3], 19))                # through Thursday 6 March

    def broken(*args: object, **kwargs: object) -> list[dict[str, object]]:
        raise Blocked("the weekly review broke (planted)")
    monkeypatch.setattr(engine, "weekly_review", broken)
    with pytest.raises(RuntimeError, match="ADVISOR STOPPED: the weekly review broke"):
        earnings_step.advise(at(DAYS[4], 7), clean, paths)
    monkeypatch.undo()                                                    # restored
    assert "weekly review" in earnings_step.advise(at(DAYS[4], 7), clean, paths)


def test_a_refusal_inside_the_hook_cannot_end_the_recorders_run(tmp_path: Path,
                                                                monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse() -> None:
        raise governor.NotCapped("REFUSED")
    monkeypatch.setattr(governor, "assert_capped", refuse)
    with pytest.raises(RuntimeError, match="advisor refused"):           # an Exception, not a SystemExit
        earnings_step.advise(datetime.now(timezone.utc), tmp_path, state.Paths.under(tmp_path))


# ------------------------------------------------------- the status branch

def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, text=True, capture_output=True).stdout.strip()


def test_the_advisor_page_is_pushed_beside_the_status_page_through_the_scan(tmp_path: Path) -> None:
    remote, work = tmp_path / "remote.git", tmp_path / "work"
    _git(tmp_path, "init", "--bare", "-b", "main", str(remote))
    _git(tmp_path, "init", "-b", "main", str(work))
    _git(work, "remote", "add", "origin", str(remote))
    status, page = tmp_path / "recorder_status.md", tmp_path / "advisor.md"
    status.write_text("# status\n", encoding="utf-8")
    page.write_text("# QuantBot advisor\n", encoding="utf-8")
    assert status_push.publish(status, tmp_path / "push.log", work, env_values={}, extra=[page]) == 0
    assert _git(remote, "ls-tree", "-r", "--name-only", "status").splitlines() == [
        "status/advisor.md", "status/recorder_status.md"]
    page.write_text("token = 9f8e7d6c5b4a39281706f5e4d3c2b1a0\n", encoding="utf-8")   # planted
    assert status_push.publish(status, tmp_path / "push.log", work, env_values={}, extra=[page]) == 2
    assert "advisor.md" in (tmp_path / "push.log").read_text(encoding="utf-8").splitlines()[-1]
