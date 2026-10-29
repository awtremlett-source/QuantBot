"""QT-29 D: ^VIX's daily row is final only once Cboe has settled it -- 16:20 New York, on either clock. Offline.

Seen live (QT-27, QT-28): the 20:00 UK top-up wrote ^VIX's row at about 20:08 UK = 16:08 New York, seven
minutes before Cboe strikes VIX's official close (16:15 New York); the next evening's re-fetch corrected
it (27 Oct 17.54 -> 17.52). The door now refuses a ^VIX row until 16:20 on New York's own clock, and the
next top-up takes it. Shares are unchanged (closed at the bell). The advisor and the bot pot read the
close dated BEFORE their day (live.vix_before), so no day is processed on an early ^VIX; with none
within 5 days, ADV-0's registered rule calls it missing, which counts as unsettled.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from qb2.advisor import live
from qb2.data import daily_step
from qb2.guard import stops
from qb2.ingest import daily

UK = ZoneInfo("Europe/London")
VIX = {"yfinance": "^VIX", "quote_currency": "USD", "exchange": "Cboe (New York clock)"}
AAPL = {"yfinance": "AAPL", "quote_currency": "USD", "exchange": "NASDAQ"}
ZONES = {"^VIX": "America/Chicago", "AAPL": "America/New_York"}       # ^VIX: the provider's own label
EARLY, FINAL = 17.54, 17.52                                            # 27 Oct, as the store saw it


def fetch(end: date) -> Callable[[str], pd.DataFrame]:
    """30 daily rows to ``end``; the row dated ``end`` carries EARLY (taken before the settle), the rest FINAL."""
    def get(symbol: str) -> pd.DataFrame:
        index = pd.bdate_range(end=str(end), periods=30, tz=ZONES[symbol])
        close = [FINAL] * 29 + [EARLY]
        return pd.DataFrame({"open": close, "high": 18.0, "low": 17.0, "close": close, "volume": 0.0},
                            index=index)
    return get


def newest(symbol: str, root: Path) -> tuple[date, float]:
    frame = daily.load(symbol, root)
    assert frame is not None
    return pd.Timestamp(frame.index.max()).date(), float(frame["close"].iloc[-1])


@pytest.mark.parametrize(("day", "hour"), [
    (date(2026, 10, 29), 20),   # this week: UK on GMT, New York still on summer time: 16:20 NY = 20:20 UK
    (date(2026, 11, 2), 21),    # from Mon 2 Nov, both on winter time: 16:20 NY = 21:20 UK
    (date(2026, 10, 15), 21),   # summer, both on summer time: 16:20 NY = 21:20 UK (BST)
])
def test_a_vix_row_waits_for_1620_new_york_on_either_clock(tmp_path: Path, day: date, hour: int) -> None:
    for minute, final in ((19, False), (21, True)):
        root, now = tmp_path / str(minute), datetime(day.year, day.month, day.day, hour, minute, tzinfo=UK)
        outcome = daily.ingest([VIX], fetch=fetch(day), clean_root=root, include_fx=False, now=now)
        assert (outcome.refused.get("^VIX") == [str(day)]) is not final, f"{now:%H:%M} UK"
        assert (newest("^VIX", root)[0] == day) is final, f"{now:%H:%M} UK"


def test_the_real_2008_uk_top_up_refuses_vix_but_keeps_the_shares(tmp_path: Path) -> None:
    """Wed 28 Oct, 20:08:19 UTC (16:08 New York): the shares had closed at 16:00; VIX had not settled."""
    now = datetime(2026, 10, 28, 20, 8, 19, tzinfo=timezone.utc)
    outcome = daily.ingest([AAPL, VIX], fetch=fetch(date(2026, 10, 28)), clean_root=tmp_path,
                           include_fx=False, now=now)
    assert outcome.refused == {"^VIX": ["2026-10-28"]}
    assert newest("AAPL", tmp_path)[0] == date(2026, 10, 28)
    assert newest("^VIX", tmp_path) == (date(2026, 10, 27), FINAL)


def test_the_next_top_up_takes_the_settled_row_and_no_early_close_is_ever_stored(tmp_path: Path) -> None:
    for day in (date(2026, 10, 28), date(2026, 10, 29), date(2026, 10, 30)):       # each evening at 20:08 UK
        daily.ingest([VIX], fetch=fetch(day), clean_root=tmp_path, include_fx=False,
                     now=datetime(day.year, day.month, day.day, 20, 8, tzinfo=UK))
        frame = daily.load("^VIX", tmp_path)
        assert frame is not None and EARLY not in set(frame["close"])          # never the 16:08 figure
        assert newest("^VIX", tmp_path)[0] == pd.bdate_range(end=str(day), periods=2)[0].date()
    # the advisor (and the bot pot) on Fri 30 Oct read Thursday's FINAL close, the previous session's
    assert live.vix_before(date(2026, 10, 30), date(2026, 10, 30), tmp_path) == (FINAL, date(2026, 10, 29))


def test_a_missing_vix_is_adv0s_registered_missing_rule_unsettled(tmp_path: Path) -> None:
    """ADV-0's register: 'unsettled: VIX's latest close dated before the day above 30, or missing (none
    within 5 calendar days)'. A ^VIX row not yet stored never stands in as a close of its own."""
    daily.ingest([VIX], fetch=fetch(date(2026, 10, 23)), clean_root=tmp_path, include_fx=False,
                 now=datetime(2026, 10, 26, 7, 0, tzinfo=UK))
    close, when = live.vix_before(date(2026, 10, 30), date(2026, 10, 30), tmp_path)
    assert (close, when) == (None, date(2026, 10, 23))                          # 7 days old: missing
    assert stops.unsettled(False, close) is True


def test_only_vix_waits_for_the_settle_and_a_day_without_a_session_is_none() -> None:
    at = datetime(2026, 10, 29, 20, 10, tzinfo=UK)
    assert daily_step.closed("AAPL", "US", date(2026, 10, 29), at) is True
    assert daily_step.closed("^VIX", "US", date(2026, 10, 29), at) is False
    assert daily_step.closed("^VIX", "US", date(2026, 10, 31), at) is None    # a Saturday
    assert daily_step.closed("GBPUSD=X", None, date(2026, 10, 29), at) is None
