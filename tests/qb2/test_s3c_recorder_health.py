"""Premortem for an unattended recorder: every way it can fail in silence.

The incident these are written against is real. On 2026-10-01 every hourly run
tried to do a full backfill, took over an hour, and was killed before finishing.
The only record of it was a log containing ``^C``, three warnings and ``^C^C`` --
no summary line, because no run ever reached the end. Four names (GOOG, AXP, APH,
ADI) were walked past and ended the day with no data, no LOST row, and no error.
Nothing was broken loudly enough to notice.

Every test below names the specific silence it breaks.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from qb2.ingest import recorder
from qb2.tools import record_now

UTC = timezone.utc
REPO_ROOT = Path(__file__).resolve().parents[2]


def bars_frame(start: datetime, count: int, price: float = 100.0) -> pd.DataFrame:
    index = pd.date_range(start, periods=count, freq="1min", tz="UTC")
    return pd.DataFrame({"open": price, "high": price + 1, "low": price - 1,
                         "close": price, "volume": 10}, index=index)


# =========================================================== the run is visible

def test_the_run_creates_its_own_log_directory(tmp_path: Path) -> None:
    """Failure mode: the log goes nowhere because the folder does not exist.

    The run's only witness is its log. A missing folder would silently throw away
    the one thing that explains a bad night. Python owns this now, not the batch
    file, because the scheduled task runs pythonw.exe with no console at all.
    """
    folder = tmp_path / "does" / "not" / "exist"
    log = record_now.RunLog(directory=folder)
    log.finish(0)
    assert folder.is_dir()
    assert log.path.is_file()


def test_every_run_gets_its_own_log_named_by_its_start_time(
        tmp_path: Path) -> None:
    """One shared log hid which run did what, and appended across kills."""
    first = record_now.RunLog(
        directory=tmp_path, now=datetime(2026, 10, 2, 7, 0, tzinfo=UTC))
    first.finish(0)
    second = record_now.RunLog(
        directory=tmp_path, now=datetime(2026, 10, 2, 8, 0, tzinfo=UTC))
    second.finish(0)

    assert first.path != second.path
    assert len(list(tmp_path.glob("run-*.log"))) == 2
    assert "run finished exit=0" in first.path.read_text(encoding="utf-8")


def test_a_failed_run_cannot_report_success_to_the_scheduler() -> None:
    """Failure mode: Task Scheduler says 0 while the run died.

    The task runs pythonw.exe directly, so the process's own exit code IS the
    task result -- there is no shell in between to swallow it. The hand-run batch
    must pass it on too.
    """
    source = (REPO_ROOT / "qb2" / "tools" / "record_now.py").read_text(
        encoding="utf-8")
    assert "raise SystemExit(main())" in source

    batch = _batch_commands()
    assert any("exit /b %RC%" in line for line in batch)


def test_logs_do_not_grow_for_ever(tmp_path: Path) -> None:
    """A log per run, kept for ever, fills a laptop quietly."""
    folder = tmp_path / "recorder"
    folder.mkdir()
    today = date(2026, 10, 2)
    for days_old in (0, 5, 29, 30, 31, 120):
        stamp = (today - timedelta(days=days_old)).isoformat()
        (folder / f"run-{stamp}T120000.log").write_text("x", encoding="utf-8")
    (folder / "keep-me.txt").write_text("not ours", encoding="utf-8")

    removed = record_now.rotate_logs(folder, keep_days=30, today=today)

    assert len(removed) == 2, [p.name for p in removed]      # 31 and 120 days old
    assert (folder / "keep-me.txt").exists(), "only our own logs may be deleted"
    assert (folder / f"run-{(today - timedelta(days=29)).isoformat()}T120000.log"
            ).exists()


def test_no_secret_can_reach_a_run_log() -> None:
    """The logs hold raw stdout. A key printed there would be a key on disk."""
    env = REPO_ROOT / ".env"
    if not env.exists():
        pytest.skip("no .env on this machine")
    secrets = [line.split("=", 1)[1].strip().strip("'\"")
               for line in env.read_text(encoding="utf-8").splitlines()
               if "=" in line and not line.strip().startswith("#")]
    secrets = [s for s in secrets if len(s) >= 8]
    logs = REPO_ROOT / "logs"
    if not logs.is_dir() or not secrets:
        pytest.skip("no logs written yet")
    for path in logs.rglob("*.log"):
        body = path.read_text(encoding="utf-8", errors="replace")
        for secret in secrets:
            assert secret not in body, f"a secret reached {path.name}"


# ====================================================== no name disappears

def test_a_name_that_vanishes_fails_the_run(tmp_path: Path) -> None:
    """THE incident, as a test. GOOG, AXP, APH and ADI went missing in silence.

    A name must leave a run saved, lost, quarantined or skipped-with-a-reason.
    Landing in none of those is not a quiet edge case; it is the run being wrong
    about what it did, which is the one thing a ledger exists to prevent.
    """
    outcome = recorder.Outcome()
    outcome.attempted = ["ABT", "GOOG", "AXP"]
    outcome.saved_names = {"ABT"}
    outcome.lost = [{"ticker": "AXP", "reason": "provider returned nothing"}]

    assert outcome.unaccounted() == ["GOOG"]

    # Account for it and the complaint goes away -- but only honestly.
    outcome.skipped.append({"ticker": "GOOG", "reason": "left for the catch-up"})
    assert outcome.unaccounted() == []


def test_the_ledger_adds_up_on_a_real_capture(tmp_path: Path) -> None:
    """attempted = saved + lost + skipped + errors, with nothing left over."""
    entries = [("AAA", "US", "USD"), ("BBB", "US", "USD"), ("CCC", "US", "USD")]

    def fetch(names: Sequence[str], interval: str,
              days: int) -> dict[str, pd.DataFrame]:
        # BBB is simply absent from the reply, exactly as a real provider does.
        return {"AAA": bars_frame(datetime(2026, 9, 29, 14, 0, tzinfo=UTC), 5)}

    outcome = recorder.capture_incremental(
        entries, "1m", fetch=fetch, root=tmp_path,
        manifest=tmp_path / "m.jsonl",
        now=datetime(2026, 9, 29, 20, 0, tzinfo=UTC), max_days=None)

    assert outcome.unaccounted() == []
    assert len(outcome.attempted) == 3
    assert outcome.saved_names == {"AAA"}
    assert {str(r["ticker"]) for r in outcome.lost} == {"BBB", "CCC"}


# ================================================ the hourly run stays hourly

def test_a_backfill_cannot_get_into_the_hourly_run(tmp_path: Path) -> None:
    """The actual cause of the >1h runs: 93 new names backfilled every hour.

    A name with no history needs the whole window. Doing that during the hourly
    top-up made the run overrun its own trigger, and the run was then killed
    before it finished -- so the names at the end never got recorded at all.
    """
    asked: list[int] = []

    def fetch(names: Sequence[str], interval: str,
              days: int) -> dict[str, pd.DataFrame]:
        asked.append(days)
        return {n: bars_frame(datetime(2026, 9, 29, 14, 0, tzinfo=UTC), 3)
                for n in names}

    entries = [("OLD", "US", "USD"), ("BRAND_NEW", "US", "USD")]
    manifest = tmp_path / "m.jsonl"
    # OLD was saved an hour ago; BRAND_NEW has never been seen.
    recorder.append_manifest({
        "kind": "capture", "status": "saved", "ticker": "OLD", "interval": "1m",
        "last_bar_utc": datetime(2026, 9, 29, 19, 0, tzinfo=UTC).isoformat()},
        manifest)

    outcome = recorder.capture_incremental(
        entries, "1m", fetch=fetch, root=tmp_path, manifest=manifest,
        now=datetime(2026, 9, 29, 20, 0, tzinfo=UTC),
        max_days=recorder.HOURLY_MAX_DAYS)

    assert asked == [1], f"the hourly run asked for {asked} days"
    assert outcome.saved_names == {"OLD"}
    skipped = {s["ticker"] for s in outcome.skipped}
    assert skipped == {"BRAND_NEW"}
    assert "catch-up" in outcome.skipped[0]["reason"]
    assert outcome.unaccounted() == [], "a skipped name is still accounted for"


def test_the_catch_up_does_take_the_backfill(tmp_path: Path) -> None:
    """The other half: the slow work must actually happen somewhere."""
    asked: list[int] = []

    def fetch(names: Sequence[str], interval: str,
              days: int) -> dict[str, pd.DataFrame]:
        asked.append(days)
        return {n: bars_frame(datetime(2026, 9, 29, 14, 0, tzinfo=UTC), 3)
                for n in names}

    outcome = recorder.capture_incremental(
        [("BRAND_NEW", "US", "USD")], "1m", fetch=fetch, root=tmp_path,
        manifest=tmp_path / "m.jsonl",
        now=datetime(2026, 9, 29, 20, 0, tzinfo=UTC), max_days=None)

    assert asked == [recorder.MAX_DAYS_PER_REQUEST["1m"]]
    assert outcome.saved_names == {"BRAND_NEW"}
    assert outcome.skipped == []


def test_the_catch_up_runs_on_the_last_trigger_of_the_day() -> None:
    """The schedule's last trigger is 20:00, while New York is open until 21:00.

    Waiting for "both markets shut" would mean the catch-up never ran at all on
    this schedule, and the backfill would never happen.
    """
    midday = datetime(2026, 10, 2, 12, 0, tzinfo=UTC).astimezone()
    assert not record_now.should_catch_up(midday)

    last_run = midday.replace(hour=record_now.LAST_RUN_HOUR_LOCAL, minute=1)
    assert record_now.should_catch_up(last_run), (
        "the day's final run must do the slow work")


def test_names_are_fetched_in_batches_not_one_at_a_time(tmp_path: Path) -> None:
    """226 separate requests is 226 latencies and 226 chances to be throttled."""
    sizes: list[int] = []

    def fetch(names: Sequence[str], interval: str,
              days: int) -> dict[str, pd.DataFrame]:
        sizes.append(len(names))
        return {n: bars_frame(datetime(2026, 9, 29, 14, 0, tzinfo=UTC), 3)
                for n in names}

    entries = [(f"N{i:03d}", "US", "USD") for i in range(95)]
    recorder.capture_incremental(
        entries, "1m", fetch=fetch, root=tmp_path, manifest=tmp_path / "m.jsonl",
        now=datetime(2026, 9, 29, 20, 0, tzinfo=UTC), max_days=None,
        batch_size=40)

    assert sizes == [40, 40, 15], f"batching went wrong: {sizes}"


def test_a_throttled_batch_is_recorded_as_lost_never_faked(tmp_path: Path) -> None:
    """Yahoo throttles without saying so. A gap must be a gap, by name.

    The forbidden outcome is an invented bar. The required outcome is that every
    name in the failed batch is written down as LOST so the next run refetches it.
    """
    def fetch(names: Sequence[str], interval: str,
              days: int) -> dict[str, pd.DataFrame]:
        raise RuntimeError("429 Too Many Requests")

    manifest = tmp_path / "m.jsonl"
    entries = [("AAA", "US", "USD"), ("BBB", "US", "USD")]
    outcome = recorder.capture_incremental(
        entries, "1m", fetch=fetch, root=tmp_path, manifest=manifest,
        now=datetime(2026, 9, 29, 20, 0, tzinfo=UTC), max_days=None)

    assert {str(r["ticker"]) for r in outcome.lost} == {"AAA", "BBB"}
    assert outcome.saved_names == set()
    assert outcome.unaccounted() == []
    assert list(tmp_path.rglob("*.parquet")) == [], "nothing may be invented"
    assert all("429" in e for e in outcome.errors)


def test_a_slow_run_raises_an_alarm_rather_than_passing_quietly() -> None:
    """A run that overruns its hour blocks the next trigger, invisibly.

    That is precisely what happened: hourly triggers were refused with error 4320
    for a whole day because the previous run was still going.
    """
    assert record_now.RUN_ALARM_MINUTES == 45.0
    assert record_now.HOURLY_TARGET_MINUTES == 10.0
    source = (REPO_ROOT / "qb2" / "tools" / "record_now.py").read_text(
        encoding="utf-8")
    assert "RUN_ALARM_MINUTES" in source and "return 1" in source
    # The alarm must make the run UNCLEAN, so the scheduler's result shows it --
    # and the hourly top-up is judged on its OWN time, not on the whole run's.
    assert re.search(r"elapsed_hourly > RUN_ALARM_MINUTES", source)
    assert "CATCHUP_ALARM_MINUTES if do_catchup else RUN_ALARM_MINUTES" in source


# ======================================================== the delay sampler

# The session meter's tests moved to test_delay_count.py with the meter (QT-12R).


def test_the_sampler_runs_before_anything_slow() -> None:
    """Sampling last meant never sampling: the run died before reaching it."""
    source = (REPO_ROOT / "qb2" / "tools" / "record_now.py").read_text(
        encoding="utf-8")
    sample_at = source.index("sample_delay.take_samples()")
    capture_at = source.index("recorder.capture_incremental(")
    assert sample_at < capture_at, (
        "the delay sample must be taken before any fetch, or a long run will "
        "swallow it again")


# ============================================================== earnings dates

def test_an_earnings_row_cannot_claim_to_be_known_before_it_was_fetched() -> None:
    """The look-ahead that would flatter every back-test.

    Earnings dates MOVE. If a row fetched today is treated as having been known
    last week, the strategy "avoids" an announcement using a date that was not
    published yet, and the back-test prints a profit nobody could have earned.
    """
    from qb2.ingest import earnings

    fetched_at = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
    frame = pd.DataFrame(
        {"EPS Estimate": [1.0, 2.0]},
        index=pd.DatetimeIndex(["2026-09-01 12:00", "2026-10-29 12:00"],
                               tz="America/New_York"))
    rows = earnings.to_rows("AAPL", frame, fetched_at, fetched_at)

    assert list(rows["when"]) == ["past", "announced"]
    assert set(rows["knowable_time"]) == {fetched_at.isoformat()}

    # A back-test standing a week earlier must see NOTHING from this fetch.
    week_before = fetched_at - timedelta(days=7)
    assert len(earnings.knowable_at(rows, week_before)) == 0
    assert len(earnings.knowable_at(rows, fetched_at)) == 2


def test_an_etf_has_no_earnings_and_is_not_counted_as_missing() -> None:
    """An ETF is a basket, not a company. Counting it as missing data would make
    every coverage number wrong and send the census red for no real reason."""
    from qb2.ingest import earnings

    coverage = [
        earnings.Coverage("AAPL", "us_liquid", "STOCK", 25, 24, 1, "OK"),
        earnings.Coverage("ISF.L", "uk_etf", "ETF", 0, 0, 0, "N/A (ETF)",
                          "a basket of shares does not report results"),
    ]
    text = earnings.report(coverage)
    assert "1/1" in text, text          # the ETF is out of the denominator
    assert "N/A" in text
    assert "MISSING" not in text


def test_the_provider_time_of_day_is_marked_unreliable() -> None:
    """It returns New York time even for London shares. We use the DATE."""
    from qb2.ingest import earnings

    frame = pd.DataFrame(
        {"EPS Estimate": [1.0]},
        index=pd.DatetimeIndex(["2026-10-30 11:00"], tz="America/New_York"))
    rows = earnings.to_rows("BP.L", frame, datetime(2026, 10, 2, tzinfo=UTC),
                            datetime(2026, 10, 2, tzinfo=UTC))
    assert bool(rows["time_of_day_reliable"].iloc[0]) is False
    assert rows["earnings_date"].iloc[0] == "2026-10-30"


# ================================================================= standing

def test_the_default_test_run_stays_offline() -> None:
    """A suite that needs the internet fails on a train and teaches nothing.

    Checked by reading this module's IMPORTS, not by grepping its own text -- a
    grep matches the very line doing the grepping and proves nothing.
    """
    import ast

    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "yfinance" not in imported
    assert "requests" not in imported


def test_the_sender_is_still_disarmed() -> None:
    from qb2.execution import sender
    assert sender.ARMED is False


# ================================================================ one writer

def test_two_recorders_cannot_write_at_once(tmp_path: Path) -> None:
    """An hourly job on a laptop WILL overlap with itself.

    A catch-up started by hand, a missed trigger fired late, a run still going
    when the next hour comes round. Two processes writing one parquet file can
    leave it truncated -- and a truncated bar file is worse than a missing one,
    because it still reads as data.
    """
    from qb2.data.front_door import StoreLocked, WriterLock

    lock = tmp_path / "recorder.lock"
    with WriterLock(lock):
        with pytest.raises(StoreLocked):
            with WriterLock(lock):
                pass
    assert not lock.exists(), "the lock must be released on the way out"


def test_standing_down_for_another_run_is_not_a_failure() -> None:
    """The scheduler overlapping is healthy; reporting it as a crash is not.

    If an overlap exited non-zero, Task Scheduler would show a failure every time
    the recorder worked correctly, and the one place anyone looks would cry wolf.
    """
    source = (REPO_ROOT / "qb2" / "tools" / "record_now.py").read_text(
        encoding="utf-8")
    stand_down = source.index("another recorder is already running")
    following = source[stand_down:stand_down + 400]
    assert "return 0" in following, (
        "an overlapping run must exit 0, not look like a broken run")


# ====================================================== quarantine that means something

def test_a_tiny_provider_revision_does_not_become_a_quarantine_file(
        tmp_path: Path) -> None:
    """Measured on live data: re-fetched bars differ by 0.018%-0.063%.

    Yahoo quietly revises its own numbers by a fraction of a basis point. Treating
    each one as a conflict produced 315 quarantine files in two days and would
    produce hundreds more every day -- which does not protect the data, it buries
    the one real conflict among thousands of false ones. The original bar still
    stands and the revision is still counted; it just does not get its own file.
    """
    manifest = tmp_path / "m.jsonl"
    first = bars_frame(datetime(2026, 9, 29, 14, 0, tzinfo=UTC), 4, price=100.0)
    recorder.save_bars(recorder.Bars("AAA", "1m", "US", "USD", first),
                       root=tmp_path, manifest=manifest)

    revised = first.copy()
    revised["close"] = revised["close"] * 1.0002          # 0.02%, as measured
    records = recorder.save_bars(
        recorder.Bars("AAA", "1m", "US", "USD", revised),
        root=tmp_path, manifest=manifest)

    quarantined = [r for r in records if r.get("kind") == "quarantine"]
    assert quarantined == [], "a 0.02% revision must not be a conflict"
    revisions = [r for r in records if r.get("kind") == "revision"]
    assert len(revisions) == 1, "but it must still be counted, not ignored"
    assert list(tmp_path.glob("quarantine/*.parquet")) == []

    kept = pd.read_parquet(tmp_path / "1m" / "AAA" / "2026-09-29.parquet")
    assert kept["close"].iloc[0] == pytest.approx(100.0), "the original stands"


def test_a_real_change_is_still_quarantined_loudly(tmp_path: Path) -> None:
    """The other half: the guard must still catch a bar that really changed.

    If the tolerance swallowed everything, the scar it came from would be back.
    """
    manifest = tmp_path / "m.jsonl"
    first = bars_frame(datetime(2026, 9, 29, 14, 0, tzinfo=UTC), 4, price=100.0)
    recorder.save_bars(recorder.Bars("AAA", "1m", "US", "USD", first),
                       root=tmp_path, manifest=manifest)

    changed = first.copy()
    changed["close"] = changed["close"] * 1.05            # 5%: a different bar
    records = recorder.save_bars(
        recorder.Bars("AAA", "1m", "US", "USD", changed),
        root=tmp_path, manifest=manifest)

    quarantined = [r for r in records if r.get("kind") == "quarantine"]
    assert len(quarantined) == 1
    assert list(tmp_path.glob("quarantine/*.parquet")), "the evidence is kept"
    kept = pd.read_parquet(tmp_path / "1m" / "AAA" / "2026-09-29.parquet")
    assert kept["close"].iloc[0] == pytest.approx(100.0), "the original stands"


def test_a_lock_from_a_dead_process_does_not_block_the_next_run(
        tmp_path: Path) -> None:
    """Found for real: a run killed mid-backfill wedged the recorder.

    The lock was 35 minutes old and its process was long gone, but the only test
    for abandonment was AGE -- and the age limit (an hour) is longer than the
    gap between hourly runs. So one killed run could block every run for an
    hour, which on perishable minute data is exactly the cost we are trying to
    avoid. A lock whose process no longer exists is abandoned, whatever its age.
    """
    from qb2.data.front_door import WriterLock

    lock = tmp_path / "recorder.lock"
    # PID 1 does not identify a live process we could be waiting on here, and a
    # freshly-written lock is nowhere near the age limit.
    lock.write_text("pid=999999 at=2026-10-02T17:43:05+00:00", encoding="utf-8")

    with WriterLock(lock, stale_after=3_600):
        pass                                   # must not raise

    assert lock.with_suffix(".lock.abandoned").exists(), (
        "the abandoned lock is kept as evidence, not silently removed")


def test_a_lock_held_by_a_live_process_is_still_respected(tmp_path: Path) -> None:
    """The other half: liveness must not become an excuse to steal any lock."""
    import os

    from qb2.data.front_door import StoreLocked, WriterLock

    lock = tmp_path / "recorder.lock"
    lock.write_text(f"pid={os.getpid()} at=2026-10-02T17:43:05+00:00",
                    encoding="utf-8")
    with pytest.raises(StoreLocked):
        with WriterLock(lock, stale_after=3_600):
            pass


# ================================================== no unfinished bar is saved

def test_every_unfinished_bar_is_dropped_not_just_the_last_one() -> None:
    """Found in live samples: 23 of 800 delay readings were NEGATIVE.

    A negative delay means the newest bar we kept is stamped in the FUTURE -- it
    had not finished happening yet. The guard only ever removed ONE trailing bar,
    so when two were unfinished the second survived and was saved. A saved
    unfinished bar has a high and a low that can still change, which is the exact
    look-ahead this recorder was built to refuse.
    """
    now = datetime(2026, 10, 2, 14, 30, tzinfo=UTC)
    # Three closed bars, then two that have not finished.
    index = pd.DatetimeIndex([
        datetime(2026, 10, 2, 14, 26, tzinfo=UTC),
        datetime(2026, 10, 2, 14, 27, tzinfo=UTC),
        datetime(2026, 10, 2, 14, 28, tzinfo=UTC),
        datetime(2026, 10, 2, 14, 30, tzinfo=UTC),   # still forming
        datetime(2026, 10, 2, 14, 31, tzinfo=UTC),   # stamped in the future
    ])
    frame = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
                          "volume": 1}, index=index)

    kept = recorder.drop_forming_bar(frame, "1m", now)

    assert len(kept) == 3, f"kept {len(kept)} bars, the last is {kept.index[-1]}"
    assert kept.index[-1] == datetime(2026, 10, 2, 14, 28, tzinfo=UTC)
    # The thing the delay sample would have reported: never negative.
    age = (now - kept.index[-1].to_pydatetime()).total_seconds()
    assert age > 0, "a kept bar must already be in the past"


def test_a_finished_bar_is_still_kept() -> None:
    """The guard must not become "throw away the newest data"."""
    now = datetime(2026, 10, 2, 14, 30, tzinfo=UTC)
    index = pd.DatetimeIndex([datetime(2026, 10, 2, 14, 28, tzinfo=UTC),
                              datetime(2026, 10, 2, 14, 29, tzinfo=UTC)])
    frame = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
                          "volume": 1}, index=index)
    kept = recorder.drop_forming_bar(frame, "1m", now)
    assert len(kept) == 2, "14:29 finished at 14:30 and must be kept"


# ================================ the task's own context (QT-10 addendum)

def test_the_run_log_records_the_directory_it_started_in() -> None:
    r"""Confirmed by probe: Task Scheduler starts this task in C:\Windows\system32.

    That is why the original shared ``recorder.log`` never existed anywhere -- the
    relative path resolved under System32, where it cannot be created. It is also
    why a window titled ``C:\Windows\System32\cmd.exe`` appeared every hour.
    The directory is now written down on every run rather than assumed, so the
    same mistake cannot be made silently twice.
    """
    source = (REPO_ROOT / "qb2" / "tools" / "record_now.py").read_text(
        encoding="utf-8")
    assert "started in directory" in source
    assert "os.getcwd()" in source


def test_every_path_the_run_writes_to_is_absolute() -> None:
    """A relative path is a path that depends on who started you.

    The log directory is built from the module's own location, so it lands in the
    repository whatever directory the scheduler chooses.
    """
    assert record_now.LOG_DIR.is_absolute()
    assert record_now.RECORDER_LOCK.is_absolute()


def test_a_run_that_was_killed_is_visible_afterwards(tmp_path: Path) -> None:
    """If the operator closes the window mid-run, that run died.

    A finished run writes a last line. A killed one cannot. So a log without that
    line is a run that did not finish -- which is exactly what could not be told
    apart before, when every run appended to one shared file.
    """
    folder = tmp_path / "recorder"
    folder.mkdir()
    (folder / "run-2026-10-02T100000.log").write_text(
        "==== run started\n  did some work\n==== run finished exit=0 at ...\n",
        encoding="utf-8")
    (folder / "run-2026-10-02T110000.log").write_text(
        "==== run started\n  did some work\n", encoding="utf-8")   # killed

    unfinished = record_now.unfinished_runs(folder)
    assert [p.name for p in unfinished] == ["run-2026-10-02T110000.log"]


def _batch_commands() -> list[str]:
    """The batch file's real commands, with its REM comments stripped.

    Checked against the commands, not the prose: the comments legitimately
    mention "pause" to explain why there is none, and a plain text search would
    match the explanation and fail.
    """
    text = (REPO_ROOT / "qb2" / "tools" / "run_recorder.bat").read_text(
        encoding="utf-8")
    return [line for line in text.splitlines()
            if not line.strip().lower().startswith("rem")]


def test_the_launcher_ends_by_itself() -> None:
    """Nothing may wait for a keypress: an unattended run has nobody to press one.

    A "pause" or a "cmd /k" would leave a window open for ever, holding the
    scheduler's instance slot and inviting someone to close it mid-run.
    """
    commands = " ".join(_batch_commands()).lower()
    assert "pause" not in commands
    assert "cmd /k" not in commands
    assert "exit /b %rc%" in commands, "it must exit with the run's own code"


# ============================= honest alarms, honest delay (found in a real run)

def test_the_catch_up_is_not_judged_by_the_hourly_alarm() -> None:
    """A 110-minute catch-up is correct behaviour, not a fault.

    The real 20:00 run took 110 minutes to backfill everything and reported
    itself NOT CLEAN, because the alarm meant for the hourly top-up was applied
    to the whole run. The alarm exists to catch an hourly run overrunning its own
    trigger; the catch-up deliberately runs when nothing follows it until 07:00.
    An alarm that fires on correct behaviour teaches people to ignore alarms.
    """
    assert record_now.RUN_ALARM_MINUTES == 45.0
    # Was ">= 240" (it was 480). Lowered under the 180-minute task kill on
    # 2026-10-05 -- see test_s3f_recorder_weekend.py -- still above the 110.
    assert record_now.CATCHUP_ALARM_MINUTES > 110.0
    assert record_now.CATCHUP_ALARM_MINUTES > record_now.RUN_ALARM_MINUTES


def test_the_delay_is_not_sampled_during_a_backfill() -> None:
    """3,106 samples in one session, worst reading 102.6 minutes -- both wrong.

    Every saved name was emitting a sample, including during the backfill, where
    "the newest bar" is the end of a 60-day historical fetch rather than the live
    feed. That inflates the count until the "20 samples over 3 sessions" bar is
    cleared by noise, and poisons the median with readings that measure nothing.

    The delay is now measured once per market per run, by the dedicated sampler
    that runs first -- one honest reading instead of hundreds of artefacts.
    """
    import inspect

    source = inspect.getsource(recorder.capture_incremental)
    assert "delay_sample" not in source, (
        "the capture path must not emit delay samples; the sampler does that")
