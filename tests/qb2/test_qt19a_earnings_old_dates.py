"""QT-19 A: a results date outside the exchange calendar is ignored, never an error.

ULVR.L's real earnings file (copied 2026-10-16 to fixtures/) holds dates from 2004;
XLON's calendar starts 2006-10-16, so bot_verdict raised DateOutOfBounds and sender
check 8 errored instead of answering. Dates outside the calendar now play no part in
the "next date"; the verdict comes from the dates inside it, and a share with NO
usable date stays blocked (fail closed, unchanged).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from qb2.guard import earnings_window

FIXTURE = Path(__file__).parent / "fixtures" / "ULVR.L_earnings_2026-10-16.csv"
NOW = datetime(2026, 10, 16, 14, 0, tzinfo=timezone.utc)


def _real() -> pd.DataFrame:
    return pd.read_csv(FIXTURE, dtype=str)


def _rows(*days: str) -> pd.DataFrame:
    return pd.DataFrame({"symbol": "X.L", "earnings_date": list(days),
                         "knowable_time": "2026-10-02T17:50:45+00:00"})


def test_ulvr_real_file_answers_instead_of_raising() -> None:
    v = earnings_window.bot_verdict("ULVR.L", "STOCK", "LSE", NOW, _real())
    assert v.blocked is False
    assert "2027-02-09" in v.reason


def test_in_calendar_window_still_blocks_beside_old_dates() -> None:
    moment = datetime(2027, 2, 8, 10, 0, tzinfo=timezone.utc)          # session before
    v = earnings_window.bot_verdict("ULVR.L", "STOCK", "LSE", moment, _real())
    assert v.blocked is True and "2027-02-09" in v.reason


def test_only_pre_2006_dates_stays_blocked() -> None:
    v = earnings_window.bot_verdict("X.L", "STOCK", "LSE", NOW,
                                    _rows("2004-07-28", "2005-05-06"))
    assert v.blocked is True and "unknown" in v.reason


def test_only_dates_past_the_calendar_end_stays_blocked() -> None:
    v = earnings_window.bot_verdict("X.L", "STOCK", "LSE", NOW, _rows("2040-01-02"))
    assert v.blocked is True and "unknown" in v.reason
