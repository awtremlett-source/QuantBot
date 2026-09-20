"""The wall, direction 2: the manual app may READ the bot's books, never write.

The engine's journal, its trial log and its price store are the product of a
forward track record whose whole value is that nothing outside the engine has
ever touched them. A stray write from a GUI -- even a well-meaning "let me fix
that row" -- would not corrupt data so much as corrupt the EVIDENCE.

So manual/ is held to three rules, each checked here:

1. Only manual/bot_readonly.py may NAME an engine artifact. Everywhere else,
   an engine filename or engine table name in a string is a violation.
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
import sqlite3
from pathlib import Path

import pytest

from manual import bot_readonly
from manual.scout import config as manual_config
from manual.scout import store as manual_store
from manual.scout import universe as manual_universe

REPO_ROOT = Path(__file__).resolve().parents[2]
MANUAL = REPO_ROOT / "manual"
MUSEUM = REPO_ROOT / "tests" / "museum" / "wall_violations"

# The doorway -- the ONE file allowed to name the engine's artifacts.
DOORWAY = "manual/bot_readonly.py"
# The only files allowed to import sqlite3 at all.
SQLITE_ALLOWED = frozenset({DOORWAY, "manual/scout/store.py"})

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


def engine_name_violations(files: list[Path], *, doorway: str = DOORWAY) -> list[str]:
    """String constants naming an engine artifact, outside the doorway."""
    found: list[str] = []
    for path in files:
        name = _relative(path) if path.is_relative_to(REPO_ROOT) else path.name
        if name == doorway:
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

def test_only_the_doorway_names_engine_artifacts() -> None:
    files = manual_python_files()
    assert len(files) > 20, f"only {len(files)} manual files scanned -- scan broken"
    assert engine_name_violations(files) == []


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
    assert engine_name_violations([planted], doorway="never-matches") != []
    assert sqlite_violations([planted], allowed=frozenset()) != []
