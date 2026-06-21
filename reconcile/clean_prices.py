"""RAW->CLEAN price reconciliation: split-adjust raw bars and write price_clean.

This is the bridge from ingested data (``price_raw``) to the series the rest of
the system reads (``price_clean``, served by ``read_price_asof``). For each
ticker it:

1. fetches corporate actions and persists them to ``corporate_actions`` (the only
   network call in the whole brick), then
2. reads that ticker's raw bars and its persisted splits from the store, and
3. split-adjusts every bar, re-runs the same row sanity checks ingest uses, and
   routes each adjusted bar to ``price_clean`` (valid) or ``quarantine`` (bad).

SPLIT ADJUSTMENT ONLY -- this is deliberate scope. A bar's ``split_factor`` is the
product of every split ratio whose action ``event_time`` is STRICTLY AFTER the
bar: bars before a 10-for-1 split divide by 10, bars on/after keep factor 1. The
adjusted close is written to both ``close`` and ``adj_close``.

LATER REFINEMENT (out of scope here): dividend adjustment. Dividends ARE fetched
and persisted to ``corporate_actions``, but they do not yet affect prices. When
added, ``adj_close`` will carry the split+dividend (total-return) close while
``close`` stays split-only -- which is why they are separate columns today.
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


class QuarantineReason(StrEnum):
    """Why an adjusted bar was rejected from price_clean (checked in order).

    These mirror the ingest reasons (same string values) so a rejection means the
    same thing wherever it is raised. The ingest-only reasons (future bar, suspect
    jump, duplicate-in-batch, malformed event_time) cannot occur here: the input
    is already-validated RAW rows, one per session, read from the store.
    """

    NAN_OR_INF_PRICE = "nan_or_inf_price"
    NON_POSITIVE_PRICE = "non_positive_price"
    OHLC_INCONSISTENT = "ohlc_inconsistent"
    BAD_VOLUME = "negative_or_nan_volume"


@dataclass(frozen=True, slots=True)
class AppliedSplit:
    """A split that affected the series: its action time and ratio."""

    event_time: str
    ratio: float


@dataclass(frozen=True, slots=True)
class ReconciliationSummary:
    """What one reconcile run did, in numbers that must reconcile.

    Invariant (per run):
        rows_raw == rows_written_clean + rows_skipped_duplicate + rows_quarantined

    ``max_abs_daily_close_move_pct`` is the largest absolute day-over-day percent
    move in the ADJUSTED close series (with the ``event_time`` it occurred on); it
    is ``None`` when there are fewer than two valid bars. A correctly split-
    adjusted series shows only small moves -- a ~90% jump would betray an unadjusted
    split.
    """

    requested_tickers: tuple[str, ...]
    rows_raw: int
    rows_written_clean: int
    rows_quarantined: int
    rows_skipped_duplicate: int
    splits_applied: tuple[AppliedSplit, ...]
    max_abs_daily_close_move_pct: float | None
    max_abs_daily_close_move_date: str | None


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
class _AdjustedBar:
    """A split-adjusted OHLCV bar, pre-sanity-check."""

    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass(frozen=True, slots=True)
class _DailyMove:
    """A day-over-day percent close move and the event_time it landed on."""

    pct: float
    event_time: str


def split_factor(event_time: str, splits: Sequence[AppliedSplit]) -> float:
    """Return the divisor for a bar at ``event_time`` given ``splits``.

    The factor is the product of every split ratio whose action event_time is
    STRICTLY AFTER ``event_time``. A bar before two splits (ratios 2 then 4) gets
    factor 8; a bar on/after all splits gets factor 1. (Canonical UTC ISO sorts
    chronologically as plain text, so the comparison is a string comparison.)
    """
    factor = 1.0
    for split in splits:
        if split.event_time > event_time:
            factor *= split.ratio
    return factor


def _is_nonfinite(value: float) -> bool:
    """True if ``value`` is NaN or +/-inf."""
    return math.isnan(value) or math.isinf(value)


def _adjust(bar: _RawBar, factor: float) -> _AdjustedBar:
    """Split-adjust ``bar``: prices divided by ``factor``, volume scaled up by it."""
    return _AdjustedBar(
        open=bar.open / factor,
        high=bar.high / factor,
        low=bar.low / factor,
        close=bar.close / factor,
        volume=round(bar.volume * factor),
    )


def _classify_clean_row(bar: _AdjustedBar) -> QuarantineReason | None:
    """Return why ``bar`` should be quarantined, or ``None`` if it is valid.

    The same battery ingest applies at the RAW boundary, re-run on the ADJUSTED
    values -- defense in depth, since adjustment (or a bad row written straight to
    price_raw) could yield a non-finite, non-positive, or inconsistent bar.
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


def _json_safe(payload: dict[str, object]) -> dict[str, object]:
    """Return a JSON-serialisable copy of ``payload`` (non-finite floats -> text)."""
    safe: dict[str, object] = {}
    for key, value in payload.items():
        if isinstance(value, float) and not math.isfinite(value):
            safe[key] = repr(value)
        else:
            safe[key] = value
    return safe


def _quarantine_row(
    ticker: str,
    bar: _RawBar,
    adjusted: _AdjustedBar,
    factor: float,
    reason: QuarantineReason,
    knowable_time: str,
) -> store.QuarantineRow:
    """Build a QuarantineRow preserving both the raw bar and the adjustment."""
    payload: dict[str, object] = {
        "ticker": ticker,
        "event_time": bar.event_time,
        "raw_open": bar.open,
        "raw_high": bar.high,
        "raw_low": bar.low,
        "raw_close": bar.close,
        "raw_volume": bar.volume,
        "split_factor": factor,
        "adj_open": adjusted.open,
        "adj_high": adjusted.high,
        "adj_low": adjusted.low,
        "adj_close": adjusted.close,
        "adj_volume": adjusted.volume,
        "source": bar.source,
    }
    return store.QuarantineRow(
        domain=_DOMAIN,
        ticker=ticker,
        event_time=bar.event_time,
        payload=json.dumps(_json_safe(payload), sort_keys=True),
        reason=reason.value,
        knowable_time=knowable_time,
    )


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


def _read_splits(conn: sqlite3.Connection, ticker: str) -> list[AppliedSplit]:
    """Read ``ticker``'s persisted splits from corporate_actions, ascending."""
    cursor = conn.execute(
        "SELECT event_time, value FROM corporate_actions "
        "WHERE ticker = ? AND action_type = ? ORDER BY event_time ASC",
        (ticker, corporate_actions.ACTION_SPLIT),
    )
    return [
        AppliedSplit(event_time=str(row[0]), ratio=float(row[1]))
        for row in cursor.fetchall()
    ]


def _max_close_move(rows: Sequence[store.PriceClean]) -> _DailyMove | None:
    """Largest abs day-over-day percent close move across the adjusted series."""
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

    A fetch failure is logged and re-raised -- never swallowed. We fail loud here
    rather than silently produce a possibly-wrong adjustment from missing splits.
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


def reconcile(
    tickers: Sequence[str], db_path: store.DbPath
) -> ReconciliationSummary:
    """Reconcile RAW->CLEAN (split-adjusted) for ``tickers``; return the summary.

    ``knowable_time`` is stamped once, at the start of the run, so every row this
    run writes (corporate actions and clean bars) shares one consistent "as of"
    instant. Per ticker: persist corporate actions, then derive the clean series
    from the store (price_raw + persisted splits). Idempotent: re-running writes
    no new clean rows and reports them as skipped duplicates.
    """
    requested = tuple(tickers)
    knowable_time = now_utc_iso()
    store.init_db(db_path)  # idempotent; ensures corporate_actions + price_clean

    rows_raw = 0
    rows_valid = 0
    rows_quarantined = 0
    rows_written_clean = 0
    splits_applied: list[AppliedSplit] = []
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

            # A split is "applied" iff at least one bar precedes it (the earliest
            # bar is strictly before it -> the strict-after test divides that bar).
            earliest = raw_bars[0].event_time
            splits_applied.extend(s for s in splits if s.event_time > earliest)

            clean_rows: list[store.PriceClean] = []
            quarantine_rows: list[store.QuarantineRow] = []
            for bar in raw_bars:
                factor = split_factor(bar.event_time, splits)
                adjusted = _adjust(bar, factor)
                reason = _classify_clean_row(adjusted)
                if reason is None:
                    clean_rows.append(
                        store.PriceClean(
                            ticker=ticker,
                            event_time=bar.event_time,
                            open=adjusted.open,
                            high=adjusted.high,
                            low=adjusted.low,
                            close=adjusted.close,
                            volume=adjusted.volume,
                            adj_close=adjusted.close,  # split-only: == close
                            knowable_time=knowable_time,
                            source=bar.source,
                        )
                    )
                else:
                    quarantine_rows.append(
                        _quarantine_row(
                            ticker, bar, adjusted, factor, reason, knowable_time
                        )
                    )

            rows_valid += len(clean_rows)
            rows_quarantined += len(quarantine_rows)
            if quarantine_rows:
                store.write_quarantine(conn, quarantine_rows)
            if clean_rows:
                rows_written_clean += store.write_price_clean(conn, clean_rows)

            max_move = _larger_move(max_move, _max_close_move(clean_rows))
    finally:
        conn.close()

    summary = ReconciliationSummary(
        requested_tickers=requested,
        rows_raw=rows_raw,
        rows_written_clean=rows_written_clean,
        rows_quarantined=rows_quarantined,
        rows_skipped_duplicate=rows_valid - rows_written_clean,
        splits_applied=tuple(splits_applied),
        max_abs_daily_close_move_pct=None if max_move is None else max_move.pct,
        max_abs_daily_close_move_date=(
            None if max_move is None else max_move.event_time
        ),
    )
    logger.info("reconcile summary: %s", summary)
    return summary
