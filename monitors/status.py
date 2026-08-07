"""On-demand status + drill -- ask "are we healthy?" and "do the lights work?".

LAW (same as the whole package): this tool OBSERVES and exercises GOVERNANCE
only. It edits no parameter, controls no strategy, and takes no trading action.
The store is opened READ-ONLY; the drill doctors throwaway COPIES made via the
SQLite backup API and deletes them -- the real DB is untouched by construction.

THE DRILL (SCARS #9 on demand): a monitor is only trustworthy while it can
still go red, so the drill breaks two copies on purpose -- stale CLEAN bars in
one, a -40% equity mark in the other -- and requires the corresponding meters
to fire. Every drill line is prefixed ``DRILL — `` so a test red can never be
mistaken for a real one, and the drill NEVER sends Telegram.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from execution.config import CONFIG
from monitors import notify
from monitors.meters import (
    MeterResult,
    Status,
    book_invariants,
    data_freshness,
    drawdown,
    quarantine_growth,
)
from tools.installer import (
    BACKUP_ENV,
    KILLSWITCH_FILE,
    TASK_DAILY,
    TASK_LOGON,
    TASK_MONTHLY,
    Runner,
    SubprocessRunner,
)

_DRILL_PREFIX = "DRILL — "
# Doctoring A deletes every CLEAN bar newer than this many days: whatever
# remains is comfortably past the freshness meter's 5-day RED line.
_DRILL_STALE_DAYS = 21


@dataclass(frozen=True, slots=True)
class DrillResult:
    """Every line prefixed ``DRILL — ``; ``passed`` = both meters fired RED."""

    lines: list[str]
    passed: bool


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)


def run_status(
    db_path: Path,
    runner: Runner | None = None,
    env: Mapping[str, str] | None = None,
    root: Path | None = None,
    today: str | None = None,
) -> tuple[list[MeterResult], str]:
    """The four DB meters + config/governance checks; overall = worst status."""
    the_runner = runner if runner is not None else SubprocessRunner()
    the_env: Mapping[str, str] = env if env is not None else os.environ
    the_root = root if root is not None else Path(__file__).resolve().parents[1]
    the_today = (
        today
        if today is not None
        else datetime.now(timezone.utc).date().isoformat()
    )

    conn = _connect_readonly(db_path)
    try:
        results: list[MeterResult] = [
            data_freshness(conn, the_today, CONFIG.ticker),
            drawdown(conn, CONFIG.ticker),
            book_invariants(conn, CONFIG.ticker),
            quarantine_growth(conn, the_today),
        ]
    finally:
        conn.close()

    telegram = notify.load_config(env=the_env, root=the_root)
    results.append(
        MeterResult(
            "telegram",
            "OK" if telegram is not None else "WARN",
            "configured" if telegram is not None
            else "unconfigured — digest is log-only",
        )
    )
    dest = the_env.get(BACKUP_ENV, "")
    results.append(
        MeterResult(
            "backup_destination",
            "OK" if dest else "WARN",
            f"{BACKUP_ENV}={dest}" if dest
            else f"{BACKUP_ENV} unset — backups are LOCAL-ONLY (rubric 7)",
        )
    )
    killswitch = the_root / KILLSWITCH_FILE
    results.append(
        MeterResult(
            "killswitch",
            "WARN" if killswitch.exists() else "OK",
            "PRESENT — new trades are STOPPED" if killswitch.exists()
            else f"absent ({KILLSWITCH_FILE} not armed)",
        )
    )
    task_checks: tuple[tuple[str, Status], ...] = (
        (TASK_DAILY, "RED"),
        (TASK_LOGON, "WARN"),
        (TASK_MONTHLY, "WARN"),
    )
    for task, absent_status in task_checks:
        present = the_runner.run(["schtasks", "/Query", "/TN", task]).returncode == 0
        results.append(
            MeterResult(
                f"task_{task}",
                "OK" if present else absent_status,
                "registered" if present else "not registered",
            )
        )

    severity = {"OK": 0, "WARN": 1, "RED": 2}
    overall = max((r.status for r in results), key=lambda s: severity[s])
    return results, overall


def _copy_db(source: Path, dest: Path) -> None:
    src = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(dest)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def run_drill(db_path: Path, today: str | None = None) -> DrillResult:
    """Prove the lights still turn red, on doctored throwaway copies only."""
    the_today = (
        today
        if today is not None
        else datetime.now(timezone.utc).date().isoformat()
    )
    lines: list[str] = []

    def say(text: str) -> None:
        lines.append(f"{_DRILL_PREFIX}{text}")

    fired_freshness = False
    fired_drawdown = False
    with tempfile.TemporaryDirectory(prefix="quantbot-drill-") as tmp:
        # Copy A: amputate recent CLEAN bars -> data_freshness must go RED.
        copy_a = Path(tmp) / "stale.db"
        _copy_db(db_path, copy_a)
        cutoff = (
            date.fromisoformat(the_today) - timedelta(days=_DRILL_STALE_DAYS)
        ).isoformat()
        conn = sqlite3.connect(copy_a)
        try:
            conn.execute(
                "DELETE FROM price_clean WHERE ticker = ? AND event_time >= ?",
                (CONFIG.ticker, f"{cutoff}T00:00:00Z"),
            )
            conn.commit()
            fresh = data_freshness(conn, the_today, CONFIG.ticker)
        finally:
            conn.close()
        say(f"copy A (CLEAN truncated before {cutoff}):")
        say(f"{fresh.name}: {fresh.status} - {fresh.detail}")
        fired_freshness = fresh.status == "RED"

        # Copy B: fake latest equity mark 40% below peak -> drawdown must RED.
        copy_b = Path(tmp) / "drawdown.db"
        _copy_db(db_path, copy_b)
        conn = sqlite3.connect(copy_b)
        try:
            row = conn.execute(
                "SELECT MAX(equity) FROM paper_equity WHERE ticker = ?",
                (CONFIG.ticker,),
            ).fetchone()
            peak = float(row[0]) if row and row[0] is not None else 10000.0
            if row is None or row[0] is None:
                conn.execute(
                    "INSERT INTO paper_equity (ticker, event_time, equity, close)"
                    " VALUES (?, ?, ?, 0.0)",
                    (CONFIG.ticker, f"{the_today}T00:00:00Z", peak),
                )
            conn.execute(
                "INSERT INTO paper_equity (ticker, event_time, equity, close) "
                "VALUES (?, ?, ?, 0.0)",
                (CONFIG.ticker, f"{the_today}T23:59:59Z", 0.6 * peak),
            )
            conn.commit()
            dd = drawdown(conn, CONFIG.ticker)
        finally:
            conn.close()
        say(f"copy B (fake mark at {0.6 * peak:,.2f} vs peak {peak:,.2f}):")
        say(f"{dd.name}: {dd.status} - {dd.detail}")
        fired_drawdown = dd.status == "RED"

    passed = fired_freshness and fired_drawdown
    say(
        "verdict: LIGHTS WORK — both meters went red on demand; copies deleted"
        if passed
        else "verdict: DRILL FAILED — a meter did NOT fire; the monitoring is "
        "broken (SCARS #9), investigate before trusting any green"
    )
    return DrillResult(lines=lines, passed=passed)


def _db_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="status", description="On-demand status + red-light drill."
    )
    parser.add_argument("--db", default="data/quantbot.db", metavar="PATH")
    parser.add_argument(
        "--drill", action="store_true", help="also prove the lights turn red"
    )
    args = parser.parse_args(argv)
    db = Path(args.db)

    results, overall = run_status(db)
    for result in results:
        print(f"{result.name}: {result.status} - {result.detail}")
    print(f"OVERALL: {overall}")

    drill_ok = True
    if args.drill:
        before = _db_hash(db)
        drill = run_drill(db)
        for line in drill.lines:
            print(line)
        drill_ok = drill.passed
        if _db_hash(db) != before:  # pragma: no cover -- must never happen
            print("FATAL: the drill modified the real DB — this is a bug")
            return 1

    # Exit code reflects REAL health only; drill reds are the drill WORKING.
    # A drill that failed to fire is itself a real monitoring failure.
    return 1 if overall == "RED" or not drill_ok else 0


if __name__ == "__main__":
    raise SystemExit(main())
