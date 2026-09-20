"""The ONE doorway from the manual app to the bot's books -- and it only reads.

TWO BOOKS, ONE WALL. The engine's journal is the product of a forward paper
track record: its value is that nothing outside the engine has ever touched
it. The manual app may LOOK at that record; it may never write a byte of it.

This module is therefore the only file under manual/ permitted to name an
engine artifact, and the guarantee is not "we remembered to be careful":

* ``open_engine_db_readonly`` opens data/quantbot.db through a SQLite URI with
  ``mode=ro``. SQLITE ITSELF refuses every write -- ``CREATE``, ``UPDATE``,
  ``DELETE`` and journal-mode pragmas all raise ``attempt to write a readonly
  database``. The guarantee belongs to the database engine, not to us.
* ``read_engine_text`` reads an ALLOW-LISTED engine text artifact in mode 'r'.
  A name outside the allow-list raises rather than resolving to a path.
* Every connection is SHORT-LIVED and lock-bounded. ``engine_db()`` is a
  context manager that always closes, and the connect timeout is
  ``READ_TIMEOUT_S`` seconds, so a window left open overnight can never sit on
  a lock or make the 07:30 run wait. If the engine is mid-write, the window
  gives up and says so -- the trading loop never yields to the GUI.

Nothing here creates, repairs or migrates anything. If the engine has not
produced a file yet, that is reported loudly (never silently swallowed --
SCARS #12) and the caller decides what to show.

tests/wall/test_manual_cannot_write_bot.py enforces all of the above, and
fails red when the doorway is widened.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.request import pathname2url

REPO_ROOT = Path(__file__).resolve().parent.parent

# Seconds to wait for a lock before giving up. Deliberately short: a GUI that
# waits is a GUI that can delay the engine.
READ_TIMEOUT_S = 2.0

# The rubric's condition 1 -- ">= 1 month clean daily paper runs" (MANIFEST.md).
TRACK_RECORD_TARGET_DAYS = 30

# The engine's artifacts. Named here and NOWHERE ELSE under manual/.
ENGINE_DB = REPO_ROOT / "data" / "quantbot.db"
TRIAL_LOG = REPO_ROOT / "data" / "trials.jsonl"
LOOP_LOG = REPO_ROOT / "data" / "loop.log"
HEALTH_DIR = REPO_ROOT / "data" / "health"

# Text artifacts the manual app may read, by name. Nothing else is reachable.
READABLE_TEXT: dict[str, Path] = {
    "trials": TRIAL_LOG,
    "loop_log": LOOP_LOG,
}


class EngineUnavailable(RuntimeError):
    """The engine artifact asked for is absent or cannot be opened for reading."""


def engine_db_available(db_path: Path | None = None) -> bool:
    """True when the engine database exists (it is gitignored, so it may not)."""
    return (db_path or ENGINE_DB).is_file()


def open_engine_db_readonly(db_path: Path | None = None,
                            timeout: float = READ_TIMEOUT_S) -> sqlite3.Connection:
    """Open the engine database READ-ONLY. Every write through it raises.

    The timeout bounds how long SQLite waits for a lock, so the window fails
    fast instead of queueing behind -- or ahead of -- the trading loop.

    Raises EngineUnavailable if the file is missing, or if SQLite cannot open
    it read-only (for example a WAL database left mid-recovery, which needs a
    writable sidecar -- that is the engine's business to finish, not ours).
    """
    path = (db_path or ENGINE_DB).resolve()
    if not path.is_file():
        raise EngineUnavailable(f"engine database not found: {path}")
    uri = f"file:{pathname2url(str(path))}?mode=ro"
    try:
        return sqlite3.connect(uri, uri=True, timeout=timeout)
    except sqlite3.OperationalError as exc:  # re-raise, never swallow
        raise EngineUnavailable(f"cannot open {path} read-only: {exc}") from exc


def read_engine_text(name: str) -> str:
    """Read one ALLOW-LISTED engine text artifact. Read mode only."""
    if name not in READABLE_TEXT:
        raise EngineUnavailable(
            f"{name!r} is not a readable engine artifact "
            f"(allowed: {', '.join(sorted(READABLE_TEXT))})")
    path = READABLE_TEXT[name]
    if not path.is_file():
        raise EngineUnavailable(f"engine artifact not found: {path}")
    return path.read_text(encoding="utf-8")


def engine_equity_marks(limit: int = 30) -> list[tuple[str, float]]:
    """Most recent (event_time, equity) marks from the engine's paper book.

    A worked example of the doorway: read, close, return plain values. The
    connection never escapes this function, so nothing downstream can hold a
    handle to the engine's database.
    """
    connection = open_engine_db_readonly()
    try:
        rows = connection.execute(
            "SELECT event_time, equity FROM paper_equity "
            "ORDER BY event_time DESC LIMIT ?", (limit,)).fetchall()
    finally:
        connection.close()
    return [(str(when), float(equity)) for when, equity in rows]


@contextmanager
def engine_db(db_path: Path | None = None,
              timeout: float = READ_TIMEOUT_S) -> Iterator[sqlite3.Connection]:
    """A SHORT-LIVED read-only connection that always closes.

    Preferred over calling open_engine_db_readonly directly: nothing can
    accidentally keep a handle on the engine's database past the read.
    """
    connection = open_engine_db_readonly(db_path, timeout)
    try:
        yield connection
    finally:
        connection.close()


@dataclass(frozen=True, slots=True)
class BotSnapshot:
    """Everything the window shows about the bot, read in one short visit.

    Every figure carries its age, because a number without an age is a number
    that quietly becomes a lie.
    """

    latest_bar: str | None          # newest equity mark -- a BAR date, UTC
    equity: float | None
    close: float | None
    ticker: str | None
    shares: float                   # net position, summed from the fills
    cash: float | None              # derived, never a copied config constant
    marks: int                      # equity marks in the journal
    first_bar: str | None
    trials: int                     # records in the trial log
    last_digest: str | None         # newest "PAPER " line from the run log
    last_log_time: str | None       # timestamp of the newest log entry
    log_has_errors: bool
    trading_days_behind: int        # completed weekdays left unprocessed
    read_at: datetime

    @property
    def stale(self) -> bool:
        """True when a completed trading day has gone unprocessed."""
        return self.latest_bar is None or self.trading_days_behind >= 1

    @property
    def track_record_days(self) -> int:
        if not (self.first_bar and self.latest_bar):
            return 0
        return (_as_date(self.latest_bar) - _as_date(self.first_bar)).days

    @property
    def bar_age_days(self) -> int | None:
        if self.latest_bar is None:
            return None
        return (self.read_at.date() - _as_date(self.latest_bar)).days


def _as_date(stamp: str) -> date:
    """The date part of an engine timestamp: '2026-08-06T00:00:00Z' -> date."""
    return date.fromisoformat(stamp[:10])


def completed_weekdays_between(start: date, end: date) -> int:
    """Weekdays strictly after `start` and strictly before `end`.

    The freshest bar the engine can hold is the previous completed session, so
    0 means "up to date". Market holidays are NOT modelled: a holiday shows as
    one day of false staleness, which is the safe direction to be wrong in --
    it over-reports, never under-reports.
    """
    days = 0
    cursor = start + timedelta(days=1)
    while cursor < end:
        if cursor.weekday() < 5:
            days += 1
        cursor += timedelta(days=1)
    return days


def _digest_lines(lines: list[str]) -> list[str]:
    """The run log's digest lines, using the engine installer's own marker."""
    return [line for line in lines if line.startswith("PAPER ")]


def _looks_stamped(line: str) -> bool:
    """'2026-07-28 21:29:05,522 INFO ...' -- the engine's logging format."""
    return (len(line) > 19 and line[:4].isdigit() and line[4] == "-"
            and line[7] == "-" and line[10] == " " and line[13] == ":")


def read_snapshot(db_path: Path | None = None,
                  trial_log: Path | None = None,
                  loop_log: Path | None = None,
                  now: datetime | None = None) -> BotSnapshot:
    """One short read-only visit to the bot's books. Never writes, never waits."""
    read_at = now or datetime.now(timezone.utc)
    trials_path = trial_log if trial_log is not None else TRIAL_LOG
    log_path = loop_log if loop_log is not None else LOOP_LOG

    latest_bar: str | None = None
    equity: float | None = None
    close: float | None = None
    ticker: str | None = None
    first_bar: str | None = None
    with engine_db(db_path) as connection:
        row = connection.execute(
            "SELECT event_time, equity, close, ticker FROM paper_equity "
            "ORDER BY event_time DESC LIMIT 1").fetchone()
        if row is not None:
            latest_bar = str(row[0])
            equity = float(row[1])
            close = float(row[2])
            ticker = str(row[3])
        marks = int(connection.execute(
            "SELECT COUNT(DISTINCT event_time) FROM paper_equity").fetchone()[0])
        earliest = connection.execute(
            "SELECT MIN(event_time) FROM paper_equity").fetchone()[0]
        if earliest is not None:
            first_bar = str(earliest)
        held = connection.execute(
            "SELECT COALESCE(SUM(shares_delta), 0) FROM paper_fills").fetchone()[0]
        shares = float(held or 0.0)

    # Cash is DERIVED from the engine's own mark (equity = shares * close + cash)
    # rather than copied from the engine's starting-capital constant. A copied
    # constant is a second source of truth waiting to drift.
    cash = None if (equity is None or close is None) else equity - shares * close

    trials = 0
    if trials_path.is_file():
        trials = sum(1 for line in trials_path.read_text(
            encoding="utf-8").splitlines() if line.strip())

    last_digest: str | None = None
    last_log_time: str | None = None
    log_has_errors = False
    if log_path.is_file():
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        digests = _digest_lines(lines)
        last_digest = digests[-1] if digests else None
        stamped = [line for line in lines if _looks_stamped(line)]
        last_log_time = stamped[-1][:19] if stamped else None
        tail = "\n".join(lines[-40:])
        log_has_errors = any(token in tail
                             for token in ("ERROR", "CRITICAL", "Traceback"))

    behind = (0 if latest_bar is None
              else completed_weekdays_between(_as_date(latest_bar), read_at.date()))

    return BotSnapshot(
        latest_bar=latest_bar, equity=equity, close=close, ticker=ticker,
        shares=shares, cash=cash, marks=marks, first_bar=first_bar,
        trials=trials, last_digest=last_digest, last_log_time=last_log_time,
        log_has_errors=log_has_errors, trading_days_behind=behind,
        read_at=read_at)
