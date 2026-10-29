"""Heavy research waits for the scheduled recorder runs (QT-27, box rule 0.3).

QB2-Recorder fires on the hour, 07:00 ... 20:00 UK, Mon-Fri (run_times.HOURS), and Windows
starts a missed run late after a wake. Heavy work -- a trial, a fold batch, a test suite --
never STARTS:

* from hh:57 until that hour's run has logged "finished";
* while any recorder run started in the last STALE_HOURS has no finish line (a catch-up
  after a wake included); an older unfinished log is a killed run and blocks nothing;
* in the first GRACE_MINUTES of a trigger hour whose run has not started yet.

With a ``margin`` (QT-29 F: ``capped --clear-of-schedule``, research only, default OFF) it also waits
while ANY scheduled QuantBot start is due within it: the recorder's :00 and the status push's :50 on
weekdays, and v1's two morning tasks on any day (QT-28's scratch guard, made one copy).

Reads the run logs only (record_now's first and finish lines); never writes, never locks.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from datetime import time as wall
from pathlib import Path

from qb2.tools import run_times

REPO_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = REPO_ROOT / "logs" / "recorder"              # record_now.LOG_DIR, without its imports
UK = run_times.UK
DUE_MINUTE = 57
GRACE_MINUTES = 15
STALE_HOURS = 3
POLL_SECONDS = 30.0
FINISHED = ("==== run finished", "==== recorder run finished")
MARGIN = timedelta(minutes=15)             # QT-29 F: the lead kept clear before every scheduled start
V1_STARTS = (wall(7, 30), wall(7, 45))     # v1's QuantBot-Daily and -Monthly (Task Scheduler, UK)


def _runs(log_dir: Path, now: datetime) -> list[tuple[datetime, bool]]:
    """(start in UK time, finished?) of every run started in the last STALE_HOURS."""
    today = now.astimezone(UK).date()
    names = {f"run-{d.isoformat()}T*.log" for d in (today, today - timedelta(days=1))}
    out = []
    for pattern in sorted(names):
        for path in sorted(log_dir.glob(pattern)):
            body = path.read_text(encoding="utf-8", errors="replace")
            head = body.splitlines()[:1]
            if not head or not head[0].startswith("==== run started "):
                continue
            start = datetime.fromisoformat(head[0].split()[-1]).astimezone(UK)
            if now - timedelta(hours=STALE_HOURS) <= start <= now:
                out.append((start, any(mark in body for mark in FINISHED)))
    return sorted(out)


def starts(day: date) -> list[datetime]:
    """Every scheduled QuantBot start that day, UK: recorder and status push on weekdays; v1 daily."""
    week = [wall(h) for h in run_times.HOURS] + run_times.PUSH_SLOTS if day.weekday() < 5 else []
    return sorted(datetime.combine(day, t, UK) for t in [*V1_STARTS, *week])


def busy(now: datetime, log_dir: Path = LOG_DIR, margin: timedelta = timedelta(0)) -> str | None:
    """Why heavy work must not start now, or None when it may."""
    uk = now.astimezone(UK)
    runs = _runs(log_dir, now)
    going = [s for s, done in runs if not done]
    if going:
        return f"the recorder run started {going[-1]:%H:%M} UK has not logged 'finished' yet"
    if margin and (soon := [s for d in (uk.date(), uk.date() + timedelta(days=1)) for s in starts(d)
                            if uk <= s <= uk + margin]):
        return f"{soon[0]:%H:%M} UK: a scheduled run starts within {margin.seconds // 60} minutes"
    if uk.weekday() >= 5:
        return None
    if uk.minute >= DUE_MINUTE and uk.hour + 1 in run_times.HOURS:
        return f"{uk:%H}:{DUE_MINUTE} UK: the {uk.hour + 1:02d}:00 recorder run is due"
    if uk.hour in run_times.HOURS and uk.minute < GRACE_MINUTES and not any(
            s.date() == uk.date() and s.hour == uk.hour for s, _ in runs):
        return f"the {uk.hour:02d}:00 recorder run has not started yet"
    return None


def wait_clear(*, say: Callable[[str], None] = print, log_dir: Path = LOG_DIR,
               now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
               sleep: Callable[[float], None] = time.sleep, poll: float = POLL_SECONDS,
               margin: timedelta = timedelta(0)) -> float:
    """Block until heavy work may start; the seconds waited (0 when clear at once)."""
    waited, last = 0.0, None
    while (why := busy(now(), log_dir, margin)) is not None:
        if why != last:
            say(f"  waiting: {why}")
            last = why
        sleep(poll)
        waited += poll
    return waited


if __name__ == "__main__":
    print(busy(datetime.now(timezone.utc)) or "clear: heavy work may start")
