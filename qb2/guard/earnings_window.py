"""No bot entry into a results announcement; the advisor warns (P15; QT-16 B5).

* **Bot:** entries are blocked from the session BEFORE an announcement through the
  session AFTER it, because the provider's hour is unreliable (its times come back
  in New York time even for London names -- qb2/ingest/earnings.py). A share whose
  next date is unknown is blocked too: no figure, no buy. An ETF is N/A -- a basket
  does not report -- and is never "missing".
* **Advisor:** warns 5 trading days before (a STARTING FIGURE); an unknown date for a
  share gives the warning "earnings date unknown".
* **Point in time:** only rows whose knowable_time is at or before the moment are
  used, and of those the LATEST snapshot (a date that moved is read as moved).

Sessions come from each exchange's own calendar, so a holiday is never a session.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import exchange_calendars as xcals  # type: ignore[import-untyped]
import pandas as pd

from qb2.execution.safety import Blocked
from qb2.research import fills

WARN_SESSIONS = 5            # STARTING FIGURE: the advisor warns 5 trading days ahead
ETF = "ETF"


@dataclass(frozen=True, slots=True)
class Verdict:
    ticker: str
    blocked: bool
    reason: str


def latest_known(frame: pd.DataFrame | None, moment: datetime) -> list[date]:
    """Announcement dates in the newest snapshot we could have known at ``moment``."""
    if frame is None or frame.empty:
        return []
    knowable = pd.to_datetime(frame["knowable_time"], utc=True)
    cutoff = pd.Timestamp(moment)
    cutoff = cutoff.tz_localize("UTC") if cutoff.tzinfo is None else cutoff.tz_convert("UTC")
    seen = knowable[knowable <= cutoff]
    if seen.empty:
        return []
    newest = frame[knowable == seen.max()]
    return sorted({date.fromisoformat(str(d)) for d in newest["earnings_date"]})


def _sessions(market: str) -> xcals.ExchangeCalendar:
    return xcals.get_calendar(fills.CALENDARS[market])


def _today(cal: xcals.ExchangeCalendar, moment: datetime, market: str) -> date:
    """The session ``moment`` falls in -- or, outside hours, the next one."""
    local = pd.Timestamp(moment).tz_convert(fills.EXCHANGE_TZ[market]).date()
    day: date = pd.Timestamp(cal.date_to_session(pd.Timestamp(local), direction="next")).date()
    return day


def _window(cal: xcals.ExchangeCalendar, day: date) -> tuple[date, date]:
    """The session before ``day`` through the session after it."""
    stamp = pd.Timestamp(day)
    before = cal.date_to_session(stamp, direction="previous")
    after = cal.date_to_session(stamp, direction="next")
    if cal.is_session(stamp):
        before, after = cal.previous_session(stamp), cal.next_session(stamp)
    return pd.Timestamp(before).date(), pd.Timestamp(after).date()


def _inside(cal: xcals.ExchangeCalendar, days: list[date]) -> list[date]:
    """QT-19 A: dates outside the calendar (ULVR.L's 2004 rows) play no part."""
    lo, hi = pd.Timestamp(cal.first_session).date(), pd.Timestamp(cal.last_session).date()
    return [d for d in days if lo < d < hi]


def bot_verdict(ticker: str, kind: str, market: str, moment: datetime,
                frame: pd.DataFrame | None) -> Verdict:
    if kind == ETF:
        return Verdict(ticker, False, "N/A (ETF): a basket does not report results")
    cal = _sessions(market)
    today = _today(cal, moment, market)
    known = _inside(cal, latest_known(frame, moment))
    for day in known:
        first, last = _window(cal, day)
        if first <= today <= last:
            return Verdict(ticker, True, f"{ticker} reports on {day}: no entry from the "
                           f"session before ({first}) through the session after ({last})")
    upcoming = [d for d in known if _window(cal, d)[1] >= today]
    if not upcoming:
        return Verdict(ticker, True, f"{ticker}'s next earnings date is unknown -- no entry "
                       "(fail closed)")
    return Verdict(ticker, False, f"{ticker} next reports on {upcoming[0]}")


def guard(ticker: str, verdict: Verdict | None) -> None:
    """Sender check 8: no verdict, another name's, or a blocking one -- no buy."""
    if verdict is None:
        raise Blocked(f"the earnings check never ran for {ticker} -- refusing to guess")
    if verdict.ticker != ticker:
        raise Blocked(f"the earnings verdict is for {verdict.ticker}, not {ticker}")
    if verdict.blocked:
        raise Blocked(verdict.reason)


def advisor_warning(ticker: str, kind: str, market: str, moment: datetime,
                    frame: pd.DataFrame | None) -> str | None:
    if kind == ETF:
        return None
    cal = _sessions(market)
    today = _today(cal, moment, market)
    ahead = [d for d in latest_known(frame, moment) if d >= today]
    if not ahead:
        return f"{ticker}: earnings date unknown"
    horizon = pd.Timestamp(cal.session_offset(pd.Timestamp(today), WARN_SESSIONS)).date()
    if ahead[0] <= horizon:
        return f"{ticker} reports on {ahead[0]} (within {WARN_SESSIONS} trading days)"
    return None
