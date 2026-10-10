"""QT-13b premortem: the after-hours step that feeds the clean store.

QT-13 found the clean store last fed on 2 Oct: nothing on the schedule ran the
front door (raw -> clean). The 1-minute census printed 0.0% for three days and
nothing went red; two label passes on the SAME data promoted 86 names on 5 Oct.
Each test below names the silence it breaks.
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from qb2.data import access, census, clean_step, front_door
from qb2.ingest import fresh_run, recorder
from qb2.tools import record_now, sample_delay

UTC = timezone.utc


# ------------------------------------------------- labels need NEW data (4) --

class _Name:
    def __init__(self, symbol: str, last_bar: str | None,
                 passes: bool = True, sessions: int = 30) -> None:
        self.symbol, self.last_bar, self.passes = symbol, last_bar, passes
        self.sessions_present, self.reasons = sessions, ()


class _Census:
    def __init__(self, names: list[_Name], taken: str) -> None:
        self.names, self.taken = names, taken


def test_the_5_oct_promotion_on_unchanged_data_does_not_promote() -> None:
    """3 Oct passed on bars ending 2 Oct; 5 Oct passed on the SAME bars and
    promoted 86 names. A second pass must be on newer data to count."""
    third = access.update_labels(
        _Census([_Name("AAPL", "2026-10-02 19:59:00+00:00")], "2026-10-03T20:00:00"))
    fifth = access.update_labels(
        _Census([_Name("AAPL", "2026-10-02 19:59:00+00:00")], "2026-10-05T20:00:00"),
        third)
    assert fifth["AAPL"].label == access.FIVE_MIN_ONLY
    assert fifth["AAPL"].consecutive_passes == 1
    assert fifth == third                         # no new evidence, nothing moves


def test_a_second_pass_on_newer_data_still_promotes() -> None:
    first = access.update_labels(
        _Census([_Name("AAPL", "2026-10-02 19:59:00+00:00")], "2026-10-03T20:00:00"))
    second = access.update_labels(
        _Census([_Name("AAPL", "2026-10-05 19:59:00+00:00")], "2026-10-05T21:30:00"),
        first)
    assert second["AAPL"].label == access.MINUTE_OK
    assert second["AAPL"].newest_bar == "2026-10-05 19:59:00+00:00"


def test_a_pass_with_no_known_last_bar_cannot_count_twice() -> None:
    first = access.update_labels(_Census([_Name("AAPL", None)], "2026-10-03T20:00:00"))
    again = access.update_labels(_Census([_Name("AAPL", None)], "2026-10-05T20:00:00"),
                                 first)
    assert again["AAPL"].label == access.FIVE_MIN_ONLY


def test_labels_written_before_qt13b_still_load(tmp_path: Path) -> None:
    path = tmp_path / "labels.json"
    path.write_text('{"labels": {"AAPL": {"symbol": "AAPL", "label": "FIVE_MIN_ONLY",'
                    ' "reason": "x", "census_taken": "t", "census_date": "d",'
                    ' "consecutive_passes": 0, "sessions_seen": 3}}}', encoding="utf-8")
    assert access.load_labels(path)["AAPL"].newest_bar == ""


# ------------------------------------------------ the calendar (7: holidays) --

def test_us_thanksgiving_is_not_a_missing_day() -> None:
    """Fri 27 Nov 2026, 12:00 UK: US was shut on Thu 26 Nov, London was open."""
    now = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
    assert clean_step.expected_session("US", now, strict=True) == date(2026, 11, 25)
    assert clean_step.expected_session("LSE", now, strict=True) == date(2026, 11, 26)
    assert clean_step.target_session(now) == date(2026, 11, 26)


def test_a_uk_bank_holiday_is_not_a_missing_day() -> None:
    """Tue 1 Sep 2026, 11:00 UK: London shut Mon 31 Aug; the US traded."""
    now = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
    assert clean_step.expected_session("LSE", now, strict=False) == date(2026, 8, 28)
    assert clean_step.expected_session("US", now, strict=False) == date(2026, 8, 31)


def test_the_us_close_decides_when_a_day_is_finished() -> None:
    """Fri 9 Oct: at 20:00 UK London has shut but New York has not."""
    assert clean_step.target_session(datetime(2026, 10, 9, 19, 0, tzinfo=UTC)) \
        == date(2026, 10, 8)
    assert clean_step.target_session(datetime(2026, 10, 9, 20, 30, tzinfo=UTC)) \
        == date(2026, 10, 9)


def test_tonights_session_is_not_overdue_until_the_next_morning() -> None:
    """The status page at 21:50 must not cry wolf about a day not yet cleaned."""
    evening = datetime(2026, 10, 9, 20, 50, tzinfo=UTC)          # Fri 21:50 UK
    assert clean_step.expected_session("US", evening, strict=False) == date(2026, 10, 8)
    monday = datetime(2026, 10, 12, 9, 30, tzinfo=UTC)          # Mon 10:30 UK
    assert clean_step.expected_session("US", monday, strict=False) == date(2026, 10, 9)


# ------------------------------------------------------ stale is loud (3) --

def _summary(interval: str, fraction: float, us: str | None,
             lse: str | None) -> clean_step.Summary:
    return clean_step.Summary(interval, fraction, {
        "US": None if us is None else date.fromisoformat(us),
        "LSE": None if lse is None else date.fromisoformat(lse)})


def test_the_three_silent_days_of_a_zero_minute_census_turn_red() -> None:
    """7-9 Oct: the clean store ended 2 Oct and the 1m census read 0.0% with no
    alarm. That exact situation must now be RED."""
    now = datetime(2026, 10, 9, 19, 0, tzinfo=UTC)
    verdict = clean_step.judge([_summary("5m", 0.0, "2026-10-02", "2026-10-02"),
                                _summary("1m", 0.0, "2026-10-02", "2026-10-02")],
                               now, strict=False)
    assert verdict.red
    assert any("1m" in r and "2026-10-08" in r for r in verdict.reasons)
    assert verdict.line() == "Clean store: fresh to 2026-10-02 · 5m census 0.0% · RED"


def test_a_census_below_its_gate_is_red_even_when_fresh() -> None:
    now = datetime(2026, 10, 12, 9, 30, tzinfo=UTC)
    verdict = clean_step.judge([_summary("5m", 0.94, "2026-10-09", "2026-10-09"),
                                _summary("1m", 0.75, "2026-10-09", "2026-10-09")],
                               now, strict=False)
    assert verdict.red and any("95%" in r for r in verdict.reasons)


def test_a_fresh_store_above_its_gates_is_ok() -> None:
    now = datetime(2026, 10, 12, 9, 30, tzinfo=UTC)
    verdict = clean_step.judge([_summary("5m", 0.982, "2026-10-09", "2026-10-09"),
                                _summary("1m", 0.747, "2026-10-09", "2026-10-09")],
                               now, strict=False)
    assert not verdict.red, verdict.reasons
    assert verdict.line() == "Clean store: fresh to 2026-10-09 · 5m census 98.2% · OK"


def test_no_census_on_file_is_red(tmp_path: Path) -> None:
    now = datetime(2026, 10, 12, 9, 30, tzinfo=UTC)
    verdict = clean_step.status_verdict(now, clean_root=tmp_path)
    assert verdict.red and "never" in verdict.line()


def test_a_step_that_stops_running_goes_red_within_one_trading_day(
        tmp_path: Path) -> None:
    """Job errors or PC off: the saved census stops moving, the clock does not."""
    _store(tmp_path, days=("2026-10-08",))
    _step(tmp_path, datetime(2026, 10, 8, 21, 0, tzinfo=UTC))
    store = tmp_path / "clean"
    for ok_at in (datetime(2026, 10, 9, 8, 50, tzinfo=UTC),       # Fri 09:50 UK
                  datetime(2026, 10, 9, 9, 50, tzinfo=UTC)):      # Fri 10:50 UK
        assert not clean_step.status_verdict(ok_at, clean_root=store).red
    monday = datetime(2026, 10, 12, 9, 50, tzinfo=UTC)            # Mon 10:50 UK
    verdict = clean_step.status_verdict(monday, clean_root=store)
    assert verdict.red and any("2026-10-09" in r for r in verdict.reasons)


# ------------------------------------------------- the step itself (2, 7) --

ENTRIES = [{"yfinance": "AAPL", "sleeve": "us_liquid"},
           {"yfinance": "BP.L", "sleeve": "uk_share"}]
SESSIONS = {"US": ("13:30", 78, 390), "LSE": ("07:00", 102, 510)}


def _raw_day(raw: Path, symbol: str, day: str) -> None:
    market = "US" if symbol == "AAPL" else "LSE"
    start, bars5, bars1 = SESSIONS[market]
    for interval, count, freq in (("5m", bars5, "5min"), ("1m", bars1, "1min")):
        index = pd.date_range(f"{day} {start}", periods=count, freq=freq, tz="UTC")
        frame = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0,
                              "close": 100.0, "volume": 10}, index=index)
        folder = raw / "intraday" / interval / symbol
        folder.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(folder / f"{day}.parquet")


def _store(tmp_path: Path, days: tuple[str, ...]) -> Path:
    for day in days:
        for symbol in ("AAPL", "BP.L"):
            _raw_day(tmp_path / "raw", symbol, day)
    return tmp_path / "clean"


def _step(tmp_path: Path, now: datetime,
          entries: Sequence[Mapping[str, object]] | None = None) -> clean_step.StepResult:
    return clean_step.run(now, entries=entries or ENTRIES, clean_root=tmp_path / "clean",
                          raw_root=tmp_path / "raw" / "intraday", digest_dir=tmp_path)


def _snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in sorted((root / "bars").rglob("*.parquet"))}


def test_every_trading_day_not_yet_cleaned_is_caught_up(tmp_path: Path) -> None:
    """The PC was off Wed and Thu nights: Friday night's run cleans all three."""
    _store(tmp_path, days=("2026-10-07", "2026-10-08", "2026-10-09"))
    result = _step(tmp_path, datetime(2026, 10, 9, 21, 0, tzinfo=UTC))
    files = sorted(_snapshot(tmp_path / "clean"))
    for day in ("2026-10-07", "2026-10-08", "2026-10-09"):
        assert f"bars/5m/AAPL/{day}.parquet" in files
        assert f"bars/1m/BP.L/{day}.parquet" in files
    assert result.verdict.fresh_to == date(2026, 10, 9)


def test_running_the_step_twice_changes_nothing(tmp_path: Path) -> None:
    _store(tmp_path, days=("2026-10-08", "2026-10-09"))
    now = datetime(2026, 10, 9, 21, 0, tzinfo=UTC)
    first = _step(tmp_path, now)
    before = _snapshot(tmp_path / "clean")
    labels = (tmp_path / "clean" / "minute_labels.json").read_text(encoding="utf-8")
    second = _step(tmp_path, now)
    assert _snapshot(tmp_path / "clean") == before
    assert (tmp_path / "clean" / "minute_labels.json").read_text(
        encoding="utf-8") == labels
    ingested = [r for r in front_door.read_manifest(tmp_path / "clean").values()]
    assert len(ingested) == 8                       # 2 names x 2 days x 2 intervals
    assert first.files_written == 8 and second.files_written == 0
    assert first.verdict == second.verdict


def test_the_step_runs_once_per_finished_day(tmp_path: Path) -> None:
    marker = tmp_path / "clean" / "after_hours.json"
    friday_night = datetime(2026, 10, 9, 21, 0, tzinfo=UTC)
    assert clean_step.is_due(friday_night, marker, after_hours=True)[0]
    clean_step.mark_done(friday_night, marker, red=False)
    assert not clean_step.is_due(friday_night, marker, after_hours=True)[0]
    monday_noon = datetime(2026, 10, 12, 11, 0, tzinfo=UTC)
    assert not clean_step.is_due(monday_noon, marker, after_hours=False)[0]
    monday_night = datetime(2026, 10, 12, 21, 0, tzinfo=UTC)
    assert clean_step.is_due(monday_night, marker, after_hours=True)[0]


def test_a_red_clean_is_retried_after_hours_only(tmp_path: Path) -> None:
    marker = tmp_path / "after_hours.json"
    now = datetime(2026, 10, 9, 21, 0, tzinfo=UTC)
    clean_step.mark_done(now, marker, red=True)
    assert clean_step.is_due(now, marker, after_hours=True)[0]
    assert not clean_step.is_due(now, marker, after_hours=False)[0]


def test_a_half_written_raw_file_is_skipped_and_named(tmp_path: Path) -> None:
    _store(tmp_path, days=("2026-10-09",))
    torn = tmp_path / "raw" / "intraday" / "5m" / "AAPL" / "2026-10-09.parquet"
    torn.write_bytes(torn.read_bytes()[: len(torn.read_bytes()) // 2])
    result = _step(tmp_path, datetime(2026, 10, 9, 21, 0, tzinfo=UTC))
    assert not (tmp_path / "clean" / "bars" / "5m" / "AAPL" / "2026-10-09.parquet").exists()
    assert any("5m/AAPL/2026-10-09.parquet" in c for c in result.complaints)
    sources = front_door.read_manifest(tmp_path / "clean")
    assert "intraday/5m/AAPL/2026-10-09.parquet" not in sources   # retried next run
    assert "intraday/5m/BP.L/2026-10-09.parquet" in sources


def test_the_step_writes_the_daily_digest_and_both_censuses(tmp_path: Path) -> None:
    _store(tmp_path, days=("2026-10-09",))
    _step(tmp_path, datetime(2026, 10, 9, 21, 0, tzinfo=UTC))
    digest = (tmp_path / "digest-2026-10-09.md").read_text(encoding="utf-8")
    assert "Clean store: fresh to 2026-10-09" in digest
    assert "minute labels" in digest
    assert (tmp_path / "clean" / "census-2026-10-09.json").is_file()
    assert (tmp_path / "clean" / "census-1m-2026-10-09.json").is_file()


def test_the_census_denominator_is_still_every_name(tmp_path: Path) -> None:
    """The step must count names with no clean data too (pinned denominator)."""
    _store(tmp_path, days=("2026-10-09",))
    entries = [*ENTRIES, {"yfinance": "MSFT", "sleeve": "us_liquid"}]
    result = _step(tmp_path, datetime(2026, 10, 9, 21, 0, tzinfo=UTC), entries)
    assert result.verdict.fraction_5m == pytest.approx(2 / 3)
    assert census.UNIVERSE_PASS_FRACTION == 0.95


# --------------------------------------- never in the sampling's way (2, 7) --

Step = Callable[[datetime, bool], str]


def _planted_run(monkeypatch: pytest.MonkeyPatch, make_step: Callable[[list[str]], Step],
                 do_catchup: bool = True) -> tuple[list[str], list[str], int]:
    """record_now._run with every slow or real thing replaced by a recorder."""
    calls: list[str] = []
    said: list[str] = []

    def capture(entries: object, interval: str, **kw: object) -> recorder.Outcome:
        calls.append(f"fetch {interval}")
        return recorder.Outcome()

    def sample() -> list[dict[str, object]]:
        calls.append("sample")
        return []

    step = make_step(calls)
    monkeypatch.setattr(sample_delay, "take_samples", sample)
    monkeypatch.setattr(recorder, "capture_incremental", capture)
    monkeypatch.setattr(clean_step, "run_if_due",
                        lambda now, after_hours: step(now, after_hours))
    monkeypatch.setattr(clean_step, "status_verdict",
                        lambda now: clean_step.Verdict(True, None, None))
    monkeypatch.setattr(recorder, "freshness", lambda: [])
    monkeypatch.setattr(sample_delay, "verdict", lambda: "planted")
    monkeypatch.setattr(record_now, "rotate_logs", lambda: [])
    monkeypatch.setattr(record_now, "say", said.append)
    # QT-14A's S4 measurements are planted out here; test_qt14a pins their order.
    monkeypatch.setattr(fresh_run, "before_clean", lambda say: None)
    monkeypatch.setattr(fresh_run, "after_clean", lambda say: None)
    args = argparse.Namespace(interval="1m", full=False)
    code = record_now._run(args, [], datetime(2026, 10, 9, 20, 30, tzinfo=UTC),
                           time.monotonic(), do_catchup)
    return calls, said, code


def test_cleaning_comes_after_the_sampling_and_every_fetch(
        monkeypatch: pytest.MonkeyPatch) -> None:
    def make(calls: list[str]) -> Step:
        def step(now: datetime, after_hours: bool) -> str:
            calls.append("clean")
            return "planted"
        return step
    calls, _, _ = _planted_run(monkeypatch, make)
    assert calls == ["sample", "fetch 1m", "fetch 1m", "fetch 5m", "fetch 1h", "clean"]


def test_a_failing_step_is_a_complaint_not_a_crash(
        monkeypatch: pytest.MonkeyPatch) -> None:
    def make(calls: list[str]) -> Step:
        def broken(now: datetime, after_hours: bool) -> str:
            raise front_door.FrontDoorError("planted")
        return broken
    _, said, code = _planted_run(monkeypatch, make)
    assert code == 1
    assert any("after-hours step failed: FrontDoorError: planted" in s for s in said)


def test_every_run_prints_the_clean_store_line_even_hourly(
        monkeypatch: pytest.MonkeyPatch) -> None:
    def make(calls: list[str]) -> Step:
        return lambda now, after_hours: "planted: not due"
    calls, said, _ = _planted_run(monkeypatch, make, do_catchup=False)
    assert calls == ["sample", "fetch 1m"]
    assert any(s.strip().startswith("Clean store: fresh to never") for s in said)
