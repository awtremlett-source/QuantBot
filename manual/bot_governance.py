"""The ONE way the window launches anything -- a fixed allow-list, nothing else.

The window must be able to do what the operator could already do by typing:
run the loop, write a health report, take a backup, run the status drill, send
a test message, arm or disarm the killswitch. It must NOT be able to do
anything else, and it must not be able to invent a command.

So there is no free-text command anywhere in this module. There is a table of
exactly the actions the Tkinter control panel (tools/gui.py) already offers,
each launched as a subprocess with:

* the ENGINE's interpreter (.venv), never the window's. The window runs on
  .venv-ui, whose pins conflict with the engine's on purpose; launching an
  engine command with the UI interpreter would run the trading loop against
  pandas 2.x, which is not what produced the live record.
* the ENGINE's working directory (the repo root), so every relative path the
  engine writes -- data/, logs, backups -- lands exactly where the scheduled
  task puts it.
* a fixed argv list and never ``shell=True``.

Every press is appended to data/manual/governance_log.jsonl before and after it
runs, so "what did I press, and what happened?" has a written answer even if
the window dies mid-command.

ONE AT A TIME: the busy guard means the window can never launch two engine
commands at once. The loop is the database's single writer, and a GUI that can
double-fire is a GUI that will.

This module and manual/bot_readonly.py are the only two doorways between the
manual app and the bot. tests/wall/ enforces that, and that this allow-list
still equals the Tkinter panel's command set exactly.
"""

from __future__ import annotations

import json
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Actions that take the engine database. MIRRORS tools/gui.py's _DB_ACTIONS --
# tests/wall/test_governance_allow_list.py fails if the two ever diverge.
DB_ACTIONS: dict[str, tuple[str, tuple[str, ...]]] = {
    "status": ("monitors.status", ()),
    "drill": ("monitors.status", ("--drill",)),
    "loop": ("execution.paper_loop", ()),
    "health": ("monitors.health", ()),
    "backup": ("tools.backup", ()),
}

# Actions that do not. Same source: the Tkinter panel's telegram button.
PLAIN_ACTIONS: dict[str, tuple[str, tuple[str, ...]]] = {
    "telegram_test": ("monitors.notify", ("--test",)),
}

ALLOWED_ACTIONS = frozenset(DB_ACTIONS) | frozenset(PLAIN_ACTIONS)

# Governance that is a FILE, not a command -- exactly as the panel does it.
KILLSWITCH_FILENAME = "STOP_NEW_TRADES"


class UnknownAction(ValueError):
    """Something asked for an action that is not on the allow-list."""


class Busy(RuntimeError):
    """An engine command is already running; the window never runs two."""


@dataclass(frozen=True, slots=True)
class RunOutcome:
    """What a press did: the argv, the exit code, the output, how long it took."""

    action: str
    argv: tuple[str, ...]
    returncode: int
    output: str
    seconds: float


# --------------------------------------------------------------- the paths ---

def engine_python() -> Path:
    """The ENGINE's interpreter. Never the window's."""
    return REPO_ROOT / ".venv" / "Scripts" / "python.exe"


def engine_db() -> Path:
    return REPO_ROOT / "data" / "quantbot.db"


def killswitch_path() -> Path:
    return REPO_ROOT / KILLSWITCH_FILENAME


def governance_log_path() -> Path:
    """The window's own log of what was pressed -- under data/manual/, its side."""
    return REPO_ROOT / "data" / "manual" / "governance_log.jsonl"


# ------------------------------------------------------------ the commands ---

def command(action: str) -> list[str]:
    """The exact argv an action runs. The single place a command is built."""
    if action in PLAIN_ACTIONS:
        module, extra = PLAIN_ACTIONS[action]
        return [str(engine_python()), "-m", module, *extra]
    if action in DB_ACTIONS:
        module, extra = DB_ACTIONS[action]
        return [str(engine_python()), "-m", module, "--db", str(engine_db()), *extra]
    raise UnknownAction(
        f"{action!r} is not a governance action "
        f"(allowed: {', '.join(sorted(ALLOWED_ACTIONS))})")


# ------------------------------------------------------------ the busy guard --

_lock = threading.Lock()
_busy: str | None = None


def busy() -> str | None:
    """The action currently running, or None."""
    with _lock:
        return _busy


def begin(action: str) -> bool:
    """Claim the one-at-a-time slot. False when something is already running."""
    global _busy
    with _lock:
        if _busy is not None:
            return False
        _busy = action
        return True


def finish() -> None:
    global _busy
    with _lock:
        _busy = None


# ----------------------------------------------------------------- the log ---

def log_press(entry: dict[str, object]) -> None:
    """Append one line to the governance log. Never raises into the caller."""
    record = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              **entry}
    path = governance_log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    except OSError as exc:  # logged, never swallowed silently (SCARS #12)
        print(f"governance log write failed: {exc}")


def read_log(limit: int = 20) -> list[dict[str, object]]:
    """The most recent presses, newest last."""
    path = governance_log_path()
    if not path.is_file():
        return []
    records: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            records.append(parsed)
    return records


# ----------------------------------------------------------------- the run ---

def run(action: str) -> RunOutcome:
    """Launch one allow-listed action. Raises Busy if one is already running.

    The caller is expected to have disabled its buttons; the guard here is the
    one that actually holds, because a double-click reaches this before any
    repaint does.
    """
    argv = command(action)          # raises UnknownAction before anything starts
    if not begin(action):
        raise Busy(f"{busy()!r} is still running -- one engine command at a time")
    log_press({"button": action, "event": "started"})
    started = datetime.now(timezone.utc)
    try:
        completed = subprocess.run(  # noqa: S603 -- fixed argv, never shell=True
            argv, cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
        output = (completed.stdout or "") + (completed.stderr or "")
        code = completed.returncode
    except OSError as exc:
        output, code = f"could not launch: {exc}", -1
    finally:
        finish()
    seconds = (datetime.now(timezone.utc) - started).total_seconds()
    log_press({"button": action, "event": "finished", "exit_code": code,
               "seconds": round(seconds, 3)})
    return RunOutcome(action=action, argv=tuple(argv), returncode=code,
                      output=output, seconds=seconds)


# --------------------------------------------------------- the killswitch ----

def killswitch_armed() -> bool:
    return killswitch_path().exists()


def arm_killswitch() -> str:
    """Create STOP_NEW_TRADES (idempotent). Governance, never trading."""
    path = killswitch_path()
    if not path.exists():
        path.write_text("armed from the manual app's Bot tab\n", encoding="utf-8")
    log_press({"button": "killswitch_arm", "event": "finished", "exit_code": 0})
    return f"killswitch ARMED ({path.name} present) - no NEW orders"


def disarm_killswitch() -> str:
    path = killswitch_path()
    if path.exists():
        path.unlink()
    log_press({"button": "killswitch_disarm", "event": "finished", "exit_code": 0})
    return f"killswitch DISARMED ({path.name} absent) - trading resumes"
