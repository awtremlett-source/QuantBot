"""QT-18 A1: P15 history in back-tests (operator GO, 2026-10-16). Offline, synthetic rows.

Each guard here was seen RED first on a planted mutant of p15_history.py / p15.py
(the session log and docs/reports/QT-18.md list them).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from qb2.guard import earnings_window
from qb2.research import fills, p15, p15_history

UTC = timezone.utc
PAST = ["2025-10-30", "2026-01-29", "2026-04-30", "2026-07-30"]     # quarterly, Thursdays
NEXT = "2026-10-29"
REAL = "2026-10-02T17:50:45+00:00"


def _raw(dates: list[str], knowable: str = REAL, symbol: str = "AAPL") -> pd.DataFrame:
    return pd.DataFrame({"symbol": symbol, "earnings_date": dates,
                         "when": ["past" if d < "2026-10-02" else "announced" for d in dates],
                         "knowable_time": knowable,
                         "source": "yfinance.get_earnings_dates"})


def _close(day: str) -> datetime:
    """US close on a summer/winter day, in UTC (16:00 New York)."""
    moment: datetime = pd.Timestamp(f"{day} 16:00", tz="America/New_York").tz_convert(
        "UTC").to_pydatetime()
    return moment


def _known(history: p15_history.History, moment: datetime) -> list[str]:
    return [d.isoformat() for d in earnings_window.latest_known(history.frame, moment)]


def test_a_date_counts_as_known_from_the_close_of_the_date_before_it() -> None:
    h = p15_history.build("AAPL", "US", _raw(PAST + [NEXT]))
    just_before = _close("2026-04-30") - timedelta(microseconds=1)
    assert "2026-07-30" not in _known(h, just_before)
    assert "2026-07-30" in _known(h, _close("2026-04-30"))
    # never earlier: not at the open, not the day before
    assert "2026-07-30" not in _known(h, datetime(2026, 4, 30, 13, 30, tzinfo=UTC))


def test_every_snapshot_lists_every_date_already_known_not_only_the_newest() -> None:
    h = p15_history.build("AAPL", "US", _raw(PAST + [NEXT]))
    between = datetime(2026, 5, 15, 15, tzinfo=UTC)
    assert _known(h, between) == ["2025-10-30", "2026-01-29", "2026-04-30", "2026-07-30"]
    v = earnings_window.bot_verdict("AAPL", "STOCK", "US", between, h.frame)
    assert not v.blocked and "2026-07-30" in v.reason


def test_the_first_date_on_record_is_never_known_early() -> None:
    h = p15_history.build("AAPL", "US", _raw(PAST + [NEXT]))
    before = datetime(2025, 10, 1, 15, tzinfo=UTC)
    assert _known(h, before) == []
    assert earnings_window.bot_verdict("AAPL", "STOCK", "US", before, h.frame).blocked
    # D1's own window (29-31 Oct) is blocked even after its close made D2 known
    assert earnings_window.bot_verdict("AAPL", "STOCK", "US",
                                       datetime(2025, 10, 31, 15, tzinfo=UTC), h.frame).blocked
    assert not earnings_window.bot_verdict("AAPL", "STOCK", "US",
                                           datetime(2025, 11, 4, 15, tzinfo=UTC), h.frame).blocked


def test_the_first_date_after_2026_10_02_is_known_from_the_date_before_it() -> None:
    """The holdout's case: AAPL reported 30 Jul; its next date (29 Oct) was first
    recorded on 2 Oct. Known from 30 Jul's close, so August is not all cash."""
    h = p15_history.build("AAPL", "US", _raw(PAST + [NEXT]))
    august = datetime(2026, 8, 20, 15, tzinfo=UTC)
    assert NEXT in _known(h, august)
    assert not earnings_window.bot_verdict("AAPL", "STOCK", "US", august, h.frame).blocked


def test_a_date_whose_predecessor_is_after_2026_10_02_waits_for_its_knowable_time() -> None:
    later = "2027-01-28"
    first = _raw(PAST + [NEXT])
    second = _raw(PAST + [NEXT, later], knowable="2026-10-06T18:00:00+00:00")
    h = p15_history.build("AAPL", "US", pd.concat([first, second], ignore_index=True))
    assert later not in _known(h, datetime(2026, 10, 6, 17, tzinfo=UTC))
    assert later in _known(h, datetime(2026, 10, 6, 18, tzinfo=UTC))
    assert later not in [d.isoformat() for d in h.dates]       # never in the synthetic rule


def test_from_2026_10_02_real_rows_win_and_a_moved_date_reads_as_moved() -> None:
    moved = _raw(PAST + ["2026-10-30"], knowable="2026-10-05T18:00:00+00:00")
    h = p15_history.build("AAPL", "US", pd.concat([_raw(PAST + [NEXT]), moved],
                                                  ignore_index=True))
    assert NEXT in _known(h, datetime(2026, 10, 5, 17, tzinfo=UTC))
    assert "2026-10-30" not in _known(h, datetime(2026, 10, 5, 17, tzinfo=UTC))
    assert _known(h, datetime(2026, 10, 5, 18, tzinfo=UTC))[-1] == "2026-10-30"
    assert (p15_history.SOURCE == h.frame.loc[
        pd.to_datetime(h.frame["knowable_time"], utc=True) >= pd.Timestamp(REAL),
        "source"]).sum() == 0


def test_a_missing_quarter_blocks_until_the_next_window_ends() -> None:
    """2026-01-29 missing from the record: the gap 30 Oct -> 30 Apr is 182 days,
    over 1.5 x the median. Blocked from 30 Oct + median until 1 May."""
    dates = ["2025-01-30", "2025-05-01", "2025-07-31", "2025-10-30", "2026-04-30",
             "2026-07-30", NEXT]
    h = p15_history.build("AAPL", "US", _raw(dates))
    assert len(h.gaps) == 1
    gap = h.gaps[0]
    assert (gap.after, gap.before, gap.blocked_to) == (
        date(2025, 10, 30), date(2026, 4, 30), date(2026, 5, 1))
    assert gap.blocked_from == date(2025, 10, 30) + timedelta(days=round(h.median_gap or 0))
    assert h.blocked(date(2026, 2, 10)) and not h.blocked(date(2026, 5, 4))
    # bot_verdict alone does NOT see it -- so p15.mask must apply it
    feb = datetime(2026, 2, 10, 15, tzinfo=UTC)
    assert not earnings_window.bot_verdict("AAPL", "STOCK", "US", feb, h.frame).blocked
    index = pd.date_range("2026-02-10 09:30", periods=7, freq="1h", tz="America/New_York")
    assert not p15.mask("AAPL", "STOCK", index, "1h", "US", h.frame, h).any()
    assert p15.mask("AAPL", "STOCK", index, "1h", "US", h.frame).all()   # frame alone: open


def test_one_stale_date_cannot_be_its_own_median() -> None:
    """AAL.L's record: 2010-03-01, then 2027-02-19 -- one 17-year gap. Capped at a
    half-year, it is a missing-quarter span over the whole back-test."""
    h = p15_history.build("AAL.L", "LSE", _raw(["2010-03-01", "2027-02-19"], symbol="AAL.L"))
    assert len(h.gaps) == 1 and h.blocked(date(2024, 3, 1)) and h.blocked(date(2026, 8, 20))
    assert h.gaps[0].blocked_from == date(2010, 3, 1) + timedelta(days=182)


def test_a_half_yearly_reporter_is_judged_by_its_own_median() -> None:
    dates = ["2024-02-22", "2024-07-25", "2025-02-20", "2025-07-24", "2026-02-19",
             "2026-07-23", "2027-02-18"]
    h = p15_history.build("RR.L", "LSE", _raw(dates, symbol="RR.L"))
    assert h.gaps == () and not h.blocked(date(2025, 11, 4))


def test_a_share_with_no_date_on_record_stays_blocked() -> None:
    h = p15_history.build("AAPL", "US", None)
    moment = datetime(2025, 6, 2, 15, tzinfo=UTC)
    assert earnings_window.bot_verdict("AAPL", "STOCK", "US", moment, h.frame).blocked


def test_a_refresh_after_the_cutoff_changes_nothing() -> None:
    base = _raw(PAST + [NEXT])
    later = _raw(PAST + ["2026-11-05"], knowable="2026-10-19T18:00:00+00:00")
    one = p15_history.build("AAPL", "US", base)
    two = p15_history.build("AAPL", "US", pd.concat([base, later], ignore_index=True))
    pd.testing.assert_frame_equal(one.frame, two.frame)
    assert one.gaps == two.gaps and one.dates == two.dates


def test_dates_before_the_exchange_calendar_are_dropped_not_crashed_on() -> None:
    """bot_verdict raised on a date before 2006-10-16 (ULVR.L's 2004 rows), flagged in
    QT-18 and fixed in QT-19 A (such dates are ignored). The copy still drops them."""
    raw = _raw(["2004-07-28", "2004-10-28"] + PAST + [NEXT])
    moment = datetime(2026, 10, 6, 15, tzinfo=UTC)
    assert not earnings_window.bot_verdict("AAPL", "STOCK", "US", moment, raw).blocked
    h = p15_history.build("AAPL", "US", raw)
    assert not earnings_window.bot_verdict("AAPL", "STOCK", "US", moment, h.frame).blocked
    assert "2004-07-28" not in set(h.frame["earnings_date"])


def test_the_stored_file_is_read_and_never_written(tmp_path: Path) -> None:
    folder = tmp_path / "earnings"
    folder.mkdir()
    target = folder / "AAPL.parquet"
    _raw(PAST + [NEXT]).to_parquet(target)
    before = target.read_bytes()
    h = p15_history.load("AAPL", "US", tmp_path)
    assert len(h.frame) > 0 and target.read_bytes() == before
    assert sorted(p.name for p in tmp_path.rglob("*") if p.is_file()) == ["AAPL.parquet"]


def test_the_backtest_schedule_uses_the_history_rule(tmp_path: Path) -> None:
    (tmp_path / "earnings").mkdir()
    _raw(PAST + [NEXT]).to_parquet(tmp_path / "earnings" / "AAPL.parquet")
    index = pd.date_range("2026-05-12 09:30", periods=7, freq="1h", tz="America/New_York")
    plan = p15.schedule("AAPL", "STOCK", index, "1h", "US", tmp_path)
    assert plan.may_enter is not None and plan.may_enter.all()
    stored = pd.read_parquet(tmp_path / "earnings" / "AAPL.parquet")
    assert not p15.mask("AAPL", "STOCK", index, "1h", "US", stored).any()   # the old way
    assert fills.positions(plan, np.ones(len(index))).any()


def test_a2_stops_on_a_thin_us_arm_or_a_mostly_blocked_share() -> None:
    from qb2.research import p15_coverage as cov
    sleeves = {"AAPL": "us_liquid", "MSFT": "us_liquid", "BP.L": "uk_share", "RR.L": "uk_share"}
    fine = {"AAPL": {"unsealed": (95, 100), "holdout": (60, 64)},
            "MSFT": {"unsealed": (96, 100), "holdout": (61, 64)},
            "BP.L": {"unsealed": (95, 100), "holdout": (61, 64)},
            "RR.L": {"unsealed": (0, 100), "holdout": (0, 64)}}          # stale five: allowed
    assert cov.stops(fine, sleeves) == []
    thin = {**fine, "MSFT": {"unsealed": (50, 100), "holdout": (61, 64)}}
    assert any("US arm" in s for s in cov.stops(thin, sleeves))
    blocked = {**fine, "BP.L": {"unsealed": (95, 100), "holdout": (20, 64)}}
    assert cov.stops(blocked, sleeves) == ["BP.L blocked on 69% of its holdout sessions"]
    slots = cov.calendar_slots("US", date(2026, 11, 27), date(2026, 11, 30))  # half day + Monday
    assert [len(slots[slots.date == d]) for d in (date(2026, 11, 27), date(2026, 11, 30))] == [4, 7]
