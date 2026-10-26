"""QT-25 C: a session's 5-minute bars are NOT YET DUE until its catch-up is due -- shown, not RED.

The false alarm: the first run after the PC wakes (Wed 21 18:21, Thu 22 18:14, Fri 23 18:08 UK) came
before that day's 5-minute catch-up, which record_now runs on the day's last trigger (20:00 UK) or once
both markets have shut, whichever is first. The clean step judged London's 5-minute bars against the
session that had just closed, called them missing, and the run NOT CLEAN -- an alarm on correct
behaviour every such day. Nothing loosened: once the catch-up is due, a missing day is RED as before.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from qb2.data import clean_step
from qb2.tools import record_now, run_times

UK = ZoneInfo("Europe/London")


def _censuses(five: str, one: str, five_us: str | None = None) -> list[clean_step.Summary]:
    """The two censuses the clean step judges: newest 5m and 1m bar per market."""
    return [clean_step.Summary.of("5m", 0.982, [("uk_etf", five), ("us_liquid", five_us or five)]),
            clean_step.Summary.of("1m", 0.742, [("uk_etf", one), ("us_liquid", one)])]


# The three runs' inputs, as their logs record them: each prior evening's 20:00 UK catch-up had
# fetched the 5m bars to the day before; the hourly 1m top-up had the day itself. (The census files
# of those runs were overwritten by the same evening's 20:00 run: same name per day.)
REPLAYS = [(datetime(2026, 10, 21, 18, 21, 58, tzinfo=UK), "2026-10-20", "2026-10-21"),
           (datetime(2026, 10, 22, 18, 14, 30, tzinfo=UK), "2026-10-21", "2026-10-22"),
           (datetime(2026, 10, 23, 18, 8, 41, tzinfo=UK), "2026-10-22", "2026-10-23")]


@pytest.mark.parametrize(("now", "five", "one"), REPLAYS)
def test_the_three_wake_up_runs_are_clean_with_the_day_not_yet_due(now: datetime, five: str,
                                                                   one: str) -> None:
    verdict = clean_step.judge(_censuses(five, one), now, strict=True)
    assert verdict.reasons == ()
    assert verdict.line() == (f"Clean store: fresh to {five} · 5m census 98.2% · OK · 5m LSE {one}: "
                              "NOT YET DUE (its catch-up runs from 20:00 UK)")


def test_once_the_catch_up_is_due_a_missing_day_is_red_as_before() -> None:
    verdict = clean_step.judge(_censuses("2026-10-22", "2026-10-23"),
                               datetime(2026, 10, 23, 20, 30, tzinfo=UK), strict=True)
    assert verdict.reasons == ("5m LSE clean bars end 2026-10-22, but the 2026-10-23 session has "
                               "finished",)


def test_an_older_missing_day_is_red_before_todays_catch_up() -> None:
    verdict = clean_step.judge(_censuses("2026-10-21", "2026-10-23", five_us="2026-10-22"),
                               datetime(2026, 10, 23, 18, 8, 41, tzinfo=UK), strict=True)
    assert verdict.reasons == ("5m LSE clean bars end 2026-10-21, but the 2026-10-22 session has "
                               "finished",)


@pytest.mark.parametrize(("day", "due"), [
    (date(2026, 10, 23), datetime(2026, 10, 23, 20, 0, tzinfo=UK)),   # BST: New York shuts 21:00 UK
    (date(2026, 10, 26), datetime(2026, 10, 26, 20, 0, tzinfo=UK)),   # this week: both at 20:00 UK
    (date(2026, 11, 26), datetime(2026, 11, 26, 16, 30, tzinfo=UK)),  # Thanksgiving: London alone
])
def test_the_catch_up_is_due_at_the_last_trigger_or_once_both_markets_have_shut(day: date,
                                                                               due: datetime) -> None:
    assert run_times.catchup_due(day) == due


def test_this_weeks_clock_judges_monday_at_1959_and_2000_uk() -> None:
    censuses = _censuses("2026-10-23", "2026-10-26", five_us="2026-10-23")
    before = clean_step.judge(censuses, datetime(2026, 10, 26, 19, 59, tzinfo=UK), strict=True)
    after = clean_step.judge(censuses, datetime(2026, 10, 26, 20, 0, tzinfo=UK), strict=True)
    assert (before.red, after.red) == (False, True)
    assert "5m LSE clean bars end 2026-10-23, but the 2026-10-26 session has finished" in after.reasons


def test_the_last_trigger_is_the_one_record_now_catches_up_on() -> None:
    assert record_now.LAST_RUN_HOUR_LOCAL == run_times.HOURS[-1] == 20
