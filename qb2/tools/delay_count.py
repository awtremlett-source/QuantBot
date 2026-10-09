"""Which delay samples COUNT towards FACTS row o -- one rule for every reader.

QT-12R (2026-10-07) went looking for why London had so few readings. The cause
was the PC being shut down every London morning, but the search found four ways
a reading could be counted when it should not, and one alarm that never rang:

- a holiday: the exchange is shut, yfinance hands back the last day's bars, and
  the old check (weekday + fixed hours) called it open -- a day-old bar posed as
  a feed delay;
- a half-day: after an early close the bars stop and every later reading grows
  by the minute; and half a session is not one of the three the plan asks for;
- a reading outside the real open-close, or of a bar from before today's open;
- two runs at once (a hand run beside the scheduled one) reading the SAME bar.

So a sample counts only when it was taken inside a FULL session on the
exchange's own calendar, of a bar from that session, and each bar counts once.

The alarm: ``session_meter`` was written and tested, and nothing ever called it.
It now runs inside ``sample_delay.verdict()``, which every recorder run prints.
"""

from __future__ import annotations

import json
import statistics
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from qb2.ingest.recorder import EXCHANGE_TZ, REGULAR_HOURS, exchange_now

CALENDAR_CODE = {"US": "XNYS", "LSE": "XLON"}

# STANDING GO default, logged 2026-10-07 (QT-12R): a finished session with fewer
# clock-checked samples than this is RED. A full session gives about 8 hourly
# readings in London and 6 in the US; 3 means the PC was on for a good part of
# it. Before this, one reading in eight and a half hours read as healthy.
MIN_SAMPLES_PER_SESSION = 3

Window = tuple[datetime, datetime]
Hours = Callable[[str, date], "Window | None"]


@lru_cache(maxsize=None)
def full_session_hours(market: str, day: date) -> Window | None:
    """(open, close) in UTC for a FULL session; None for a weekend, a holiday,
    an early close, or a day outside the calendar's range (unknown = not counted).
    """
    import exchange_calendars as xcals  # type: ignore[import-untyped]
    import pandas as pd
    from exchange_calendars.errors import DateOutOfBounds  # type: ignore[import-untyped]

    calendar = xcals.get_calendar(CALENDAR_CODE[market])
    stamp = pd.Timestamp(day)
    try:
        if not calendar.is_session(stamp):
            return None
        opens, closes = calendar.session_open_close(stamp)
    except DateOutOfBounds:
        return None
    if closes.tz_convert(EXCHANGE_TZ[market]).time() < REGULAR_HOURS[market][1]:
        return None
    return opens.to_pydatetime(), closes.to_pydatetime()


def _window(market: str, moment: datetime, hours: Hours | None) -> Window | None:
    if market not in CALENDAR_CODE:
        return None
    # Looked up at call time, so a test can plant its own calendar.
    lookup = hours or full_session_hours
    return lookup(market, exchange_now(market, moment).date())


def in_full_session(market: str, moment: datetime,
                    hours: Hours | None = None) -> bool:
    """Is this market inside a full regular session right now? Real calendar."""
    window = _window(market, moment, hours)
    return window is not None and window[0] <= moment <= window[1]


def read_samples(manifest: Path) -> list[dict[str, object]]:
    """Every delay_sample row on file. Unreadable lines are skipped, as before."""
    return scan_samples(manifest)[0]


def scan_samples(manifest: Path) -> tuple[list[dict[str, object]], int]:
    """read_samples, plus how many sample lines could not be read -- a line
    half-written while the recorder appends -- so a reader can say so (QT-12S)."""
    rows: list[dict[str, object]] = []
    bad = 0
    if not manifest.exists():
        return rows, bad
    with manifest.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if '"delay_sample"' not in line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                bad += 1
                continue
            if isinstance(row, dict) and row.get("kind") == "delay_sample":
                rows.append(row)
    return rows, bad


def countable(rows: Iterable[dict[str, object]], *, verified_only: bool = False,
              hours: Hours | None = None) -> list[dict[str, object]]:
    """The rows that may count, each observed bar once."""
    seen: set[tuple[str, int]] = set()
    out: list[dict[str, object]] = []
    for row in rows:
        if verified_only and not row.get("clock_checked"):
            continue
        market = str(row.get("market"))
        age = row.get("age_seconds")
        raw = row.get("age_seconds_raw", age)
        if not isinstance(age, (int, float)) or not isinstance(raw, (int, float)):
            continue
        try:
            at = datetime.fromisoformat(str(row.get("at_utc")))
        except ValueError:
            continue
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        window = _window(market, at, hours)
        if window is None or not window[0] <= at <= window[1]:
            continue
        # The laptop's own clock on both sides, so this is the bar's timestamp.
        bar = at - timedelta(seconds=float(raw))
        if bar < window[0]:
            continue                       # yesterday's close: "no bar yet"
        # To the second: the same bar read twice lands within ~0.1 s of itself.
        key = (market, round(bar.timestamp()))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def session_meter(manifest: Path, *, markets: Sequence[str] = ("US", "LSE"),
                  days_back: int = 3, today: date | None = None,
                  hours: Hours | None = None) -> list[dict[str, object]]:
    """RED for any market whose recent full session has fewer than
    MIN_SAMPLES_PER_SESSION clock-checked samples. Half-days are not checked:
    they do not count, so they cannot be short."""
    lookup = hours or full_session_hours
    rows = countable(read_samples(manifest), verified_only=True, hours=lookup)
    per_day = Counter((str(r["market"]), str(r["at_utc"])[:10]) for r in rows)
    end = today or datetime.now(timezone.utc).date()
    meters: list[dict[str, object]] = []
    for market in markets:
        short: list[str] = []
        for back in range(1, days_back + 1):
            day = end - timedelta(days=back)
            if lookup(market, day) is None:
                continue
            got = per_day[(market, day.isoformat())]
            if got < MIN_SAMPLES_PER_SESSION:
                short.append(f"{day.isoformat()} ({got} of "
                             f"{MIN_SAMPLES_PER_SESSION})")
        meters.append({
            "market": market,
            "status": "RED" if short else "OK",
            "sessions_checked": days_back,
            "short_sessions": short,
            "detail": (f"too few clock-checked samples on {', '.join(short)} -- "
                       "the sampler did not run for most of the session (PC "
                       "off or asleep?)" if short else
                       f"every full session in the last {days_back} day(s) has "
                       f"at least {MIN_SAMPLES_PER_SESSION} samples"),
        })
    return meters


@dataclass(frozen=True, slots=True)
class Summary:
    """FACTS row o's figures for one market, in minutes (QT-13)."""

    market: str
    count: int
    sessions: int
    median: float
    p90: float
    worst: float


def summary(rows: Iterable[dict[str, object]], market: str) -> Summary | None:
    """Row o's figures from rows that ``countable`` has already passed.

    The 90th percentile is ``statistics.quantiles(n=10, method="inclusive")``:
    nine in ten counted samples were this fresh or fresher. None: no samples.
    """
    mine = [r for r in rows if r.get("market") == market]
    ages = [float(a) / 60 for r in mine
            if isinstance(a := r.get("age_seconds"), (int, float))]
    if not ages:
        return None
    p90 = (statistics.quantiles(ages, n=10, method="inclusive")[8]
           if len(ages) > 1 else ages[0])
    return Summary(market, len(ages), len({str(r["at_utc"])[:10] for r in mine}),
                   statistics.median(ages), p90, max(ages))
