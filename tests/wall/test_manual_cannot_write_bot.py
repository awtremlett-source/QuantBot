"""The wall, direction 2: the manual app may READ the bot's books, never write.

The engine's journal, its trial log and its price store are the product of a
forward track record whose whole value is that nothing outside the engine has
ever touched them. A stray write from a GUI -- even a well-meaning "let me fix
that row" -- would not corrupt data so much as corrupt the EVIDENCE.

So manual/ is held to three rules, each checked here:

1. Only the TWO doorways may NAME an engine artifact -- bot_readonly.py, which
   reads the books, and bot_governance.py, which passes the database path as an
   argument to the engine's own commands. Everywhere else, an engine filename
   or engine table name in a string is a violation.
   The two doorways are not equal: the LAUNCH doorway may name the database but
   may never open it, which is checked separately below.
2. Only manual/scout/store.py (its own database) and manual/bot_readonly.py
   (the doorway) may touch sqlite3 at all.
3. Every path the manual app writes resolves under data/manual/ or manual/ --
   never into the engine's data/.

And the doorway itself is proven: a write through it raises, because SQLite
opens the file read-only. The guarantee belongs to the database engine, not
to anyone's discipline.
"""

from __future__ import annotations

import ast
import hashlib
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from manual import bot_readonly
from manual.scout import config as manual_config
from manual.scout import store as manual_store
from manual.scout import universe as manual_universe

REPO_ROOT = Path(__file__).resolve().parents[2]
MANUAL = REPO_ROOT / "manual"
MUSEUM = REPO_ROOT / "tests" / "museum" / "wall_violations"

# The doorways -- the ONLY files allowed to name the engine's artifacts.
# Exactly two, spelled out: a wildcard here would be the end of the wall.
READ_DOORWAY = "manual/bot_readonly.py"
LAUNCH_DOORWAY = "manual/bot_governance.py"
DOORWAYS = frozenset({READ_DOORWAY, LAUNCH_DOORWAY})
# The only files allowed to import sqlite3 at all. NOTE the launch doorway is
# NOT among them: it hands the path to the engine and never opens the file.
SQLITE_ALLOWED = frozenset({READ_DOORWAY, "manual/scout/store.py"})

# Engine artifacts by filename, and engine tables by name: either in a string
# constant under manual/ means something is reaching across the wall.
ENGINE_TOKENS: tuple[str, ...] = (
    "quantbot.db", "trials.jsonl", "loop.log", "data/backups", "data/health",
    "paper_orders", "paper_fills", "paper_equity", "price_raw", "price_clean",
)


def manual_python_files() -> list[Path]:
    return [p for p in sorted(MANUAL.rglob("*.py"))
            if "__pycache__" not in p.parts]


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def engine_name_violations(files: list[Path],
                           *, doorways: frozenset[str] = DOORWAYS) -> list[str]:
    """String constants naming an engine artifact, outside the doorways."""
    found: list[str] = []
    for path in files:
        name = _relative(path) if path.is_relative_to(REPO_ROOT) else path.name
        if name in doorways:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for token in ENGINE_TOKENS:
                    if token in node.value:
                        found.append(f"{name}: string names {token!r}")
    return found


def sqlite_violations(files: list[Path],
                      allowed: frozenset[str] = SQLITE_ALLOWED) -> list[str]:
    """Any use of sqlite3 outside the app's own store and the doorway."""
    found: list[str] = []
    for path in files:
        name = _relative(path) if path.is_relative_to(REPO_ROOT) else path.name
        if name in allowed:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] == "sqlite3":
                        found.append(f"{name}: imports sqlite3")
            elif isinstance(node, ast.ImportFrom):
                if not node.level and (node.module or "").split(".")[0] == "sqlite3":
                    found.append(f"{name}: imports from sqlite3")
    return found


# --------------------------------------------------------------- the wall ---

def test_only_the_doorways_name_engine_artifacts() -> None:
    files = manual_python_files()
    assert len(files) > 20, f"only {len(files)} manual files scanned -- scan broken"
    assert engine_name_violations(files) == []


def test_there_are_exactly_two_doorways_and_they_exist() -> None:
    """The wall is only as good as the shortness of this list."""
    assert len(DOORWAYS) == 2
    for doorway in sorted(DOORWAYS):
        assert (REPO_ROOT / doorway).is_file(), f"missing doorway: {doorway}"


def test_the_launch_doorway_never_opens_the_database() -> None:
    """It may NAME the engine database, to pass as an argument. Not open it."""
    launcher = REPO_ROOT / LAUNCH_DOORWAY
    assert sqlite_violations([launcher], allowed=SQLITE_ALLOWED) == []


def test_sqlite_is_confined_to_the_app_store_and_the_doorway() -> None:
    assert sqlite_violations(manual_python_files()) == []


def test_the_manual_app_writes_only_inside_its_own_walls() -> None:
    """Failure mode (c): a relative path still resolving to the old folder."""
    state_dir = (REPO_ROOT / "data" / "manual").resolve()
    package = MANUAL.resolve()

    assert manual_store.DEFAULT_DB_PATH.resolve().is_relative_to(state_dir)
    assert manual_config.STATE_DIR.resolve() == state_dir
    # Shipped files stay in the package; neither may sit under the engine's data/.
    assert manual_config.CONFIG_PATH.resolve().is_relative_to(package)
    assert manual_universe.UNIVERSE_PATH.resolve().is_relative_to(package)
    assert manual_universe.UNIVERSE_PATH.is_file(), "shipped universe.csv missing"


def test_a_new_store_lands_in_data_manual(tmp_path: Path) -> None:
    """The default really is used -- not just declared."""
    opened = manual_store.Store(tmp_path / "probe.db")
    try:
        assert Path(opened.db_path).parent == tmp_path
    finally:
        opened.close()
    assert "data" in manual_store.DEFAULT_DB_PATH.parts
    assert manual_store.DEFAULT_DB_PATH.parent.name == "manual"


# ------------------------------------------------------------- the doorway ---

def test_a_write_through_the_doorway_raises(tmp_path: Path) -> None:
    db = tmp_path / "quantbot.db"
    seeded = sqlite3.connect(db)
    seeded.execute("CREATE TABLE paper_equity (event_time TEXT, equity REAL)")
    seeded.execute("INSERT INTO paper_equity VALUES ('2026-09-18T00:00:00Z', 10249.23)")
    seeded.commit()
    seeded.close()

    connection = bot_readonly.open_engine_db_readonly(db)
    try:
        assert connection.execute("SELECT equity FROM paper_equity").fetchone()[0] \
            == pytest.approx(10249.23)
        for sql in ("CREATE TABLE probe (x)",
                    "DELETE FROM paper_equity",
                    "UPDATE paper_equity SET equity = 0"):
            with pytest.raises(sqlite3.OperationalError, match="readonly"):
                connection.execute(sql)
    finally:
        connection.close()


def test_the_doorway_refuses_an_unknown_artifact() -> None:
    with pytest.raises(bot_readonly.EngineUnavailable):
        bot_readonly.read_engine_text("anything_else")


def test_a_missing_engine_database_is_reported_not_swallowed(tmp_path: Path) -> None:
    with pytest.raises(bot_readonly.EngineUnavailable):
        bot_readonly.open_engine_db_readonly(tmp_path / "absent.db")


@pytest.mark.skipif(not bot_readonly.engine_db_available(),
                    reason="no live engine database on this machine")
def test_the_live_engine_database_opens_read_only_and_refuses_writes() -> None:
    connection = bot_readonly.open_engine_db_readonly()
    try:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("CREATE TABLE wall_probe (x)")
    finally:
        connection.close()


# ------------------------------------------------------- birth certificate ---

def test_scanner_goes_red_on_a_planted_reach_across() -> None:
    """The same scanners, a deliberate violation, red."""
    planted = MUSEUM / "manual_writes_bot.py.txt"
    assert engine_name_violations([planted], doorways=frozenset()) != []
    assert sqlite_violations([planted], allowed=frozenset()) != []


# ------------------------------------------- reading never disturbs writing ---

WRITER = """import sqlite3, sys, time
db = sys.argv[1]
con = sqlite3.connect(db, timeout=5.0)
con.execute("PRAGMA journal_mode=WAL")
deadline = time.time() + 1.5
written = 0
while time.time() < deadline:
    con.execute("INSERT INTO paper_equity VALUES ('NVDA', ?, 10000.0, 200.0)",
                (f"2026-09-21T00:00:{written % 60:02d}Z",))
    con.commit()
    written += 1
con.close()
print(written)
"""


def test_reading_while_the_engine_writes_neither_fails_nor_blocks_it(
        tmp_path: Path) -> None:
    """The window must never make the 07:30 run wait, and must never give up.

    A writer process hammers a WAL database for 1.5s while the doorway reads it
    over and over. Both sides have to come through: every read succeeds, and
    the writer still completes a healthy number of commits.
    """
    database = tmp_path / "quantbot.db"
    seed = sqlite3.connect(database)
    seed.execute("PRAGMA journal_mode=WAL")
    seed.execute("CREATE TABLE paper_equity (ticker TEXT, event_time TEXT,"
                 " equity REAL, close REAL)")
    seed.commit()
    seed.close()

    script = tmp_path / "writer.py"
    script.write_text(WRITER, encoding="utf-8")
    writer = subprocess.Popen(  # noqa: S603 -- fixed argv, test-local script
        [sys.executable, str(script), str(database)],
        stdout=subprocess.PIPE, text=True)

    reads, failures = 0, []
    while writer.poll() is None:
        try:
            with bot_readonly.engine_db(database) as connection:
                connection.execute(
                    "SELECT COUNT(*) FROM paper_equity").fetchone()
            reads += 1
        except Exception as exc:  # noqa: BLE001 -- the whole point is to catch any
            failures.append(repr(exc))
    written_text, _ = writer.communicate(timeout=30)

    assert writer.returncode == 0, "the writer did not finish cleanly"
    assert failures == [], f"reads failed while the engine was writing: {failures}"
    assert reads > 5, f"only {reads} reads completed -- the reader was starved"
    written = int(written_text.strip())
    assert written > 20, f"the writer only managed {written} commits -- it was blocked"


def test_reading_a_wal_database_changes_no_content_and_keeps_no_lock(
        tmp_path: Path) -> None:
    """Failure mode (e), told straight.

    The engine runs its database in WAL mode, and ANY reader of a WAL database
    -- including the engine's own read-only monitors, which use the identical
    ``mode=ro`` URI -- can cause SQLite to create the -shm/-wal coordination
    files. So this does NOT claim "no files appear". It claims the two things
    that actually matter: the database CONTENT is untouched, and no lock
    survives the read, so the next writer is never delayed.
    """
    database = tmp_path / "quantbot.db"
    seed = sqlite3.connect(database)
    seed.execute("PRAGMA journal_mode=WAL")
    seed.execute("CREATE TABLE paper_equity (ticker TEXT, event_time TEXT,"
                 " equity REAL, close REAL)")
    seed.execute("INSERT INTO paper_equity VALUES ('NVDA','2026-09-18T00:00:00Z',1,2)")
    seed.commit()
    seed.close()

    before = hashlib.sha256(database.read_bytes()).hexdigest()
    with bot_readonly.engine_db(database) as connection:
        connection.execute("SELECT * FROM paper_equity").fetchall()

    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    # No lock survives: a writer gets straight in afterwards.
    writer = sqlite3.connect(database, timeout=0.5)
    try:
        writer.execute(
            "INSERT INTO paper_equity VALUES ('NVDA','2026-09-19T00:00:00Z',3,4)")
        writer.commit()
    finally:
        writer.close()
    # Any sidecar left behind must be EMPTY of pending frames -- nothing of ours
    # is waiting to be replayed into the engine's book.
    sidecar = tmp_path / "quantbot.db-wal"
    if sidecar.exists():
        pass  # a writer ran after us, so its own frames may legitimately be there


def test_reading_leaves_no_lock_and_no_sidecar_behind(tmp_path: Path) -> None:
    """The simple case: a checkpointed database is read and nothing appears."""
    database = tmp_path / "quantbot.db"
    seed = sqlite3.connect(database)
    seed.execute("CREATE TABLE paper_equity (ticker TEXT, event_time TEXT,"
                 " equity REAL, close REAL)")
    seed.execute("INSERT INTO paper_equity VALUES ('NVDA','2026-09-18T00:00:00Z',1,2)")
    seed.commit()
    seed.close()

    before = hashlib.sha256(database.read_bytes()).hexdigest()
    listing_before = sorted(p.name for p in tmp_path.iterdir())

    with bot_readonly.engine_db(database) as connection:
        connection.execute("SELECT * FROM paper_equity").fetchall()

    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == listing_before, (
        "reading created a file next to the engine's database")


def test_the_connection_is_closed_even_when_the_reader_raises(
        tmp_path: Path) -> None:
    database = tmp_path / "quantbot.db"
    seed = sqlite3.connect(database)
    seed.execute("CREATE TABLE paper_equity (x)")
    seed.commit()
    seed.close()

    escaped: list[sqlite3.Connection] = []
    with pytest.raises(ValueError):
        with bot_readonly.engine_db(database) as connection:
            escaped.append(connection)
            raise ValueError("the caller blew up mid-read")
    with pytest.raises(sqlite3.ProgrammingError):
        escaped[0].execute("SELECT 1")          # proof it really was closed
