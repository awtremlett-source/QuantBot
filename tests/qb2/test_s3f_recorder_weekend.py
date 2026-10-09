"""The recorder after a weekend, and the tests that must never touch real data.

Found on 2026-10-05, before the first Monday under the incremental recorder:

* Every hourly run on a Monday would have skipped every name. The hourly limit
  was counted in CALENDAR days, and Friday's close to Monday morning is three of
  them, over the limit of two -- so all 225 names were "left for the catch-up",
  every hour, all day, and each run still reported itself clean.
* The catch-up alarm (480 minutes) sat above the scheduler's own 3-hour kill, so
  it could never fire: the task would be killed first.
* One test (test_recorder.py, the provider-limit test) called the recorder with
  no manifest of its own and appended "AAPL 1m lost" to the REAL manifest on
  every run -- 19 lines between 2 and 5 October.
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from qb2.ingest import recorder
from qb2.tools import record_now, sample_delay

UTC = timezone.utc
REPO_ROOT = Path(__file__).resolve().parents[2]


def bars_frame(start: datetime, count: int) -> pd.DataFrame:
    index = pd.date_range(start, periods=count, freq="1min", tz="UTC")
    return pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0,
                         "close": 100.0, "volume": 10}, index=index)


# ============================================= tests never touch real data ====

def _refused(probe: Path, write: Callable[[Path], object]) -> bool:
    """True if the write was refused. A probe that got through is removed."""
    try:
        write(probe)
    except PermissionError:
        return True
    finally:
        if probe.exists():          # only when the guard failed; a delete is a write
            probe.unlink()
    return False


def test_a_test_cannot_append_to_the_real_data_folder() -> None:
    """The exact leak: an append to data/raw/intraday/ from inside a test."""
    probe = REPO_ROOT / "data" / "raw" / "intraday" / "qb2-test-guard-probe.tmp"

    def append(path: Path) -> None:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("a test wrote this\n")

    assert _refused(probe, append), "a test was allowed to write into data/"


def test_a_test_cannot_write_parquet_into_real_data() -> None:
    """Parquet goes through pyarrow, not Python's open -- guarded separately."""
    probe = REPO_ROOT / "data" / "qb2-test-guard-probe.parquet"
    frame = bars_frame(datetime(2026, 10, 2, 14, 0, tzinfo=UTC), 2)
    assert _refused(probe, lambda p: frame.to_parquet(p)), (
        "a test was allowed to write a parquet file into data/")


def test_a_test_cannot_write_into_the_real_run_logs() -> None:
    probe = REPO_ROOT / "logs" / "recorder" / "qb2-test-guard-probe.log"
    assert _refused(probe, lambda p: p.write_text("x", encoding="utf-8")), (
        "a test was allowed to write into logs/")


def test_reading_real_data_is_still_allowed() -> None:
    """The guard refuses writes only. Tests that read the universe still work."""
    with open(REPO_ROOT / "pyproject.toml", encoding="utf-8") as handle:
        assert handle.read(1)


# =============================================== A: a weekend is not a backfill

def _saved(manifest: Path, ticker: str, last_bar: datetime) -> None:
    recorder.append_manifest({
        "kind": "capture", "status": "saved", "ticker": ticker,
        "interval": "1m", "last_bar_utc": last_bar.isoformat()}, manifest)


def test_monday_morning_tops_up_fridays_names(tmp_path: Path) -> None:
    """Fri 20:59Z to Mon 08:00Z is 3 calendar days but ONE weekday.

    Counted in calendar days, every name was skipped at every Monday trigger,
    and the run still reported clean.
    """
    asked: list[int] = []

    def fetch(names: Sequence[str], interval: str,
              days: int) -> dict[str, pd.DataFrame]:
        asked.append(days)
        return {n: bars_frame(datetime(2026, 10, 5, 7, 0, tzinfo=UTC), 3)
                for n in names}

    manifest = tmp_path / "m.jsonl"
    _saved(manifest, "FRIDAY", datetime(2026, 10, 2, 20, 59, tzinfo=UTC))

    outcome = recorder.capture_incremental(
        [("FRIDAY", "US", "USD")], "1m", fetch=fetch, root=tmp_path,
        manifest=manifest, now=datetime(2026, 10, 5, 8, 0, tzinfo=UTC),
        max_days=recorder.HOURLY_MAX_DAYS)

    assert outcome.skipped == [], f"Monday skipped Friday's name: {outcome.skipped}"
    assert outcome.saved_names == {"FRIDAY"}
    # The REQUEST is still in calendar days, so Friday's last hour is covered.
    assert asked == [3]


def test_a_real_gap_still_waits_for_the_catch_up(tmp_path: Path) -> None:
    """The limit still bites: Wed to Mon is Thu, Fri, Mon -- three weekdays."""
    manifest = tmp_path / "m.jsonl"
    _saved(manifest, "WEDNESDAY", datetime(2026, 9, 30, 20, 59, tzinfo=UTC))

    def fetch(names: Sequence[str], interval: str,
              days: int) -> dict[str, pd.DataFrame]:
        raise AssertionError("a three-weekday gap must not be fetched hourly")

    outcome = recorder.capture_incremental(
        [("WEDNESDAY", "US", "USD"), ("BRAND_NEW", "US", "USD")], "1m",
        fetch=fetch, root=tmp_path, manifest=manifest,
        now=datetime(2026, 10, 5, 8, 0, tzinfo=UTC),
        max_days=recorder.HOURLY_MAX_DAYS)

    assert {s["ticker"] for s in outcome.skipped} == {"WEDNESDAY", "BRAND_NEW"}
    assert "weekday" in outcome.skipped[0]["reason"]


# ====================================== B and C: planted runs through _run =====

class _Planted:
    """A run with a fake clock and a fake provider. Nothing real is touched."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch,
                 outcomes: dict[bool, Callable[[], recorder.Outcome]],
                 minutes: dict[bool, float]) -> None:
        self.now = 0.0
        self.lines: list[str] = []

        def capture(entries: Sequence[tuple[str, str, str]], interval: str,
                    **kwargs: object) -> recorder.Outcome:
            hourly = kwargs.get("max_days") is not None
            self.now += minutes[hourly] * 60
            return outcomes[hourly]()

        monkeypatch.setattr(time, "monotonic", lambda: self.now)
        monkeypatch.setattr(recorder, "capture_incremental", capture)
        monkeypatch.setattr(recorder, "freshness", lambda: [])
        monkeypatch.setattr(sample_delay, "take_samples", lambda: [])
        monkeypatch.setattr(sample_delay, "verdict", lambda: "QUOTE DELAY: planted")
        monkeypatch.setattr(record_now, "rotate_logs", lambda: [])
        monkeypatch.setattr(record_now, "_clean_step", lambda after_hours: [])
        monkeypatch.setattr(record_now, "say", self.lines.append)

    def run(self, do_catchup: bool) -> int:
        args = argparse.Namespace(interval="1m", full=False)
        started = datetime(2026, 10, 5, 8, 0, tzinfo=UTC)
        return record_now._run(args, [], started, self.now, do_catchup)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def _outcome(saved: int, skipped: int) -> recorder.Outcome:
    out = recorder.Outcome()
    for n in range(saved):
        out.attempted.append(f"S{n}")
        out.saved_names.add(f"S{n}")
    for n in range(skipped):
        out.attempted.append(f"K{n}")
        out.skipped.append({"ticker": f"K{n}", "interval": "1m",
                            "reason": "planted skip"})
    return out


def test_an_hourly_run_that_skips_most_names_is_not_clean(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """225 of 226 skipped, exit 0, "clean": a green light over an empty run."""
    planted = _Planted(monkeypatch, {True: lambda: _outcome(1, 225)},
                       {True: 2.0})
    assert planted.run(do_catchup=False) == 1
    assert "RUN NOT CLEAN" in planted.text
    assert "skipped 225 of 226" in planted.text


def test_an_hourly_run_with_a_few_skips_is_still_clean(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Exactly half is not MORE than half. One new name is normal."""
    planted = _Planted(monkeypatch, {True: lambda: _outcome(113, 113)},
                       {True: 2.0})
    assert planted.run(do_catchup=False) == 0, planted.text


def test_skips_in_a_catch_up_run_are_not_a_fault(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """In a catch-up run the skipped names are backfilled minutes later."""
    planted = _Planted(monkeypatch, {True: lambda: _outcome(1, 225),
                                     False: lambda: _outcome(226, 0)},
                       {True: 2.0, False: 5.0})
    assert planted.run(do_catchup=True) == 0, planted.text


def test_the_catch_up_alarm_fires_before_the_scheduler_kills_the_run() -> None:
    """The task's ExecutionTimeLimit is 3 hours. An alarm above it never rings."""
    assert record_now.TASK_KILL_MINUTES == 180.0
    assert record_now.CATCHUP_ALARM_MINUTES < record_now.TASK_KILL_MINUTES
    # Friday 2 October's first-ever backfill of 131 names took 110 minutes and
    # was correct. The alarm must not fire on that.
    assert record_now.CATCHUP_ALARM_MINUTES > 110.0


def test_a_planted_slow_catch_up_raises_the_alarm(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Hourly part 2 minutes, catch-up 3 x 50 -- 152 minutes in all."""
    planted = _Planted(monkeypatch, {True: lambda: _outcome(226, 0),
                                     False: lambda: _outcome(226, 0)},
                       {True: 2.0, False: 50.0})
    assert planted.run(do_catchup=True) == 1
    assert "alarm for a catch-up" in planted.text
    assert "hourly top-up alone" not in planted.text, (
        "only the catch-up was slow; the hourly alarm must stay quiet")


def test_a_normal_catch_up_is_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    planted = _Planted(monkeypatch, {True: lambda: _outcome(226, 0),
                                     False: lambda: _outcome(226, 0)},
                       {True: 2.0, False: 8.0})
    assert planted.run(do_catchup=True) == 0, planted.text
