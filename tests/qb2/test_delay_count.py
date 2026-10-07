"""QT-12R: which delay samples COUNT towards FACTS row o, and the meter that
watches for sessions the recorder missed.

Every rule is tested on BOTH markets, so a fix that only covers the US (the
market that happened to have samples) cannot pass.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from qb2.tools import delay_count, sample_delay

# One ordinary full session per market, and a time inside it (UTC).
INSIDE = {"US": datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc),
          "LSE": datetime(2026, 10, 6, 10, 0, tzinfo=timezone.utc)}
AGE = {"US": 75.0, "LSE": 970.0}          # what each feed really shows


def _row(market: str, at: datetime, age: float | None = None,
         verified: bool = True) -> dict[str, object]:
    seconds = AGE[market] if age is None else age
    return {"kind": "delay_sample", "market": market,
            "age_seconds": seconds, "age_seconds_raw": seconds,
            "clock_checked": verified,
            "at_utc": at.isoformat(timespec="seconds")}


def _write(path: Path, rows: list[dict[str, object]]) -> Path:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return path


def _hourly(market: str, day: date, count: int) -> list[dict[str, object]]:
    start = INSIDE[market].replace(year=day.year, month=day.month, day=day.day)
    return [_row(market, start + timedelta(hours=n) - timedelta(hours=1))
            for n in range(count)]


# ------------------------------------------------------- what counts at all --

@pytest.mark.parametrize("market", ["US", "LSE"])
def test_an_ordinary_in_hours_sample_counts_in_both_markets(market: str) -> None:
    assert delay_count.countable([_row(market, INSIDE[market])]) != []


@pytest.mark.parametrize("market, holiday", [
    ("US", datetime(2026, 9, 7, 15, 0, tzinfo=timezone.utc)),     # Labor Day
    ("LSE", datetime(2026, 8, 31, 10, 0, tzinfo=timezone.utc)),   # bank holiday
])
def test_a_holiday_is_not_a_session(market: str, holiday: datetime) -> None:
    """The old check knew weekdays, not holidays. On a holiday yfinance hands
    back the last day's bars, so a day-old bar posed as a 'delay while open'."""
    assert not delay_count.in_full_session(market, holiday)
    stale = _row(market, holiday, age=3 * 24 * 3600.0)
    assert delay_count.countable([stale]) == []


@pytest.mark.parametrize("market, half_day", [
    ("US", datetime(2026, 11, 27, 15, 0, tzinfo=timezone.utc)),   # shuts 13:00 ET
    ("LSE", datetime(2026, 12, 24, 10, 0, tzinfo=timezone.utc)),  # shuts 12:30
])
def test_a_half_day_is_not_counted_as_a_session(market: str, half_day: datetime,
                                                tmp_path: Path) -> None:
    """Even inside its short hours: half a session is not one of the three."""
    assert delay_count.full_session_hours(market, half_day.date()) is None
    rows = [_row(market, half_day + timedelta(minutes=n)) for n in range(5)]
    assert sample_delay.sessions_covered(_write(tmp_path / "m.jsonl", rows)) == {}


@pytest.mark.parametrize("market, outside", [
    ("US", datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)),    # 08:00 New York
    ("US", datetime(2026, 10, 6, 21, 0, tzinfo=timezone.utc)),    # after the close
    ("LSE", datetime(2026, 10, 6, 6, 30, tzinfo=timezone.utc)),   # 07:30 London
    ("LSE", datetime(2026, 10, 6, 16, 0, tzinfo=timezone.utc)),   # 17:00 London
])
def test_an_out_of_hours_sample_is_not_counted(market: str,
                                               outside: datetime) -> None:
    assert delay_count.countable([_row(market, outside)]) == []


@pytest.mark.parametrize("market", ["US", "LSE"])
def test_a_bar_from_before_the_open_is_not_a_delay(market: str) -> None:
    """Minutes after the open the newest bar can still be yesterday's close.
    That is 'no bar yet', not a 16-hour feed delay."""
    rows = [_row(market, INSIDE[market], age=16 * 3600.0)]
    assert delay_count.countable(rows) == []


@pytest.mark.parametrize("market", ["US", "LSE"])
def test_overlapping_runs_reading_the_same_bar_count_once(market: str) -> None:
    """A hand run beside the scheduled one (the recorder's lock does not cover
    `python -m qb2.tools.sample_delay`) reads the same bar twice."""
    first = _row(market, INSIDE[market])
    second = _row(market, INSIDE[market] + timedelta(seconds=20),
                  age=AGE[market] + 20)
    assert len(delay_count.countable([first, second])) == 1
    later = _row(market, INSIDE[market] + timedelta(hours=1))
    assert len(delay_count.countable([first, second, later])) == 2


def test_the_sampler_writes_nothing_on_a_holiday(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The front door: weekday hours say open, the calendar says shut."""
    import pandas as pd
    import yfinance

    from qb2.ingest import recorder

    class Stale:                       # what yfinance returns on a holiday
        def __init__(self, ticker: str) -> None:
            pass

        def history(self, period: str, interval: str) -> pd.DataFrame:
            index = pd.date_range("2026-08-28 15:28", periods=3, freq="1min",
                                  tz="UTC")
            return pd.DataFrame({"Close": [1.0, 1.0, 1.0]}, index=index)

    monkeypatch.setattr(recorder, "market_is_open", lambda market, now=None: True)
    monkeypatch.setattr(delay_count, "full_session_hours", lambda market, day: None)
    monkeypatch.setattr(yfinance, "Ticker", Stale)
    manifest = tmp_path / "manifest.jsonl"
    assert sample_delay.take_samples(manifest=manifest) == []
    assert not manifest.exists()


# ------------------------------------------------------------- the meter --

@pytest.mark.parametrize("market", ["US", "LSE"])
def test_a_session_with_no_samples_is_red(market: str, tmp_path: Path) -> None:
    """The birth certificate (SCARS #9), for the meter that was missing."""
    manifest = _write(tmp_path / "manifest.jsonl", [])
    meters = delay_count.session_meter(
        manifest, markets=(market,), days_back=3, today=date(2026, 10, 7))
    assert meters[0]["status"] == "RED"
    assert meters[0]["short_sessions"]
    assert "did not run" in str(meters[0]["detail"])


@pytest.mark.parametrize("market", ["US", "LSE"])
def test_one_sample_in_a_session_is_red_not_healthy(market: str,
                                                    tmp_path: Path) -> None:
    """What really happened to London on Mon 5 and Tue 6 Oct: the PC was on for
    minutes of the session, one or two readings landed, and the old meter
    (RED only at zero) called that fine."""
    manifest = _write(tmp_path / "manifest.jsonl",
                      _hourly(market, date(2026, 10, 6), 1))
    meters = delay_count.session_meter(
        manifest, markets=(market,), days_back=1, today=date(2026, 10, 7))
    assert meters[0]["status"] == "RED", meters[0]["detail"]
    assert "2026-10-06 (1 of" in str(meters[0]["detail"])


@pytest.mark.parametrize("market", ["US", "LSE"])
def test_unverified_samples_do_not_make_the_meter_green(market: str,
                                                        tmp_path: Path) -> None:
    rows = [{**row, "clock_checked": False}
            for row in _hourly(market, date(2026, 10, 6), 5)]
    manifest = _write(tmp_path / "manifest.jsonl", rows)
    meters = delay_count.session_meter(
        manifest, markets=(market,), days_back=1, today=date(2026, 10, 7))
    assert meters[0]["status"] == "RED"


@pytest.mark.parametrize("market", ["US", "LSE"])
def test_a_well_sampled_session_is_green(market: str, tmp_path: Path) -> None:
    """The other half of the certificate: it must be able to go green too."""
    rows: list[dict[str, object]] = []
    for day in (date(2026, 10, 5), date(2026, 10, 6)):
        rows += _hourly(market, day, delay_count.MIN_SAMPLES_PER_SESSION)
    manifest = _write(tmp_path / "manifest.jsonl", rows)
    meters = delay_count.session_meter(
        manifest, markets=(market,), days_back=2, today=date(2026, 10, 7))
    assert meters[0]["status"] == "OK", meters[0]["detail"]


def test_the_meter_is_in_the_verdict_every_run_prints(tmp_path: Path) -> None:
    """It existed, it was tested, and nothing ever called it -- so it could not
    fire. The hourly run prints verdict(), so the meter lives there."""
    manifest = _write(tmp_path / "manifest.jsonl",
                      _hourly("LSE", date(2026, 10, 6), 1))
    text = sample_delay.verdict(manifest, today=date(2026, 10, 7))
    assert "meter LSE: RED" in text
    assert "meter US: RED" in text
