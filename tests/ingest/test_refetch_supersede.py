"""Deterministic, fully-OFFLINE tests for the trailing re-fetch-and-supersede policy.

The scar being fixed: an ingest run mid-session captures a PARTIAL bar; the
idempotent write then skips every later re-fetch of that bar, freezing the
snapshot values forever. The policy: every ingest re-fetches a trailing window,
and a stored bar whose re-fetched values DIFFER is superseded -- old row archived
to quarantine (never deleted), fresh row written, atomically.

fetch_daily is mocked (no network); ``now`` is pinned for determinism.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from data_store import store
from data_store.store import PriceRaw
from ingest import front_door, yfinance_source
from ingest.front_door import QuarantineReason
from ingest.yfinance_source import DailyBar
from reconcile import clean_prices, corporate_actions

_FIXED_NOW = "2026-06-16T00:00:00Z"


def _bar(
    event_time: str,
    *,
    op: float = 100.0,
    hi: float = 105.0,
    lo: float = 95.0,
    cl: float = 100.0,
    vol: float = 1_000_000.0,
    ticker: str = "NVDA",
) -> DailyBar:
    return DailyBar(
        ticker=ticker,
        event_time=event_time,
        open=op,
        high=hi,
        low=lo,
        close=cl,
        volume=vol,
    )


def _seed_batch() -> list[DailyBar]:
    """Three valid bars; the 06-03 close (101.0) plays the 'partial snapshot'."""
    return [
        _bar("2026-06-01T00:00:00Z", cl=100.0),
        _bar("2026-06-02T00:00:00Z", cl=102.0),
        _bar("2026-06-03T00:00:00Z", cl=101.0, hi=103.0, vol=500_000.0),
    ]


def _official_last_bar() -> DailyBar:
    """The 06-03 bar as the source reports it AFTER the session closed."""
    return _bar("2026-06-03T00:00:00Z", cl=99.0, hi=104.0, lo=94.0, vol=2_000_000.0)


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_network(*args: object, **kwargs: object) -> object:
        raise AssertionError("network access attempted during an offline test")

    monkeypatch.setattr("ingest.yfinance_source.yf.download", _no_network)


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return tmp_path / "refetch.db"


def _install_fetch(
    monkeypatch: pytest.MonkeyPatch, batch: list[DailyBar]
) -> list[tuple[str, str | None, str | None]]:
    """Mock fetch_daily with ``batch``; pin now; return the recorded calls."""
    calls: list[tuple[str, str | None, str | None]] = []

    def _fake_fetch(
        ticker: str, start: str | None = None, end: str | None = None
    ) -> list[DailyBar]:
        calls.append((ticker, start, end))
        return list(batch)

    monkeypatch.setattr(yfinance_source, "fetch_daily", _fake_fetch)
    monkeypatch.setattr(front_door, "now_utc_iso", lambda: _FIXED_NOW)
    return calls


def _raw_row(db: Path, event_time: str) -> tuple[float, float, float, float, int]:
    conn = store.connect(db)
    try:
        row = conn.execute(
            "SELECT open, high, low, close, volume FROM price_raw "
            "WHERE ticker = 'NVDA' AND event_time = ?",
            (event_time,),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    return (float(row[0]), float(row[1]), float(row[2]), float(row[3]), int(row[4]))


def _quarantine_rows(db: Path) -> list[tuple[str, str, str, str]]:
    conn = store.connect(db)
    try:
        return [
            (str(r[0]), str(r[1]), str(r[2]), str(r[3]))
            for r in conn.execute(
                "SELECT domain, event_time, reason, payload FROM quarantine"
            ).fetchall()
        ]
    finally:
        conn.close()


def test_identical_refetch_skips_and_supersedes_nothing(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fetch(monkeypatch, _seed_batch())
    front_door.ingest(["NVDA"], db)
    quarantine_before = _quarantine_rows(db)

    second = front_door.ingest(["NVDA"], db)  # identical values re-fetched

    assert second.rows_superseded == 0
    assert second.rows_skipped_duplicate == 3
    assert second.rows_written == 0
    assert _quarantine_rows(db) == quarantine_before  # no supersede archives


def test_differing_refetch_supersedes_and_archives_old_row(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fetch(monkeypatch, _seed_batch())
    front_door.ingest(["NVDA"], db)

    # The source now reports the OFFICIAL 06-03 session (close 101 -> 99 etc.).
    batch = _seed_batch()[:2] + [_official_last_bar()]
    _install_fetch(monkeypatch, batch)
    summary = front_door.ingest(["NVDA"], db)

    assert summary.rows_superseded == 1
    assert summary.rows_skipped_duplicate == 2  # the two unchanged bars
    assert summary.rows_written == 0
    # The invariant still reconciles with the new column in play.
    assert summary.rows_valid == (
        summary.rows_written + summary.rows_skipped_duplicate + summary.rows_superseded
    )

    # price_raw now carries the official values...
    assert _raw_row(db, "2026-06-03T00:00:00Z") == (100.0, 104.0, 94.0, 99.0, 2_000_000)
    # ...and the old snapshot is preserved verbatim in quarantine.
    superseded = [
        row for row in _quarantine_rows(db) if row[2] == "superseded_by_refetch"
    ]
    assert len(superseded) == 1
    domain, event_time, _reason, payload = superseded[0]
    assert domain == "price_raw"
    assert event_time == "2026-06-03T00:00:00Z"
    old = json.loads(payload)
    assert old["close"] == 101.0  # the frozen snapshot, kept for audit
    assert old["volume"] == 500_000


def test_replace_price_raw_is_all_or_nothing(db: Path) -> None:
    # Atomicity proxy: a batch with one malformed row must change NOTHING --
    # the stored bar is never deleted without its replacement landing, so a
    # reader can never catch the store with the bar absent.
    store.init_db(db)
    conn = store.connect(db)
    try:
        good = PriceRaw(
            ticker="NVDA",
            event_time="2026-06-03T00:00:00Z",
            open=100.0,
            high=105.0,
            low=95.0,
            close=101.0,
            volume=500_000,
            knowable_time=_FIXED_NOW,
            source="yfinance",
        )
        store.write_price_raw(conn, [good])

        fresh_ok = PriceRaw(
            ticker="NVDA",
            event_time="2026-06-03T00:00:00Z",
            open=100.0,
            high=104.0,
            low=94.0,
            close=99.0,
            volume=2_000_000,
            knowable_time=_FIXED_NOW,
            source="yfinance",
        )
        fresh_bad = PriceRaw(
            ticker="NVDA",
            event_time="not-a-timestamp",  # malformed: rejected by validation
            open=1.0,
            high=1.0,
            low=1.0,
            close=1.0,
            volume=1,
            knowable_time=_FIXED_NOW,
            source="yfinance",
        )
        with pytest.raises(ValueError):
            store.replace_price_raw(conn, [fresh_ok, fresh_bad], _FIXED_NOW)

        # The whole batch rolled back: old values intact, no archive rows.
        row = conn.execute(
            "SELECT close, volume FROM price_raw WHERE event_time = ?",
            ("2026-06-03T00:00:00Z",),
        ).fetchone()
        assert (float(row[0]), int(row[1])) == (101.0, 500_000)
        n_quarantine = conn.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0]
        assert n_quarantine == 0
    finally:
        conn.close()


def test_trailing_window_sets_fetch_start(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _install_fetch(monkeypatch, _seed_batch())
    front_door.ingest(["NVDA"], db)  # first-ever ingest: start passes through
    assert calls[0] == ("NVDA", None, None)

    # With stored history (latest bar 2026-06-03) and NO --start, the fetch
    # reaches back exactly 7 calendar days from the latest stored bar.
    front_door.ingest(["NVDA"], db)
    assert calls[1] == ("NVDA", "2026-05-27", None)

    # An explicit EARLIER start wins (backfill requests are honoured)...
    front_door.ingest(["NVDA"], db, start="2015-01-01")
    assert calls[2] == ("NVDA", "2015-01-01", None)
    # ...but a LATER start is widened to the refresh window (never narrower).
    front_door.ingest(["NVDA"], db, start="2026-06-02")
    assert calls[3] == ("NVDA", "2026-05-27", None)


def test_invalid_differing_refetch_quarantines_and_keeps_stored_row(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fetch(monkeypatch, _seed_batch())
    front_door.ingest(["NVDA"], db)

    # Re-fetch delivers a DIFFERENT but INSANE 06-03 bar (NaN close). It must be
    # quarantined as bad data and must NOT supersede the stored row.
    bad_last = _bar("2026-06-03T00:00:00Z", cl=float("nan"))
    _install_fetch(monkeypatch, _seed_batch()[:2] + [bad_last])
    summary = front_door.ingest(["NVDA"], db)

    assert summary.rows_superseded == 0
    assert summary.rows_quarantined == 1
    assert _raw_row(db, "2026-06-03T00:00:00Z") == (100.0, 103.0, 95.0, 101.0, 500_000)
    reasons = {row[2] for row in _quarantine_rows(db)}
    assert QuarantineReason.NAN_OR_INF_PRICE.value in reasons
    assert "superseded_by_refetch" not in reasons


def test_end_to_end_partial_then_official_reaches_clean(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # THE scar scenario, full pipeline: partial snapshot ingested, official
    # values re-fetched next run, reconcile rebuilds -- CLEAN must carry the
    # official close, and the partial one must survive only as an audit record.
    monkeypatch.setattr(corporate_actions, "fetch_actions", lambda ticker: [])

    _install_fetch(monkeypatch, _seed_batch())  # 06-03 close=101.0 (partial)
    front_door.ingest(["NVDA"], db)
    clean_prices.reconcile(["NVDA"], db)

    _install_fetch(monkeypatch, _seed_batch()[:2] + [_official_last_bar()])
    summary = front_door.ingest(["NVDA"], db)  # 06-03 close=99.0 (official)
    assert summary.rows_superseded == 1
    clean_prices.reconcile(["NVDA"], db)

    conn = store.connect(db)
    try:
        clean_close = conn.execute(
            "SELECT close FROM price_clean "
            "WHERE ticker = 'NVDA' AND event_time = '2026-06-03T00:00:00Z'",
        ).fetchone()
        assert float(clean_close[0]) == 99.0  # CLEAN carries the official close
    finally:
        conn.close()
    # The partial snapshot is still auditable in quarantine.
    payloads = [
        json.loads(row[3])
        for row in _quarantine_rows(db)
        if row[2] == "superseded_by_refetch"
    ]
    assert any(p.get("close") == 101.0 for p in payloads)
