"""One-command installer / verifier / uninstaller (the end-goal packaging).

``python -m tools.installer install | verify | uninstall`` -- normally reached
via the thin bootstrap ``install.ps1`` at the repo root. BUILDING and verifying
this on the current machine is safe at any time; EXECUTING an install on any
OTHER machine is rubric-gated -- follow docs/DEPLOY.md, never wing it.

DESIGN LAWS:

* SINGLE-WRITER ACROSS MACHINES: ``data/quantbot.db`` lives on LOCAL disk only,
  never a network share -- SQLite over SMB risks silent corruption. At most ONE
  machine has scheduled tasks registered at any moment; ``uninstall`` exists
  precisely so the old machine is decommissioned before a new one is armed.
* GENERATED PATHS: everything is derived from the resolved repo root at run
  time -- no hardcoded usernames or machine paths anywhere in this module.
* IDEMPOTENT: rerunning ``install`` repairs rather than duplicates (schtasks
  ``/F`` overwrites, the venv is reused, the DB is init-only-if-missing).
* PYTHON 3.13 REQUIRED: checked first; refused with clear instructions if
  absent (the pinned wheels and the validated environment assume it).

All system calls go through a small :class:`Runner` interface so the offline
tests can assert the exact commands constructed without executing anything.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Protocol

TASK_DAILY = "QuantBot-Daily"
TASK_LOGON = "QuantBot-Logon"
TASK_MONTHLY = "QuantBot-Monthly"
DAILY_TIME = "07:30"
LOGON_DELAY = "0002:00"
MONTHLY_TIME = "07:45"
KILLSWITCH_FILE = "STOP_NEW_TRADES"
# The operator-set off-laptop backup destination (tools/backup.py ENV_DEST).
BACKUP_ENV = "QUANTBOT_BACKUP_DIR"
REQUIRED_PYTHON = (3, 13)

# The scheduled tasks' entry points, rendered from the RESOLVED repo root.
_BAT_TEMPLATE = (
    "cd /d {root}\n"
    ".venv\\Scripts\\python.exe -m execution.paper_loop "
    "--db data\\quantbot.db >> data\\loop.log 2>&1\n"
)
# The mkdir guard matters: cmd's >> redirect fails if the directory is absent,
# and on a fresh machine the monthly task can fire before any report ran.
_HEALTH_BAT_TEMPLATE = (
    "cd /d {root}\n"
    'if not exist "data\\health" mkdir "data\\health"\n'
    ".venv\\Scripts\\python.exe -m monitors.health "
    "--db data\\quantbot.db >> data\\health\\health.log 2>&1\n"
)

# Printed when registering the logon task needs elevation this shell lacks.
LOGON_FALLBACK = """\
QuantBot-Logon could not be registered from this shell (needs elevation).
Manual fallback (5 steps, Task Scheduler GUI):
  1. Start menu -> type "Task Scheduler" -> open it.
  2. Create Basic Task... -> name it QuantBot-Logon -> Next.
  3. Trigger: When I log on -> Next. Action: Start a program -> browse to
     tools\\run_paper_loop.bat in this repo -> Next -> Finish.
  4. Double-click the task -> Triggers tab -> Edit -> tick "Delay task for:"
     and pick 2 minutes (lets Wi-Fi connect first) -> OK.
  5. Right-click the task -> Run; check data\\loop.log gained a digest line
     (a quiet bars=0 no-op is CORRECT if the daily task already ran today)."""

MONTHLY_FALLBACK = """\
QuantBot-Monthly could not be registered from this shell (needs elevation).
Manual fallback (5 steps, Task Scheduler GUI):
  1. Start menu -> type "Task Scheduler" -> open it.
  2. Create Basic Task... -> name it QuantBot-Monthly -> Next.
  3. Trigger: Monthly -> all months, day 1, start time 07:45 -> Next.
  4. Action: Start a program -> browse to tools\\run_health.bat in this
     repo -> Next -> Finish.
  5. Right-click the task -> Run; check data\\health\\ gained a report file."""


@dataclass(frozen=True, slots=True)
class RunResult:
    """Exit code + combined output of one external command."""

    returncode: int
    output: str


class Runner(Protocol):
    """Anything that can execute an external command (tests inject fakes)."""

    def run(self, args: Sequence[str]) -> RunResult: ...


class SubprocessRunner:
    """The real thing: subprocess.run with captured, merged output."""

    def run(self, args: Sequence[str]) -> RunResult:
        proc = subprocess.run(  # noqa: S603 -- fixed argv, never shell=True
            list(args), capture_output=True, text=True, check=False
        )
        return RunResult(proc.returncode, (proc.stdout or "") + (proc.stderr or ""))


@dataclass(frozen=True, slots=True)
class CheckResult:
    """One verify line: a name, OK/WARN/RED, and a one-line detail."""

    name: str
    status: str
    detail: str


def _say(message: str) -> None:
    print(message)


def generate_bat(root: Path) -> Path:
    """Write tools/run_paper_loop.bat rendered from ``root``; return its path.

    LF newlines, byte-for-byte reproducible: on the machine that committed the
    bat, regeneration must be a no-op (the live check in the install report).
    """
    bat = root / "tools" / "run_paper_loop.bat"
    bat.parent.mkdir(parents=True, exist_ok=True)
    bat.write_text(_BAT_TEMPLATE.format(root=root), newline="\n")
    return bat


def generate_health_bat(root: Path) -> Path:
    """Write tools/run_health.bat (same contract as :func:`generate_bat`)."""
    bat = root / "tools" / "run_health.bat"
    bat.parent.mkdir(parents=True, exist_ok=True)
    bat.write_text(_HEALTH_BAT_TEMPLATE.format(root=root), newline="\n")
    return bat


def _ensure_db(root: Path) -> str:
    """Init the DB if missing; otherwise PRAGMA integrity_check it."""
    db = root / "data" / "quantbot.db"
    if not db.exists():
        from data_store import store  # heavy import, deferred until needed

        db.parent.mkdir(parents=True, exist_ok=True)  # store.init_db won't
        store.init_db(db)
        return f"initialized fresh DB at {db}"
    conn = sqlite3.connect(db)
    try:
        verdict = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
    finally:
        conn.close()
    if verdict != "ok":
        return f"INTEGRITY FAILED: {verdict}"
    return f"existing DB integrity ok ({db})"


def _ensure_env_file(root: Path) -> str:
    """Copy .env.example -> .env if absent (names only; no secrets required yet)."""
    env_file = root / ".env"
    example = root / ".env.example"
    if env_file.exists():
        return ".env present"
    if not example.exists():
        return "WARNING: no .env and no .env.example template to copy"
    shutil.copyfile(example, env_file)
    return ".env created from .env.example (no secrets currently required)"


def _register_tasks(root: Path, runner: Runner) -> None:
    """Register the daily task (must succeed) and attempt the logon one."""
    bat = str(root / "tools" / "run_paper_loop.bat")
    daily = runner.run(
        [
            "schtasks", "/Create", "/TN", TASK_DAILY, "/TR", bat,
            "/SC", "DAILY", "/ST", DAILY_TIME, "/F",
        ]
    )
    if daily.returncode == 0:
        _say(f"task {TASK_DAILY}: registered (daily {DAILY_TIME}, /F overwrite)")
    else:
        _say(f"task {TASK_DAILY}: FAILED to register -- {daily.output.strip()}")

    logon = runner.run(
        [
            "schtasks", "/Create", "/TN", TASK_LOGON, "/TR", bat,
            "/SC", "ONLOGON", "/DELAY", LOGON_DELAY, "/F",
        ]
    )
    if logon.returncode == 0:
        _say(f"task {TASK_LOGON}: registered (on logon, {LOGON_DELAY} delay)")
    else:
        # Expected without elevation -- NOT fatal; the daily task still covers
        # every day the machine is on at 07:30, and catch-up covers the rest.
        _say(LOGON_FALLBACK)

    health_bat = str(root / "tools" / "run_health.bat")
    monthly = runner.run(
        [
            "schtasks", "/Create", "/TN", TASK_MONTHLY, "/TR", health_bat,
            "/SC", "MONTHLY", "/D", "1", "/ST", MONTHLY_TIME, "/F",
        ]
    )
    if monthly.returncode == 0:
        _say(f"task {TASK_MONTHLY}: registered (monthly, day 1, {MONTHLY_TIME})")
    else:
        _say(MONTHLY_FALLBACK)


def cmd_install(
    root: Path,
    runner: Runner,
    version_info: tuple[int, int] | None = None,
    env: Mapping[str, str] | None = None,
) -> int:
    """install: generate, init/check, register, explain killswitch, then verify."""
    version = version_info if version_info is not None else sys.version_info[:2]
    if tuple(version) != REQUIRED_PYTHON:
        _say(
            f"ERROR: Python {REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]} required, "
            f"running {version[0]}.{version[1]}. Install Python 3.13 from "
            "python.org (tick 'py launcher'), then rerun install.ps1."
        )
        return 1

    bat = generate_bat(root)
    _say(f"generated {bat} from resolved root {root}")
    health_bat = generate_health_bat(root)
    _say(f"generated {health_bat} from resolved root {root}")
    _say(f"database: {_ensure_db(root)}")
    _say(f"env file: {_ensure_env_file(root)}")
    _register_tasks(root, runner)
    _say(
        f"killswitch: create a file named {KILLSWITCH_FILE} at the repo root "
        "to stop all NEW orders (pending fills still settle, equity still "
        "marks); delete it to resume. The killswitch is the HUMAN's lever."
    )
    return cmd_verify(root, runner, env=env)


def _pins_check(root: Path) -> CheckResult:
    """Every pinned distribution in requirements.txt is installed."""
    req = root / "requirements.txt"
    if not req.exists():
        return CheckResult("pins", "RED", "requirements.txt missing")
    names = [
        line.split("==")[0].strip()
        for line in req.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    missing: list[str] = []
    for name in names:
        try:
            metadata.version(name)
        except metadata.PackageNotFoundError:
            missing.append(name)
    if missing:
        return CheckResult("pins", "RED", f"missing: {', '.join(missing)}")
    return CheckResult("pins", "OK", f"{len(names)}/{len(names)} pins installed")


def _db_check(root: Path, today: str) -> CheckResult:
    db = root / "data" / "quantbot.db"
    if not db.exists():
        return CheckResult("database", "RED", f"missing: {db}")
    conn = sqlite3.connect(db)
    try:
        verdict = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        row = conn.execute(
            "SELECT MAX(event_time) FROM price_clean WHERE ticker = 'NVDA'"
        ).fetchone()
    except sqlite3.DatabaseError as exc:
        return CheckResult("database", "RED", f"unreadable: {exc}")
    finally:
        conn.close()
    if verdict != "ok":
        return CheckResult("database", "RED", f"integrity_check: {verdict}")
    latest = row[0] if row else None
    if latest is None:
        return CheckResult(
            "database", "WARN", "integrity ok; no CLEAN NVDA bars yet (first "
            "run or pre-restore state)"
        )
    age = (date.fromisoformat(today) - date.fromisoformat(str(latest)[:10])).days
    status = "WARN" if age > 5 else "OK"
    return CheckResult(
        "database", status, f"integrity ok; latest CLEAN NVDA bar "
        f"{str(latest)[:10]} ({age}d old)"
    )


def _digest_check(root: Path) -> CheckResult:
    log = root / "data" / "loop.log"
    if not log.exists():
        return CheckResult("last_digest", "WARN", "no data\\loop.log yet")
    digests = [
        line
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.startswith("PAPER ")
    ]
    if not digests:
        return CheckResult("last_digest", "WARN", "log exists but no digest line yet")
    return CheckResult("last_digest", "OK", digests[-1])


def cmd_verify(
    root: Path,
    runner: Runner,
    env: Mapping[str, str] | None = None,
    today: str | None = None,
) -> int:
    """verify: report every install-health check; exit non-zero on any RED."""
    the_env: Mapping[str, str] = env if env is not None else os.environ
    the_today = (
        today
        if today is not None
        else datetime.now(timezone.utc).date().isoformat()
    )
    checks: list[CheckResult] = []

    version = sys.version_info[:2]
    checks.append(
        CheckResult(
            "python",
            "OK" if version == REQUIRED_PYTHON else "RED",
            f"{sys.version.split()[0]} at {sys.executable}",
        )
    )
    venv_python = root / ".venv" / "Scripts" / "python.exe"
    checks.append(
        CheckResult(
            "venv",
            "OK" if venv_python.exists() else "RED",
            str(venv_python),
        )
    )
    checks.append(_pins_check(root))
    checks.append(_db_check(root, the_today))

    for task, absent_status, absent_note in (
        (TASK_DAILY, "RED", "not registered -- rerun install"),
        (TASK_LOGON, "WARN", "not registered (GUI fallback pending; optional)"),
        (TASK_MONTHLY, "WARN", "not registered (GUI fallback pending; optional)"),
    ):
        query = runner.run(["schtasks", "/Query", "/TN", task])
        checks.append(
            CheckResult(
                f"task_{task}",
                "OK" if query.returncode == 0 else absent_status,
                "registered" if query.returncode == 0 else absent_note,
            )
        )

    killswitch = root / KILLSWITCH_FILE
    checks.append(
        CheckResult(
            "killswitch",
            "WARN" if killswitch.exists() else "OK",
            "PRESENT -- new trades are STOPPED" if killswitch.exists()
            else f"absent ({KILLSWITCH_FILE} not armed)",
        )
    )
    dest = the_env.get(BACKUP_ENV)
    checks.append(
        CheckResult(
            "backup_destination",
            "OK" if dest else "WARN",
            f"{BACKUP_ENV}={dest}" if dest
            else f"{BACKUP_ENV} unset -- backups are LOCAL-ONLY (rubric 7)",
        )
    )

    # Telegram digest: configured = both secrets present (env or .env file).
    # notify.load_config is the single source of truth for "configured".
    from monitors import notify  # deferred: pulls requests

    telegram = notify.load_config(env=the_env, root=root)
    checks.append(
        CheckResult(
            "telegram",
            "OK" if telegram is not None else "WARN",
            "configured (token + chat id present)" if telegram is not None
            else "unconfigured — digest is log-only",
        )
    )
    checks.append(_digest_check(root))

    worst = "OK"
    for check in checks:
        _say(f"{check.name}: {check.status} - {check.detail}")
        if check.status == "RED":
            worst = "RED"
        elif check.status == "WARN" and worst == "OK":
            worst = "WARN"
    _say(f"VERIFY OVERALL: {worst}")
    return 1 if worst == "RED" else 0


def cmd_uninstall(root: Path, runner: Runner) -> int:
    """uninstall: remove BOTH scheduled tasks; leave code, .venv and data/.

    data/ is the product (the journal); uninstall decommissions this machine's
    WRITER role only, preserving the single-writer law during migration.
    """
    for task in (TASK_DAILY, TASK_LOGON, TASK_MONTHLY):
        existed = runner.run(["schtasks", "/Query", "/TN", task]).returncode == 0
        if existed:
            result = runner.run(["schtasks", "/Delete", "/TN", task, "/F"])
            verdict = "removed" if result.returncode == 0 else (
                f"DELETE FAILED -- {result.output.strip()}"
            )
        else:
            verdict = "was not registered"
        _say(f"task {task}: {verdict}")
    _say("code, .venv and data/ left untouched (data is the product)")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="installer",
        description="Install, verify, or uninstall the QuantBot scheduled runs.",
    )
    parser.add_argument("command", choices=("install", "verify", "uninstall"))
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    runner = SubprocessRunner()
    if args.command == "install":
        return cmd_install(root, runner)
    if args.command == "verify":
        return cmd_verify(root, runner)
    return cmd_uninstall(root, runner)


if __name__ == "__main__":
    raise SystemExit(main())
