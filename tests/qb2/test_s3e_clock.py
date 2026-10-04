"""Premortem for the clock behind the quote-delay measurement.

The delay is *our clock now* minus *the newest bar's timestamp*. That subtraction
is only as good as the first number, and a wrong clock produces a wrong delay that
looks entirely ordinary. A laptop that slept, or that has drifted, is the common
case -- not an exotic one.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from qb2.ingest import recorder
from qb2.tools import clock, sample_delay

UTC = timezone.utc


def test_a_wrong_clock_is_corrected_in_the_reported_age() -> None:
    """The planted offset: a clock two minutes FAST.

    The bar is 90 seconds old in truth. A clock two minutes fast makes it look
    210 seconds old. Correcting by the measured offset gets back to 90, and
    without the correction the feed is blamed for the laptop's error.
    """
    bar = datetime(2026, 10, 5, 15, 0, 0, tzinfo=UTC)
    true_now = datetime(2026, 10, 5, 15, 1, 30, tzinfo=UTC)      # 90s later
    local_now = datetime(2026, 10, 5, 15, 3, 30, tzinfo=UTC)     # clock 2 min fast

    # offset = true - local = -120s when the clock is fast.
    fast = clock.ClockCheck(True, offset_seconds=-120.0,
                            round_trip_seconds=0.05, server="planted")

    sample = recorder.delay_sample("US", bar, local_now, clock_check=fast)
    assert sample is not None
    assert sample["age_seconds_raw"] == pytest.approx(210.0)
    assert sample["age_seconds"] == pytest.approx(90.0), (
        "the reported age must be corrected by the measured clock offset")
    assert sample["clock_checked"] is True
    assert sample["clock_offset_seconds"] == pytest.approx(-120.0)
    assert true_now == local_now.fromtimestamp(
        local_now.timestamp() - 120, tz=UTC), "the planted arithmetic itself"


def test_a_slow_clock_is_corrected_the_other_way() -> None:
    """A clock running BEHIND makes a bar look fresher than it is."""
    bar = datetime(2026, 10, 5, 15, 0, 0, tzinfo=UTC)
    local_now = datetime(2026, 10, 5, 15, 0, 30, tzinfo=UTC)     # looks 30s old
    slow = clock.ClockCheck(True, offset_seconds=+60.0,
                            round_trip_seconds=0.05, server="planted")

    sample = recorder.delay_sample("US", bar, local_now, clock_check=slow)
    assert sample is not None
    assert sample["age_seconds_raw"] == pytest.approx(30.0)
    assert sample["age_seconds"] == pytest.approx(90.0), (
        "a slow clock hides real staleness; correcting reveals it")


def test_an_unreachable_time_server_flags_the_sample_rather_than_guessing() -> None:
    """Losing the reading would be worse; trusting it silently would be worst.

    The sample is kept, the age is left uncorrected, and it is marked unverified
    so it cannot quietly count towards the threshold at which row o may be quoted.
    """
    bar = datetime(2026, 10, 5, 15, 0, 0, tzinfo=UTC)
    now = datetime(2026, 10, 5, 15, 1, 0, tzinfo=UTC)
    unreachable = clock.ClockCheck(False, error="time.example: timed out")

    sample = recorder.delay_sample("US", bar, now, clock_check=unreachable)
    assert sample is not None, "the reading is kept"
    assert sample["clock_checked"] is False
    assert sample["age_seconds"] == sample["age_seconds_raw"], (
        "with no offset known, nothing may be invented")
    assert "timed out" in str(sample["clock_error"])


def test_an_unverified_sample_does_not_count_towards_the_threshold(
        tmp_path: Path) -> None:
    """"Never silently trusted" means it must not reach the quotable count.

    Otherwise a day of unreachable time servers would quietly satisfy the bar
    that FACTS row o is allowed to be quoted at.
    """
    manifest = tmp_path / "manifest.jsonl"
    with manifest.open("w", encoding="utf-8") as fh:
        for day in ("2026-10-05", "2026-10-06", "2026-10-07"):
            for n in range(8):
                fh.write(json.dumps({
                    "kind": "delay_sample", "market": "US", "age_seconds": 90.0,
                    "clock_checked": False,
                    "at_utc": f"{day}T15:0{n}:00+00:00"}) + "\n")

    text = sample_delay.verdict(manifest)
    # "UNMEASURED" contains "MEASURED", so the check has to be precise.
    assert "UNMEASURED" in text
    assert "US: MEASURED" not in text, "unverified readings must not qualify"
    assert "24 unverified" in text, "and they must be reported, not hidden"


def test_verified_samples_do_count(tmp_path: Path) -> None:
    """The other half: the correction must not block the measurement for ever."""
    manifest = tmp_path / "manifest.jsonl"
    with manifest.open("w", encoding="utf-8") as fh:
        for day in ("2026-10-05", "2026-10-06", "2026-10-07"):
            for n in range(8):
                fh.write(json.dumps({
                    "kind": "delay_sample", "market": "US", "age_seconds": 90.0,
                    "clock_checked": True, "clock_offset_seconds": 0.1,
                    "at_utc": f"{day}T15:0{n}:00+00:00"}) + "\n")
    text = sample_delay.verdict(manifest)
    assert "MEASURED" in text and "NOT YET ENOUGH" not in text


def test_a_badly_wrong_clock_is_called_suspect() -> None:
    """A few hundred milliseconds is housekeeping; minutes is a broken reading."""
    assert not clock.ClockCheck(True, offset_seconds=0.134,
                                round_trip_seconds=0.05).suspect
    assert clock.ClockCheck(True, offset_seconds=-180.0,
                            round_trip_seconds=0.05).suspect


def test_a_slow_round_trip_is_not_trusted_as_a_tight_measurement() -> None:
    """A two-second round trip cannot pin a clock to better than a second."""
    assert clock.ClockCheck(True, offset_seconds=0.1,
                            round_trip_seconds=0.05).trustworthy
    assert not clock.ClockCheck(True, offset_seconds=0.1,
                                round_trip_seconds=2.5).trustworthy


def test_asking_an_unreachable_server_never_raises() -> None:
    """An offline laptop must not crash the recorder; it must say it is offline."""
    answer = clock.ask_one("127.0.0.1", timeout=0.2)   # nothing listens here
    assert answer.checked is False
    assert answer.error
    assert answer.offset_seconds == 0.0, "no offset may be invented"


def test_check_falls_back_through_the_server_list() -> None:
    """One unreachable host is ordinary on a laptop; it must not cost the day."""
    answer = clock.check(servers=("127.0.0.1",), timeout=0.2)
    assert answer.checked is False
    assert "could not be reached" in answer.error or "127.0.0.1" in answer.error
