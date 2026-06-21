"""Connection management and the typed read/write API for the data store.

This module is the *only* write path to the store (the single-writer law). Every
insert goes through a ``write_*`` function here, and every insert is idempotent
(``INSERT ... ON CONFLICT DO NOTHING``), so re-running an ingest after a crash or
on a sometimes-off laptop never duplicates rows -- it just fills the gaps.

Reads are point-in-time: :func:`read_price_asof` / :func:`read_sentiment_asof`
return only rows whose ``knowable_time`` is at or before a caller-supplied
``as_of`` instant. That is how the research layer avoids lookahead bias. Reads
serve the CLEAN tables only.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from data_store import schema
from data_store.timeutils import validate_iso

# Accepted forms for a database location.
DbPath = str | Path


# --------------------------------------------------------------------------- #
# Typed row objects -- the write API takes these, never loose tuples, so the
# column order lives in exactly one place (here) and callers get type checking.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class PriceRaw:
    """One raw OHLCV daily bar, exactly as a source delivered it."""

    ticker: str
    event_time: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    knowable_time: str
    source: str


@dataclass(frozen=True, slots=True)
class PriceClean:
    """One reconciled OHLCV daily bar, with a split/dividend-adjusted close."""

    ticker: str
    event_time: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    adj_close: float
    knowable_time: str
    source: str


@dataclass(frozen=True, slots=True)
class Sentiment:
    """One sentiment / alt-data observation.

    The RAW and CLEAN sentiment tables share the same columns, so one row type
    serves both write paths.
    """

    ticker: str
    event_time: str
    metric: str
    value: float
    knowable_time: str
    source: str


@dataclass(frozen=True, slots=True)
class CorporateAction:
    """One corporate action for a ticker, as fetched from a source.

    ``value`` is interpreted by ``action_type``: for ``'split'`` it is the split
    ratio (e.g. ``10.0`` for a 10-for-1 split); for ``'dividend'`` it is the cash
    amount per share.
    """

    ticker: str
    event_time: str
    action_type: str
    value: float
    knowable_time: str
    source: str


@dataclass(frozen=True, slots=True)
class QuarantineRow:
    """One rejected row, preserved verbatim for audit (quarantine, never delete).

    ``payload`` is the rejected row serialised as JSON; ``reason`` is a specific,
    machine-readable cause; ``event_time`` may be ``None`` if the row was rejected
    for lacking a usable one.
    """

    domain: str
    ticker: str
    event_time: str | None
    payload: str
    reason: str
    knowable_time: str


# --------------------------------------------------------------------------- #
# Connection management
# --------------------------------------------------------------------------- #
# journal_mode=WAL persists in the database file once set; the other two are
# per-connection and must be re-applied on every open.
_PRAGMAS: tuple[str, ...] = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA foreign_keys=ON",
    "PRAGMA synchronous=NORMAL",
)


def connect(db_path: DbPath) -> sqlite3.Connection:
    """Open a connection to the store with the store's standard pragmas.

    Use this for every connection (read or write) so settings are consistent.
    """
    conn = sqlite3.connect(db_path)
    for pragma in _PRAGMAS:
        conn.execute(pragma)
    return conn


def init_db(db_path: DbPath) -> None:
    """Create every table and index and set the pragmas. Safe to re-run.

    All DDL uses ``IF NOT EXISTS``, so calling this on an existing store is a
    no-op that simply re-asserts the schema.
    """
    conn = connect(db_path)
    try:
        with conn:  # one transaction; commits on success, rolls back on error
            for statement in schema.ALL_STATEMENTS:
                conn.execute(statement)
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Write API -- idempotent inserts, returning the count of NEW rows
# --------------------------------------------------------------------------- #
_PRICE_RAW_SQL = (
    "INSERT INTO price_raw "
    "(ticker, event_time, open, high, low, close, volume, knowable_time, source) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
    "ON CONFLICT DO NOTHING"
)

_PRICE_CLEAN_SQL = (
    "INSERT INTO price_clean "
    "(ticker, event_time, open, high, low, close, volume, adj_close, "
    "knowable_time, source) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
    "ON CONFLICT DO NOTHING"
)

_SENTIMENT_RAW_SQL = (
    "INSERT INTO sentiment_raw "
    "(ticker, event_time, metric, value, knowable_time, source) "
    "VALUES (?, ?, ?, ?, ?, ?) "
    "ON CONFLICT DO NOTHING"
)

_SENTIMENT_CLEAN_SQL = (
    "INSERT INTO sentiment_clean "
    "(ticker, event_time, metric, value, knowable_time, source) "
    "VALUES (?, ?, ?, ?, ?, ?) "
    "ON CONFLICT DO NOTHING"
)

_CORPORATE_ACTIONS_SQL = (
    "INSERT INTO corporate_actions "
    "(ticker, event_time, action_type, value, knowable_time, source) "
    "VALUES (?, ?, ?, ?, ?, ?) "
    "ON CONFLICT DO NOTHING"
)

# Quarantine is an append-only audit log (no UNIQUE constraint, so no
# ON CONFLICT): re-running a rejecting ingest appends a fresh incident record.
_QUARANTINE_SQL = (
    "INSERT INTO quarantine "
    "(domain, ticker, event_time, payload, reason, knowable_time) "
    "VALUES (?, ?, ?, ?, ?, ?)"
)


def _insert_many(
    conn: sqlite3.Connection,
    sql: str,
    params: Sequence[Sequence[object]],
) -> int:
    """Run an idempotent ``executemany`` and return how many rows were inserted.

    Counts via the connection's ``total_changes`` delta: rows skipped by
    ``ON CONFLICT DO NOTHING`` are not "changes", so the delta is exactly the
    number of genuinely new rows.
    """
    if not params:
        return 0
    before = conn.total_changes
    with conn:  # commit on success; rollback + re-raise on error (no swallowing)
        conn.executemany(sql, params)
    return conn.total_changes - before


def write_price_raw(conn: sqlite3.Connection, rows: Sequence[PriceRaw]) -> int:
    """Insert raw price bars idempotently; return the number of new rows.

    Timestamps are validated up front, so one bad row rejects the whole batch
    before anything is written (fail-fast, all-or-nothing).
    """
    return _insert_many(
        conn,
        _PRICE_RAW_SQL,
        [
            (
                r.ticker,
                validate_iso(r.event_time),
                r.open,
                r.high,
                r.low,
                r.close,
                r.volume,
                validate_iso(r.knowable_time),
                r.source,
            )
            for r in rows
        ],
    )


def write_price_clean(conn: sqlite3.Connection, rows: Sequence[PriceClean]) -> int:
    """Insert reconciled price bars idempotently; return the number of new rows."""
    return _insert_many(
        conn,
        _PRICE_CLEAN_SQL,
        [
            (
                r.ticker,
                validate_iso(r.event_time),
                r.open,
                r.high,
                r.low,
                r.close,
                r.volume,
                r.adj_close,
                validate_iso(r.knowable_time),
                r.source,
            )
            for r in rows
        ],
    )


def replace_price_clean(
    conn: sqlite3.Connection,
    ticker: str,
    fresh_rows: Sequence[PriceClean],
    superseded: Sequence[QuarantineRow],
) -> int:
    """Atomically rebuild one ticker's CLEAN rows (archive -> delete -> insert).

    In ONE transaction: append ``superseded`` (the rows being replaced) to
    quarantine, delete the ticker's existing ``price_clean`` rows, then insert
    ``fresh_rows``. All-or-nothing -- any error rolls back the whole rebuild, so
    ``price_clean`` is never left half-written. This is how a re-derived series
    replaces an out-of-date one while honouring quarantine-never-delete. Returns
    the number of fresh rows written (all of them: the delete clears conflicts).
    """
    fresh_params = [
        (
            r.ticker,
            validate_iso(r.event_time),
            r.open,
            r.high,
            r.low,
            r.close,
            r.volume,
            r.adj_close,
            validate_iso(r.knowable_time),
            r.source,
        )
        for r in fresh_rows
    ]
    superseded_params = [
        (
            q.domain,
            q.ticker,
            q.event_time,
            q.payload,
            q.reason,
            validate_iso(q.knowable_time),
        )
        for q in superseded
    ]
    with conn:  # one transaction: archive + delete + insert, or nothing at all
        if superseded_params:
            conn.executemany(_QUARANTINE_SQL, superseded_params)
        conn.execute("DELETE FROM price_clean WHERE ticker = ?", (ticker,))
        if fresh_params:
            conn.executemany(_PRICE_CLEAN_SQL, fresh_params)
    return len(fresh_rows)


def write_sentiment_raw(conn: sqlite3.Connection, rows: Sequence[Sentiment]) -> int:
    """Insert raw sentiment rows idempotently; return the number of new rows."""
    return _insert_many(
        conn,
        _SENTIMENT_RAW_SQL,
        [
            (
                r.ticker,
                validate_iso(r.event_time),
                r.metric,
                r.value,
                validate_iso(r.knowable_time),
                r.source,
            )
            for r in rows
        ],
    )


def write_sentiment_clean(conn: sqlite3.Connection, rows: Sequence[Sentiment]) -> int:
    """Insert reconciled sentiment rows idempotently; return new-row count."""
    return _insert_many(
        conn,
        _SENTIMENT_CLEAN_SQL,
        [
            (
                r.ticker,
                validate_iso(r.event_time),
                r.metric,
                r.value,
                validate_iso(r.knowable_time),
                r.source,
            )
            for r in rows
        ],
    )


def write_corporate_actions(
    conn: sqlite3.Connection, rows: Sequence[CorporateAction]
) -> int:
    """Insert corporate actions idempotently; return the number of new rows.

    Timestamps are validated up front (fail-fast, all-or-nothing). Re-fetching the
    same action is a no-op via ``ON CONFLICT DO NOTHING``.
    """
    return _insert_many(
        conn,
        _CORPORATE_ACTIONS_SQL,
        [
            (
                r.ticker,
                validate_iso(r.event_time),
                r.action_type,
                r.value,
                validate_iso(r.knowable_time),
                r.source,
            )
            for r in rows
        ],
    )


def write_quarantine(conn: sqlite3.Connection, rows: Sequence[QuarantineRow]) -> int:
    """Append rejected rows to the quarantine log; return the number written.

    Only ``knowable_time`` (our own stamp) is validated. ``event_time`` is stored
    verbatim -- possibly ``None`` -- because the whole point of quarantine is to
    preserve bad input as-is, so it must never be rejected for being malformed.
    """
    return _insert_many(
        conn,
        _QUARANTINE_SQL,
        [
            (
                r.domain,
                r.ticker,
                r.event_time,
                r.payload,
                r.reason,
                validate_iso(r.knowable_time),
            )
            for r in rows
        ],
    )


# --------------------------------------------------------------------------- #
# Read API -- point-in-time, CLEAN tables only
# --------------------------------------------------------------------------- #
def read_price_asof(
    conn: sqlite3.Connection,
    ticker: str,
    as_of: str,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """Return CLEAN price bars for ``ticker`` knowable at or before ``as_of``.

    Only rows whose ``knowable_time <= as_of`` are returned -- this is the
    lookahead guard. Optionally restrict ``event_time`` to the inclusive window
    ``[start, end]``. Rows come back ordered by ``event_time`` ascending.

    All timestamp arguments must be canonical UTC ISO-8601 (see
    :mod:`data_store.timeutils`); they are validated here.
    """
    validate_iso(as_of)
    sql = "SELECT * FROM price_clean WHERE ticker = ? AND knowable_time <= ?"
    params: list[object] = [ticker, as_of]
    if start is not None:
        sql += " AND event_time >= ?"
        params.append(validate_iso(start))
    if end is not None:
        sql += " AND event_time <= ?"
        params.append(validate_iso(end))
    sql += " ORDER BY event_time ASC"
    return pd.read_sql_query(sql, conn, params=params)


def read_sentiment_asof(
    conn: sqlite3.Connection,
    ticker: str,
    as_of: str,
    metric: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """Return CLEAN sentiment rows for ``ticker`` knowable at or before ``as_of``.

    Only rows whose ``knowable_time <= as_of`` are returned (the lookahead
    guard). Optionally filter to a single ``metric`` and/or restrict
    ``event_time`` to the inclusive window ``[start, end]``. Rows come back
    ordered by ``event_time`` ascending.
    """
    validate_iso(as_of)
    sql = "SELECT * FROM sentiment_clean WHERE ticker = ? AND knowable_time <= ?"
    params: list[object] = [ticker, as_of]
    if metric is not None:
        sql += " AND metric = ?"
        params.append(metric)
    if start is not None:
        sql += " AND event_time >= ?"
        params.append(validate_iso(start))
    if end is not None:
        sql += " AND event_time <= ?"
        params.append(validate_iso(end))
    sql += " ORDER BY event_time ASC"
    return pd.read_sql_query(sql, conn, params=params)
