"""QT-27 rule 0.3: heavy research never starts in a scheduled recorder run's way."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from qb2.tools import run_window

UTC = timezone.utc                       # UK = UTC on 28 Oct 2026 (clocks went back on the 25th)


def _log(folder: Path, start: datetime, finished: bool = True) -> None:
    lines = [f"==== run started {start.isoformat(timespec='seconds')}", "  recorder: 226 names"]
    if finished:
        lines.append(f"==== run finished exit=0 at {(start + timedelta(minutes=3)).isoformat()}")
    (folder / f"run-{start:%Y-%m-%dT%H%M%S}.log").write_text("\n".join(lines), encoding="utf-8")


def test_the_three_minutes_before_a_trigger_are_busy(tmp_path: Path) -> None:
    _log(tmp_path, datetime(2026, 10, 28, 9, 0, 2, tzinfo=UTC))
    assert run_window.busy(datetime(2026, 10, 28, 9, 56, tzinfo=UTC), tmp_path) is None
    why = run_window.busy(datetime(2026, 10, 28, 9, 57, tzinfo=UTC), tmp_path)
    assert why is not None and "10:00" in why
    assert run_window.busy(datetime(2026, 10, 28, 6, 58, tzinfo=UTC), tmp_path) is not None   # 07:00 run


def test_a_run_without_its_finished_line_is_waited_out(tmp_path: Path) -> None:
    _log(tmp_path, datetime(2026, 10, 28, 10, 0, 2, tzinfo=UTC), finished=False)
    why = run_window.busy(datetime(2026, 10, 28, 10, 20, tzinfo=UTC), tmp_path)
    assert why is not None and "finished" in why
    _log(tmp_path, datetime(2026, 10, 28, 10, 0, 2, tzinfo=UTC), finished=True)
    assert run_window.busy(datetime(2026, 10, 28, 10, 20, tzinfo=UTC), tmp_path) is None


def test_a_catch_up_run_after_a_wake_is_waited_out(tmp_path: Path) -> None:
    _log(tmp_path, datetime(2026, 10, 28, 6, 11, 59, tzinfo=UTC), finished=False)
    assert run_window.busy(datetime(2026, 10, 28, 6, 30, tzinfo=UTC), tmp_path) is not None


def test_an_hour_whose_run_has_not_started_is_busy_for_its_first_quarter(tmp_path: Path) -> None:
    _log(tmp_path, datetime(2026, 10, 28, 10, 0, 2, tzinfo=UTC))
    assert run_window.busy(datetime(2026, 10, 28, 11, 1, tzinfo=UTC), tmp_path) is not None
    assert run_window.busy(datetime(2026, 10, 28, 11, 16, tzinfo=UTC), tmp_path) is None


def test_nights_and_weekends_are_clear_and_a_dead_log_does_not_block_for_ever(tmp_path: Path) -> None:
    assert run_window.busy(datetime(2026, 10, 31, 10, 58, tzinfo=UTC), tmp_path) is None      # Saturday
    assert run_window.busy(datetime(2026, 10, 28, 22, 58, tzinfo=UTC), tmp_path) is None
    _log(tmp_path, datetime(2026, 10, 28, 15, 0, 2, tzinfo=UTC), finished=False)              # killed run
    assert run_window.busy(datetime(2026, 10, 28, 21, 30, tzinfo=UTC), tmp_path) is None


def test_wait_clear_waits_until_the_run_has_finished(tmp_path: Path) -> None:
    _log(tmp_path, datetime(2026, 10, 28, 12, 0, 2, tzinfo=UTC), finished=False)
    clock = [datetime(2026, 10, 28, 12, 1, tzinfo=UTC)]
    said: list[str] = []

    def sleep(seconds: float) -> None:
        clock[0] += timedelta(seconds=seconds)
        if clock[0] >= datetime(2026, 10, 28, 12, 4, tzinfo=UTC):
            _log(tmp_path, datetime(2026, 10, 28, 12, 0, 2, tzinfo=UTC), finished=True)

    waited = run_window.wait_clear(say=said.append, log_dir=tmp_path, now=lambda: clock[0], sleep=sleep)
    assert waited > 0 and clock[0] >= datetime(2026, 10, 28, 12, 4, tzinfo=UTC) and said
