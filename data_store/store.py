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

import logging
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from data_store import schema
from data_store.timeutils import validate_iso

logger = logging.getLogger(__name__)

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


@dataclass(frozen=True, slots=True)
class PaperOrder:
    """One paper-book order: a decision that changed the target weight.

    ``decision_event_time`` is the completed bar the signal was computed on;
    the order fills at the NEXT bar's open. ``id`` is ``None`` until inserted.
    """

    ticker: str
    decision_event_time: str
    target_weight: float
    created_knowable_time: str
    status: str
    id: int | None = None


@dataclass(frozen=True, slots=True)
class PaperFill:
    """One executed paper fill: which bar's open filled an order, and the deltas."""

    order_id: int
    fill_event_time: str
    fill_price: float
    shares_delta: float
    cash_delta: float
    knowable_time: str


@dataclass(frozen=True, slots=True)
class PaperState:
    """The paper book's mutable working state for one ticker (NOT journal)."""

    ticker: str
    shares: float
    cash: float
    last_decided_event_time: str


@dataclass(frozen=True, slots=True)
class PaperEquity:
    """One mark-to-market equity point: ``equity = cash + shares * close``."""

    ticker: str
    event_time: str
    equity: float
    close: float


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


# --------------------------------------------------------------------------- #
# Paper-book API (execution layer)
#
# TRANSACTION CONTRACT: unlike the batch write_* functions above (which commit
# internally), these execute WITHOUT committing -- the paper loop owns the
# transaction so each processed bar (settle + equity + order + state advance)
# commits atomically, and --dry-run can roll everything back. Journal law: the
# only UPDATE on journal tables is the pending -> filled transition;
# paper_state is mutable working state, not journal.
# --------------------------------------------------------------------------- #
def insert_paper_order(conn: sqlite3.Connection, order: PaperOrder) -> int | None:
    """Insert one order; return its id, or ``None`` if that decision bar already
    has an order (UNIQUE(ticker, decision_event_time) -- idempotent re-runs).

    A skipped duplicate is logged, never silent: in normal operation the loop's
    catch-up cursor prevents re-deciding a bar, so a duplicate means a re-run
    over already-journaled ground and the original order stands.
    """
    validate_iso(order.decision_event_time)
    validate_iso(order.created_knowable_time)
    cur = conn.execute(
        "INSERT INTO paper_orders "
        "(ticker, decision_event_time, target_weight, created_knowable_time, status) "
        "VALUES (?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
        (
            order.ticker,
            order.decision_event_time,
            order.target_weight,
            order.created_knowable_time,
            order.status,
        ),
    )
    if cur.rowcount == 0:
        logger.info(
            "paper order already journaled for %s @ %s; keeping the original",
            order.ticker,
            order.decision_event_time,
        )
        return None
    return int(cur.lastrowid) if cur.lastrowid is not None else None


def read_pending_paper_orders(
    conn: sqlite3.Connection, ticker: str
) -> list[PaperOrder]:
    """Return ``ticker``'s pending orders, oldest decision first."""
    rows = conn.execute(
        "SELECT id, ticker, decision_event_time, target_weight, "
        "created_knowable_time, status FROM paper_orders "
        "WHERE ticker = ? AND status = 'pending' ORDER BY decision_event_time ASC",
        (ticker,),
    ).fetchall()
    return [
        PaperOrder(
            id=int(r[0]),
            ticker=str(r[1]),
            decision_event_time=str(r[2]),
            target_weight=float(r[3]),
            created_knowable_time=str(r[4]),
            status=str(r[5]),
        )
        for r in rows
    ]


def read_last_paper_order(conn: sqlite3.Connection, ticker: str) -> PaperOrder | None:
    """Return the most recent non-cancelled order (the commanded weight), if any."""
    row = conn.execute(
        "SELECT id, ticker, decision_event_time, target_weight, "
        "created_knowable_time, status FROM paper_orders "
        "WHERE ticker = ? AND status != 'cancelled' "
        "ORDER BY decision_event_time DESC LIMIT 1",
        (ticker,),
    ).fetchone()
    if row is None:
        return None
    return PaperOrder(
        id=int(row[0]),
        ticker=str(row[1]),
        decision_event_time=str(row[2]),
        target_weight=float(row[3]),
        created_knowable_time=str(row[4]),
        status=str(row[5]),
    )


def fill_paper_order(conn: sqlite3.Connection, fill: PaperFill) -> None:
    """Journal one fill and flip its order pending -> filled (the ONE allowed
    UPDATE on a journal table). Raises if the order is not currently pending --
    filling a non-pending order is a bug, never a condition to paper over.
    """
    validate_iso(fill.fill_event_time)
    validate_iso(fill.knowable_time)
    cur = conn.execute(
        "UPDATE paper_orders SET status = 'filled' "
        "WHERE id = ? AND status = 'pending'",
        (fill.order_id,),
    )
    if cur.rowcount != 1:
        raise ValueError(
            f"order {fill.order_id} is not pending; refusing to journal a fill"
        )
    conn.execute(
        "INSERT INTO paper_fills "
        "(order_id, fill_event_time, fill_price, shares_delta, cash_delta, "
        "knowable_time) VALUES (?, ?, ?, ?, ?, ?)",
        (
            fill.order_id,
            fill.fill_event_time,
            fill.fill_price,
            fill.shares_delta,
            fill.cash_delta,
            fill.knowable_time,
        ),
    )


def read_paper_fills(conn: sqlite3.Connection, ticker: str) -> list[PaperFill]:
    """Return every fill for ``ticker``'s orders, oldest fill bar first."""
    rows = conn.execute(
        "SELECT f.order_id, f.fill_event_time, f.fill_price, f.shares_delta, "
        "f.cash_delta, f.knowable_time FROM paper_fills f "
        "JOIN paper_orders o ON o.id = f.order_id "
        "WHERE o.ticker = ? ORDER BY f.fill_event_time ASC",
        (ticker,),
    ).fetchall()
    return [
        PaperFill(
            order_id=int(r[0]),
            fill_event_time=str(r[1]),
            fill_price=float(r[2]),
            shares_delta=float(r[3]),
            cash_delta=float(r[4]),
            knowable_time=str(r[5]),
        )
        for r in rows
    ]


def read_paper_state(conn: sqlite3.Connection, ticker: str) -> PaperState | None:
    """Return the paper book's working state for ``ticker`` (``None`` = first run)."""
    row = conn.execute(
        "SELECT ticker, shares, cash, last_decided_event_time "
        "FROM paper_state WHERE ticker = ?",
        (ticker,),
    ).fetchone()
    if row is None:
        return None
    return PaperState(
        ticker=str(row[0]),
        shares=float(row[1]),
        cash=float(row[2]),
        last_decided_event_time=str(row[3]),
    )


def write_paper_state(conn: sqlite3.Connection, state: PaperState) -> None:
    """Create or update the singleton working state for ``state.ticker``."""
    validate_iso(state.last_decided_event_time)
    conn.execute(
        "INSERT INTO paper_state (ticker, shares, cash, last_decided_event_time) "
        "VALUES (?, ?, ?, ?) ON CONFLICT (ticker) DO UPDATE SET "
        "shares = excluded.shares, cash = excluded.cash, "
        "last_decided_event_time = excluded.last_decided_event_time",
        (state.ticker, state.shares, state.cash, state.last_decided_event_time),
    )


def insert_paper_equity(conn: sqlite3.Connection, row: PaperEquity) -> bool:
    """Insert one equity mark; return False if that bar is already marked
    (UNIQUE(ticker, event_time) -- idempotent re-runs over journaled ground).
    """
    validate_iso(row.event_time)
    cur = conn.execute(
        "INSERT INTO paper_equity (ticker, event_time, equity, close) "
        "VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING",
        (row.ticker, row.event_time, row.equity, row.close),
    )
    return cur.rowcount == 1


def read_paper_equity(conn: sqlite3.Connection, ticker: str) -> list[PaperEquity]:
    """Return every equity mark for ``ticker``, oldest bar first."""
    rows = conn.execute(
        "SELECT ticker, event_time, equity, close FROM paper_equity "
        "WHERE ticker = ? ORDER BY event_time ASC",
        (ticker,),
    ).fetchall()
    return [
        PaperEquity(
            ticker=str(r[0]),
            event_time=str(r[1]),
            equity=float(r[2]),
            close=float(r[3]),
        )
        for r in rows
    ]
