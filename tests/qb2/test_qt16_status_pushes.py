"""QT-16 step 0: the status page names a :50 push missed while the PC was awake.

Mon 12 Oct 2026, as found: the PC woke at 18:02 UK; the recorder ran 18:06 and
19:00; QB2-StatusPush (one trigger repeating hourly) never ran at 18:50 or 19:50.
Nothing on the page said so. Fail-first: written before run_times.pushes_today.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from qb2.tools import run_times

UK = ZoneInfo("Europe/London")
TWENTY_PAST_EIGHT = datetime(2026, 10, 12, 20, 20, tzinfo=UK)


def _log(tmp_path: Path, *stamps: str) -> Path:
    log = tmp_path / "push.log"
    log.write_text("".join(f"{s} pushed status/recorder_status.md to refs/heads/status\n"
                           for s in stamps) +
                   "2026-10-12T19:30:00+00:00 status written, push skipped (--no-push)\n",
                   encoding="utf-8")
    return log


def _uk(hhmm: str) -> datetime:
    h, m = hhmm.split(":")
    return datetime(2026, 10, 12, int(h), int(m), tzinfo=UK)


def test_slots_missed_while_awake_are_named(tmp_path: Path) -> None:
    log = _log(tmp_path, "2026-10-09T23:07:00+00:00", "2026-10-12T18:20:16+00:00")
    starts = [_uk("18:06"), _uk("19:00"), _uk("20:00")]
    line = run_times.pushes_today(log, starts, TWENTY_PAST_EIGHT)
    assert line.startswith("- Status pushes today: 1")
    assert "MISSED while the PC was awake: 18:50, 19:50" in line


def test_slots_while_asleep_are_not_blamed_on_the_task(tmp_path: Path) -> None:
    log = _log(tmp_path)
    line = run_times.pushes_today(log, [_uk("18:06")], _uk("18:30"))
    assert "MISSED" not in line                  # 08:50-17:50: asleep, nothing to prove


def test_on_time_pushes_raise_nothing(tmp_path: Path) -> None:
    log = _log(tmp_path, "2026-10-12T17:50:41+00:00", "2026-10-12T18:50:39+00:00")
    starts = [_uk("18:06"), _uk("19:00"), _uk("20:00")]
    line = run_times.pushes_today(log, starts, TWENTY_PAST_EIGHT)
    assert line == "- Status pushes today: 2"
