"""Verified journal backup -- rubric condition 7 (protect the product).

The product of months of paper trading -- the trade journal (orders, fills,
equity marks), the price history, and the honest trial tally (trials.jsonl) --
lives ONLY in data/ on a sometimes-off laptop. This tool snapshots it, VERIFIES
the snapshot before trusting it, and prunes old snapshots. Three rules:

* ONLINE BACKUP API, never a file copy. The store runs SQLite in WAL mode, so a
  plain file copy of a live database can capture a torn state (main file without
  its -wal). ``sqlite3.Connection.backup`` produces a consistent snapshot.
* VERIFY BEFORE TRUSTING (monitors law #9 in spirit): the snapshot must open
  read-only, pass ``PRAGMA integrity_check``, and match the source's row counts
  table by table; the trials copy must match the source line count. A failed
  check deletes the bad artifacts and raises -- an unverified backup reported as
  "OK" is worse than no backup.
* A backup on the SAME dying laptop protects nothing. The report flags such a
  destination as ``local_only``; callers must warn loudly until the operator
  points ``QUANTBOT_BACKUP_DIR`` at an off-laptop folder (e.g. OneDrive).

CLI: ``python -m tools.backup --db data/quantbot.db [--dest DIR] [--retain-days N]``
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import shutil
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from data_store.timeutils import now_utc_iso

logger = logging.getLogger(__name__)

# Operator-set destination for off-laptop backups (e.g. a OneDrive folder).
ENV_DEST = "QUANTBOT_BACKUP_DIR"
DEFAULT_RETAIN_DAYS = 14

# The warning callers print when a backup landed on the machine it protects.
LOCAL_ONLY_WARNING = (
    "WARNING: BACKUP IS LOCAL-ONLY — set QUANTBOT_BACKUP_DIR to an "
    "off-laptop folder (e.g. OneDrive)"
)

# Every table the snapshot must reproduce exactly (the journal + its evidence).
_TABLES: tuple[str, ...] = (
    "price_raw",
    "price_clean",
    "paper_orders",
    "paper_fills",
    "paper_equity",
    "quarantine",
)

# The ONLY filenames retention may ever touch (never prune anything else).
_SNAPSHOT_NAME = re.compile(r"quantbot-(\d{8})\.db|trials-(\d{8})\.jsonl")


class BackupVerificationError(Exception):
    """The snapshot failed verification and was deleted -- the journal is
    NOT protected by this run."""


@dataclass(frozen=True, slots=True)
class BackupReport:
    """What one backup run produced and proved.

    ``tables_checked`` maps each verified table to its (matching) row count;
    ``pruned`` lists the expired snapshot files retention removed; ``local_only``
    means the destination is on the same machine/repo as the journal itself, so
    the backup does not yet protect against losing the laptop.
    """

    dest_dir: Path
    db_snapshot_path: Path
    trials_snapshot_path: Path | None
    verified: bool
    tables_checked: dict[str, int]
    pruned: list[Path]
    local_only: bool

    def line(self) -> str:
        """The one-line human summary."""
        trials = (
            self.trials_snapshot_path.name
            if self.trials_snapshot_path is not None
            else "ABSENT"
        )
        rows = sum(self.tables_checked.values())
        where = "LOCAL-ONLY" if self.local_only else "off-repo destination"
        return (
            f"BACKUP {self.db_snapshot_path.name} -> {self.dest_dir} | "
            f"verified={self.verified} ({len(self.tables_checked)} tables, "
            f"{rows} rows) | trials={trials} | pruned={len(self.pruned)} | {where}"
        )


def _resolve_dest(db_path: Path, dest_dir: str | Path | None) -> Path:
    """Explicit argument > QUANTBOT_BACKUP_DIR > backups/ beside the database
    (which is data/backups/ for the live store)."""
    if dest_dir is not None:
        return Path(dest_dir)
    env = os.environ.get(ENV_DEST, "").strip()
    if env:
        return Path(env)
    return db_path.parent / "backups"


def _is_local_only(dest: Path, db_path: Path) -> bool:
    """True when the destination lives inside the repo (cwd) or beside the
    journal's own data directory -- i.e. on the laptop the backup should
    survive losing."""
    resolved = dest.resolve()
    repo_root = Path.cwd().resolve()
    data_dir = db_path.resolve().parent
    return resolved.is_relative_to(repo_root) or resolved.is_relative_to(data_dir)


def _snapshot_db(source: sqlite3.Connection, db_snap: Path) -> None:
    """Copy the live database into ``db_snap`` via sqlite3's ONLINE BACKUP API.

    Never a file copy: the store runs WAL, and copying the main file of a live
    WAL database can capture a torn state. (Module-level seam: the verification
    tests wrap this to tamper with the snapshot post-copy.)
    """
    dest_conn = sqlite3.connect(str(db_snap))
    try:
        source.backup(dest_conn)
        # A snapshot is a SINGLE-FILE artifact: drop the WAL mode it inherited
        # from the live store, so no -wal/-shm sidecars ride along (and the
        # read-only verification open cannot spawn them either).
        dest_conn.execute("PRAGMA journal_mode=DELETE")
    finally:
        dest_conn.close()


def _count_rows(conn: sqlite3.Connection, table: str) -> int:
    # table comes from the fixed _TABLES tuple, never from input.
    row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    return int(row[0])


def _line_count(path: Path) -> int:
    with path.open("rb") as fh:
        return sum(1 for _ in fh)


def _delete_artifacts(paths: Sequence[Path]) -> None:
    """Remove snapshot files (plus any -wal/-shm sidecars of a .db)."""
    for path in paths:
        path.unlink(missing_ok=True)
        if path.suffix == ".db":
            path.with_name(path.name + "-wal").unlink(missing_ok=True)
            path.with_name(path.name + "-shm").unlink(missing_ok=True)


def _verify_snapshot(
    db_snap: Path,
    trials_snap: Path | None,
    expected_counts: dict[str, int],
    expected_trials_lines: int | None,
) -> None:
    """Prove the snapshot is trustworthy or raise :class:`BackupVerificationError`.

    Read-only open + ``PRAGMA integrity_check`` + per-table row counts against
    the source's counts, and the trials copy's line count. Every problem found
    is collected into the error message (no silent swallow, no early exit).
    """
    problems: list[str] = []
    uri = f"file:{db_snap.resolve().as_posix()}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:
        raise BackupVerificationError(
            f"snapshot cannot be opened read-only: {exc}"
        ) from exc
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        verdict = str(row[0]) if row is not None else "<no result>"
        if verdict != "ok":
            problems.append(f"integrity_check returned {verdict!r}")
        for table, expected in expected_counts.items():
            try:
                actual = _count_rows(conn, table)
            except sqlite3.Error as exc:
                problems.append(f"{table}: unreadable in snapshot ({exc})")
                continue
            if actual != expected:
                problems.append(
                    f"{table}: snapshot has {actual} rows, source had {expected}"
                )
    except sqlite3.Error as exc:
        problems.append(f"snapshot unreadable: {exc}")
    finally:
        conn.close()

    if trials_snap is not None and expected_trials_lines is not None:
        actual_lines = _line_count(trials_snap)
        if actual_lines != expected_trials_lines:
            problems.append(
                f"trials copy has {actual_lines} lines, source had "
                f"{expected_trials_lines}"
            )

    if problems:
        raise BackupVerificationError("; ".join(problems))


def _prune(dest: Path, as_of: date, retain_days: int) -> list[Path]:
    """Remove snapshot files whose filename date is more than ``retain_days``
    old. Only names matching the snapshot patterns are ever touched."""
    cutoff = as_of - timedelta(days=retain_days)
    pruned: list[Path] = []
    for entry in sorted(dest.iterdir()):
        match = _SNAPSHOT_NAME.fullmatch(entry.name)
        if match is None:
            continue
        stamp = match.group(1) or match.group(2)
        try:
            entry_date = datetime.strptime(stamp, "%Y%m%d").date()
        except ValueError:
            continue  # date-shaped but not a date; leave it alone
        if entry_date < cutoff:
            entry.unlink()
            pruned.append(entry)
    return pruned


def run_backup(
    db_path: str | Path,
    dest_dir: str | Path | None = None,
    retain_days: int = DEFAULT_RETAIN_DAYS,
    now: str | None = None,
) -> BackupReport:
    """Snapshot the journal, verify the snapshot, prune expired ones; report.

    One ``quantbot-YYYYMMDD.db`` (UTC date) per day -- a same-day rerun REPLACES
    that day's snapshot; ``trials.jsonl`` rides along as ``trials-YYYYMMDD.jsonl``
    when present (its absence is noted, not an error). Verification failure
    deletes this run's artifacts and raises :class:`BackupVerificationError`;
    retention runs ONLY after a verified backup and never touches anything but
    expired snapshot files.
    """
    source_path = Path(db_path)
    if not source_path.exists():
        raise FileNotFoundError(f"database not found: {source_path}")
    if retain_days < 1:
        raise ValueError(f"retain_days must be >= 1, got {retain_days}")
    the_now = now if now is not None else now_utc_iso()
    as_of = datetime.strptime(the_now[:10], "%Y-%m-%d").date()
    stamp = the_now[:10].replace("-", "")

    dest = _resolve_dest(source_path, dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    local_only = _is_local_only(dest, source_path)

    db_snap = dest / f"quantbot-{stamp}.db"
    trials_src = source_path.parent / "trials.jsonl"
    trials_snap: Path | None = None

    # Same-day rerun replaces today's pair: clear leftovers before snapshotting.
    _delete_artifacts([db_snap, dest / f"trials-{stamp}.jsonl"])

    source = sqlite3.connect(str(source_path))
    try:
        _snapshot_db(source, db_snap)
        # Counts taken on the SAME connection/session the snapshot came from
        # (the loop is single-process, so nothing writes between the two).
        expected_counts = {table: _count_rows(source, table) for table in _TABLES}
    finally:
        source.close()

    expected_trials_lines: int | None = None
    if trials_src.exists():
        trials_snap = dest / f"trials-{stamp}.jsonl"
        shutil.copyfile(trials_src, trials_snap)
        expected_trials_lines = _line_count(trials_src)
    else:
        logger.info("trials.jsonl not found at %s; noted, not an error", trials_src)

    try:
        _verify_snapshot(db_snap, trials_snap, expected_counts, expected_trials_lines)
    except BackupVerificationError:
        # Never leave an unverified snapshot lying around looking like a backup.
        _delete_artifacts([db_snap] if trials_snap is None else [db_snap, trials_snap])
        raise

    pruned = _prune(dest, as_of, retain_days)  # only after a VERIFIED backup

    report = BackupReport(
        dest_dir=dest,
        db_snapshot_path=db_snap,
        trials_snapshot_path=trials_snap,
        verified=True,
        tables_checked=expected_counts,
        pruned=pruned,
        local_only=local_only,
    )
    logger.info("%s", report.line())
    return report


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: ``python -m tools.backup --db data/quantbot.db [--dest DIR]
    [--retain-days N]``."""
    parser = argparse.ArgumentParser(
        prog="backup",
        description="Verified journal backup (SQLite online-backup + retention).",
    )
    parser.add_argument(
        "--db",
        required=True,
        metavar="PATH",
        help="Path to the SQLite database, e.g. data/quantbot.db",
    )
    parser.add_argument(
        "--dest",
        default=None,
        metavar="DIR",
        help=f"Destination folder (default: ${ENV_DEST}, else backups/ beside the db)",
    )
    parser.add_argument(
        "--retain-days",
        type=int,
        default=DEFAULT_RETAIN_DAYS,
        metavar="N",
        help=f"Prune snapshots older than N days (default {DEFAULT_RETAIN_DAYS})",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    report = run_backup(
        Path(args.db), dest_dir=args.dest, retain_days=int(args.retain_days)
    )
    print(report.line())
    if report.local_only:
        print(LOCAL_ONLY_WARNING)
    return 0


if __name__ == "__main__":  # pragma: no cover -- exercised via the CLI live run
    raise SystemExit(main())
