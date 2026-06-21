"""Deterministic, fully-OFFLINE tests for RAW->CLEAN verify-and-copy reconciliation.

yfinance OHLC are already split-adjusted, so reconcile VERIFIES continuity across
splits and COPIES raw->clean (it must NOT re-divide). yfinance is never called:
:func:`reconcile.corporate_actions.fetch_actions` is mocked, and an autouse
fixture replaces the underlying ``yf.Ticker`` with a tripwire that raises if any
code path reaches it.

The price_raw fixture is seeded directly through the store write API so we can
plant rows the front door would never have admitted (a bad row; an UNADJUSTED
cliff at a split).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

import pytest

from data_store import store
from reconcile import clean_prices, corporate_actions
from reconcile.clean_prices import QuarantineReason, UnadjustedSplitError

# Pinned "now" for the run -> the knowable_time stamp on everything written.
_FIXED_NOW = "2024-06-20T00:00:00Z"
_RAW_KNOWABLE = "2024-06-19T00:00:00Z"

_SPLIT_DATE = "2024-06-10T00:00:00Z"
_SPLIT_RATIO = 10.0
_DIV_DATE = "2024-06-05T00:00:00Z"

# Raw bars as an ALREADY split-adjusted source delivers them: a continuous
# ~100-level series straight across the split date (NOT a 1000 -> 100 cliff).
_ADJUSTED_RAW: list[tuple[str, float]] = [
    ("2024-06-05T00:00:00Z", 99.0),
    ("2024-06-06T00:00:00Z", 100.0),
    ("2024-06-07T00:00:00Z", 101.0),  # last bar before the split
    ("2024-06-10T00:00:00Z", 100.0),  # split date
    ("2024-06-11T00:00:00Z", 101.0),
    ("2024-06-12T00:00:00Z", 102.0),
]
_VOLUME = 1_000_000


def _raw_bar(
    event_time: str,
    close: float,
    volume: int = _VOLUME,
    *,
    span: float = 2.0,
    ticker: str = "NVDA",
) -> store.PriceRaw:
    """A consistent OHLCV raw bar centred on ``close`` (open=close, high/low +/-span)."""
    return store.PriceRaw(
        ticker=ticker,
        event_time=event_time,
        open=close,
        high=close + span,
        low=close - span,
        close=close,
        volume=volume,
        knowable_time=_RAW_KNOWABLE,
        source="yfinance",
    )


def _seed_raw(db: Path, bars: Sequence[store.PriceRaw]) -> None:
    """Seed price_raw with ``bars`` through the real store write API."""
    store.init_db(db)
    conn = store.connect(db)
    try:
        store.write_price_raw(conn, list(bars))
    finally:
        conn.close()


def _adjusted_bars(extra: Sequence[store.PriceRaw] = ()) -> list[store.PriceRaw]:
    return [_raw_bar(et, close) for et, close in _ADJUSTED_RAW] + list(extra)


def _split_action(ticker: str = "NVDA") -> corporate_actions.ActionRecord:
    return corporate_actions.ActionRecord(
        ticker=ticker,
        event_time=_SPLIT_DATE,
        action_type=corporate_actions.ACTION_SPLIT,
        value=_SPLIT_RATIO,
        source="yfinance",
    )


def _dividend_action(ticker: str = "NVDA") -> corporate_actions.ActionRecord:
    return corporate_actions.ActionRecord(
        ticker=ticker,
        event_time=_DIV_DATE,
        action_type=corporate_actions.ACTION_DIVIDEND,
        value=0.5,
        source="yfinance",
    )


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tripwire: any attempt to reach real yfinance fails the test."""

    def _no_network(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("network access attempted during an offline test")

    monkeypatch.setattr("reconcile.corporate_actions.yf.Ticker", _no_network)


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return tmp_path / "reconcile.db"


@pytest.fixture
def fetch_calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Mock fetch_actions (one split + one dividend); record the tickers requested."""
    calls: list[str] = []

    def _fake_fetch(ticker: str) -> list[corporate_actions.ActionRecord]:
        calls.append(ticker)
        return [_split_action(ticker), _dividend_action(ticker)]

    monkeypatch.setattr(corporate_actions, "fetch_actions", _fake_fetch)
    monkeypatch.setattr(clean_prices, "now_utc_iso", lambda: _FIXED_NOW)
    return calls


def test_clean_is_a_verified_copy_of_raw(db: Path, fetch_calls: list[str]) -> None:
    _seed_raw(db, _adjusted_bars())
    summary = clean_prices.reconcile(["NVDA"], db)

    # Counts and the per-run invariant.
    assert summary.requested_tickers == ("NVDA",)
    assert summary.rows_raw == 6
    assert summary.rows_written_clean == 6
    assert summary.rows_quarantined == 0
    assert summary.rows_skipped_duplicate == 0
    assert summary.rows_raw == (
        summary.rows_written_clean
        + summary.rows_skipped_duplicate
        + summary.rows_quarantined
    )

    # Offline proof.
    assert fetch_calls == ["NVDA"]

    # The split passed the continuity check with a small across-boundary move.
    assert len(summary.splits_checked) == 1
    check = summary.splits_checked[0]
    assert check.event_time == _SPLIT_DATE
    assert check.ratio == _SPLIT_RATIO
    assert check.status == "pass"
    assert check.across_split_move_pct is not None
    assert check.across_split_move_pct < 35.0  # 101 -> 100 is ~1%

    # max daily move reflects only the ~1% real moves, NOT a split cliff.
    assert summary.max_abs_daily_close_move_pct is not None
    assert summary.max_abs_daily_close_move_pct < 5.0

    conn = store.connect(db)
    try:
        clean = {
            row[0]: (row[1], row[2], row[3], row[4])
            for row in conn.execute(
                "SELECT event_time, open, high, low, close FROM price_clean"
            )
        }
        adj = {
            row[0]: (row[1], row[2])
            for row in conn.execute(
                "SELECT event_time, close, adj_close FROM price_clean"
            )
        }
        raw = {
            row[0]: (row[1], row[2], row[3], row[4])
            for row in conn.execute(
                "SELECT event_time, open, high, low, close FROM price_raw"
            )
        }
        # corporate actions persisted (split + dividend); dividend not applied.
        assert conn.execute(
            "SELECT COUNT(*) FROM corporate_actions"
        ).fetchone()[0] == 2
    finally:
        conn.close()

    # CLEAN == RAW, bar for bar -- no re-division.
    assert clean == raw
    # Pre-split closes are NOT divided by 10 (would be ~10 if double-adjusted).
    assert clean["2024-06-07T00:00:00Z"][3] == pytest.approx(101.0)
    assert clean["2024-06-10T00:00:00Z"][3] == pytest.approx(100.0)
    # adj_close == close (splits-only; dividends out of scope).
    for _event_time, (close, adj_close) in adj.items():
        assert adj_close == pytest.approx(close)


def test_second_identical_run_is_idempotent(
    db: Path, fetch_calls: list[str]
) -> None:
    _seed_raw(db, _adjusted_bars())
    first = clean_prices.reconcile(["NVDA"], db)
    second = clean_prices.reconcile(["NVDA"], db)

    assert first.rows_written_clean == 6
    assert first.rows_skipped_duplicate == 0

    # Unchanged re-run writes nothing new and reports all rows as skipped.
    assert second.rows_raw == 6
    assert second.rows_written_clean == 0
    assert second.rows_skipped_duplicate == 6
    assert second.rows_quarantined == 0

    conn = store.connect(db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM price_clean").fetchone()[0] == 6
        # No churn: an unchanged re-run does NOT archive anything to quarantine.
        assert conn.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0] == 0
        # corporate_actions write is idempotent too.
        assert conn.execute(
            "SELECT COUNT(*) FROM corporate_actions"
        ).fetchone()[0] == 2
    finally:
        conn.close()

    assert fetch_calls == ["NVDA", "NVDA"]


def test_unadjusted_split_is_flagged_and_raises(
    db: Path, fetch_calls: list[str]
) -> None:
    # Raw data that still has the ~10x cliff (source did NOT pre-adjust).
    cliff = [
        _raw_bar("2024-06-06T00:00:00Z", 1010.0, span=10.0),
        _raw_bar("2024-06-07T00:00:00Z", 1000.0, span=10.0),  # before the split
        _raw_bar("2024-06-10T00:00:00Z", 100.0),  # on the split -> 10x cliff
        _raw_bar("2024-06-11T00:00:00Z", 101.0),
    ]
    _seed_raw(db, cliff)

    with pytest.raises(UnadjustedSplitError) as excinfo:
        clean_prices.reconcile(["NVDA"], db)
    assert "did not pre-adjust" in str(excinfo.value)

    conn = store.connect(db)
    try:
        # No CLEAN written for the ticker -- we refused to publish.
        assert conn.execute("SELECT COUNT(*) FROM price_clean").fetchone()[0] == 0
        # Exactly the two boundary rows quarantined, with the specific reason.
        boundary = {
            row[0]: row[1]
            for row in conn.execute("SELECT event_time, reason FROM quarantine")
        }
        assert boundary == {
            "2024-06-07T00:00:00Z": QuarantineReason.UNADJUSTED_SPLIT_SUSPECTED.value,
            "2024-06-10T00:00:00Z": QuarantineReason.UNADJUSTED_SPLIT_SUSPECTED.value,
        }
        # price_raw is untouched (system of record).
        assert conn.execute("SELECT COUNT(*) FROM price_raw").fetchone()[0] == 4
    finally:
        conn.close()


def test_bad_raw_row_is_quarantined_not_written_to_clean(
    db: Path, fetch_calls: list[str]
) -> None:
    # A negative-close row planted straight into price_raw, placed AWAY from the
    # split boundary so it does not perturb the continuity check (which uses the
    # last raw close before the split date).
    bad = _raw_bar("2024-06-04T00:00:00Z", -5.0)
    _seed_raw(db, _adjusted_bars(extra=[bad]))

    summary = clean_prices.reconcile(["NVDA"], db)

    assert summary.rows_raw == 7
    assert summary.rows_written_clean == 6
    assert summary.rows_quarantined == 1
    assert summary.rows_skipped_duplicate == 0

    conn = store.connect(db)
    try:
        in_clean = conn.execute(
            "SELECT COUNT(*) FROM price_clean WHERE event_time = ?",
            ("2024-06-04T00:00:00Z",),
        ).fetchone()[0]
        assert in_clean == 0

        row = conn.execute(
            "SELECT domain, reason, payload FROM quarantine WHERE event_time = ?",
            ("2024-06-04T00:00:00Z",),
        ).fetchone()
        assert row[0] == "price_clean"
        assert row[1] == QuarantineReason.NON_POSITIVE_PRICE.value
        json.loads(row[2])  # payload is valid JSON
    finally:
        conn.close()


def test_rebuild_replaces_changed_clean_rows_and_archives_old(
    db: Path, fetch_calls: list[str]
) -> None:
    # Pre-populate price_clean with WRONG values (simulating the old double-adjusted
    # rows), then reconcile and confirm they are replaced and archived.
    _seed_raw(db, _adjusted_bars())
    store.init_db(db)
    conn = store.connect(db)
    try:
        wrong = [
            store.PriceClean(
                ticker="NVDA",
                event_time=et,
                open=close / 10,
                high=close / 10,
                low=close / 10,
                close=close / 10,  # the old ÷10 bug
                volume=_VOLUME,
                adj_close=close / 10,
                knowable_time=_RAW_KNOWABLE,
                source="yfinance",
            )
            for et, close in _ADJUSTED_RAW
        ]
        store.write_price_clean(conn, wrong)
    finally:
        conn.close()

    summary = clean_prices.reconcile(["NVDA"], db)

    # All six rows are rebuilt (the wrong data differed from the fresh copy).
    assert summary.rows_written_clean == 6
    assert summary.rows_skipped_duplicate == 0

    conn = store.connect(db)
    try:
        # CLEAN now holds the correct (un-divided) closes.
        close_07 = conn.execute(
            "SELECT close FROM price_clean WHERE event_time = ?",
            ("2024-06-07T00:00:00Z",),
        ).fetchone()[0]
        assert close_07 == pytest.approx(101.0)
        assert conn.execute("SELECT COUNT(*) FROM price_clean").fetchone()[0] == 6

        # The six wrong rows were archived (quarantine-never-delete), not dropped.
        n_superseded = conn.execute(
            "SELECT COUNT(*) FROM quarantine WHERE reason = ?",
            (QuarantineReason.SUPERSEDED_BY_REBUILD.value,),
        ).fetchone()[0]
        assert n_superseded == 6
    finally:
        conn.close()


def test_real_fetch_path_makes_no_network_call() -> None:
    # Only the autouse network tripwire is active (fetch_actions is NOT mocked).
    with pytest.raises(corporate_actions.ActionsFetchError) as excinfo:
        corporate_actions.fetch_actions("NVDA")
    assert "network access attempted" in str(excinfo.value)
