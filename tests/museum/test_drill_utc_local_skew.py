"""Incident: the red-light drill failed for one hour a night, and it was a clock.

WHAT HAPPENED. Between 00:00 and 01:00 UK summer time, the engine suite reported
``test_drill_fires_both_meters_and_leaves_no_trace`` as FAILED. Nothing had
changed in the code. During that hour British Summer Time runs a day ahead of
UTC, and the two halves of that test were reading different clocks:

* the fixture built its bars and equity marks with ``date.today()`` -- LOCAL;
* ``run_drill`` defaulted to ``datetime.now(timezone.utc).date()`` -- UTC.

So the drill doctored its copy with a crashed equity mark stamped
``<utc-today>T23:59:59Z`` while the fixture's healthy mark sat at
``<utc-today + 1 day>T00:00:00Z``. ``drawdown_from_peak`` reads the LATEST mark,
which was the healthy one, so the drawdown light could not fire and the drill
reported that the lights were broken.

The monitor was fine. The FIXTURE was wrong, and it was wrong about something
worth having a scar for: a test that builds its world on a different clock from
the code under test is testing a coincidence.

THE SCAR: fixtures use the code's clock.

This test recreates that hour on demand -- it forces the LOCAL clock a day ahead
of UTC, exactly as BST does -- and requires the drill to work through it. It was
RED before the fixture was fixed. If anyone ever puts ``date.today()`` back, it
goes red again.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import cast

import pytest

import tests.monitors.test_status as status_tests
from monitors.status import run_drill


class _LocalDateOneDayAhead:
    """Stands in for ``date`` at 00:30 BST: today() is a day ahead of UTC.

    Deliberately NOT a subclass of ``date``: the fixture only ever calls
    ``date.today()``, and a stand-in that offers exactly that says so more
    plainly than a subclass which silently inherits everything else.
    """

    @staticmethod
    def today() -> date:
        return datetime.now(timezone.utc).date() + timedelta(days=1)


def _real_fixture_body() -> Callable[[Path], Path]:
    """The engine suite's own ``db`` fixture, as a plain callable.

    pytest keeps the undecorated function on the fixture object. Reaching for it
    is deliberate: this test must exercise the REAL fixture, so that fixing it
    fixes this test and reverting it breaks this test.
    """
    return cast(Callable[[Path], Path],
                getattr(status_tests.db, "__wrapped__"))


@pytest.fixture
def db_built_during_the_bst_midnight_hour(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """The REAL engine fixture, built while the local clock runs a day ahead.

    It calls the engine suite's own ``db`` fixture body rather than a copy, so
    fixing the real fixture fixes this test too -- and reverting it breaks this
    test again. A copy here would have rotted apart from the thing it guards.

    ``raising=False`` on purpose: once the fixture stopped reading the local
    clock it stopped importing ``date`` at all, and this patch became the
    no-op it should be. Put ``date.today()`` back and the patch bites again.
    """
    monkeypatch.setattr(status_tests, "date", _LocalDateOneDayAhead,
                        raising=False)
    return _real_fixture_body()(tmp_path)


def test_the_drill_still_fires_when_local_time_runs_ahead_of_utc(
        db_built_during_the_bst_midnight_hour: Path) -> None:
    """Both lights must go red on demand, whatever the local clock says."""
    result = run_drill(db_built_during_the_bst_midnight_hour)

    report = "\n".join(result.lines)
    assert "data_freshness: RED" in report, report
    assert "drawdown: RED" in report, report
    assert result.passed is True, (
        "the drill could not prove the lights work while the local clock ran "
        f"ahead of UTC -- a fixture/code clock mismatch:\n{report}")


def test_the_fixture_no_longer_depends_on_the_local_clock() -> None:
    """The fix, stated directly: the fixture reads UTC, like the code does.

    Belt and braces for the test above -- that one proves the behaviour, this
    one names the cause, so a future reader sees immediately what to keep.
    """
    import inspect

    source = inspect.getsource(_real_fixture_body())
    assert "date.today()" not in source, (
        "the engine's status fixture is back on the LOCAL clock; it must use "
        "the same UTC clock run_drill uses (see this module's docstring)")
    assert "timezone.utc" in source


def test_the_incident_itself_is_still_reproducible(tmp_path: Path) -> None:
    """The museum piece: recreate the exact state and watch the light fail.

    A healthy equity mark dated AFTER the drill's doctored one -- which is what
    a local-clock fixture produced during the BST hour -- and the drawdown light
    cannot fire, because the meter reads the newest mark. This does not guard
    against regression (the two tests above do that); it keeps the mechanism
    demonstrable, so nobody has to rediscover it from first principles.
    """
    database = _real_fixture_body()(tmp_path)
    tomorrow = datetime.now(timezone.utc).date() + timedelta(days=1)
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            "INSERT INTO paper_equity (ticker, event_time, equity, close) "
            "VALUES ('NVDA', ?, 10000.0, 100.0)", (f"{tomorrow}T00:00:00Z",))
        connection.commit()
    finally:
        connection.close()

    result = run_drill(database)

    report = "\n".join(result.lines)
    assert "data_freshness: RED" in report          # this half still fires
    assert "drawdown: OK" in report, report          # and this half cannot
    assert result.passed is False
