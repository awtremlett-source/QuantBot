"""Deterministic, fully-OFFLINE tests for the front-door ingest.

yfinance is never called: :func:`ingest.yfinance_source.fetch_daily` is mocked
with a canned batch, and an autouse fixture replaces the underlying
``yf.download`` with a tripwire that raises if any code path reaches it.

``now`` is pinned (monkeypatched) so the future-bar check is deterministic
regardless of the wall clock.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import NoReturn

import pandas as pd
import pytest

from data_store import store
from ingest import front_door, yfinance_source
from ingest.front_door import QuarantineReason
from ingest.yfinance_source import DailyBar

# Pinned "now" for the run. June 2026 bars are in the past; the 2099 bar is the
# future bar. (Canonical UTC ISO sorts chronologically as plain text.)
_FIXED_NOW = "2026-06-16T00:00:00Z"

# Expected partition of the canned batch.
_VALID_EVENT_TIMES = [
    "2026-06-01T00:00:00Z",
    "2026-06-02T00:00:00Z",
    "2026-06-03T00:00:00Z",
]
_EXPECTED_QUARANTINE = {
    "2026-06-04T00:00:00Z": QuarantineReason.SUSPECT_JUMP.value,  # +98% vs prev
    "2026-06-10T00:00:00Z": QuarantineReason.NAN_OR_INF_PRICE.value,  # close=NaN
    "2026-06-11T00:00:00Z": QuarantineReason.NON_POSITIVE_PRICE.value,  # close<0
    "2026-06-12T00:00:00Z": QuarantineReason.OHLC_INCONSISTENT.value,  # high<open
    "2026-06-13T00:00:00Z": QuarantineReason.BAD_VOLUME.value,  # volume<0
    "2099-01-01T00:00:00Z": QuarantineReason.FUTURE_BAR.value,  # after `now`
}


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


def _canned_batch() -> list[DailyBar]:
    """3 valid bars + one of each rejection class (6 bad). Returned fresh each call."""
    return [
        # --- valid (small moves, consistent OHLC) ---
        _bar("2026-06-01T00:00:00Z", cl=100.0),
        _bar("2026-06-02T00:00:00Z", cl=102.0),
        _bar("2026-06-03T00:00:00Z", cl=101.0),
        # --- >50% jump vs previous valid close (101 -> 200) ---
        _bar("2026-06-04T00:00:00Z", op=200.0, hi=205.0, lo=195.0, cl=200.0),
        # --- NaN price ---
        _bar("2026-06-10T00:00:00Z", cl=float("nan")),
        # --- non-positive price ---
        _bar("2026-06-11T00:00:00Z", cl=-5.0, lo=-10.0),
        # --- OHLC-inconsistent: max(open,close)=100 > high=90 ---
        _bar("2026-06-12T00:00:00Z", op=100.0, hi=90.0, lo=80.0, cl=85.0),
        # --- negative volume ---
        _bar("2026-06-13T00:00:00Z", vol=-100.0),
        # --- future-dated bar (after pinned `now`) ---
        _bar("2099-01-01T00:00:00Z"),
    ]


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tripwire: any attempt to reach real yfinance.download fails the test."""

    def _no_network(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("network access attempted during an offline test")

    # String-target form: resolves the dotted path at runtime, so the test does
    # not depend on yfinance_source re-exporting its `yf` import.
    monkeypatch.setattr("ingest.yfinance_source.yf.download", _no_network)


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return tmp_path / "ingest.db"


def _install_fetch(
    monkeypatch: pytest.MonkeyPatch,
    batch: list[DailyBar],
    now: str = _FIXED_NOW,
) -> None:
    """Make fetch_daily return ``batch`` and pin ``now`` (for the future check)."""

    def _fake_fetch(
        ticker: str, start: str | None = None, end: str | None = None
    ) -> list[DailyBar]:
        return list(batch)

    monkeypatch.setattr(yfinance_source, "fetch_daily", _fake_fetch)
    monkeypatch.setattr(front_door, "now_utc_iso", lambda: now)


@pytest.fixture
def fetch_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, str | None, str | None]]:
    """Mock fetch_daily with the canned batch; record (ticker, start, end) calls."""
    calls: list[tuple[str, str | None, str | None]] = []

    def _fake_fetch(
        ticker: str, start: str | None = None, end: str | None = None
    ) -> list[DailyBar]:
        calls.append((ticker, start, end))
        return _canned_batch()

    monkeypatch.setattr(yfinance_source, "fetch_daily", _fake_fetch)
    monkeypatch.setattr(front_door, "now_utc_iso", lambda: _FIXED_NOW)
    return calls


def test_ingest_routes_valid_and_quarantines_bad(
    db: Path, fetch_calls: list[tuple[str, str | None, str | None]]
) -> None:
    summary = front_door.ingest(["NVDA"], db)

    # Exact reconciliation counts for the canned batch.
    assert summary.requested_tickers == ("NVDA",)
    assert summary.failed_tickers == ()
    assert summary.rows_fetched == 9
    assert summary.rows_valid == 3
    assert summary.rows_quarantined == 6
    assert summary.rows_written == 3
    assert summary.rows_skipped_duplicate == 0
    # The two reconciliation invariants must hold.
    assert summary.rows_fetched == summary.rows_valid + summary.rows_quarantined
    assert summary.rows_valid == summary.rows_written + summary.rows_skipped_duplicate

    # Offline proof: our mock was used exactly once; real network never touched.
    assert fetch_calls == [("NVDA", None, None)]

    conn = store.connect(db)
    try:
        price = conn.execute(
            "SELECT event_time, source FROM price_raw ORDER BY event_time"
        ).fetchall()
        assert [row[0] for row in price] == _VALID_EVENT_TIMES
        assert {row[1] for row in price} == {"yfinance"}

        quarantined = conn.execute(
            "SELECT event_time, reason, domain, payload FROM quarantine"
        ).fetchall()
        # Exactly six rows persisted (pinned independently of the summary count).
        assert len(quarantined) == 6
        # Each bad bar landed in quarantine with the correct, specific reason.
        assert {row[0]: row[1] for row in quarantined} == _EXPECTED_QUARANTINE
        assert {row[2] for row in quarantined} == {"price"}
        # Every payload is valid JSON (non-finite floats were stringified).
        for row in quarantined:
            json.loads(row[3])

        # knowable_time is stamped ONCE per run: one consistent value across both
        # tables. (Pinned to _FIXED_NOW by the fetch_calls fixture.)
        stamps = {
            row[0]
            for row in conn.execute(
                "SELECT knowable_time FROM price_raw "
                "UNION SELECT knowable_time FROM quarantine"
            )
        }
        assert stamps == {_FIXED_NOW}
    finally:
        conn.close()


def test_second_identical_run_is_idempotent(
    db: Path, fetch_calls: list[tuple[str, str | None, str | None]]
) -> None:
    first = front_door.ingest(["NVDA"], db)
    second = front_door.ingest(["NVDA"], db)

    assert first.rows_written == 3
    assert first.rows_skipped_duplicate == 0

    # Re-running the identical batch writes nothing new; all valid rows are
    # reported as skipped duplicates.
    assert second.rows_fetched == 9
    assert second.rows_valid == 3
    assert second.rows_written == 0
    assert second.rows_skipped_duplicate == 3

    conn = store.connect(db)
    try:
        n_price = conn.execute("SELECT COUNT(*) FROM price_raw").fetchone()[0]
        assert n_price == 3  # still only the 3 valid bars -- no duplicates

        # Quarantine is an append-only audit log (by design): each run re-appends
        # its 6 rejects, so two runs leave 12 rows. This locks in the deliberate
        # asymmetry (price_raw idempotent, quarantine append-only).
        n_quar = conn.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0]
        assert n_quar == 12
    finally:
        conn.close()

    # Mock used once per run; never the real network.
    assert fetch_calls == [("NVDA", None, None), ("NVDA", None, None)]


def test_fetch_failure_is_recorded_and_does_not_abort(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _fake_fetch(
        ticker: str, start: str | None = None, end: str | None = None
    ) -> list[DailyBar]:
        if ticker == "BAD":
            raise yfinance_source.FetchError("simulated fetch failure")
        return _canned_batch()

    monkeypatch.setattr(yfinance_source, "fetch_daily", _fake_fetch)
    monkeypatch.setattr(front_door, "now_utc_iso", lambda: _FIXED_NOW)

    summary = front_door.ingest(["BAD", "NVDA"], db)

    assert summary.requested_tickers == ("BAD", "NVDA")
    assert summary.failed_tickers == ("BAD",)  # logged + recorded, not raised
    assert summary.rows_fetched == 9  # only NVDA contributed
    assert summary.rows_valid == 3
    assert summary.rows_written == 3


def test_real_fetch_path_makes_no_network_call() -> None:
    # Only the autouse network tripwire is active here (fetch_daily is NOT mocked).
    # The real fetch_daily must fail fast instead of reaching the network.
    with pytest.raises(yfinance_source.FetchError) as excinfo:
        yfinance_source.fetch_daily("NVDA")
    assert "network access attempted" in str(excinfo.value)


def test_empty_fetch_result_raises_fetcherror(monkeypatch: pytest.MonkeyPatch) -> None:
    # An empty frame must become a loud FetchError, never a silent empty list.
    def _empty_download(*args: object, **kwargs: object) -> pd.DataFrame:
        return pd.DataFrame()

    monkeypatch.setattr("ingest.yfinance_source.yf.download", _empty_download)
    with pytest.raises(yfinance_source.FetchError) as excinfo:
        yfinance_source.fetch_daily("NVDA")
    assert "no rows" in str(excinfo.value)


def test_inf_price_and_nan_volume_are_quarantined(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Exercises the second trigger of NAN_OR_INF_PRICE (inf, not NaN) and of
    # BAD_VOLUME (NaN volume, not negative) -- branches the canned batch misses.
    batch = [
        _bar("2026-06-01T00:00:00Z", hi=float("inf")),
        _bar("2026-06-02T00:00:00Z", vol=float("nan")),
    ]
    _install_fetch(monkeypatch, batch)

    summary = front_door.ingest(["NVDA"], db)
    assert summary.rows_valid == 0
    assert summary.rows_quarantined == 2

    conn = store.connect(db)
    try:
        reasons = {
            row[0]: row[1]
            for row in conn.execute("SELECT event_time, reason FROM quarantine")
        }
        assert reasons == {
            "2026-06-01T00:00:00Z": QuarantineReason.NAN_OR_INF_PRICE.value,
            "2026-06-02T00:00:00Z": QuarantineReason.BAD_VOLUME.value,
        }
    finally:
        conn.close()


def test_ohlc_low_above_min_is_quarantined(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Isolates the FIRST OHLC sub-clause: low > min(open, close). The canned batch
    # only trips the middle clause (max(open,close) > high).
    batch = [_bar("2026-06-01T00:00:00Z", op=100.0, cl=100.0, lo=110.0, hi=120.0)]
    _install_fetch(monkeypatch, batch)

    summary = front_door.ingest(["NVDA"], db)
    assert summary.rows_valid == 0
    assert summary.rows_quarantined == 1

    conn = store.connect(db)
    try:
        reason = conn.execute("SELECT reason FROM quarantine").fetchone()
        assert reason[0] == QuarantineReason.OHLC_INCONSISTENT.value
    finally:
        conn.close()


def test_future_bar_check_uses_pinned_now(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Pin `now` BETWEEN two otherwise-valid bars: the later bar is then in the
    # future and must be quarantined. This proves the pin is load-bearing -- with
    # the real wall clock both 2026-06 bars would be in the past.
    batch = [
        _bar("2026-06-01T00:00:00Z", cl=100.0),
        _bar("2026-06-03T00:00:00Z", cl=101.0),
    ]
    _install_fetch(monkeypatch, batch, now="2026-06-02T00:00:00Z")

    summary = front_door.ingest(["NVDA"], db)
    assert summary.rows_valid == 1
    assert summary.rows_quarantined == 1

    conn = store.connect(db)
    try:
        row = conn.execute("SELECT event_time, reason FROM quarantine").fetchone()
        assert row == ("2026-06-03T00:00:00Z", QuarantineReason.FUTURE_BAR.value)
    finally:
        conn.close()


def test_suspect_jump_measured_against_previous_valid_close(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A quarantined bar sits between the baseline and the jump candidate. The jump
    # must be measured against the last VALID close (100), not the bad bar -- if
    # the code compared against the previous in-batch bar (-1), the `prev_close>0`
    # guard would skip the jump check and the 06-03 bar would wrongly pass.
    batch = [
        _bar("2026-06-01T00:00:00Z", cl=100.0),
        _bar("2026-06-02T00:00:00Z", cl=-1.0, lo=-1.0),
        _bar("2026-06-03T00:00:00Z", op=160.0, hi=165.0, lo=155.0, cl=160.0),
    ]
    _install_fetch(monkeypatch, batch)

    summary = front_door.ingest(["NVDA"], db)
    assert summary.rows_valid == 1  # only the 06-01 baseline
    assert summary.rows_quarantined == 2

    conn = store.connect(db)
    try:
        reasons = {
            row[0]: row[1]
            for row in conn.execute("SELECT event_time, reason FROM quarantine")
        }
        assert reasons["2026-06-02T00:00:00Z"] == QuarantineReason.NON_POSITIVE_PRICE.value
        assert reasons["2026-06-03T00:00:00Z"] == QuarantineReason.SUSPECT_JUMP.value
    finally:
        conn.close()


def test_duplicate_session_in_batch_is_quarantined(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Two DIFFERENT valid bars for the same (ticker, event_time). The second must
    # be preserved in quarantine, NOT silently dropped by the idempotent write and
    # NOT mislabeled as a skipped duplicate (which means "already in store").
    batch = [
        _bar("2026-06-01T00:00:00Z", cl=100.0),
        _bar("2026-06-01T00:00:00Z", cl=101.0),
    ]
    _install_fetch(monkeypatch, batch)

    summary = front_door.ingest(["NVDA"], db)
    assert summary.rows_fetched == 2
    assert summary.rows_valid == 1  # only the first occurrence
    assert summary.rows_quarantined == 1
    assert summary.rows_written == 1
    assert summary.rows_skipped_duplicate == 0  # fresh run -> no "already in store"

    conn = store.connect(db)
    try:
        reason = conn.execute("SELECT reason FROM quarantine").fetchone()
        assert reason[0] == QuarantineReason.DUPLICATE_IN_BATCH.value
        n_price = conn.execute("SELECT COUNT(*) FROM price_raw").fetchone()[0]
        assert n_price == 1
    finally:
        conn.close()


def test_malformed_event_time_is_quarantined_not_aborted(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A non-canonical event_time on an otherwise-valid bar must be routed to
    # quarantine at the boundary, not crash the whole run. The valid bar in the
    # same batch still lands in price_raw.
    batch = [
        _bar("2026-06-01T00:00:00Z", cl=100.0),
        _bar("2026-06-02", cl=101.0),  # malformed: date only, no time or Z
    ]
    _install_fetch(monkeypatch, batch)

    summary = front_door.ingest(["NVDA"], db)
    assert summary.rows_fetched == 2
    assert summary.rows_valid == 1
    assert summary.rows_quarantined == 1
    assert summary.failed_tickers == ()  # run completed; no abort

    conn = store.connect(db)
    try:
        row = conn.execute("SELECT event_time, reason FROM quarantine").fetchone()
        assert row == ("2026-06-02", QuarantineReason.MALFORMED_EVENT_TIME.value)
        n_price = conn.execute("SELECT COUNT(*) FROM price_raw").fetchone()[0]
        assert n_price == 1
    finally:
        conn.close()
