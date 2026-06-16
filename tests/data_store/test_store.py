"""Tests for the data_store storage API.

Covers schema/WAL setup, exact write->read round-trips, idempotent writes, the
point-in-time (lookahead-prevention) read, timestamp round-tripping, ordering,
and event-time window filtering.
"""

from __future__ import annotations

import dataclasses
import sqlite3
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from data_store import store, timeutils
from data_store.store import PriceClean, PriceRaw, Sentiment

# A reusable, fully-specified CLEAN price bar. Individual tests vary only the
# fields they care about via dataclasses.replace(...). All numeric values are
# exactly representable as IEEE-754 doubles, so "round-trips exactly" is testable
# with plain == rather than approximate comparison.
_BASE_PRICE = PriceClean(
    ticker="AAPL",
    event_time="2026-06-15T00:00:00Z",
    open=100.0,
    high=102.5,
    low=99.5,
    close=101.25,
    volume=1_000_000,
    adj_close=101.0,
    knowable_time="2026-06-15T00:00:00Z",
    source="test",
)

_BASE_SENTIMENT = Sentiment(
    ticker="AAPL",
    event_time="2026-06-15T00:00:00Z",
    metric="news_score",
    value=0.75,
    knowable_time="2026-06-15T00:00:00Z",
    source="test",
)

# Comfortably after every event/knowable time used below, so an as_of of this
# value never itself hides a row (the per-test as_of values do that on purpose).
_FAR_FUTURE = "2026-07-01T00:00:00Z"


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """A connection to a freshly initialised store on a real (temp-file) DB.

    A file-backed DB (not :memory:) is required for WAL mode to actually engage.
    """
    db = tmp_path / "store.db"
    store.init_db(db)
    connection = store.connect(db)
    try:
        yield connection
    finally:
        connection.close()


def test_init_creates_all_tables_and_wal_mode(tmp_path: Path) -> None:
    db = tmp_path / "wal.db"
    store.init_db(db)
    connection = store.connect(db)
    try:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        tables = {row[0] for row in rows}
        assert {
            "price_raw",
            "price_clean",
            "sentiment_raw",
            "sentiment_clean",
        } <= tables

        mode = connection.execute("PRAGMA journal_mode").fetchone()
        assert mode is not None
        assert mode[0] == "wal"
    finally:
        connection.close()


def test_price_clean_round_trips_exactly(conn: sqlite3.Connection) -> None:
    assert store.write_price_clean(conn, [_BASE_PRICE]) == 1

    df = store.read_price_asof(conn, "AAPL", _FAR_FUTURE)
    assert len(df) == 1
    got = df.iloc[0]
    assert got["ticker"] == "AAPL"
    assert got["event_time"] == "2026-06-15T00:00:00Z"
    assert float(got["open"]) == 100.0
    assert float(got["high"]) == 102.5
    assert float(got["low"]) == 99.5
    assert float(got["close"]) == 101.25
    assert int(got["volume"]) == 1_000_000
    assert float(got["adj_close"]) == 101.0
    assert got["knowable_time"] == "2026-06-15T00:00:00Z"
    assert got["source"] == "test"


def test_sentiment_clean_round_trips_exactly(conn: sqlite3.Connection) -> None:
    assert store.write_sentiment_clean(conn, [_BASE_SENTIMENT]) == 1

    df = store.read_sentiment_asof(conn, "AAPL", _FAR_FUTURE)
    assert len(df) == 1
    got = df.iloc[0]
    assert got["ticker"] == "AAPL"
    assert got["event_time"] == "2026-06-15T00:00:00Z"
    assert got["metric"] == "news_score"
    assert float(got["value"]) == 0.75
    assert got["knowable_time"] == "2026-06-15T00:00:00Z"
    assert got["source"] == "test"


def test_writing_same_clean_row_twice_inserts_once(conn: sqlite3.Connection) -> None:
    # First write inserts; the identical second write conflicts on
    # UNIQUE(ticker, event_time) and inserts nothing.
    assert store.write_price_clean(conn, [_BASE_PRICE]) == 1
    assert store.write_price_clean(conn, [_BASE_PRICE]) == 0

    df = store.read_price_asof(conn, "AAPL", _FAR_FUTURE)
    assert len(df) == 1


def test_raw_write_is_idempotent(conn: sqlite3.Connection) -> None:
    raw = PriceRaw(
        ticker="MSFT",
        event_time="2026-06-15T00:00:00Z",
        open=400.0,
        high=405.0,
        low=399.0,
        close=402.5,
        volume=2_000_000,
        knowable_time="2026-06-15T00:00:00Z",
        source="yfinance",
    )
    assert store.write_price_raw(conn, [raw]) == 1
    assert store.write_price_raw(conn, [raw]) == 0

    count = conn.execute("SELECT COUNT(*) FROM price_raw").fetchone()
    assert count is not None
    assert count[0] == 1


def test_asof_excludes_rows_knowable_after_as_of(conn: sqlite3.Connection) -> None:
    # The lookahead-prevention test. BOTH bars have an event_time BEFORE the
    # as_of cutoff, so an event_time window cannot be what hides either one --
    # only the knowable_time filter can.
    as_of = "2026-06-15T12:00:00Z"
    visible = dataclasses.replace(
        _BASE_PRICE,
        event_time="2026-06-10T00:00:00Z",
        knowable_time="2026-06-11T00:00:00Z",  # knowable BEFORE as_of -> returns
    )
    not_yet = dataclasses.replace(
        _BASE_PRICE,
        event_time="2026-06-14T00:00:00Z",
        knowable_time="2026-06-20T00:00:00Z",  # knowable AFTER as_of -> hidden
    )
    store.write_price_clean(conn, [visible, not_yet])

    df = store.read_price_asof(conn, "AAPL", as_of)

    # Only the row we could legitimately have known by `as_of` comes back.
    assert list(df["event_time"]) == ["2026-06-10T00:00:00Z"]
    # !! LOOKAHEAD GUARD !!  read_price_asof filters `knowable_time <= as_of`.
    # If you DELETE that filter from store.read_price_asof, BOTH bars return and
    # THIS ASSERTION MUST FAIL. That failure is the whole point: it proves the
    # store cannot serve data before it was knowable.


def test_timestamps_survive_as_utc_iso(conn: sqlite3.Connection) -> None:
    event_time = "2026-06-15T00:00:00Z"
    knowable_time = "2026-06-15T13:30:00Z"
    row = dataclasses.replace(
        _BASE_PRICE, event_time=event_time, knowable_time=knowable_time
    )
    store.write_price_clean(conn, [row])

    df = store.read_price_asof(conn, "AAPL", _FAR_FUTURE)
    got_event = str(df.iloc[0]["event_time"])
    got_knowable = str(df.iloc[0]["knowable_time"])

    # Stored text is byte-for-byte the canonical string we wrote...
    assert got_event == event_time
    assert got_knowable == knowable_time
    # ...and still validates and parses as canonical UTC ISO-8601.
    assert timeutils.validate_iso(got_event) == event_time
    assert timeutils.to_utc_iso(timeutils.parse_iso(got_knowable)) == knowable_time


def test_read_orders_by_event_time_ascending(conn: sqlite3.Connection) -> None:
    # Insert deliberately out of chronological order.
    later = dataclasses.replace(_BASE_PRICE, event_time="2026-06-12T00:00:00Z")
    earlier = dataclasses.replace(_BASE_PRICE, event_time="2026-06-09T00:00:00Z")
    middle = dataclasses.replace(_BASE_PRICE, event_time="2026-06-10T00:00:00Z")
    store.write_price_clean(conn, [later, earlier, middle])

    df = store.read_price_asof(conn, "AAPL", _FAR_FUTURE)
    assert list(df["event_time"]) == [
        "2026-06-09T00:00:00Z",
        "2026-06-10T00:00:00Z",
        "2026-06-12T00:00:00Z",
    ]


def test_event_time_window_is_inclusive(conn: sqlite3.Connection) -> None:
    for day in ("08", "09", "10", "11", "12"):
        store.write_price_clean(
            conn,
            [dataclasses.replace(_BASE_PRICE, event_time=f"2026-06-{day}T00:00:00Z")],
        )

    df = store.read_price_asof(
        conn,
        "AAPL",
        _FAR_FUTURE,
        start="2026-06-09T00:00:00Z",
        end="2026-06-11T00:00:00Z",
    )
    assert list(df["event_time"]) == [
        "2026-06-09T00:00:00Z",
        "2026-06-10T00:00:00Z",
        "2026-06-11T00:00:00Z",
    ]


def test_sentiment_metric_filter(conn: sqlite3.Connection) -> None:
    news = _BASE_SENTIMENT
    rsi = dataclasses.replace(_BASE_SENTIMENT, metric="rsi", value=55.0)
    store.write_sentiment_clean(conn, [news, rsi])

    df = store.read_sentiment_asof(conn, "AAPL", _FAR_FUTURE, metric="rsi")
    assert list(df["metric"]) == ["rsi"]
    assert float(df.iloc[0]["value"]) == 55.0


def test_validate_iso_rejects_non_canonical() -> None:
    bad_values = [
        "2026-06-15",  # date only, no time
        "2026-06-15T00:00:00",  # missing the Z
        "2026-06-15T00:00:00+00:00",  # numeric offset instead of Z
        "2026-06-15T00:00:00.000Z",  # sub-second precision
        "2026-6-5T00:00:00Z",  # not zero-padded
        "2026-13-01T00:00:00Z",  # impossible month
        "not-a-timestamp",
    ]
    for value in bad_values:
        with pytest.raises(ValueError):
            timeutils.validate_iso(value)


def test_to_utc_iso_converts_to_utc() -> None:
    # 09:30 at UTC+2 is 07:30 UTC.
    tz_plus_two = timezone(timedelta(hours=2))
    dt = datetime(2026, 6, 15, 9, 30, 0, tzinfo=tz_plus_two)
    assert timeutils.to_utc_iso(dt) == "2026-06-15T07:30:00Z"


def test_write_rejects_bad_timestamp_atomically(conn: sqlite3.Connection) -> None:
    # A batch containing one invalid timestamp must reject wholesale: validation
    # happens before any insert, so nothing from the batch is written.
    good = _BASE_PRICE
    bad = dataclasses.replace(
        _BASE_PRICE, event_time="2026-06-16", knowable_time="2026-06-16T00:00:00Z"
    )
    with pytest.raises(ValueError):
        store.write_price_clean(conn, [good, bad])

    df = store.read_price_asof(conn, "AAPL", _FAR_FUTURE)
    assert len(df) == 0
