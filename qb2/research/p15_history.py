"""P15 history for back-tests ONLY: what we would have known of past results dates (QT-18 A1).

Operator, 2026-10-16, verbatim: *"GO on P15 history: in back-tests only, a results
date counts as known from the results date before it, if that earlier date is
before 2026-10-02; from 2026-10-02 only knowable_time counts; a share with no date
on record stays blocked."*

Why: the store's earnings dates were first recorded on 2026-10-02, so asked
honestly the sender's check knew nothing before then and blocked every share on
every past hour (QT-17). Live, Yahoo lists the next date as soon as one report is
out; this rebuilds that, conservatively, as an IN-MEMORY copy of a share's
earnings frame. It is handed to the SAME ``earnings_window.bot_verdict`` the
sender uses (via p15.py). Nothing is written; the stored file is never changed.
The live path may not import this file (tests/wall/test_p15_history_wall.py).

* **Known from the close.** For dates on record D1 < D2 < ... : if D(j-1) is before
  2026-10-02, Dj counts as known from the CLOSE of D(j-1)'s session (the next
  session's, if D(j-1) is not one), on that exchange's clock. That covers the first
  date on or after 2026-10-02 too, as listed by the EARLIEST real snapshot.
* **Cumulative snapshots.** ``latest_known`` reads ONLY the newest snapshot, so
  the snapshot made at D(j-1)'s close lists every date D1 ... Dj, not just Dj.
* **D1** has no date before it: never known early, so the share is blocked (fail
  closed) until real rows say otherwise or D2 becomes known at D1's close.
* **Missing quarter.** A gap D(j-1) -> Dj longer than 1.5 x the share's median gap
  means a report is missing from the record: blocked from D(j-1) + median gap until
  Dj's window ends. ``bot_verdict`` cannot see this (Dj is "upcoming"), so it is
  returned as ``spans`` for p15.py to apply beside it. Decided while operator away
  (QT-18): the median is capped at 182 days, because a listed company reports at
  least half-yearly -- else a share with one stale date (AAL.L: 2010, then 2027)
  would be its own median and trade through 17 years of unrecorded results.
* **From 2026-10-02 on** only real rows count, at their real knowable_time: every
  synthetic snapshot is older than the first real one, so the newest wins.
* **Input cutoff.** Only rows knowable by 2026-10-09 23:59:59 UTC (the last bar any
  QT-18 trial or holdout reads): a later refresh by the recorder changes nothing.
* **Outside the calendar.** Dates before the exchange calendar's first session
  (2006-10-16) are dropped from the copy: they cannot touch a window after 2023,
  and ``bot_verdict`` raises on them (flagged in QT-18, not fixed: qb2/guard is
  out of the box's scope).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import exchange_calendars as xcals  # type: ignore[import-untyped]
import pandas as pd

from qb2.guard import earnings_window
from qb2.ingest import earnings
from qb2.research import fills

REAL_FROM = date(2026, 10, 2)                      # the operator's date
CUTOFF = datetime(2026, 10, 9, 23, 59, 59, tzinfo=timezone.utc)
GAP_FACTOR = 1.5
MEDIAN_CAP_DAYS = 182                              # decided while operator away (QT-18)
SOURCE = "p15_history (synthetic, back-tests only)"


@dataclass(frozen=True, slots=True)
class Gap:
    after: date                  # D(j-1)
    before: date                 # Dj
    blocked_from: date           # D(j-1) + the median gap
    blocked_to: date             # the last session of Dj's window


@dataclass(frozen=True, slots=True)
class History:
    symbol: str
    frame: pd.DataFrame          # what bot_verdict is handed
    dates: tuple[date, ...]      # D1 < D2 < ... the rule was built from
    median_gap: float | None
    gaps: tuple[Gap, ...] = field(default_factory=tuple)

    def blocked(self, day: date) -> bool:
        """Inside a missing-quarter span on this (exchange) day?"""
        return any(g.blocked_from <= day <= g.blocked_to for g in self.gaps)


def _calendar(market: str) -> xcals.ExchangeCalendar:
    return xcals.get_calendar(fills.CALENDARS[market])


def _inside(cal: xcals.ExchangeCalendar, day: date) -> bool:
    return bool(cal.first_session.date() <= day <= cal.last_session.date())


def close_of(cal: xcals.ExchangeCalendar, day: date, market: str) -> pd.Timestamp:
    """The close of ``day``'s session (or the next session's), in UTC."""
    if _inside(cal, day):
        session = cal.date_to_session(pd.Timestamp(day), direction="next")
        return pd.Timestamp(cal.session_close(session)).tz_convert("UTC")
    return pd.Timestamp(fills._close_ns(day, market), tz="UTC")


def _window_end(cal: xcals.ExchangeCalendar, day: date) -> date:
    if _inside(cal, day):
        return earnings_window._window(cal, day)[1]
    return day + timedelta(days=4)                  # outside the calendar: generous


def _dates(raw: pd.DataFrame) -> tuple[list[date], pd.DataFrame]:
    """Past dates on record, plus the first date on/after REAL_FROM from the earliest
    real snapshot; and the real rows themselves."""
    knowable = pd.to_datetime(raw["knowable_time"], utc=True)
    real = raw[knowable <= pd.Timestamp(CUTOFF)].copy()
    if real.empty:
        return [], real
    days = pd.to_datetime(real["earnings_date"]).dt.date
    past = sorted({d for d in days if d < REAL_FROM})
    earliest = pd.to_datetime(real["knowable_time"], utc=True)
    first = sorted(d for d in days[earliest == earliest.min()] if d >= REAL_FROM)
    return past + first[:1], real


def build(symbol: str, market: str, raw: pd.DataFrame | None) -> History:
    """The in-memory frame and the missing-quarter spans for one share."""
    if raw is None or raw.empty:
        return History(symbol, pd.DataFrame(columns=["symbol", "earnings_date",
                                                     "knowable_time"]), (), None)
    cal = _calendar(market)
    dates, real = _dates(raw)
    rows: list[dict[str, object]] = []
    for j in range(1, len(dates)):        # every D(j-1) is before REAL_FROM (_dates)
        known = close_of(cal, dates[j - 1], market)
        rows += [{"symbol": symbol, "earnings_date": d.isoformat(), "knowable_time": known,
                  "source": SOURCE} for d in dates[:j + 1]]
    synthetic = pd.DataFrame(rows, columns=["symbol", "earnings_date", "knowable_time",
                                            "source"])
    real = real.assign(knowable_time=pd.to_datetime(real["knowable_time"], utc=True))
    if len(synthetic) and len(real) and synthetic["knowable_time"].max() >= \
            real["knowable_time"].min():
        raise ValueError(f"{symbol}: a synthetic snapshot is not older than the first "
                         "real one -- the real rows must win from 2026-10-02")
    frame = pd.concat([synthetic, real[synthetic.columns.intersection(real.columns)]],
                      ignore_index=True)
    keep = [_inside(cal, date.fromisoformat(str(d)[:10])) for d in frame["earnings_date"]]
    frame = frame[keep].reset_index(drop=True)
    steps = [(b - a).days for a, b in zip(dates, dates[1:])]
    median = float(statistics.median(steps)) if steps else None
    gaps: list[Gap] = []
    if median is not None:
        usual = min(median, MEDIAN_CAP_DAYS)
        for a, b in zip(dates, dates[1:]):
            if (b - a).days > GAP_FACTOR * usual:
                gaps.append(Gap(a, b, a + timedelta(days=round(usual)), _window_end(cal, b)))
    return History(symbol, frame, tuple(dates), median, tuple(gaps))


def load(symbol: str, market: str, clean_root: Path | None = None) -> History:
    """The stored file, read (never written), turned into the back-test's history."""
    return build(symbol, market, earnings.load(symbol, clean_root))
