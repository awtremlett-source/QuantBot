"""QT-29 F (QT-27/28 PROPOSE 5): research runners stay clear of the scheduled runs. Offline, a fake clock.

``python -m qb2.tools.capped --clear-of-schedule -- <runner>`` waits before it starts until no recorder run
is going and no scheduled start is due within 15 minutes: the recorder's :00 (07-20 UK) and the status
push's :50 (08:50-21:50 UK) on weekdays, and v1's QuantBot-Daily 07:30 and -Monthly 07:45 on any day.
Default OFF: the recorder itself runs through capped and must never wait for its own run.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from qb2.tools import capped, run_window

UK = ZoneInfo("Europe/London")
THU = datetime(2026, 10, 29, 8, 40, tzinfo=UK)                  # the 08:50 push is 10 minutes away


class Clock:
    """A fake clock that moves only when slept on."""

    def __init__(self, start: datetime) -> None:
        self.now, self.slept = start, 0.0

    def __call__(self) -> datetime:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)
        self.slept += seconds


def log_dir(tmp: Path, *starts: datetime) -> Path:
    """Finished recorder logs, one per start."""
    for s in starts:
        (tmp / f"run-{s:%Y-%m-%dT%H%M%S}.log").write_text(
            f"==== run started {s.isoformat()}\n==== run finished exit=0 at {s.isoformat()}\n", encoding="utf-8")
    return tmp


@pytest.mark.parametrize(("at", "why"), [
    (datetime(2026, 10, 29, 8, 40, tzinfo=UK), "08:50 UK"),     # the status push
    (datetime(2026, 10, 29, 19, 50, tzinfo=UK), "19:50 UK"),    # the push, then 20:00's top-up run
    (datetime(2026, 10, 31, 7, 20, tzinfo=UK), "07:30 UK"),     # Saturday: v1's daily task still runs
])
def test_a_scheduled_start_within_15_minutes_holds_heavy_work(tmp_path: Path, at: datetime, why: str) -> None:
    logs = log_dir(tmp_path, at.replace(minute=0))
    assert why in str(run_window.busy(at, logs, run_window.MARGIN))
    assert run_window.busy(at, logs) is None                    # without the margin: as before
    assert run_window.busy(at.replace(minute=at.minute - 15) + timedelta(minutes=-1), logs, run_window.MARGIN) is None


def test_with_the_flag_the_runner_starts_only_once_clear(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clock, logs = Clock(THU), log_dir(tmp_path, THU.replace(minute=0))
    started: list[tuple[datetime, list[str]]] = []

    def launch(cmd: Sequence[str], **_: object) -> int:
        started.append((clock(), list(cmd)))
        return 0

    monkeypatch.setattr(capped, "launch", launch)
    monkeypatch.setattr(capped, "log", lambda line: None)

    def wait(**kw: object) -> float:
        return run_window.wait_clear(now=clock, sleep=clock.sleep, log_dir=logs, say=lambda s: None,
                                     margin=kw["margin"])              # type: ignore[arg-type]

    # 08:50's push, then 09:00's recorder run (its log, below, shows it started and finished): clear after 09:00
    (logs / "run-2026-10-29T090000.log").write_text("==== run started 2026-10-29T09:00:00+00:00\n"
                                                    "==== run finished exit=0\n", encoding="utf-8")
    assert capped.main(["--clear-of-schedule", "--", "python", "-m", "qb2.research.cm_run"], wait=wait) == 0
    when, cmd = started[0]
    assert cmd == ["python", "-m", "qb2.research.cm_run"] and when >= datetime(2026, 10, 29, 9, 0, tzinfo=UK)
    assert run_window.busy(when, logs, run_window.MARGIN) is None and clock.slept > 0


def test_without_the_flag_nothing_waits_the_recorder_never_waits_for_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[list[str]] = []

    def launch(cmd: Sequence[str], **_: object) -> int:
        started.append(list(cmd))
        return 0

    monkeypatch.setattr(capped, "launch", launch)

    def never(**_: object) -> float:
        raise AssertionError("waited without --clear-of-schedule")

    assert capped.main(["--", "pythonw", "-m", "qb2.tools.record_now"], wait=never) == 0
    assert started == [["pythonw", "-m", "qb2.tools.record_now"]]
