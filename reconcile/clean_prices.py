"""RAW->CLEAN price reconciliation: VERIFY the source's split adjustment, then copy.

yfinance's OHLC (``auto_adjust=False``) are ALREADY split-adjusted by Yahoo, so
the RAW series is continuous across splits. This brick therefore does NOT
re-adjust prices -- doing so would double-adjust and create a fake ~ratio-sized
cliff at each split (this exact bug was caught in testing by the move meter). It:

1. fetches corporate actions and persists them to ``corporate_actions`` (the only
   network call in the whole brick), then
2. VERIFIES, per known split, that the raw series is CONTINUOUS across the split
   date -- a source that pre-adjusted shows a small move; one that did NOT shows a
   ~ratio-sized cliff, then
3. copies the validated RAW bars into ``price_clean`` (the series
   ``read_price_asof`` serves), re-running the same row sanity battery ingest uses.

If a split's boundary shows a large discontinuity (> ``_CONTINUITY_THRESHOLD_PCT``)
the source did NOT pre-adjust it (or the data is bad): the boundary rows are
quarantined (``unadjusted_split_suspected``) and the run RAISES. We refuse to
publish a CLEAN series we cannot trust rather than guess an adjustment.

``adj_close == close`` for now (splits only). DIVIDEND adjustment is a later
refinement and will use Yahoo's ``Adj Close`` (split+dividend) column -- which is
why ``close`` and ``adj_close`` are separate columns today.

REBUILD: re-running replaces a ticker's CLEAN rows atomically -- the old rows are
archived to quarantine (``superseded_by_rebuild``) and deleted before the fresh
rows are written (quarantine-never-delete). An UNCHANGED re-run is a no-op
(idempotent): identical data writes nothing and is reported as skipped duplicates.
``price_raw`` is the system of record and is never modified here.
"""

from __future__ import annotations

import json
import logging
import math
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from data_store import store
from data_store.timeutils import now_utc_iso
from reconcile import corporate_actions

logger = logging.getLogger(__name__)

# Domain tag stored on every quarantine row this module writes.
_DOMAIN = "price_clean"

# A close-to-close move larger than this across a split boundary means the source
# did NOT pre-adjust the split (a 10-for-1 split shows ~900% otherwise). Well
# above any plausible single-day market move, so it never false-positives on real
# volatility, yet far below a split cliff.
_CONTINUITY_THRESHOLD_PCT = 35.0

# SplitCheck.status values.
_STATUS_PASS = "pass"
_STATUS_FLAGGED = "flagged"


class QuarantineReason(StrEnum):
    """Why a row was sent to quarantine by the reconciler (sanity reasons first).

    The four price-sanity reasons mirror ingest (same string values) so a
    rejection means the same thing wherever it is raised. The last two are
    reconcile-specific bookkeeping reasons, not row defects.
    """

    NAN_OR_INF_PRICE = "nan_or_inf_price"
    NON_POSITIVE_PRICE = "non_positive_price"
    OHLC_INCONSISTENT = "ohlc_inconsistent"
    BAD_VOLUME = "negative_or_nan_volume"
    UNADJUSTED_SPLIT_SUSPECTED = "unadjusted_split_suspected"
    SUPERSEDED_BY_REBUILD = "superseded_by_rebuild"


class UnadjustedSplitError(RuntimeError):
    """Raised when a split's boundary shows a discontinuity the source left in.

    The reconciler refuses to write CLEAN for the affected ticker and quarantines
    the boundary rows first -- a loud failure, never a silent wrong series.
    """


@dataclass(frozen=True, slots=True)
class SplitCheck:
    """The continuity verdict for one known split.

    ``across_split_move_pct`` is ``None`` when the split falls outside the loaded
    bar range (no boundary to test). ``status`` is ``"pass"`` or ``"flagged"``.
    """

    event_time: str
    ratio: float
    across_split_move_pct: float | None
    status: str


@dataclass(frozen=True, slots=True)
class ReconciliationSummary:
    """What one reconcile run did, in numbers that must reconcile.

    Invariant (per run):
        rows_raw == rows_written_clean + rows_skipped_duplicate + rows_quarantined

    ``rows_quarantined`` counts only RAW rows that failed a sanity check -- NOT the
    boundary rows of a flagged split, nor rows archived by a rebuild (those are
    separate bookkeeping). ``max_abs_daily_close_move_pct`` (with its
    ``event_time``) is the largest day-over-day move in the CLEAN close series; on
    a correctly pre-adjusted source it reflects only real volatility.
    """

    requested_tickers: tuple[str, ...]
    rows_raw: int
    rows_written_clean: int
    rows_quarantined: int
    rows_skipped_duplicate: int
    splits_checked: tuple[SplitCheck, ...]
    max_abs_daily_close_move_pct: float | None
    max_abs_daily_close_move_date: str | None


@dataclass(frozen=True, slots=True)
class _Split:
    """A persisted split: its action time and ratio."""

    event_time: str
    ratio: float


@dataclass(frozen=True, slots=True)
class _RawBar:
    """A raw bar read back from price_raw (only the fields the cleaner needs)."""

    event_time: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    source: str


@dataclass(frozen=True, slots=True)
class _DailyMove:
    """A day-over-day percent close move and the event_time it landed on."""

    pct: float
    event_time: str


# A CLEAN row's comparable signature (everything but knowable_time), keyed by
# event_time -- used to decide whether a rebuild is actually needed.
_Signature = tuple[float, float, float, float, int, float, str]


def _is_nonfinite(value: float) -> bool:
    """True if ``value`` is NaN or +/-inf."""
    return math.isnan(value) or math.isinf(value)


def _json_safe(payload: dict[str, object]) -> dict[str, object]:
    """Return a JSON-serialisable copy of ``payload`` (non-finite floats -> text)."""
    safe: dict[str, object] = {}
    for key, value in payload.items():
        if isinstance(value, float) and not math.isfinite(value):
            safe[key] = repr(value)
        else:
            safe[key] = value
    return safe


def _quarantine(
    ticker: str,
    event_time: str,
    payload: dict[str, object],
    reason: str,
    knowable_time: str,
) -> store.QuarantineRow:
    """Build a QuarantineRow with ``payload`` serialised as JSON."""
    return store.QuarantineRow(
        domain=_DOMAIN,
        ticker=ticker,
        event_time=event_time,
        payload=json.dumps(_json_safe(payload), sort_keys=True),
        reason=reason,
        knowable_time=knowable_time,
    )


def _classify_clean_row(bar: _RawBar) -> QuarantineReason | None:
    """Return why ``bar`` should be quarantined, or ``None`` if it is valid.

    The same battery ingest applies at the RAW boundary, re-run here as defense in
    depth (a row written straight to price_raw could be non-finite, non-positive,
    or inconsistent).
    """
    prices = (bar.open, bar.high, bar.low, bar.close)
    if any(_is_nonfinite(price) for price in prices):
        return QuarantineReason.NAN_OR_INF_PRICE
    if any(price <= 0 for price in prices):
        return QuarantineReason.NON_POSITIVE_PRICE
    open_, high, low, close = prices
    if not (low <= min(open_, close) and max(open_, close) <= high and low <= high):
        return QuarantineReason.OHLC_INCONSISTENT
    if bar.volume < 0:
        return QuarantineReason.BAD_VOLUME
    return None


def _sanity_payload(bar: _RawBar) -> dict[str, object]:
    """Audit payload for a sanity-rejected bar (the raw values, verbatim)."""
    return {
        "event_time": bar.event_time,
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "volume": bar.volume,
        "source": bar.source,
    }


def _read_raw_bars(conn: sqlite3.Connection, ticker: str) -> list[_RawBar]:
    """Read all of ``ticker``'s raw bars from price_raw, ascending event_time."""
    cursor = conn.execute(
        "SELECT event_time, open, high, low, close, volume, source "
        "FROM price_raw WHERE ticker = ? ORDER BY event_time ASC",
        (ticker,),
    )
    return [
        _RawBar(
            event_time=str(row[0]),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=int(row[5]),
            source=str(row[6]),
        )
        for row in cursor.fetchall()
    ]


def _read_splits(conn: sqlite3.Connection, ticker: str) -> list[_Split]:
    """Read ``ticker``'s persisted splits from corporate_actions, ascending."""
    cursor = conn.execute(
        "SELECT event_time, value FROM corporate_actions "
        "WHERE ticker = ? AND action_type = ? ORDER BY event_time ASC",
        (ticker, corporate_actions.ACTION_SPLIT),
    )
    return [
        _Split(event_time=str(row[0]), ratio=float(row[1]))
        for row in cursor.fetchall()
    ]


def _read_clean_signatures(
    conn: sqlite3.Connection, ticker: str
) -> dict[str, _Signature]:
    """Existing CLEAN rows for ``ticker`` as event_time -> data signature.

    ``knowable_time`` is deliberately excluded: an unchanged re-run must compare
    equal so it is a no-op and does NOT churn the point-in-time stamp.
    """
    cursor = conn.execute(
        "SELECT event_time, open, high, low, close, volume, adj_close, source "
        "FROM price_clean WHERE ticker = ? ORDER BY event_time ASC",
        (ticker,),
    )
    return {
        str(row[0]): (
            float(row[1]),
            float(row[2]),
            float(row[3]),
            float(row[4]),
            int(row[5]),
            float(row[6]),
            str(row[7]),
        )
        for row in cursor.fetchall()
    }


def _signature_payload(event_time: str, sig: _Signature) -> dict[str, object]:
    """Audit payload for a superseded CLEAN row, reconstructed from its signature."""
    return {
        "event_time": event_time,
        "open": sig[0],
        "high": sig[1],
        "low": sig[2],
        "close": sig[3],
        "volume": sig[4],
        "adj_close": sig[5],
        "source": sig[6],
    }


def _boundary_bars(
    raw_bars: Sequence[_RawBar], split_event_time: str
) -> tuple[_RawBar | None, _RawBar | None]:
    """Return (last bar strictly before the split, first bar on/after it).

    Either side is ``None`` if the split falls outside the loaded range. Bars are
    assumed ascending by event_time. (Canonical UTC ISO sorts chronologically as
    plain text, so comparisons are string comparisons.)
    """
    before: _RawBar | None = None
    after: _RawBar | None = None
    for bar in raw_bars:
        if bar.event_time < split_event_time:
            before = bar
        else:
            after = bar
            break
    return before, after


def _verify_splits(
    conn: sqlite3.Connection,
    ticker: str,
    raw_bars: Sequence[_RawBar],
    splits: Sequence[_Split],
    knowable_time: str,
) -> list[SplitCheck]:
    """Confirm the raw series is continuous across every known split.

    Returns one :class:`SplitCheck` per split. On a discontinuity beyond the
    threshold the boundary rows are quarantined and :class:`UnadjustedSplitError`
    is raised (the source did not pre-adjust -- we refuse to publish CLEAN).
    """
    checks: list[SplitCheck] = []
    for split in splits:
        before, after = _boundary_bars(raw_bars, split.event_time)
        if before is None or after is None or after.close <= 0:
            # No testable boundary (split outside the range, or a non-positive
            # close that the row sanity check will catch on its own).
            checks.append(SplitCheck(split.event_time, split.ratio, None, _STATUS_PASS))
            continue

        move = abs(before.close - after.close) / after.close * 100.0
        if move > _CONTINUITY_THRESHOLD_PCT:
            checks.append(
                SplitCheck(split.event_time, split.ratio, move, _STATUS_FLAGGED)
            )
            boundary = [
                _quarantine(
                    ticker,
                    bar.event_time,
                    {
                        **_sanity_payload(bar),
                        "split_event_time": split.event_time,
                        "split_ratio": split.ratio,
                        "across_split_move_pct": move,
                    },
                    QuarantineReason.UNADJUSTED_SPLIT_SUSPECTED.value,
                    knowable_time,
                )
                for bar in (before, after)
            ]
            store.write_quarantine(conn, boundary)
            raise UnadjustedSplitError(
                f"{ticker}: raw close moves {move:.1f}% across the {split.ratio}"
                f"-for-1 split on {split.event_time} (threshold "
                f"{_CONTINUITY_THRESHOLD_PCT}%) -- source did not pre-adjust; "
                f"refusing to write CLEAN. Boundary rows quarantined."
            )
        checks.append(SplitCheck(split.event_time, split.ratio, move, _STATUS_PASS))
    return checks


def _max_close_move(rows: Sequence[store.PriceClean]) -> _DailyMove | None:
    """Largest abs day-over-day percent close move across the CLEAN series."""
    best: _DailyMove | None = None
    for i in range(1, len(rows)):
        prev_close = rows[i - 1].close
        if prev_close <= 0:
            continue
        pct = abs(rows[i].close - prev_close) / prev_close * 100.0
        if best is None or pct > best.pct:
            best = _DailyMove(pct=pct, event_time=rows[i].event_time)
    return best


def _larger_move(a: _DailyMove | None, b: _DailyMove | None) -> _DailyMove | None:
    """Return whichever move is larger (``None`` only if both are ``None``)."""
    if a is None:
        return b
    if b is None:
        return a
    return a if a.pct >= b.pct else b


def _persist_actions(
    conn: sqlite3.Connection, ticker: str, knowable_time: str
) -> None:
    """Fetch ``ticker``'s corporate actions and persist them (fetch is the only net).

    A fetch failure is logged and re-raised -- never swallowed. Both splits and
    dividends are stored; dividends are kept for the later dividend-adjustment
    refinement and do not affect prices today.
    """
    try:
        fetched = corporate_actions.fetch_actions(ticker)
    except corporate_actions.ActionsFetchError:
        logger.exception("reconcile: corporate-action fetch failed for %s", ticker)
        raise

    actions = [
        store.CorporateAction(
            ticker=record["ticker"],
            event_time=record["event_time"],
            action_type=record["action_type"],
            value=record["value"],
            knowable_time=knowable_time,
            source=record["source"],
        )
        for record in fetched
    ]
    if actions:
        store.write_corporate_actions(conn, actions)


def _write_or_rebuild_clean(
    conn: sqlite3.Connection,
    ticker: str,
    clean_rows: Sequence[store.PriceClean],
    knowable_time: str,
) -> int:
    """Write ``clean_rows``, rebuilding atomically only if the data has changed.

    If the existing CLEAN rows already match (same data, ignoring knowable_time),
    this is a no-op and returns 0 (idempotent). Otherwise the existing rows are
    archived to quarantine and replaced atomically. Returns rows written.
    """
    existing = _read_clean_signatures(conn, ticker)
    fresh: dict[str, _Signature] = {
        r.event_time: (
            r.open,
            r.high,
            r.low,
            r.close,
            r.volume,
            r.adj_close,
            r.source,
        )
        for r in clean_rows
    }
    if existing == fresh:
        return 0  # identical data already present -- nothing to do

    superseded = [
        _quarantine(
            ticker,
            event_time,
            _signature_payload(event_time, sig),
            QuarantineReason.SUPERSEDED_BY_REBUILD.value,
            knowable_time,
        )
        for event_time, sig in existing.items()
    ]
    return store.replace_price_clean(conn, ticker, list(clean_rows), superseded)


def reconcile(
    tickers: Sequence[str], db_path: store.DbPath
) -> ReconciliationSummary:
    """Reconcile RAW->CLEAN (verify-and-copy) for ``tickers``; return the summary.

    ``knowable_time`` is stamped once at the start of the run, so every row this
    run writes shares one consistent "as of" instant. Per ticker: persist
    corporate actions, verify split continuity (raises on a discontinuity), then
    copy the validated raw bars into ``price_clean`` (rebuilding if they changed).
    """
    requested = tuple(tickers)
    knowable_time = now_utc_iso()
    store.init_db(db_path)  # idempotent; ensures corporate_actions + price_clean

    rows_raw = 0
    rows_valid = 0
    rows_quarantined = 0
    rows_written_clean = 0
    splits_checked: list[SplitCheck] = []
    max_move: _DailyMove | None = None

    conn = store.connect(db_path)
    try:
        for ticker in requested:
            _persist_actions(conn, ticker, knowable_time)
            splits = _read_splits(conn, ticker)
            raw_bars = _read_raw_bars(conn, ticker)
            rows_raw += len(raw_bars)
            if not raw_bars:
                continue

            # Verify the source pre-adjusted every known split (raises if not).
            splits_checked.extend(
                _verify_splits(conn, ticker, raw_bars, splits, knowable_time)
            )

            # CLEAN is a validated COPY of RAW -- no re-adjustment.
            clean_rows: list[store.PriceClean] = []
            quarantine_rows: list[store.QuarantineRow] = []
            for bar in raw_bars:
                reason = _classify_clean_row(bar)
                if reason is None:
                    clean_rows.append(
                        store.PriceClean(
                            ticker=ticker,
                            event_time=bar.event_time,
                            open=bar.open,
                            high=bar.high,
                            low=bar.low,
                            close=bar.close,
                            volume=bar.volume,
                            adj_close=bar.close,  # splits-only; dividends later
                            knowable_time=knowable_time,
                            source=bar.source,
                        )
                    )
                else:
                    quarantine_rows.append(
                        _quarantine(
                            ticker,
                            bar.event_time,
                            _sanity_payload(bar),
                            reason.value,
                            knowable_time,
                        )
                    )

            rows_valid += len(clean_rows)
            rows_quarantined += len(quarantine_rows)
            if quarantine_rows:
                store.write_quarantine(conn, quarantine_rows)

            rows_written_clean += _write_or_rebuild_clean(
                conn, ticker, clean_rows, knowable_time
            )
            max_move = _larger_move(max_move, _max_close_move(clean_rows))
    finally:
        conn.close()

    summary = ReconciliationSummary(
        requested_tickers=requested,
        rows_raw=rows_raw,
        rows_written_clean=rows_written_clean,
        rows_quarantined=rows_quarantined,
        rows_skipped_duplicate=rows_valid - rows_written_clean,
        splits_checked=tuple(splits_checked),
        max_abs_daily_close_move_pct=None if max_move is None else max_move.pct,
        max_abs_daily_close_move_date=(
            None if max_move is None else max_move.event_time
        ),
    )
    logger.info("reconcile summary: %s", summary)
    return summary
