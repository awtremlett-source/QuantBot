"""Deterministic, fully-OFFLINE tests for RAW->CLEAN split-adjusted reconciliation.

yfinance is never called: :func:`reconcile.corporate_actions.fetch_actions` is
mocked with canned actions, and an autouse fixture replaces the underlying
``yf.Ticker`` with a tripwire that raises if any code path reaches it.

``now`` is pinned (monkeypatched) so ``knowable_time`` is deterministic. The
price_raw fixture is seeded directly through the store write API (so we can also
plant a deliberately bad row that the front door would never have admitted).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

import pytest

from data_store import store
from reconcile import clean_prices, corporate_actions
from reconcile.clean_prices import AppliedSplit, QuarantineReason

# Pinned "now" for the run -> the knowable_time stamp on everything written.
_FIXED_NOW = "2024-06-20T00:00:00Z"
_RAW_KNOWABLE = "2024-06-19T00:00:00Z"

# A 10-for-1 split, and a dividend we expect to be PERSISTED but NOT applied
# (dividend adjustment is out of scope for this brick).
_SPLIT_DATE = "2024-06-10T00:00:00Z"
_SPLIT_RATIO = 10.0
_DIV_DATE = "2024-06-05T00:00:00Z"

# Raw bars spanning the split: 4 BEFORE at close ~1000, 4 ON/AFTER at close ~100.
_PRE_SPLIT: list[tuple[str, float]] = [
    ("2024-06-03T00:00:00Z", 1000.0),
    ("2024-06-04T00:00:00Z", 1010.0),
    ("2024-06-05T00:00:00Z", 1020.0),
    ("2024-06-06T00:00:00Z", 1030.0),
]
_POST_SPLIT: list[tuple[str, float]] = [
    ("2024-06-10T00:00:00Z", 104.0),  # on the split date -> factor 1 (not divided)
    ("2024-06-11T00:00:00Z", 105.0),
    ("2024-06-12T00:00:00Z", 106.0),
    ("2024-06-13T00:00:00Z", 107.0),
]
_PRE_VOLUME = 1_000_000
_POST_VOLUME = 5_000_000


def _raw_bar(
    event_time: str,
    close: float,
    volume: int,
    *,
    span: float = 5.0,
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


def _seed_raw(db: Path, extra: Sequence[store.PriceRaw] = ()) -> None:
    """Seed price_raw with the split-spanning fixture (plus any ``extra`` rows)."""
    rows = [_raw_bar(et, close, _PRE_VOLUME) for et, close in _PRE_SPLIT]
    rows += [_raw_bar(et, close, _POST_VOLUME, span=1.0) for et, close in _POST_SPLIT]
    rows += list(extra)
    store.init_db(db)
    conn = store.connect(db)
    try:
        store.write_price_raw(conn, rows)
    finally:
        conn.close()


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


def test_split_adjusts_to_a_continuous_series(
    db: Path, fetch_calls: list[str]
) -> None:
    _seed_raw(db)
    summary = clean_prices.reconcile(["NVDA"], db)

    # Reconciliation counts and the per-run invariant.
    assert summary.requested_tickers == ("NVDA",)
    assert summary.rows_raw == 8
    assert summary.rows_written_clean == 8
    assert summary.rows_quarantined == 0
    assert summary.rows_skipped_duplicate == 0
    assert summary.rows_raw == (
        summary.rows_written_clean
        + summary.rows_skipped_duplicate
        + summary.rows_quarantined
    )

    # Offline proof: our mock was used exactly once; real network never touched.
    assert fetch_calls == ["NVDA"]

    # splits_applied lists exactly the one split (event_time + ratio).
    assert summary.splits_applied == (
        AppliedSplit(event_time=_SPLIT_DATE, ratio=_SPLIT_RATIO),
    )

    conn = store.connect(db)
    try:
        clean = {
            row[0]: (row[1], row[2], row[3])  # event_time -> (close, volume, adj_close)
            for row in conn.execute(
                "SELECT event_time, close, volume, adj_close "
                "FROM price_clean ORDER BY event_time"
            )
        }
        # knowable_time stamped once per run.
        stamps = {
            row[0] for row in conn.execute("SELECT knowable_time FROM price_clean")
        }
        assert stamps == {_FIXED_NOW}
        # Both corporate actions persisted; the dividend is stored, not applied.
        action_types = {
            row[0] for row in conn.execute("SELECT action_type FROM corporate_actions")
        }
        assert action_types == {"split", "dividend"}
        assert conn.execute(
            "SELECT COUNT(*) FROM corporate_actions"
        ).fetchone()[0] == 2
    finally:
        conn.close()

    # Pre-split CLEAN closes are raw/10 (~100); the dividend did NOT shift them.
    assert clean["2024-06-03T00:00:00Z"][0] == pytest.approx(100.0)
    assert clean["2024-06-06T00:00:00Z"][0] == pytest.approx(103.0)
    # Post-split closes are unchanged (~100) -> the series is continuous.
    assert clean["2024-06-10T00:00:00Z"][0] == pytest.approx(104.0)
    assert clean["2024-06-13T00:00:00Z"][0] == pytest.approx(107.0)

    # Split-only: adj_close == close on every row.
    for _event_time, (close, _volume, adj_close) in clean.items():
        assert adj_close == pytest.approx(close)

    # Pre-split adjusted volume = raw_volume * 10; post-split volume unchanged.
    assert clean["2024-06-03T00:00:00Z"][1] == _PRE_VOLUME * 10
    assert clean["2024-06-10T00:00:00Z"][1] == _POST_VOLUME

    # The adjusted series moves only ~1%/day -- nowhere near the ~90% fake drop
    # an UNADJUSTED 1030 -> 104 boundary would show.
    assert summary.max_abs_daily_close_move_pct is not None
    assert summary.max_abs_daily_close_move_pct < 5.0
    assert summary.max_abs_daily_close_move_date is not None


def test_second_identical_run_is_idempotent(
    db: Path, fetch_calls: list[str]
) -> None:
    _seed_raw(db)
    first = clean_prices.reconcile(["NVDA"], db)
    second = clean_prices.reconcile(["NVDA"], db)

    assert first.rows_written_clean == 8
    assert first.rows_skipped_duplicate == 0

    # Re-running writes nothing new; all 8 valid rows report as skipped duplicates.
    assert second.rows_raw == 8
    assert second.rows_written_clean == 0
    assert second.rows_skipped_duplicate == 8
    assert second.rows_quarantined == 0

    conn = store.connect(db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM price_clean").fetchone()[0] == 8
        # corporate_actions write is idempotent too: still 2 rows, not 4.
        assert conn.execute(
            "SELECT COUNT(*) FROM corporate_actions"
        ).fetchone()[0] == 2
    finally:
        conn.close()

    assert fetch_calls == ["NVDA", "NVDA"]


def test_bad_raw_row_is_quarantined_not_written_to_clean(
    db: Path, fetch_calls: list[str]
) -> None:
    # A negative-close row planted straight into price_raw (the front door would
    # have caught it, but the cleaner must defend itself too). It sits before the
    # split, so factor 10 still applies -> adjusted close -0.5, still non-positive.
    bad = _raw_bar("2024-06-07T00:00:00Z", -5.0, _PRE_VOLUME)
    _seed_raw(db, extra=[bad])

    summary = clean_prices.reconcile(["NVDA"], db)

    assert summary.rows_raw == 9
    assert summary.rows_written_clean == 8
    assert summary.rows_quarantined == 1
    assert summary.rows_skipped_duplicate == 0

    conn = store.connect(db)
    try:
        # The bad row is NOT in price_clean.
        in_clean = conn.execute(
            "SELECT COUNT(*) FROM price_clean WHERE event_time = ?",
            ("2024-06-07T00:00:00Z",),
        ).fetchone()[0]
        assert in_clean == 0

        # It IS in quarantine, domain 'price_clean', with the specific reason.
        row = conn.execute(
            "SELECT domain, reason, payload FROM quarantine WHERE event_time = ?",
            ("2024-06-07T00:00:00Z",),
        ).fetchone()
        assert row[0] == "price_clean"
        assert row[1] == QuarantineReason.NON_POSITIVE_PRICE.value
        json.loads(row[2])  # payload is valid JSON
    finally:
        conn.close()


def test_real_fetch_path_makes_no_network_call() -> None:
    # Only the autouse network tripwire is active here (fetch_actions is NOT mocked).
    # The real fetch_actions must fail fast as ActionsFetchError, never reach the net.
    with pytest.raises(corporate_actions.ActionsFetchError) as excinfo:
        corporate_actions.fetch_actions("NVDA")
    assert "network access attempted" in str(excinfo.value)


def test_split_factor_compounds_multiple_splits() -> None:
    # Factor math in isolation: two splits, ratios 2 then 4.
    splits = [
        AppliedSplit(event_time="2024-03-01T00:00:00Z", ratio=2.0),
        AppliedSplit(event_time="2024-09-01T00:00:00Z", ratio=4.0),
    ]
    # A bar before BOTH splits is divided by 2 * 4 = 8.
    assert clean_prices.split_factor("2024-01-01T00:00:00Z", splits) == 8.0
    # Between the two splits: only the later (ratio 4) is strictly after.
    assert clean_prices.split_factor("2024-06-01T00:00:00Z", splits) == 4.0
    # On/after both splits: factor 1.
    assert clean_prices.split_factor("2024-09-01T00:00:00Z", splits) == 1.0
    assert clean_prices.split_factor("2024-12-01T00:00:00Z", splits) == 1.0
