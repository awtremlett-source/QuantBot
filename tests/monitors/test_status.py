"""Tests for on-demand status + drill (observe + governance only).

The drill tests are the point: both doctored copies MUST fire their meter, the
REAL db file must be byte-identical afterwards, the temp copies must be gone,
and every drill line must carry the unmistakable ``DRILL — `` prefix."""

from __future__ import annotations

import glob
import hashlib
import tempfile
from collections.abc import Sequence
from datetime import date, timedelta
from pathlib import Path

import pytest

from data_store import store
from data_store.store import PriceClean
from monitors.status import run_drill, run_status
from tools.installer import RunResult

TICKER = "NVDA"


class FakeRunner:
    def __init__(self, fail_tasks: Sequence[str] = ()) -> None:
        self.calls: list[list[str]] = []
        self._fail = set(fail_tasks)

    def run(self, args: Sequence[str]) -> RunResult:
        call = list(args)
        self.calls.append(call)
        failed = any(task in call for task in self._fail)
        return RunResult(1 if failed else 0, "")


def _bar(day: str) -> PriceClean:
    return PriceClean(
        ticker=TICKER, event_time=f"{day}T00:00:00Z", open=100.0, high=101.0,
        low=99.0, close=100.0, volume=1_000_000, adj_close=100.0,
        knowable_time=f"{day}T01:00:00Z", source="test",
    )


@pytest.fixture
def db(tmp_path: Path) -> Path:
    """A CURRENT store: 40 daily bars ending today, a healthy book."""
    the_db = tmp_path / "status.db"
    store.init_db(the_db)
    conn = store.connect(the_db)
    try:
        today = date.today()
        days = [(today - timedelta(days=i)).isoformat() for i in range(40)]
        store.write_price_clean(conn, [_bar(d) for d in sorted(days)])
        conn.execute(
            "INSERT INTO paper_state (ticker, shares, cash, "
            "last_decided_event_time) VALUES (?, 0.0, 10000.0, ?)",
            (TICKER, f"{sorted(days)[-1]}T00:00:00Z"),
        )
        conn.executemany(
            "INSERT INTO paper_equity (ticker, event_time, equity, close) "
            "VALUES (?, ?, 10000.0, 100.0)",
            [(TICKER, f"{d}T00:00:00Z") for d in sorted(days)[-5:]],
        )
        conn.commit()
    finally:
        conn.close()
    return the_db


# ------------------------------------------------------------ run_status


def test_status_aggregation_healthy_book_warn_config(
    db: Path, tmp_path: Path
) -> None:
    results, overall = run_status(
        db, runner=FakeRunner(), env={}, root=tmp_path
    )
    by_name = {r.name: r.status for r in results}
    assert by_name["data_freshness"] == "OK"
    assert by_name["drawdown"] == "OK"
    assert by_name["book_invariants"] == "OK"
    assert by_name["quarantine_growth"] == "OK"
    assert by_name["telegram"] == "WARN"  # unconfigured
    assert by_name["backup_destination"] == "WARN"  # env unset
    assert by_name["killswitch"] == "OK"
    assert by_name["task_QuantBot-Daily"] == "OK"
    assert overall == "WARN"


def test_status_missing_daily_task_is_red(db: Path, tmp_path: Path) -> None:
    results, overall = run_status(
        db, runner=FakeRunner(fail_tasks=["QuantBot-Daily"]),
        env={}, root=tmp_path,
    )
    assert overall == "RED"
    by_name = {r.name: r.status for r in results}
    assert by_name["task_QuantBot-Daily"] == "RED"


def test_status_armed_killswitch_warns(db: Path, tmp_path: Path) -> None:
    (tmp_path / "STOP_NEW_TRADES").write_text("armed\n")
    results, _ = run_status(db, runner=FakeRunner(), env={}, root=tmp_path)
    by_name = {r.name: r.status for r in results}
    assert by_name["killswitch"] == "WARN"


def test_status_never_writes(db: Path, tmp_path: Path) -> None:
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    run_status(db, runner=FakeRunner(), env={}, root=tmp_path)
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before


# ------------------------------------------------------------ run_drill


def test_drill_fires_both_meters_and_leaves_no_trace(db: Path) -> None:
    before = hashlib.sha256(db.read_bytes()).hexdigest()

    drill = run_drill(db)

    # Both target meters went RED on the doctored copies...
    assert drill.passed is True
    text = "\n".join(drill.lines)
    assert "data_freshness: RED" in text
    assert "drawdown: RED" in text
    assert "LIGHTS WORK" in text
    # ...every line is unmistakably a drill...
    assert all(line.startswith("DRILL — ") for line in drill.lines)
    # ...the REAL db is byte-identical...
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    # ...and the temp copies are gone.
    leftovers = glob.glob(str(Path(tempfile.gettempdir()) / "quantbot-drill-*"))
    assert leftovers == []


def test_drill_reports_failure_if_a_meter_cannot_fire(
    db: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Break the drawdown meter (pretend it always says OK): the drill MUST
    # come back failed -- a drill that cannot fail is decoration.
    from monitors import status as status_mod
    from monitors.meters import MeterResult

    monkeypatch.setattr(
        status_mod, "drawdown",
        lambda conn, ticker="NVDA": MeterResult("drawdown", "OK", "stubbed"),
    )
    drill = run_drill(db)
    assert drill.passed is False
    assert any("DRILL FAILED" in line for line in drill.lines)
