"""QT-12S: the hourly recorder status file and its push to the "status" branch.

Each premortem failure has its own test: counts that disagree with
delay_count, a secret in the file, a half-written manifest line, a push that
lands on main or carries other files, a push that fails quietly, and a job
that could collide with the recorder.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from qb2.tools import delay_count, status_push

# 18:55 UK on Thu 8 Oct 2026: London has closed, the US is open.
NOW = datetime(2026, 10, 8, 17, 55, tzinfo=timezone.utc)
AGE = {"US": 75.0, "LSE": 1000.0}


def _row(market: str, at: datetime, verified: bool = True) -> dict[str, object]:
    return {"kind": "delay_sample", "market": market, "clock_checked": verified,
            "age_seconds": AGE[market], "age_seconds_raw": AGE[market],
            "at_utc": at.isoformat(timespec="seconds")}


def _utc(day: int, hour: int, minute: int = 12) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=timezone.utc)


def _planted(tmp_path: Path) -> Path:
    """Counted, uncounted and duplicate rows across four sessions."""
    rows = [_row("LSE", _utc(5, 13)), _row("LSE", _utc(6, 10)),
            _row("LSE", _utc(6, 10)),                  # same bar twice: once
            _row("LSE", _utc(7, 5)),                   # before the open
            _row("LSE", _utc(7, 15), verified=False),  # clock never checked
            _row("US", _utc(2, 15)),                   # before 2026-10-05
            _row("US", _utc(5, 15)), _row("US", _utc(7, 16))]
    # Today: London every hour 09:12-16:12 UK except 12:12; US 15:12-18:12 UK.
    rows += [_row("LSE", _utc(8, h)) for h in (8, 9, 10, 12, 13, 14, 15)]
    rows += [_row("US", _utc(8, h)) for h in (14, 15, 16, 17)]
    path = tmp_path / "manifest.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def _logs(tmp_path: Path) -> Path:
    folder = tmp_path / "recorder"
    folder.mkdir()
    (folder / "run-2026-10-08T171242.log").write_text(
        "==== run started 2026-10-08T16:12:42+00:00\n"
        "     started in directory: C:\\Users\\someone\\TRADING\n"
        "==== run finished exit=0 at 2026-10-08T16:15:00+00:00\n", encoding="utf-8")
    return folder


def _status(tmp_path: Path, manifest: Path | None = None) -> str:
    return status_push.build_status(manifest or _planted(tmp_path),
                                    _logs(tmp_path), NOW)


# ------------------------------------------- counts are delay_count's counts --

def test_counts_match_delay_count_on_the_same_planted_data(tmp_path: Path) -> None:
    manifest = _planted(tmp_path)
    counted = delay_count.countable(delay_count.read_samples(manifest),
                                    verified_only=True)
    since = [r for r in counted if str(r["at_utc"]) >= "2026-10-05"]
    want = {m: sum(1 for r in since if r["market"] == m) for m in ("LSE", "US")}
    assert want == {"LSE": 9, "US": 6}            # the fixture is what we think
    text = _status(tmp_path, manifest)
    assert f"since 2026-10-05: {want['LSE']} of 20" in text.split("## US")[0]
    assert f"since 2026-10-05: {want['US']} of 20" in text.split("## US")[1]
    assert "Counted today: 7" in text.split("## US")[0]
    assert "Counted today: 4" in text.split("## US")[1]


def test_status_names_the_missed_hour_and_the_last_run(tmp_path: Path) -> None:
    text = _status(tmp_path)
    london, us = text.split("## US")
    assert "Missed hours today: 12:00" in london
    assert "Missed hours today: none" in us
    assert "Updated at: 2026-10-08 18:55 (UK)" in text
    assert "started 17:12, finished 17:15, exit 0" in text
    assert "Meter:" in london and "Meter:" in us
    assert "Delay median: 16.7 min" in london


def test_status_carries_no_paths_from_outside_the_repo(tmp_path: Path) -> None:
    text = _status(tmp_path)
    assert "C:\\" not in text and "someone" not in text
    assert status_push.secret_hits(text, {}) == []


# ------------------------------------------------------------- secret scan --

def test_a_planted_key_is_refused_and_logged_loudly(tmp_path: Path) -> None:
    status = tmp_path / "recorder_status.md"
    fake = "fAkE0key1ZZ9plantedQ7w8e9r0t1y2u3"
    status.write_text(f"# status\nkey: {fake}\n", encoding="utf-8")
    calls: list[list[str]] = []
    code = status_push.publish(status, tmp_path / "push.log", tmp_path,
                               env_values={}, git=lambda a, **k: calls.append(a))
    assert code != 0 and calls == []              # nothing reached git
    log = (tmp_path / "push.log").read_text(encoding="utf-8")
    assert "REFUSED" in log and fake not in log


@pytest.mark.parametrize("text", [
    "T212_API_KEY=abc123",                      # an .env name with a value
    "token is s3cr3tvalue here",                # a value that is in .env
    "see C:\\Users\\someone\\TRADING\\.env",    # a path outside the repo
])
def test_other_secret_shapes_are_caught(text: str) -> None:
    assert status_push.secret_hits(text, {"T212_API_SECRET": "s3cr3tvalue"})


def test_the_scan_never_repeats_the_secret() -> None:
    hits = status_push.secret_hits("x s3cr3tvalue", {"T212_API_SECRET": "s3cr3tvalue"})
    assert hits and all("s3cr3tvalue" not in h for h in hits)


# ------------------------------------------------------ half-written manifest --

def test_a_half_written_last_line_is_skipped_and_noted(tmp_path: Path) -> None:
    manifest = _planted(tmp_path)
    with manifest.open("a", encoding="utf-8") as fh:
        fh.write('{"kind": "delay_sample", "market": "LS')
    rows, bad = delay_count.scan_samples(manifest)
    assert bad == 1 and len(rows) == 19
    text = _status(tmp_path, manifest)
    assert "1 unreadable manifest line skipped" in text
    assert "since 2026-10-05: 9 of 20" in text


# ------------------------------------------------- the push: target and files --

def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, text=True,
                          capture_output=True).stdout.strip()


@pytest.fixture()
def repo(tmp_path: Path) -> tuple[Path, Path]:
    remote = tmp_path / "remote.git"
    work = tmp_path / "work"
    _git(tmp_path, "init", "--bare", "-b", "main", str(remote))
    _git(tmp_path, "init", "-b", "main", str(work))
    _git(work, "config", "user.name", "t")
    _git(work, "config", "user.email", "t@example.invalid")
    (work / "code.py").write_text("x = 1\n", encoding="utf-8")
    (work / "other.txt").write_text("not for the status branch\n", encoding="utf-8")
    _git(work, "add", "code.py")
    _git(work, "commit", "-m", "main")
    _git(work, "remote", "add", "origin", str(remote))
    _git(work, "push", "origin", "main")
    return work, remote


def test_push_lands_only_the_status_file_on_the_status_branch(
        repo: tuple[Path, Path], tmp_path: Path) -> None:
    work, remote = repo
    main_before = _git(remote, "rev-parse", "refs/heads/main")
    head_before, porcelain_before = _git(work, "rev-parse", "HEAD"), _git(work, "status", "--porcelain")
    status = tmp_path / "recorder_status.md"
    for n in (1, 2):                              # twice: still ONE commit
        status.write_text(f"# status {n}\n", encoding="utf-8")
        assert status_push.publish(status, tmp_path / "push.log", work, env_values={}) == 0
    assert _git(remote, "rev-parse", "refs/heads/main") == main_before
    assert _git(remote, "ls-tree", "-r", "--name-only", "status") == "status/recorder_status.md"
    assert _git(remote, "rev-list", "--count", "status") == "1"
    assert _git(remote, "show", "status:status/recorder_status.md") == "# status 2"
    assert _git(work, "rev-parse", "HEAD") == head_before
    assert _git(work, "status", "--porcelain") == porcelain_before   # index untouched
    assert status_push.STATUS_REF == "refs/heads/status"


def test_a_failed_push_exits_non_zero_and_logs_it(repo: tuple[Path, Path],
                                                  tmp_path: Path) -> None:
    work, _ = repo
    _git(work, "remote", "set-url", "origin", str(tmp_path / "no-such-remote.git"))
    status = tmp_path / "recorder_status.md"
    status.write_text("# status\n", encoding="utf-8")
    log = tmp_path / "logs" / "push.log"
    assert status_push.publish(status, log, work, env_values={}) != 0
    assert "PUSH FAILED" in log.read_text(encoding="utf-8")


# --------------------------------------------- never in the recorder's way --

def test_the_job_never_takes_the_recorder_lock_or_writes_data() -> None:
    source = Path(status_push.__file__).read_text(encoding="utf-8")
    assert "WriterLock" not in source and "recorder.lock" not in source
    data = status_push.REPO_ROOT / "data"
    for target in (status_push.STATUS_FILE, status_push.PUSH_LOG):
        assert data not in target.parents


def test_the_manifest_is_only_read(tmp_path: Path) -> None:
    manifest = _planted(tmp_path)
    before = manifest.read_bytes()
    manifest.chmod(0o444)
    try:
        _status(tmp_path, manifest)
    finally:
        manifest.chmod(0o644)
    assert manifest.read_bytes() == before


# ------------------------------------- QT-13: runs that drift off the hour --

def _runs(tmp_path: Path, starts: list[str]) -> Path:
    folder = tmp_path / "drift"
    folder.mkdir()
    for start in starts:                       # UTC, as the recorder logs it
        stamp = datetime.fromisoformat(start)
        name = f"run-{status_push._uk(stamp):%Y-%m-%dT%H%M%S}.log"
        (folder / name).write_text(
            f"==== run started {start}\n==== run finished exit=0 at {start}\n",
            encoding="utf-8")
    return folder


def test_runs_that_start_late_in_the_hour_are_flagged(tmp_path: Path) -> None:
    """9 Oct: Windows re-anchored the hourly trigger to a 08:53 catch-up, so every
    run landed at :53 and London's 16:00 slot fell after the close. The page
    called the 17:00 hour 'missed' at 17:50; it was due at 17:53."""
    logs = _runs(tmp_path, ["2026-10-08T14:53:36+00:00",
                            "2026-10-08T15:53:36+00:00",
                            "2026-10-08T16:53:36+00:00"])
    text = status_push.build_status(_planted(tmp_path), logs, NOW)
    assert "Runs today (UK): 15:53, 16:53, 17:53" in text
    assert "OFF THE HOUR: 3 of 3" in text


def test_runs_on_the_hour_raise_no_flag(tmp_path: Path) -> None:
    logs = _runs(tmp_path, ["2026-10-07T16:00:02+00:00",   # yesterday: not today
                            "2026-10-08T15:00:02+00:00",
                            "2026-10-08T16:12:42+00:00"])
    text = status_push.build_status(_planted(tmp_path), logs, NOW)
    assert "Runs today (UK): 16:00, 17:12" in text
    assert "OFF THE HOUR" not in text
