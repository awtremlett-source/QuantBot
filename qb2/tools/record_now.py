"""Run the recorder once. This is what the scheduled task calls.

Two jobs, deliberately separated, because mixing them is what broke it:

* **The hourly run** tops up 1-minute bars from each name's last saved bar, in
  batches. Nothing else. It is meant to finish in minutes.
* **The catch-up** backfills names that have no history and tops up the 5m and 1h
  series. It is slow, so it runs once a day, after both markets have shut, inside
  the same scheduled task's last run of the day. No second task, no administrator.

Why this split exists, in one sentence: on 2026-10-01 every hourly run tried to
backfill 93 brand-new names as well as top up 128 old ones, took over an hour, and
was killed before it finished -- the recorder log for that day is literally
``^C``, three warnings, and ``^C^C``, with no summary line because no run ever
reached the end. Names late in the list simply never got recorded.

Three things every run now does, whatever mode it is in:

* **Samples the quote delay FIRST**, before any fetch. It takes seconds. Doing it
  last meant it never happened, because the run never got that far -- which is why
  FACTS row o sat unmeasured for three attempts.
* **Keeps a ledger.** Every name attempted must come out saved, lost, quarantined
  or skipped-with-a-reason. A name in none of those categories fails the run
  loudly. That is the guard that would have caught GOOG, AXP, APH and ADI being
  walked past in silence.
* **Reports its own duration** and raises an alarm past a threshold, because a run
  that overruns its hour blocks the next trigger and nobody finds out.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from qb2.data.front_door import StoreLocked, WriterLock
from qb2.ingest import fresh_run, recorder, tickers

REPO_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = REPO_ROOT / "logs" / "recorder"

# STARTING FIGURES, tested first.
HOURLY_TARGET_MINUTES = 10.0     # what a healthy hourly run should come in under
RUN_ALARM_MINUTES = 45.0         # past this, the HOURLY run blocks its own trigger
# The catch-up is MEANT to be slow: it runs on the day's last trigger with
# nothing after it until 07:00. The real 2026-10-02 catch-up took 110 minutes to
# backfill 131 new names and was wrongly reported as a failure. An alarm that
# fires on correct behaviour just teaches people to ignore alarms. But it must
# sit BELOW the scheduled task's ExecutionTimeLimit (PT3H): the old 480 could
# never ring, because the scheduler kills the run at 180 first.
TASK_KILL_MINUTES = 180.0
CATCHUP_ALARM_MINUTES = 150.0
# More than this share of names skipped by the hourly limit, in a run with no
# catch-up behind it, is an empty run -- and must not report itself clean.
HOURLY_SKIP_ALARM_SHARE = 0.5
LOG_KEEP_DAYS = 30
RECORDER_LOCK = REPO_ROOT / "data" / "raw" / "intraday" / "recorder.lock"


_LOG: "RunLog | None" = None


def say(line: str) -> None:
    """Print, and record in the run log if one is open."""
    if _LOG is not None:
        _LOG.write(line)
    else:
        print(line)


class RunLog:
    """Writes the run to its own file AND to the screen, if there is a screen.

    Python owns this rather than the batch file for one reason: the scheduled
    task must not open a console window. The operator could see a
    ``C:\\Windows\\System32\\cmd.exe`` window appear every hour, which is both
    intrusive and a standing invitation to close it mid-run. With the logging
    here, the task can run ``pythonw.exe``, which has no console at all.

    It also records the directory the process STARTED in. Task Scheduler starts a
    task in ``C:\\Windows\\System32`` when no "Start in" is set, and that is
    almost certainly why the old shared ``recorder.log`` never appeared: the
    relative path resolved under System32, where it could not be written. The
    starting directory is now written down every run instead of being assumed.
    """

    def __init__(self, directory: Path | None = None,
                 now: datetime | None = None) -> None:
        self.started = now or datetime.now(timezone.utc)
        folder = directory or LOG_DIR
        folder.mkdir(parents=True, exist_ok=True)
        stamp = self.started.astimezone().strftime("%Y-%m-%dT%H%M%S")
        self.path = folder / f"run-{stamp}.log"
        self.handle = self.path.open("a", encoding="utf-8")
        self.write(f"==== run started {self.started.isoformat(timespec='seconds')}")
        self.write(f"     started in directory: {os.getcwd()}")
        self.write(f"     python: {sys.executable}")

    def write(self, line: str) -> None:
        self.handle.write(line + "\n")
        self.handle.flush()
        try:
            print(line)
        except (OSError, ValueError):
            pass            # pythonw has no stdout; the file is the record

    def finish(self, code: int) -> None:
        """The LAST line. Its absence is how a killed run is recognised.

        If the operator closes the window mid-run, or the laptop sleeps, the
        process dies without writing this. A log with no finish line is a run
        that did not finish -- which is exactly what we could not tell before.
        """
        self.write(f"==== run finished exit={code} "
                   f"at {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
        self.handle.close()


def unfinished_runs(directory: Path | None = None) -> list[Path]:
    """Logs with no finish line: runs that were killed rather than completed."""
    folder = directory or LOG_DIR
    if not folder.is_dir():
        return []
    finished = ("==== run finished", "==== recorder run finished")
    out: list[Path] = []
    for path in sorted(folder.glob("run-*.log")):
        body = path.read_text(encoding="utf-8", errors="replace")
        # The second marker is the short-lived batch-written format from
        # 2026-10-02. Those runs really did finish; not accepting it would leave
        # three permanent false alarms, and a monitor that cries wolf gets ignored.
        if not any(marker in body for marker in finished):
            out.append(path)
    return out


def rotate_logs(directory: Path | None = None,
                keep_days: int = LOG_KEEP_DAYS,
                today: date | None = None) -> list[Path]:
    """Delete run logs older than ``keep_days``. Returns what it removed.

    Logs are the only record of an unattended run, so they are kept for a month
    -- long enough to look back at a bad week, short enough that the folder does
    not grow without limit on a laptop.
    """
    folder = directory or LOG_DIR
    if not folder.is_dir():
        return []
    cutoff = (today or date.today()) - timedelta(days=keep_days)
    removed: list[Path] = []
    for path in sorted(folder.glob("run-*.log")):
        stamp = path.stem.removeprefix("run-")[:10]
        try:
            when = date.fromisoformat(stamp)
        except ValueError:
            continue                      # not ours to delete
        if when < cutoff:
            path.unlink(missing_ok=True)
            removed.append(path)
    return removed


# The scheduled task repeats hourly for 14 hours from 07:00 local, so its LAST
# run of the day starts at 20:00 -- while New York is still open until 21:00. A
# catch-up that waited for "both markets shut" would therefore never run at all
# on this schedule. The day's final run does it instead: nothing follows it until
# 07:00 the next morning, so it has the night to be slow in.
LAST_RUN_HOUR_LOCAL = 20


def both_markets_shut(now: datetime | None = None) -> bool:
    moment = now or datetime.now(timezone.utc)
    return not (recorder.market_is_open("US", moment)
                or recorder.market_is_open("LSE", moment))


def is_last_run_of_day(now: datetime | None = None) -> bool:
    """True from the final scheduled trigger onwards, on a weekday."""
    moment = (now or datetime.now(timezone.utc)).astimezone()
    return moment.weekday() < 5 and moment.hour >= LAST_RUN_HOUR_LOCAL


def should_catch_up(now: datetime | None = None) -> bool:
    """When the slow work is allowed to happen.

    Either both markets have shut, or this is the day's last scheduled run. Never
    in the middle of the session, where it would make the hourly top-up overrun
    its own trigger -- which is exactly what went wrong on 2026-10-01.
    """
    return both_markets_shut(now) or is_last_run_of_day(now)


def _report(label: str, outcome: recorder.Outcome) -> list[str]:
    """The ledger line for one interval, and any complaint about it."""
    complaints: list[str] = []
    lines = [
        f"  {label}: attempted {len(outcome.attempted)} = "
        f"saved {len(outcome.saved_names)} + lost {len(outcome.lost)} + "
        f"skipped {len(outcome.skipped)} + errors {len(outcome.errors)} "
        f"| {outcome.rows_saved:,} bars in {len(outcome.captures)} files, "
        f"{outcome.quarantined} quarantined, "
        f"{len(outcome.delay_samples)} delay samples"]
    missing = outcome.unaccounted()
    if missing:
        complaints.append(
            f"{label}: {len(missing)} name(s) attempted and then unaccounted for: "
            f"{', '.join(missing[:12])}"
            + (" ..." if len(missing) > 12 else ""))
    for line in lines:
        say(line)
    reasons: dict[str, int] = {}
    for row in outcome.lost:
        reasons[str(row.get("reason"))] = reasons.get(str(row.get("reason")), 0) + 1
    for reason, count in sorted(reasons.items(), key=lambda kv: -kv[1])[:4]:
        say(f"      LOST x{count}: {reason}")
    if outcome.skipped:
        say(f"      skipped x{len(outcome.skipped)}: "
            f"{outcome.skipped[0]['reason']}")
    return complaints


def _clean_step(after_hours: bool) -> list[str]:
    """The after-hours step (QT-13b): raw -> clean, both censuses, the labels.

    Called AFTER the sampling and the fetches, so it can never delay them. It
    runs once per finished trading day (qb2/data/clean_step.py decides), and
    every run prints the clean store's verdict, so a stale store is never silent.
    """
    from qb2.data import clean_step

    complaints: list[str] = []
    try:
        result = clean_step.run_if_due(datetime.now(timezone.utc),
                                       after_hours=after_hours)
    except Exception as exc:                  # noqa: BLE001 - logged, never silent
        result = None
        complaints.append(f"the after-hours step failed: {type(exc).__name__}: {exc}")
    if isinstance(result, str):
        say(f"  after-hours step: not due ({result})")
    elif result is not None:
        say("  after-hours step:")
        for line in result.lines:
            say(f"    {line}")
        complaints += result.complaints
    say("  " + clean_step.status_verdict(datetime.now(timezone.utc)).line())
    return complaints


def main(argv: Sequence[str] | None = None) -> int:
    """Run once, under a lock so two recorders can never write the same file.

    An hourly job on a laptop WILL overlap with itself: a catch-up run started by
    hand, a missed trigger fired late, a run still going when the next hour comes
    round. Two processes writing one parquet file can leave it truncated, and a
    truncated bar file is worse than a missing one because it still reads.
    """
    parser = argparse.ArgumentParser(
        prog="record_now", description="Capture intraday bars once.")
    parser.add_argument("--interval", default="1m",
                        choices=sorted(recorder.MAX_DAYS_PER_REQUEST))
    parser.add_argument("--catchup", action="store_true",
                        help="force the slow after-hours work (backfills, 5m, 1h)")
    parser.add_argument("--no-catchup", action="store_true",
                        help="never do the slow work, even after hours")
    parser.add_argument("--full", action="store_true",
                        help="ignore resume points and refetch the whole window")
    args = parser.parse_args(argv)

    started = datetime.now(timezone.utc)
    clock = time.monotonic()
    entries = tickers.recording_list()
    do_catchup = args.catchup or (should_catch_up(started)
                                  and not args.no_catchup)

    log = RunLog(now=started)
    global _LOG
    _LOG = log
    say(f"[{started:%Y-%m-%d %H:%M:%S}Z] recorder: {len(entries)} names · "
        f"LSE open={recorder.market_is_open('LSE', started)} · "
        f"US open={recorder.market_is_open('US', started)} · "
        f"mode={'hourly+catchup' if do_catchup else 'hourly'}")
    try:
        lock = WriterLock(RECORDER_LOCK)
        lock.__enter__()
    except StoreLocked as held:
        # Not a failure: the scheduler is doing exactly what it should. Exit 0 so
        # a healthy overlap does not look like a broken run.
        say(f"  another recorder is already running -- standing down. {held}")
        log.finish(0)
        return 0
    try:
        code = _run(args, entries, started, clock, do_catchup)
    finally:
        lock.__exit__(None, None, None)
    log.finish(code)
    return code


def _run(args: argparse.Namespace, entries: list[tuple[str, str, str]],
         started: datetime, clock: float, do_catchup: bool) -> int:

    complaints: list[str] = []

    # --- the delay sample comes FIRST, before anything slow ---
    from qb2.tools import sample_delay
    samples = sample_delay.take_samples()
    if samples:
        for sample in samples:
            age = sample.get("age_seconds")
            minutes = float(age) / 60 if isinstance(age, (int, float)) else 0.0
            say(f"  delay {sample['market']}: {minutes:.1f} min")
    else:
        say("  delay: no sample (markets shut) -- correct, not a failure")

    # --- the hourly top-up ---
    hourly = recorder.capture_incremental(
        entries, args.interval,
        max_days=None if args.full else recorder.HOURLY_MAX_DAYS)
    complaints += _report(f"{args.interval} hourly", hourly)
    attempted = len(hourly.attempted)
    if (not do_catchup and attempted
            and len(hourly.skipped) > HOURLY_SKIP_ALARM_SHARE * attempted):
        # In a catch-up run the same names are backfilled minutes later, so the
        # skips cost nothing. Without one, they wait until the evening.
        complaints.append(
            f"{args.interval} hourly: skipped {len(hourly.skipped)} of "
            f"{attempted} names on the hourly limit -- this run recorded almost "
            f"nothing, and they wait for the evening catch-up")
    elapsed_hourly = (time.monotonic() - clock) / 60
    say(f"  hourly took {elapsed_hourly:.1f} min "
          f"(target under {HOURLY_TARGET_MINUTES:.0f})")

    # --- the slow work, only once both markets are shut ---
    if do_catchup:
        backlog = recorder.capture_incremental(
            entries, args.interval, max_days=None)
        complaints += _report(f"{args.interval} backfill", backlog)
        for interval in ("5m", "1h"):
            slow = recorder.capture_incremental(entries, interval, max_days=None)
            complaints += _report(f"{interval} catch-up", slow)

    # --- the after-hours step: raw -> clean, censuses, labels. ALWAYS after the
    # sampling and the fetches above, so it can never slow them (QT-13b). ---
    complaints += fresh_run.around_clean(_clean_step, after_hours=do_catchup, say=say)

    rotated = rotate_logs()
    if rotated:
        say(f"  rotated {len(rotated)} log(s) older than {LOG_KEEP_DAYS} days")

    for meter in recorder.freshness():
        marker = "RED " if meter["status"] == "RED" else "OK  "
        say(f"  freshness {marker}{meter['interval']:>3}: {meter['detail']}")
    say("  " + sample_delay.verdict().replace("\n", "\n  "))

    minutes = (time.monotonic() - clock) / 60
    say(f"[{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}Z] "
          f"finished in {minutes:.1f} min")

    limit = CATCHUP_ALARM_MINUTES if do_catchup else RUN_ALARM_MINUTES
    if minutes > limit:
        complaints.append(
            f"this run took {minutes:.0f} minutes, over the {limit:.0f} minute "
            + ("alarm for a catch-up: it should have finished overnight"
               if do_catchup else
               "alarm: it is at risk of overrunning its own hourly trigger"))
    if elapsed_hourly > RUN_ALARM_MINUTES:
        complaints.append(
            f"the hourly top-up alone took {elapsed_hourly:.0f} minutes, over the "
            f"{RUN_ALARM_MINUTES:.0f} minute alarm: it will block the next trigger")

    if complaints:
        say("\nRUN NOT CLEAN:")
        for complaint in complaints:
            say(f"  ! {complaint}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
