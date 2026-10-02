"""The one and only writer into the clean store. Everything else reads.

A "front door" means there is exactly one way in, and the checks live at the door
rather than being repeated hopefully in a dozen callers (SCARS #2, #3). RAW is the
bytes the provider gave us and is never edited; CLEAN is a validated copy, and if
the two ever disagree about what happened, RAW wins and CLEAN is rebuilt.

What the door insists on, and why each one is here:

**One writer, enforced by a lock.** Two copies of the recorder running at once --
easy on a laptop that wakes from sleep and fires a catch-up run into a run already
going -- would interleave writes into the same file. The lock makes the second one
wait or refuse, and a stale lock from a machine that was switched off mid-run is
detected rather than respected forever.

**The manifest is the commit point.** A parquet file is written under a temporary
name, flushed to the physical disk, and only then renamed and recorded in the
manifest. A file with no manifest line is not part of the store. So a crash or a
closed laptop lid leaves either nothing or a whole bar-file, never a half-written
one that reads as real data.

**Pence become pounds, exactly once.** T212 and yfinance both quote most London
instruments in pence (FACTS row r). A store that mixes pence and pounds has a
silent 100x step in it. CLEAN is therefore always in POUNDS for London and dollars
for the US, the conversion is recorded per row, and the guard below refuses to run
twice over the same bars.

**Splits are checked, never re-applied.** This is scar #22 and it is worth stating
in full: yfinance's OHLC is ALREADY split-adjusted. Dividing by the split ratio a
second time would halve a price that was never doubled, and the error looks exactly
like a real fall. So the split table is used to EXPLAIN jumps, not to change
prices. Nothing in this module multiplies or divides a price by a split ratio.

**A session is measured against the real calendar.** How many minutes SHOULD a
session have? Not 390 every day: exchanges close early, and the UK and US move
their clocks on different weekends. ``exchange_calendars`` is asked, so a half-day
is not reported as missing data.

**Reconciliation is exact, not approximate.** Every row that goes in comes out
somewhere -- written, already present, quarantined or dropped with a reason -- and
the arithmetic is asserted. "About right" is how data quietly goes missing.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_INTRADAY = REPO_ROOT / "data" / "raw" / "intraday"
CLEAN = REPO_ROOT / "data" / "clean"

OHLC = ("open", "high", "low", "close")
COLUMNS = ("open", "high", "low", "close", "volume")

# Raw folders that are NOT input. The 1,382 hourly day-files moved aside on
# 2026-09-30 when hourly data was repartitioned by month are still on disk --
# nothing is deleted -- but reading them would double-count every hourly bar.
EXCLUDED_RAW_PREFIXES = ("superseded-",)

# Pence in, pounds out. Both spellings of pence appear: T212 writes GBX, yfinance
# writes GBp.
PENCE = frozenset({"GBX", "GBp"})
PENCE_PER_POUND = 100.0

# A price that moves by this much between neighbouring bars is not a market move;
# it is a units change or a split. STARTING FIGURE, tested first.
JUMP_RATIO = 10.0
LOCK_STALE_SECONDS = 3_600


class FrontDoorError(RuntimeError):
    """Something at the door was wrong. Never swallowed, never guessed past."""


class StoreLocked(FrontDoorError):
    """Another writer holds the lock."""


# --------------------------------------------------------------------- locking

class WriterLock:
    """One writer at a time. A lock older than an hour is treated as abandoned.

    Why not trust the lock forever: this runs on a laptop that gets shut mid-run,
    and a lock file that outlives its process would stop every future run until
    someone noticed. Why not ignore it: two writers would interleave.
    """

    def __init__(self, path: Path | None = None,
                 stale_after: float = LOCK_STALE_SECONDS) -> None:
        self.path = path or (CLEAN / "writer.lock")
        self.stale_after = stale_after

    @staticmethod
    def _holder_is_alive(text: str) -> bool:
        """Is the process named in the lock still running?

        Age alone is not enough. A run killed mid-way leaves a FRESH lock behind,
        and the age limit is longer than the gap between hourly runs -- so one
        killed run could block every run for an hour. On perishable minute data
        that is exactly the loss we are trying to prevent. If the process named in
        the lock is gone, the lock is abandoned however new it looks.
        """
        match = re.search(r"pid=(\d+)", text)
        if match is None:
            return True            # no pid recorded: fall back to the age rule
        pid = int(match.group(1))
        try:
            os.kill(pid, 0)        # signal 0 asks "does this process exist?"
        except ProcessLookupError:
            return False           # POSIX: no such process
        except PermissionError:
            return True            # someone else's process, but it exists
        except OSError as exc:
            # Windows has no ESRCH here: CPython calls OpenProcess, and a pid
            # that does not exist comes back as ERROR_INVALID_PARAMETER (87).
            # Access denied (5) means the process IS there and is not ours.
            return getattr(exc, "winerror", None) != 87
        return True

    def __enter__(self) -> WriterLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            age = time.time() - self.path.stat().st_mtime
            held_by = self.path.read_text(encoding="utf-8").strip()
            if age < self.stale_after and self._holder_is_alive(held_by):
                raise StoreLocked(
                    f"another writer holds {self.path} (held {age:,.0f}s ago by "
                    f"{held_by}). Refusing to "
                    "write: two writers would interleave rows in one file")
            # Abandoned: say so loudly rather than silently stealing it.
            self.path.replace(self.path.with_suffix(".lock.abandoned"))
        self.path.write_text(
            f"pid={os.getpid()} at={datetime.now(timezone.utc).isoformat()}",
            encoding="utf-8")
        return self

    def __exit__(self, *exc: object) -> None:
        self.path.unlink(missing_ok=True)


# ----------------------------------------------------------------- the results

@dataclass(slots=True)
class Reconciliation:
    """Where every row went. The totals must agree exactly."""

    rows_in: int = 0
    rows_written: int = 0
    rows_already_present: int = 0
    rows_quarantined: int = 0
    rows_dropped: int = 0
    files_read: int = 0
    files_written: int = 0
    files_skipped_unchanged: int = 0
    files_excluded: int = 0
    pence_converted: int = 0
    problems: list[str] = field(default_factory=list)

    @property
    def accounted_for(self) -> int:
        return (self.rows_written + self.rows_already_present
                + self.rows_quarantined + self.rows_dropped)

    def check(self) -> None:
        if self.rows_in != self.accounted_for:
            raise FrontDoorError(
                f"reconciliation failed: {self.rows_in:,} rows went in but "
                f"{self.accounted_for:,} are accounted for "
                f"(written {self.rows_written:,}, already present "
                f"{self.rows_already_present:,}, quarantined "
                f"{self.rows_quarantined:,}, dropped {self.rows_dropped:,}). "
                "Refusing to report success with rows unexplained")


# ------------------------------------------------------------------- the store

def raw_files(interval: str, symbols: Sequence[str] | None = None,
              root: Path | None = None) -> Iterator[Path]:
    """Every raw file for an interval, with the superseded folders left out."""
    base = (root or RAW_INTRADAY)
    folder = base / interval
    if not folder.exists():
        return
    for path in sorted(folder.rglob("*.parquet")):
        if any(part.startswith(EXCLUDED_RAW_PREFIXES)
               for part in path.relative_to(base.parent).parts):
            continue
        if symbols is not None and path.parent.name not in symbols:
            continue
        yield path


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_path(interval: str, symbol: str, period: str,
               root: Path | None = None) -> Path:
    return (root or CLEAN) / "bars" / interval / symbol / f"{period}.parquet"


def manifest_path(root: Path | None = None) -> Path:
    return (root or CLEAN) / "manifest.jsonl"


def read_manifest(root: Path | None = None) -> dict[str, dict[str, object]]:
    """What the store believes it holds, keyed by the raw file it came from.

    The manifest IS the store's index: a parquet file nobody wrote a line about
    is treated as absent, because it may be a half-written leftover.
    """
    path = manifest_path(root)
    if not path.exists():
        return {}
    known: dict[str, dict[str, object]] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                # A torn last line is the signature of a crash mid-append. Skip it
                # and let the file be re-ingested; never guess at its contents.
                continue
            if isinstance(row, dict) and row.get("event") == "ingested":
                known[str(row.get("source"))] = row
    return known


def _append_manifest(row: Mapping[str, object], root: Path | None = None) -> None:
    """The commit point. Flushed to the disk itself, not just to the OS."""
    path = manifest_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def _write_parquet_atomically(frame: pd.DataFrame, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".parquet.partial")
    frame.to_parquet(temporary)
    # Flush to the physical disk before the rename, so a power cut cannot leave a
    # file that exists but holds nothing. The handle must be WRITABLE for this:
    # fsync on a read-only handle fails with EBADF on Windows.
    with temporary.open("r+b") as fh:
        fh.flush()
        os.fsync(fh.fileno())
    temporary.replace(destination)


# ------------------------------------------------------------------- the rules

def to_pounds(frame: pd.DataFrame, currency: str) -> tuple[pd.DataFrame, bool]:
    """Pence to pounds, exactly once. Volume is a count and is left alone."""
    if currency not in PENCE:
        return frame, False
    converted = frame.copy()
    for column in OHLC:
        converted[column] = converted[column] / PENCE_PER_POUND
    return converted, True


def impossible_rows(frame: pd.DataFrame) -> pd.Series:
    """Rows that cannot be a real bar, whatever the market did."""
    high, low = frame["high"], frame["low"]
    return (
        (high < low)
        | (frame["open"] > high) | (frame["open"] < low)
        | (frame["close"] > high) | (frame["close"] < low)
        | (frame[list(OHLC)] <= 0).any(axis=1)
        | frame[list(OHLC)].isna().any(axis=1)
        | (frame["volume"] < 0)
    )


def unexplained_jumps(frame: pd.DataFrame, splits: Mapping[str, float],
                      ) -> list[tuple[str, float]]:
    """Jumps that no split explains. Reported, never corrected.

    SCARS #22: yfinance's prices are already split-adjusted, so a split must NOT
    be applied again here. A jump that a known split would explain is therefore
    evidence that something has gone wrong UPSTREAM, not an invitation to divide.
    """
    if len(frame) < 2:
        return []
    close = frame["close"]
    ratio = (close / close.shift(1)).dropna()
    found: list[tuple[str, float]] = []
    for when, value in ratio.items():
        if value >= JUMP_RATIO or (value > 0 and value <= 1.0 / JUMP_RATIO):
            stamp = pd.Timestamp(when).date().isoformat()
            if stamp not in splits:
                found.append((str(when), float(value)))
    return found


def expected_minutes(market: str, day: pd.Timestamp, interval: str) -> int | None:
    """How many bars this session should hold, from the real exchange calendar.

    Returns None when the calendar is unavailable, so a missing dependency is an
    honest "unknown" rather than a confident wrong number.
    """
    try:
        import exchange_calendars as xcals  # type: ignore[import-untyped]
    except ImportError:                       # pragma: no cover - pinned dependency
        return None
    code = {"US": "XNYS", "LSE": "XLON"}.get(market)
    minutes_per_bar = {"1m": 1, "5m": 5, "15m": 15, "1h": 60}.get(interval)
    if code is None or minutes_per_bar is None:
        return None
    calendar = xcals.get_calendar(code)
    stamp = pd.Timestamp(day).tz_localize(None).normalize()
    if not calendar.is_session(stamp):
        return 0
    open_at = calendar.session_open(stamp)
    close_at = calendar.session_close(stamp)
    minutes = int((close_at - open_at).total_seconds() // 60)
    return minutes // minutes_per_bar


# ---------------------------------------------------------------- the door itself

def ingest_file(path: Path, *, symbol: str, interval: str, market: str,
                currency: str, splits: Mapping[str, float],
                known: Mapping[str, Mapping[str, object]],
                tally: Reconciliation, clean_root: Path | None = None,
                raw_root: Path | None = None) -> None:
    """Take one raw file through the door. Idempotent: unchanged input, no work."""
    base = (raw_root or RAW_INTRADAY).parent
    source = path.relative_to(base).as_posix()
    digest = file_digest(path)

    frame = pd.read_parquet(path)
    tally.files_read += 1
    tally.rows_in += len(frame)

    previous = known.get(source)
    if previous is not None and previous.get("sha256") == digest:
        # Already ingested, byte for byte. Doing it again would be identical work,
        # so the only honest thing is to count the rows and move on.
        tally.files_skipped_unchanged += 1
        tally.rows_already_present += len(frame)
        return

    if list(frame.columns) != list(COLUMNS):
        raise FrontDoorError(
            f"{source}: unexpected columns {list(frame.columns)}, wanted "
            f"{list(COLUMNS)}. Refusing to guess which column is the close")

    bad = impossible_rows(frame)
    if bad.any():
        quarantine = (clean_root or CLEAN) / "quarantine" / interval / symbol
        quarantine.mkdir(parents=True, exist_ok=True)
        frame[bad].to_parquet(quarantine / f"{path.stem}-impossible.parquet")
        tally.rows_quarantined += int(bad.sum())
        tally.problems.append(
            f"{source}: {int(bad.sum())} impossible row(s) quarantined")
        frame = frame[~bad]

    frame, converted = to_pounds(frame, currency)
    if converted:
        tally.pence_converted += len(frame)

    for when, ratio in unexplained_jumps(frame, splits):
        tally.problems.append(
            f"{symbol}: unexplained {ratio:.1f}x jump at {when} -- no split on "
            "record. NOT corrected (SCARS #22: prices arrive already adjusted)")

    out_currency = "GBP" if currency in PENCE else currency
    frame = frame.copy()
    frame["currency"] = out_currency
    frame.index.name = "ts"
    frame = frame.sort_index()
    duplicated = frame.index.duplicated(keep="first")
    if duplicated.any():
        tally.rows_dropped += int(duplicated.sum())
        tally.problems.append(
            f"{source}: dropped {int(duplicated.sum())} duplicate timestamp(s)")
        frame = frame[~duplicated]

    destination = clean_path(interval, symbol, path.stem, clean_root)
    _write_parquet_atomically(frame, destination)
    tally.files_written += 1
    tally.rows_written += len(frame)

    _append_manifest({
        "event": "ingested",
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "sha256": digest,
        "destination": destination.relative_to(clean_root or CLEAN).as_posix(),
        "rows": len(frame),
        "interval": interval,
        "symbol": symbol,
        "market": market,
        "quote_currency": currency,
        "stored_currency": out_currency,
        "pence_to_pounds": converted,
    }, clean_root)
    # Keep the in-memory index in step, so the same file appearing twice in one
    # run is recognised rather than written twice.
    if isinstance(known, dict):
        known[source] = {"source": source, "sha256": digest, "rows": len(frame)}


def ingest(intervals: Sequence[str] = ("1m", "5m", "1h"),
           symbols: Sequence[str] | None = None,
           splits: Mapping[str, Mapping[str, float]] | None = None,
           clean_root: Path | None = None,
           raw_root: Path | None = None) -> Reconciliation:
    """Walk RAW into CLEAN under the lock, then prove the arithmetic.

    Safe to run at the end of every recorder run: anything already ingested is
    recognised by its hash and skipped, so a catch-up run after a weekend does the
    same work as a run that never stopped.
    """
    from qb2.ingest import tickers

    markets = {t: m for t, m, _ in tickers.recording_list()}
    tally = Reconciliation()
    all_splits = splits or {}

    # Read the index ONCE. Re-reading it per file turned a 12,000-file run into
    # quadratic work on a growing file.
    known = read_manifest(clean_root)

    with WriterLock(((clean_root or CLEAN) / "writer.lock")):
        for interval in intervals:
            for path in raw_files(interval, symbols, raw_root):
                symbol = path.parent.name
                market = markets.get(symbol)
                if market is None:
                    # Recorded under a name that has left the active list (AHT.L,
                    # IEUR.L and friends). The data stays on disk untouched; it is
                    # simply not promoted into the clean store.
                    # Counted as excluded and NOT counted as rows_in: these rows
                    # were never offered to the store, so they are not the store's
                    # to account for. Subtracting them from rows_in instead drove
                    # the total negative.
                    tally.files_excluded += 1
                    continue
                currency = tickers.quote_currency(symbol) or (
                    "GBp" if symbol.endswith(".L") else "USD")
                ingest_file(path, symbol=symbol, interval=interval, market=market,
                            currency=currency, splits=all_splits.get(symbol, {}),
                            known=known, tally=tally,
                            clean_root=clean_root, raw_root=raw_root)
        tally.check()
        _append_manifest({
            "event": "run",
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            **{k: v for k, v in asdict(tally).items() if k != "problems"},
            "problem_count": len(tally.problems),
        }, clean_root)
    return tally
