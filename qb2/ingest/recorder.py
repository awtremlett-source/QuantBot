"""Record intraday bars now, because they cannot be fetched later.

docs/t212/FACTS.md row n was measured, not assumed: minute bars arrive only
**8 days per request**, and 5- and 15-minute bars reach back about 60 trading
days. Beyond that the data does not exist to be asked for. **Every day this does
not run is a day the bot can never be tested on.** That is the whole reason this
module is built before any strategy.

It captures RAW and nothing else. Bars land in data/raw/intraday/ exactly as the
provider sent them, and a separate front door (S3b) is the only thing that may
put them in the data store -- the same single-writer rule v1 lives by (SCARS
#2, #3).

Five things it refuses to get wrong:

* **A forming bar is not a bar.** The last row of a live request is still being
  built; saving it would store a high that has not happened yet. It is dropped.
* **Never overwrite.** If a bar we already saved comes back with different
  numbers, the new version goes to a quarantine file and the original stands.
  Which one is right is a question for a human, not for a silent overwrite.
* **Pence are not pounds.** London prices arrive in pence (GBp) from some
  sources and pounds from others. A 100x jump between runs fails loudly rather
  than quietly making a strategy look brilliant.
* **Clocks change on different dates.** The UK moves on 2026-10-25 and the US on
  2026-11-01, so for one week the gap is 4 hours, not 5. Everything is stored in
  UTC and converted with a real timezone database.
* **A gap it cannot fill is written down as LOST**, never interpolated, never
  quietly skipped.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_ROOT = REPO_ROOT / "data" / "raw" / "intraday"
MANIFEST = RAW_ROOT / "manifest.jsonl"
QUARANTINE = RAW_ROOT / "quarantine"

# Provider limits, measured in FACTS.md row n -- not guessed.
MAX_DAYS_PER_REQUEST = {"1m": 8, "5m": 60, "15m": 60, "1h": 730}
BACKFILL_PERIOD = {"5m": "60d", "1h": "730d"}

# Exchange clocks. Stored as names, so the timezone database handles the
# changeover dates rather than us adding hours by hand.
EXCHANGE_TZ = {"US": "America/New_York", "LSE": "Europe/London"}
REGULAR_HOURS = {                   # local exchange time, regular session only
    "US": (datetime.min.time().replace(hour=9, minute=30),
           datetime.min.time().replace(hour=16, minute=0)),
    "LSE": (datetime.min.time().replace(hour=8, minute=0),
            datetime.min.time().replace(hour=16, minute=30)),
}

# STARTING FIGURE, tested first: a weekday capture older than this is RED.
STALE_AFTER_DAYS = 2
# STARTING FIGURE: a price this many times the previous one is a unit change,
# not a market move. 100x is the pence/pounds mistake.
UNIT_JUMP_FACTOR = 50.0

OHLC = ("open", "high", "low", "close")


def _as_int(value: object) -> int:
    """A count out of a JSON manifest line, or 0 -- never a crash on a bad file."""
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    return 0


class RecorderError(RuntimeError):
    """Something the recorder will not paper over."""


@dataclass(frozen=True, slots=True)
class Bars:
    """One instrument's bars, with the units and the clock stated."""

    ticker: str
    interval: str
    market: str
    currency: str
    frame: pd.DataFrame


@dataclass
class Outcome:
    """What one run did, in numbers that can be checked afterwards."""

    captures: list[dict[str, object]] = field(default_factory=list)
    quarantined: int = 0
    lost: list[dict[str, object]] = field(default_factory=list)
    delay_samples: list[dict[str, object]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def rows_saved(self) -> int:
        return sum(_as_int(c.get("rows")) for c in self.captures)


# ------------------------------------------------------------- the clock -----

def exchange_now(market: str, now: datetime | None = None) -> datetime:
    """UTC turned into the exchange's own wall clock, changeover dates included."""
    zone = EXCHANGE_TZ.get(market)
    if zone is None:
        raise RecorderError(f"no timezone known for market {market!r}")
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(ZoneInfo(zone))


def market_is_open(market: str, now: datetime | None = None) -> bool:
    """Regular session only. Extended hours are not recorded as regular bars."""
    local = exchange_now(market, now)
    if local.weekday() >= 5:
        return False
    opens, closes = REGULAR_HOURS[market]
    return opens <= local.time() <= closes


def utc_offset_hours(market: str, moment: datetime) -> float:
    """The offset from UTC on a given date -- the thing that changes twice a year."""
    local = exchange_now(market, moment)
    offset = local.utcoffset()
    return 0.0 if offset is None else offset.total_seconds() / 3600.0


# -------------------------------------------------- correctness at the edge --

def drop_forming_bar(frame: pd.DataFrame, interval: str,
                     now: datetime | None = None) -> pd.DataFrame:
    """Remove the last bar if its period has not finished yet.

    A 1-minute bar stamped 14:31 is not complete until 14:32. Saving it stores a
    high, low and close that can still change, and a backtest built on it is
    reading the future.
    """
    if frame.empty:
        return frame
    minutes = {"1m": 1, "5m": 5, "15m": 15, "1h": 60}.get(interval)
    if minutes is None:
        raise RecorderError(f"unknown interval {interval!r}")
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    last = frame.index[-1]
    last_utc = last.tz_convert("UTC") if last.tzinfo else last.tz_localize("UTC")
    if last_utc + timedelta(minutes=minutes) > moment:
        return frame.iloc[:-1]
    return frame


def ohlc_problems(frame: pd.DataFrame) -> pd.Series:
    """True where a row is not a possible bar. Quarantined, never repaired."""
    if frame.empty:
        return pd.Series(dtype=bool)
    missing = frame[list(OHLC)].isna().any(axis=1)
    bad_high = (frame["high"] < frame[["open", "close"]].max(axis=1))
    bad_low = (frame["low"] > frame[["open", "close"]].min(axis=1))
    crossed = frame["low"] > frame["high"]
    negative = (frame[list(OHLC)] <= 0).any(axis=1)
    volume_bad = frame["volume"] < 0 if "volume" in frame else False
    return missing | bad_high | bad_low | crossed | negative | volume_bad


def unit_jump(previous_close: float | None, first_close: float) -> float | None:
    """The ratio between runs. ~100 means pence met pounds."""
    if not previous_close or previous_close <= 0 or first_close <= 0:
        return None
    ratio = first_close / previous_close
    return ratio if ratio >= UNIT_JUMP_FACTOR or ratio <= 1 / UNIT_JUMP_FACTOR else None


# ------------------------------------------------------------- the writing ---

# Coarse intervals are partitioned by MONTH, not by day. An hourly backfill
# covering ~2.9 years is about 500 trading days PER TICKER: at one file each that
# is ~59,000 files holding a handful of rows apiece, which is slow to write, slow
# to read and mostly filesystem overhead. Minute and five-minute data stay
# day-partitioned, because a single day of minute bars is a real file.
PARTITION_BY_MONTH = frozenset({"1h"})


def _paths(ticker: str, interval: str, day: date) -> tuple[Path, Path]:
    folder = RAW_ROOT / interval / ticker
    stem = f"{day:%Y-%m}" if interval in PARTITION_BY_MONTH else day.isoformat()
    return folder, folder / f"{stem}.parquet"


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def append_manifest(record: dict[str, object], manifest: Path | None = None) -> None:
    """One line per capture. Append-only: the log of what we have is evidence."""
    target = manifest or MANIFEST
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")
        handle.flush()


def read_manifest(manifest: Path | None = None) -> list[dict[str, object]]:
    target = manifest or MANIFEST
    if not target.is_file():
        return []
    rows: list[dict[str, object]] = []
    for raw in target.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            print("recorder manifest: unreadable line -- treating as a gap")
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def last_saved_bar(ticker: str, interval: str,
                   manifest: Path | None = None) -> datetime | None:
    """Where to carry on from. This is what makes a missed run harmless."""
    newest: datetime | None = None
    for row in read_manifest(manifest):
        if row.get("ticker") != ticker or row.get("interval") != interval:
            continue
        if row.get("status") != "saved":
            continue
        stamp = row.get("last_bar_utc")
        if not isinstance(stamp, str):
            continue
        try:
            moment = datetime.fromisoformat(stamp)
        except ValueError:
            continue
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        if newest is None or moment > newest:
            newest = moment
    return newest


def save_bars(bars: Bars, *, root: Path | None = None,
              manifest: Path | None = None,
              now: datetime | None = None) -> list[dict[str, object]]:
    """Write one day per file. Overlaps dedupe; changed bars quarantine.

    Returns one manifest record per day written, which is also what the caller
    counts. Nothing is returned for a day that produced no complete bars.
    """
    global RAW_ROOT
    previous_root = RAW_ROOT
    if root is not None:
        RAW_ROOT = root
    try:
        return _save_bars(bars, manifest=manifest, now=now)
    finally:
        RAW_ROOT = previous_root


def _save_bars(bars: Bars, *, manifest: Path | None,
               now: datetime | None) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    frame = bars.frame
    if frame.empty:
        return records

    problems = ohlc_problems(frame)
    if bool(problems.any()):
        bad = frame[problems]
        QUARANTINE.mkdir(parents=True, exist_ok=True)
        target = QUARANTINE / (f"{bars.ticker}-{bars.interval}-ohlc-"
                               f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.parquet")
        bad.to_parquet(target)
        append_manifest({"kind": "quarantine", "reason": "ohlc_sanity",
                         "ticker": bars.ticker, "interval": bars.interval,
                         "rows": int(len(bad)), "file": str(target)}, manifest)
        frame = frame[~problems]

    if bars.interval in PARTITION_BY_MONTH:
        grouper = [d.date().replace(day=1) for d in frame.index]
    else:
        grouper = list(frame.index.date)
    for day, chunk in frame.groupby(grouper):
        folder, path = _paths(bars.ticker, bars.interval, day)
        folder.mkdir(parents=True, exist_ok=True)
        keep = chunk

        if path.is_file():
            existing = pd.read_parquet(path)
            shared = existing.index.intersection(chunk.index)
            if len(shared) > 0:
                changed = ~existing.loc[shared, list(OHLC)].round(6).eq(
                    chunk.loc[shared, list(OHLC)].round(6)).all(axis=1)
                if bool(changed.any()):
                    QUARANTINE.mkdir(parents=True, exist_ok=True)
                    conflict = QUARANTINE / (
                        f"{bars.ticker}-{bars.interval}-{day}-changed-"
                        f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.parquet")
                    chunk.loc[shared][changed].to_parquet(conflict)
                    append_manifest(
                        {"kind": "quarantine", "reason": "value_changed",
                         "ticker": bars.ticker, "interval": bars.interval,
                         "rows": int(changed.sum()), "file": str(conflict),
                         "note": "the saved bar stands; a human decides"},
                        manifest)
            keep = chunk[~chunk.index.isin(existing.index)]
            if keep.empty:
                continue
            keep = pd.concat([existing, keep]).sort_index()

        keep = keep[~keep.index.duplicated(keep="first")]
        keep.to_parquet(path)
        record = {
            "kind": "capture", "status": "saved", "ticker": bars.ticker,
            "interval": bars.interval, "market": bars.market,
            "currency": bars.currency, "day": str(day),
            "first_bar_utc": str(keep.index[0]), "last_bar_utc": str(keep.index[-1]),
            "rows": int(len(keep)), "file": str(path), "file_hash": _hash(path),
            "fetched_at_utc": (now or datetime.now(timezone.utc)).isoformat(
                timespec="seconds"),
        }
        append_manifest(record, manifest)
        records.append(record)
    return records


def record_lost(ticker: str, interval: str, reason: str,
                manifest: Path | None = None) -> dict[str, object]:
    """A gap we cannot fill. Written down, never interpolated."""
    record: dict[str, object] = {
        "kind": "lost", "status": "LOST", "ticker": ticker,
        "interval": interval, "reason": reason,
        "at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    append_manifest(record, manifest)
    return record


# ------------------------------------------------------- the delay sample ----

def delay_sample(market: str, last_bar_utc: datetime,
                 now: datetime | None = None) -> dict[str, object] | None:
    """How old is the newest closed bar? Only sampled while the market is open.

    Outside hours this returns None rather than a number, because a bar that is
    old because the market is shut says nothing about the feed's delay. That is
    exactly the trap FACTS.md row o fell into.
    """
    moment = now or datetime.now(timezone.utc)
    if not market_is_open(market, moment):
        return None
    if last_bar_utc.tzinfo is None:
        last_bar_utc = last_bar_utc.replace(tzinfo=timezone.utc)
    age = (moment - last_bar_utc).total_seconds()
    return {"kind": "delay_sample", "market": market,
            "age_seconds": round(age, 1),
            "at_utc": moment.isoformat(timespec="seconds")}


# ------------------------------------------------------- the freshness meter --

def freshness(manifest: Path | None = None, now: datetime | None = None,
              stale_after_days: int = STALE_AFTER_DAYS) -> list[dict[str, object]]:
    """Per interval: how old is the newest good capture, and is that RED?

    A weekday-only rule, because a Monday-morning check should not shout about
    Saturday. RED means the recorder has stopped and days are being lost.
    """
    moment = now or datetime.now(timezone.utc)
    newest: dict[str, datetime] = {}
    for row in read_manifest(manifest):
        if row.get("status") != "saved":
            continue
        interval = str(row.get("interval", ""))
        stamp = row.get("fetched_at_utc")
        if not isinstance(stamp, str):
            continue
        try:
            fetched = datetime.fromisoformat(stamp)
        except ValueError:
            continue
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        if interval not in newest or fetched > newest[interval]:
            newest[interval] = fetched

    results: list[dict[str, object]] = []
    for interval in sorted(MAX_DAYS_PER_REQUEST):
        latest = newest.get(interval)
        if latest is None:
            results.append({"interval": interval, "status": "RED",
                            "detail": "never recorded -- no good capture exists for this interval"})
            continue
        weekdays = _weekdays_between(latest, moment)
        status = "RED" if weekdays > stale_after_days else "OK"
        results.append({
            "interval": interval, "status": status,
            "age_days": round((moment - latest).total_seconds() / 86_400, 2),
            "weekdays_since": weekdays,
            "detail": (f"last good capture {weekdays} weekday(s) ago "
                       f"(RED over {stale_after_days})")})
    return results


def _weekdays_between(start: datetime, end: datetime) -> int:
    days, cursor = 0, start.date() + timedelta(days=1)
    while cursor <= end.date():
        if cursor.weekday() < 5:
            days += 1
        cursor += timedelta(days=1)
    return days


# ---------------------------------------------------------------- the fetch --

def yfinance_fetch(ticker: str, interval: str, days: int) -> pd.DataFrame:
    """The real provider. Injected everywhere else so tests stay offline."""
    import yfinance as yf

    period = f"{min(days, MAX_DAYS_PER_REQUEST[interval])}d"
    frame = yf.Ticker(ticker).history(period=period, interval=interval,
                                      auto_adjust=False, prepost=False)
    if frame.empty:
        return frame
    frame = frame.rename(columns=str.lower)
    wanted = [c for c in (*OHLC, "volume") if c in frame.columns]
    frame = frame[wanted]
    if frame.index.tz is None:
        frame.index = frame.index.tz_localize("UTC")
    return frame.sort_index()


Fetcher = Callable[[str, str, int], pd.DataFrame]

# STARTING FIGURES: how hard to try when the provider pushes back. Free data is
# rate-limited without telling us how, so this is deliberately patient and short.
FETCH_ATTEMPTS = 3
FETCH_BACKOFF_SECONDS = (2.0, 8.0)


def fetch_with_backoff(fetch: Fetcher, ticker: str, interval: str, days: int,
                       *, sleeper: Callable[[float], None] = time.sleep
                       ) -> pd.DataFrame:
    """Try, wait, try again. Give up honestly rather than hammering.

    Yahoo throttles without a documented signal, so a failure is treated as
    "probably too fast" and retried with a growing pause. After the last attempt
    the error is raised for the caller to record as a LOST gap -- never swallowed
    (SCARS #12), and never retried forever.
    """
    last: Exception | None = None
    for attempt in range(FETCH_ATTEMPTS):
        try:
            return fetch(ticker, interval, days)
        except Exception as exc:                          # noqa: BLE001
            last = exc
            if attempt == FETCH_ATTEMPTS - 1:
                break
            pause = FETCH_BACKOFF_SECONDS[min(attempt,
                                              len(FETCH_BACKOFF_SECONDS) - 1)]
            print(f"recorder: {ticker} {interval} failed "
                  f"({type(exc).__name__}), waiting {pause:.0f}s then retrying")
            sleeper(pause)
    assert last is not None
    raise last


def capture(entries: Sequence[tuple[str, str, str]], interval: str, *,
            fetch: Fetcher = yfinance_fetch, root: Path | None = None,
            manifest: Path | None = None, now: datetime | None = None,
            days: int | None = None,
            sleeper: Callable[[float], None] = time.sleep) -> Outcome:
    """Capture one interval for a list of (yfinance ticker, market, currency).

    Errors are caught PER TICKER and recorded, so one dead symbol cannot stop
    the run and lose everybody else's day (SCARS #12: handled and logged).
    """
    outcome = Outcome()
    asked = days if days is not None else MAX_DAYS_PER_REQUEST[interval]
    for ticker, market, currency in entries:
        try:
            frame = fetch_with_backoff(fetch, ticker, interval, asked,
                                       sleeper=sleeper)
        except Exception as exc:                          # noqa: BLE001
            outcome.errors.append(f"{ticker} {interval}: "
                                  f"{type(exc).__name__}: {exc}")
            outcome.lost.append(record_lost(ticker, interval,
                                            f"fetch failed: {type(exc).__name__}",
                                            manifest))
            continue
        if frame is None or frame.empty:
            outcome.lost.append(record_lost(ticker, interval,
                                            "provider returned nothing", manifest))
            continue

        complete = drop_forming_bar(frame, interval, now)
        if complete.empty:
            outcome.lost.append(record_lost(
                ticker, interval, "only a forming bar was available", manifest))
            continue

        sample = delay_sample(market, complete.index[-1].to_pydatetime(), now)
        if sample is not None:
            append_manifest(sample, manifest)
            outcome.delay_samples.append(sample)

        bars = Bars(ticker=ticker, interval=interval, market=market,
                    currency=currency, frame=complete)
        before = len(read_manifest(manifest))
        records = save_bars(bars, root=root, manifest=manifest, now=now)
        outcome.captures.extend(records)
        after = read_manifest(manifest)
        outcome.quarantined += sum(1 for row in after[before:]
                                   if row.get("kind") == "quarantine")
    return outcome
