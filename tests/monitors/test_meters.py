"""Birth certificates for every meter (SCARS #9): each one is fed a healthy
fixture (OK) AND a deliberately broken one (RED). A meter that cannot go red
is wallpaper -- these tests are what make the MONITORS block trustworthy."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from data_store import store
from data_store.store import PriceClean
from monitors.meters import (
    backup_status,
    book_invariants,
    data_freshness,
    drawdown,
    quarantine_growth,
    run_all,
)
from tools.backup import BackupReport

TICKER = "NVDA"
TODAY = "2024-01-15"


def _bar(day: str) -> PriceClean:
    """One CLEAN bar on ``day`` (YYYY-MM-DD); knowable an hour after midnight."""
    return PriceClean(
        ticker=TICKER,
        event_time=f"{day}T00:00:00Z",
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.0,
        volume=1_000_000,
        adj_close=100.0,
        knowable_time=f"{day}T01:00:00Z",
        source="test",
    )


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db = tmp_path / "meters.db"
    store.init_db(db)
    return store.connect(db)


def _install_bars(conn: sqlite3.Connection, days: list[str]) -> None:
    store.write_price_clean(conn, [_bar(d) for d in days])


def _mark(conn: sqlite3.Connection, day: str, equity: float) -> None:
    conn.execute(
        "INSERT INTO paper_equity (ticker, event_time, equity, close) "
        "VALUES (?, ?, ?, ?)",
        (TICKER, f"{day}T00:00:00Z", equity, 100.0),
    )


def _state(
    conn: sqlite3.Connection, day: str, shares: float = 48.0, cash: float = -5.0
) -> None:
    """Paper state cursor at ``day``; cash defaults to the KNOWN ~-5 overdraft."""
    conn.execute(
        "INSERT INTO paper_state (ticker, shares, cash, last_decided_event_time) "
        "VALUES (?, ?, ?, ?)",
        (TICKER, shares, cash, f"{day}T00:00:00Z"),
    )


def _order(conn: sqlite3.Connection, day: str, status: str) -> None:
    conn.execute(
        "INSERT INTO paper_orders (ticker, decision_event_time, target_weight, "
        "created_knowable_time, status) VALUES (?, ?, 1.0, ?, ?)",
        (TICKER, f"{day}T00:00:00Z", f"{day}T02:00:00Z", status),
    )


def _quarantine_rows(conn: sqlite3.Connection, n: int, day: str) -> None:
    conn.executemany(
        "INSERT INTO quarantine (domain, ticker, event_time, payload, reason, "
        "knowable_time) VALUES ('price', ?, NULL, '{}', 'test', ?)",
        [(TICKER, f"{day}T09:00:{i:02d}Z") for i in range(n)],
    )


def _report(*, verified: bool = True, local_only: bool = False) -> BackupReport:
    return BackupReport(
        dest_dir=Path("dest"),
        db_snapshot_path=Path("dest/quantbot-00000000.db"),
        trials_snapshot_path=None,
        verified=verified,
        tables_checked={},
        pruned=[],
        local_only=local_only,
    )


# ------------------------------------------------------------ data_freshness


def test_freshness_ok_on_yesterdays_bar(conn: sqlite3.Connection) -> None:
    _install_bars(conn, ["2024-01-13", "2024-01-14"])
    result = data_freshness(conn, TODAY)
    assert result.status == "OK"
    assert "1d old" in result.detail


def test_freshness_warn_at_four_days(conn: sqlite3.Connection) -> None:
    _install_bars(conn, ["2024-01-11"])
    assert data_freshness(conn, TODAY).status == "WARN"


def test_freshness_red_on_stale_bars(conn: sqlite3.Connection) -> None:
    _install_bars(conn, ["2024-01-07"])  # 8 calendar days before TODAY
    result = data_freshness(conn, TODAY)
    assert result.status == "RED"
    assert "8d old" in result.detail


def test_freshness_red_on_empty_store(conn: sqlite3.Connection) -> None:
    assert data_freshness(conn, TODAY).status == "RED"


# ------------------------------------------------------------ drawdown


def test_drawdown_ok_at_small_dd(conn: sqlite3.Connection) -> None:
    _mark(conn, "2024-01-13", 10000.0)
    _mark(conn, "2024-01-14", 9500.0)  # -5%
    result = drawdown(conn)
    assert result.status == "OK"
    assert "-5.00%" in result.detail


def test_drawdown_warn_at_80pct_of_validated_worst(conn: sqlite3.Connection) -> None:
    _mark(conn, "2024-01-13", 10000.0)
    _mark(conn, "2024-01-14", 7000.0)  # -30%, past -29.2% warn line
    assert drawdown(conn).status == "WARN"


def test_drawdown_red_past_validated_worst(conn: sqlite3.Connection) -> None:
    _mark(conn, "2024-01-13", 10000.0)
    _mark(conn, "2024-01-14", 6000.0)  # -40%, past the -36.5% validated worst
    result = drawdown(conn)
    assert result.status == "RED"
    assert "-40.00%" in result.detail
    assert "-36.5%" in result.detail  # the threshold is always shown


# ------------------------------------------------------------ book_invariants


def _healthy_book(conn: sqlite3.Connection) -> None:
    _install_bars(conn, ["2024-01-13", "2024-01-14"])
    _state(conn, "2024-01-14")  # cash -5.00: the known slippage overdraft
    _mark(conn, "2024-01-14", 9500.0)


def test_invariants_ok_on_healthy_book_with_known_overdraft(
    conn: sqlite3.Connection,
) -> None:
    _healthy_book(conn)
    result = book_invariants(conn)
    assert result.status == "OK"
    assert "cash=-5.00" in result.detail  # the quirk must NOT trip the meter


def test_invariants_red_on_negative_shares(conn: sqlite3.Connection) -> None:
    _install_bars(conn, ["2024-01-14"])
    _state(conn, "2024-01-14", shares=-1.0)
    _mark(conn, "2024-01-14", 9500.0)
    result = book_invariants(conn)
    assert result.status == "RED"
    assert "long-only" in result.detail


def test_invariants_red_on_missing_equity_mark(conn: sqlite3.Connection) -> None:
    _install_bars(conn, ["2024-01-14"])
    _state(conn, "2024-01-14")  # no _mark for the cursor bar
    result = book_invariants(conn)
    assert result.status == "RED"
    assert "no equity mark" in result.detail


def test_invariants_red_on_stale_pending_order(conn: sqlite3.Connection) -> None:
    _healthy_book(conn)
    _order(conn, "2024-01-13", "pending")  # a NEWER clean bar (01-14) exists
    result = book_invariants(conn)
    assert result.status == "RED"
    assert "pending order" in result.detail


def test_invariants_red_on_cash_below_floor(conn: sqlite3.Connection) -> None:
    _install_bars(conn, ["2024-01-14"])
    _state(conn, "2024-01-14", cash=-30.0)  # far beyond the ~-5 overdraft
    _mark(conn, "2024-01-14", 9500.0)
    result = book_invariants(conn)
    assert result.status == "RED"
    assert "below floor" in result.detail


def test_invariants_red_when_book_missing(conn: sqlite3.Connection) -> None:
    assert book_invariants(conn).status == "RED"


# ------------------------------------------------------------ quarantine_growth


def test_quarantine_ok_when_nothing_rejected_today(conn: sqlite3.Connection) -> None:
    _quarantine_rows(conn, 5, "2024-01-10")  # old rows never count
    assert quarantine_growth(conn, TODAY).status == "OK"


def test_quarantine_ignores_rebuild_bookkeeping_rows(
    conn: sqlite3.Connection,
) -> None:
    # A routine CLEAN rebuild archives thousands of rows with this reason; they
    # are bookkeeping, not rejections, and must never trip the meter (the live
    # false-RED this fix descends from: 2,899 rows archived by the 2026-07-28
    # rebuild, caught by the doctored-copy proof on 2026-08-06).
    conn.executemany(
        "INSERT INTO quarantine (domain, ticker, event_time, payload, reason, "
        "knowable_time) VALUES ('price', ?, NULL, '{}', 'superseded_by_rebuild', ?)",
        [(TICKER, f"{TODAY}T09:00:{i % 60:02d}Z") for i in range(2899)],
    )
    assert quarantine_growth(conn, TODAY).status == "OK"


def test_quarantine_warn_on_a_hiccup(conn: sqlite3.Connection) -> None:
    _quarantine_rows(conn, 3, TODAY)
    assert quarantine_growth(conn, TODAY).status == "WARN"


def test_quarantine_red_on_mass_rejection(conn: sqlite3.Connection) -> None:
    _quarantine_rows(conn, 25, TODAY)
    result = quarantine_growth(conn, TODAY)
    assert result.status == "RED"
    assert "25 row(s)" in result.detail


# ------------------------------------------------------------ backup_status


def test_backup_ok_when_verified_off_laptop() -> None:
    assert backup_status(_report()).status == "OK"


def test_backup_warn_when_local_only() -> None:
    result = backup_status(_report(local_only=True))
    assert result.status == "WARN"
    assert "LOCAL-ONLY" in result.detail


def test_backup_red_when_verify_failed_or_absent() -> None:
    assert backup_status(None).status == "RED"
    assert backup_status(_report(verified=False)).status == "RED"


# ------------------------------------------------------------ run_all


def test_run_all_healthy_book_local_only_backup_is_warn(
    conn: sqlite3.Connection,
) -> None:
    _healthy_book(conn)
    results, overall = run_all(conn, _report(local_only=True), TODAY)
    assert [r.name for r in results] == [
        "data_freshness",
        "drawdown",
        "book_invariants",
        "quarantine_growth",
        "backup_status",
    ]
    assert overall == "WARN"  # everything OK except the honest local-only backup


def test_run_all_one_red_meter_makes_overall_red(conn: sqlite3.Connection) -> None:
    _healthy_book(conn)
    _quarantine_rows(conn, 25, TODAY)
    results, overall = run_all(conn, _report(), TODAY)
    assert overall == "RED"
    by_name = {r.name: r.status for r in results}
    assert by_name["quarantine_growth"] == "RED"
    assert by_name["drawdown"] == "OK"  # a RED never contaminates its neighbours
