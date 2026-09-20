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

Nothing here creates, repairs or migrates anything. If the engine has not
produced a file yet, that is reported loudly (never silently swallowed --
SCARS #12) and the caller decides what to show.

tests/wall/test_manual_cannot_write_bot.py enforces all of the above, and
fails red when the doorway is widened.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from urllib.request import pathname2url

REPO_ROOT = Path(__file__).resolve().parent.parent

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


def open_engine_db_readonly(db_path: Path | None = None) -> sqlite3.Connection:
    """Open the engine database READ-ONLY. Every write through it raises.

    Raises EngineUnavailable if the file is missing, or if SQLite cannot open
    it read-only (for example a WAL database left mid-recovery, which needs a
    writable sidecar -- that is the engine's business to finish, not ours).
    """
    path = (db_path or ENGINE_DB).resolve()
    if not path.is_file():
        raise EngineUnavailable(f"engine database not found: {path}")
    uri = f"file:{pathname2url(str(path))}?mode=ro"
    try:
        return sqlite3.connect(uri, uri=True)
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
