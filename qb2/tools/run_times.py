"""Did today's recorder runs start when the triggers say? (QT-13b)

Since QT-13-GO, QB2-Recorder has 14 fixed triggers, 07:00 ... 20:00 UK, Mon-Fri,
with no repetition. So the rule for the status page is plain:

* every run should start on the hour (within ON_TIME);
* ONE late run is expected after a switch-on: Windows makes up the missed start
  once ("run as soon as possible after a missed start"). It is named as such;
* the same off-hour minute twice is DRIFT -- the QT-13 fault, where repetition
  re-based on a catch-up and every run landed at :53. That must not come back;
* an hour whose run never started is listed, so a missing :00 run is visible.

QT-16: the status task's own record. QB2-StatusPush now has 14 fixed triggers at
:50 (08:50 ... 21:50 UK, Mon-Fri), like the recorder; on 12 Oct its one repeating
trigger skipped 18:50 and 19:50 with the PC awake, and nothing said so. A :50 slot
with a recorder run on BOTH sides of it (the PC was awake) and no push near it is
named as MISSED.

Reads the run logs' first lines and push.log only. Never writes, never takes a lock.
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
PUSH_SLOTS = [time(h, 50) for h in range(8, 22)]   # QB2-StatusPush's 14 fixed triggers
PUSH_NEAR = timedelta(minutes=10)


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


def pushes_today(push_log: Path, starts: Sequence[datetime], now: datetime) -> str:
    """Pushes made today, and any :50 slot missed while the PC was evidently awake."""
    local = now.astimezone(UK)
    lines = push_log.read_text(encoding="utf-8").splitlines() if push_log.is_file() else []
    pushed = [moment for line in lines if " pushed " in line
              if (moment := datetime.fromisoformat(line.split()[0]).astimezone(UK)).date()
              == local.date()]
    slots = ([datetime.combine(local.date(), at, UK) for at in PUSH_SLOTS]
             if local.weekday() < 5 else [])
    missed = [s for s in slots if s + PUSH_NEAR <= local
              and any(r <= s for r in starts) and any(r >= s for r in starts)
              and not any(abs(p - s) <= PUSH_NEAR for p in pushed)]
    line = f"- Status pushes today: {len(pushed)}"
    if missed:
        line += (" -- MISSED while the PC was awake: " + ", ".join(f"{s:%H:%M}" for s in missed)
                 + " (check QB2-StatusPush's triggers)")
    return line
