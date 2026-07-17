"""Offline tests for the verified journal backup (tools/backup.py).

Everything runs against temp stores in tmp dirs. The autouse fixture clears
QUANTBOT_BACKUP_DIR so an operator's real off-laptop destination can never
receive test snapshots.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from data_store import store
from tools import backup
from tools.backup import BackupVerificationError, run_backup

NOW = "2026-07-17T08:00:00Z"  # stamp 20260717; retention cutoff = 2026-07-03
STAMP = "20260717"


@pytest.fixture(autouse=True)
def _no_operator_dest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(backup.ENV_DEST, raising=False)


def _make_source(data_dir: Path, *, trials_lines: int | None = 3) -> Path:
    """A real store DB with one row in every checked table, plus a trial log."""
    data_dir.mkdir(parents=True, exist_ok=True)
    db = data_dir / "quantbot.db"
    store.init_db(db)
    conn = store.connect(db)
    try:
        conn.execute(
            "INSERT INTO price_raw VALUES ('TEST','t0',1,1,1,1,100,'t0','test')"
        )
        conn.execute(
            "INSERT INTO price_clean VALUES ('TEST','t0',1,1,1,1,100,1,'t0','test')"
        )
        conn.execute(
            "INSERT INTO paper_orders (ticker, decision_event_time, target_weight,"
            " created_knowable_time, status) VALUES ('TEST','t0',1.0,'t0','filled')"
        )
        conn.execute("INSERT INTO paper_fills VALUES (1,'t1',1.0,1.0,-1.0,'t1')")
        conn.execute("INSERT INTO paper_equity VALUES ('TEST','t1',10000.0,1.0)")
        conn.execute(
            "INSERT INTO quarantine VALUES ('price','TEST','t0','{}','test','t0')"
        )
        conn.commit()
    finally:
        conn.close()
    if trials_lines is not None:
        (data_dir / "trials.jsonl").write_text(
            "".join(f'{{"trial": {i}}}\n' for i in range(trials_lines)),
            encoding="utf-8",
        )
    return db


def _add_equity_row(db: Path, event_time: str) -> None:
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            "INSERT INTO paper_equity VALUES ('TEST', ?, 1.0, 1.0)", (event_time,)
        )
        conn.commit()
    finally:
        conn.close()


# ------------------------------------------------------------------ snapshot


def test_snapshot_is_verified_and_counts_match_source(tmp_path: Path) -> None:
    db = _make_source(tmp_path / "data")
    dest = tmp_path / "offsite"

    report = run_backup(db, dest_dir=dest, now=NOW)

    assert report.verified is True
    assert report.dest_dir == dest
    assert report.db_snapshot_path == dest / f"quantbot-{STAMP}.db"
    assert report.db_snapshot_path.exists()
    assert report.tables_checked == {
        "price_raw": 1,
        "price_clean": 1,
        "paper_orders": 1,
        "paper_fills": 1,
        "paper_equity": 1,
        "quarantine": 1,
    }
    assert report.local_only is False  # a separate tmp dir is "off-laptop" here

    # The snapshot itself opens READ-ONLY, is intact, and holds the same rows.
    uri = f"file:{report.db_snapshot_path.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("SELECT COUNT(*) FROM paper_equity").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("INSERT INTO paper_equity VALUES ('X','x',1.0,1.0)")
    finally:
        conn.close()


def test_trials_copied_and_line_count_matches(tmp_path: Path) -> None:
    db = _make_source(tmp_path / "data", trials_lines=3)
    report = run_backup(db, dest_dir=tmp_path / "offsite", now=NOW)

    assert report.trials_snapshot_path is not None
    assert report.trials_snapshot_path.name == f"trials-{STAMP}.jsonl"
    copied = report.trials_snapshot_path.read_text(encoding="utf-8")
    assert copied == (tmp_path / "data" / "trials.jsonl").read_text(encoding="utf-8")
    assert len(copied.splitlines()) == 3


def test_absent_trials_is_noted_not_an_error(tmp_path: Path) -> None:
    db = _make_source(tmp_path / "data", trials_lines=None)
    report = run_backup(db, dest_dir=tmp_path / "offsite", now=NOW)

    assert report.verified is True
    assert report.trials_snapshot_path is None  # the report's "absent" note
    assert "ABSENT" in report.line()


def test_same_day_rerun_replaces_that_days_pair(tmp_path: Path) -> None:
    db = _make_source(tmp_path / "data")
    dest = tmp_path / "offsite"

    first = run_backup(db, dest_dir=dest, now=NOW)
    assert first.tables_checked["paper_equity"] == 1

    _add_equity_row(db, "t2")  # the source moved on since the morning run
    second = run_backup(db, dest_dir=dest, now=NOW)

    # Still exactly ONE pair for the day -- and it is the NEW snapshot.
    assert sorted(p.name for p in dest.iterdir()) == [
        f"quantbot-{STAMP}.db",
        f"trials-{STAMP}.jsonl",
    ]
    assert second.tables_checked["paper_equity"] == 2


# ----------------------------------------------------------------- retention


def test_retention_prunes_only_expired_snapshot_pairs(tmp_path: Path) -> None:
    db = _make_source(tmp_path / "data")
    dest = tmp_path / "offsite"
    dest.mkdir()
    expired_db = dest / "quantbot-20260601.db"  # > 14 days before 2026-07-17
    expired_trials = dest / "trials-20260601.jsonl"
    recent_db = dest / "quantbot-20260710.db"  # within 14 days: kept
    unrelated = dest / "README.txt"  # never touched
    date_shaped = dest / "quantbot-99999999.db"  # not a real date: left alone
    for f in (expired_db, expired_trials, recent_db, unrelated, date_shaped):
        f.write_text("placeholder", encoding="utf-8")

    report = run_backup(db, dest_dir=dest, now=NOW, retain_days=14)

    assert set(report.pruned) == {expired_db, expired_trials}
    assert not expired_db.exists() and not expired_trials.exists()
    assert recent_db.exists() and unrelated.exists() and date_shaped.exists()


# -------------------------------------------------------------- verification


def test_tampered_snapshot_is_deleted_raises_and_never_prunes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _make_source(tmp_path / "data")
    dest = tmp_path / "offsite"
    dest.mkdir()
    expired = dest / "quantbot-20260601.db"  # would be pruned on a GOOD run
    expired.write_text("placeholder", encoding="utf-8")

    real_snapshot = backup._snapshot_db

    def tampered(source: sqlite3.Connection, db_snap: Path) -> None:
        real_snapshot(source, db_snap)  # a genuine snapshot...
        evil = sqlite3.connect(str(db_snap))  # ...then corrupt it post-copy
        try:
            evil.execute("INSERT INTO paper_equity VALUES ('TEST','t9',1.0,1.0)")
            evil.commit()
        finally:
            evil.close()

    monkeypatch.setattr(backup, "_snapshot_db", tampered)
    with pytest.raises(BackupVerificationError, match="paper_equity"):
        run_backup(db, dest_dir=dest, now=NOW)

    # The bad artifacts are gone; the expired pair was NOT pruned (failed run).
    assert sorted(p.name for p in dest.iterdir()) == [expired.name]


# ------------------------------------------------------- destination heuristic


def test_default_dest_beside_the_db_is_local_only(tmp_path: Path) -> None:
    db = _make_source(tmp_path / "data")
    report = run_backup(db, now=NOW)  # no arg, no env -> backups/ beside the db
    assert report.dest_dir == tmp_path / "data" / "backups"
    assert report.local_only is True


def test_dest_resolution_explicit_beats_env_beats_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _make_source(tmp_path / "data")
    cloud = tmp_path / "cloud"
    monkeypatch.setenv(backup.ENV_DEST, str(cloud))

    via_env = run_backup(db, now=NOW)
    assert via_env.dest_dir == cloud
    assert via_env.local_only is False

    explicit = tmp_path / "explicit"
    via_arg = run_backup(db, dest_dir=explicit, now=NOW)
    assert via_arg.dest_dir == explicit
