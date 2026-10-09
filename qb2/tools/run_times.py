"""Did today's recorder runs start when the triggers say? (QT-13b)

Since QT-13-GO, QB2-Recorder has 14 fixed triggers, 07:00 ... 20:00 UK, Mon-Fri,
with no repetition. So the rule for the status page is plain:

* every run should start on the hour (within ON_TIME);
* ONE late run is expected after a switch-on: Windows makes up the missed start
  once ("run as soon as possible after a missed start"). It is named as such;
* the same off-hour minute twice is DRIFT -- the QT-13 fault, where repetition
  re-based on a catch-up and every run landed at :53. That must not come back;
* an hour whose run never started is listed, so a missing :00 run is visible.

Reads the run logs' first lines only. Never writes, never takes a lock.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

UK = ZoneInfo("Europe/London")
HOURS = range(7, 21)                       # the 14 fixed triggers, UK wall clock
ON_TIME_MINUTES = 5                        # a wake from sleep can take a minute
GRACE = timedelta(minutes=20)              # a slot is judged once its run is due


def starts_today(log_dir: Path, now: datetime) -> list[datetime]:
    """Today's run start times (UK), from each log's first line."""
    today = now.astimezone(UK).date()
    starts = []
    for path in sorted(log_dir.glob(f"run-{today.isoformat()}T*.log")):
        head = path.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
        if head and head[0].startswith("==== run started "):
            starts.append(datetime.fromisoformat(head[0].split()[-1]).astimezone(UK))
    return starts


def judge(starts: Sequence[datetime], now: datetime) -> list[str]:
    """Plain-words lines for the status page."""
    late = [s for s in starts if s.minute >= ON_TIME_MINUTES]
    line = "- Runs today (UK): " + (", ".join(f"{s:%H:%M}" for s in starts) or "none yet")
    repeated = sorted(m for m, n in Counter(s.minute for s in late).items() if n >= 2)
    if repeated:
        line += (" -- DRIFT: " + ", ".join(f":{m:02d}" for m in repeated) + " more than "
                 "once, so the hourly trigger has moved off :00 (the QT-13 fault); "
                 "check QB2-Recorder's triggers")
    elif len(late) == 1 and late[0] == starts[0]:
        line += f" -- {late[0]:%H:%M} was the catch-up after switch-on (expected)"
    elif late:
        line += (f" -- OFF THE HOUR: {len(late)} of {len(starts)} ("
                 + ", ".join(f"{s:%H:%M}" for s in late) + ")")
    lines = [line]
    local = now.astimezone(UK)
    if local.weekday() < 5:
        slots = [h for h in HOURS
                 if datetime.combine(local.date(), time(h), UK) + GRACE <= local]
        missed = [h for h in slots if not any(s.hour == h for s in starts)]
        if missed:
            lines.append("- Missed runs today: " + ", ".join(f"{h:02d}:00" for h in missed)
                         + " (PC off or asleep?)")
    return lines
