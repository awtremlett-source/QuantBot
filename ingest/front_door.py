"""The front door: sanity/scale-check fetched bars, then write RAW or quarantine.

This is where untrusted external data is admitted into the store. For each
requested ticker we fetch daily bars, run every bar through a fixed battery of
checks, and route it to exactly one of two places:

* a clean bar -> ``price_raw`` (idempotent write), or
* a rejected bar -> ``quarantine`` with a SPECIFIC reason (append-only).

Nothing is written unchecked; nothing rejected is silently dropped. Each run
returns -- and logs as one line -- a :class:`ReconciliationSummary` so the
counts always balance: ``rows_fetched == rows_valid + rows_quarantined`` and
``rows_valid == rows_written + rows_skipped_duplicate`` (per run).

Scope: RAW only. No price adjustment / CLEAN reconciliation happens here.
"""

from __future__ import annotations

import json
import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from data_store import store
from data_store.store import PriceRaw, QuarantineRow
from data_store.timeutils import now_utc_iso, validate_iso
from ingest import yfinance_source
from ingest.yfinance_source import DailyBar, FetchError

logger = logging.getLogger(__name__)

# Domain tag stored on every quarantine row this module writes.
_PRICE_DOMAIN = "price"
# Source tag stored on every price_raw row this module writes.
_SOURCE = "yfinance"
# A close that moves more than this fraction vs the previous valid bar is suspect.
_MAX_CLOSE_MOVE = 0.5


class QuarantineReason(StrEnum):
    """Specific, machine-readable reasons a bar is rejected to quarantine.

    The per-bar reasons are checked in the order listed and the FIRST match wins.
    DUPLICATE_IN_BATCH is detected separately, at batch level, before per-bar
    classification.
    """

    MALFORMED_EVENT_TIME = "malformed_event_time"
    NAN_OR_INF_PRICE = "nan_or_inf_price"
    NON_POSITIVE_PRICE = "non_positive_price"
    OHLC_INCONSISTENT = "ohlc_inconsistent"
    BAD_VOLUME = "negative_or_nan_volume"
    FUTURE_BAR = "future_bar"
    SUSPECT_JUMP = "suspect_jump"
    DUPLICATE_IN_BATCH = "duplicate_in_batch"


@dataclass(frozen=True, slots=True)
class ReconciliationSummary:
    """What one ingest run did, in numbers that must reconcile.

    Invariants (per run):
        rows_fetched == rows_valid + rows_quarantined
        rows_valid   == rows_written + rows_skipped_duplicate
    """

    requested_tickers: tuple[str, ...]
    failed_tickers: tuple[str, ...]
    rows_fetched: int
    rows_valid: int
    rows_quarantined: int
    rows_written: int
    rows_skipped_duplicate: int


def _is_nonfinite(value: float) -> bool:
    """True if ``value`` is NaN or +/-inf."""
    return math.isnan(value) or math.isinf(value)


def _json_safe(bar: DailyBar) -> dict[str, object]:
    """Return a JSON-serialisable copy of ``bar`` (non-finite floats -> text).

    ``json.dumps`` would emit bare ``NaN``/``Infinity`` tokens (invalid JSON), so
    we stringify non-finite numbers to keep the quarantine payload valid JSON.
    """
    safe: dict[str, object] = {}
    for key, value in bar.items():
        if isinstance(value, float) and not math.isfinite(value):
            safe[key] = repr(value)  # "nan", "inf", "-inf"
        else:
            safe[key] = value
    return safe


def _quarantine_row(
    bar: DailyBar, reason: QuarantineReason, knowable_time: str
) -> QuarantineRow:
    """Build a QuarantineRow that preserves ``bar`` verbatim as JSON."""
    return QuarantineRow(
        domain=_PRICE_DOMAIN,
        ticker=bar["ticker"],
        event_time=bar["event_time"],
        payload=json.dumps(_json_safe(bar), sort_keys=True),
        reason=reason.value,
        knowable_time=knowable_time,
    )


def _classify_bar(
    bar: DailyBar,
    knowable_time: str,
    prev_close: float | None,
) -> QuarantineReason | None:
    """Return the reason ``bar`` should be quarantined, or ``None`` if it is valid.

    ``prev_close`` is the close of the previous *valid* bar for this ticker (in
    event_time order), or ``None`` if there isn't one yet -- used for the jump
    check so a bad intervening bar can't poison the comparison.
    """
    # Boundary defense: a non-canonical event_time would make the future-bar
    # string comparison meaningless and would crash the downstream write. Catch
    # it here and route to quarantine rather than letting it abort the run.
    try:
        validate_iso(bar["event_time"])
    except ValueError:
        return QuarantineReason.MALFORMED_EVENT_TIME

    prices = (bar["open"], bar["high"], bar["low"], bar["close"])

    if any(_is_nonfinite(price) for price in prices):
        return QuarantineReason.NAN_OR_INF_PRICE
    if any(price <= 0 for price in prices):
        return QuarantineReason.NON_POSITIVE_PRICE

    open_, high, low, close = prices
    # The third clause (low <= high) is logically implied by the first two; it is
    # kept to match the spec's stated OHLC formula verbatim.
    if not (low <= min(open_, close) and max(open_, close) <= high and low <= high):
        return QuarantineReason.OHLC_INCONSISTENT

    volume = bar["volume"]
    if _is_nonfinite(volume) or volume < 0:
        return QuarantineReason.BAD_VOLUME

    if bar["event_time"] > knowable_time:  # canonical ISO sorts chronologically
        return QuarantineReason.FUTURE_BAR

    if prev_close is not None and prev_close > 0:
        if abs(close - prev_close) / prev_close > _MAX_CLOSE_MOVE:
            return QuarantineReason.SUSPECT_JUMP

    return None


def _classify_ticker(
    ticker: str,
    bars: Sequence[DailyBar],
    knowable_time: str,
) -> tuple[list[PriceRaw], list[QuarantineRow]]:
    """Split one ticker's bars into (valid price_raw rows, quarantine rows).

    Bars are processed in event_time order so the jump check compares each close
    against the previous *valid* close.
    """
    valid: list[PriceRaw] = []
    quarantined: list[QuarantineRow] = []
    prev_close: float | None = None
    seen_event_times: set[str] = set()

    for bar in sorted(bars, key=lambda b: b["event_time"]):
        event_time = bar["event_time"]
        if event_time in seen_event_times:
            # A second bar claims a session we already processed. The idempotent
            # write would silently DROP it (ON CONFLICT DO NOTHING) and the count
            # would mislabel it a benign duplicate -- so instead preserve it in
            # quarantine. This keeps rows_skipped_duplicate meaning strictly
            # "already in the store from a prior run".
            quarantined.append(
                _quarantine_row(bar, QuarantineReason.DUPLICATE_IN_BATCH, knowable_time)
            )
            continue
        seen_event_times.add(event_time)

        reason = _classify_bar(bar, knowable_time, prev_close)
        if reason is None:
            valid.append(
                PriceRaw(
                    ticker=bar["ticker"],
                    event_time=bar["event_time"],
                    open=bar["open"],
                    high=bar["high"],
                    low=bar["low"],
                    close=bar["close"],
                    volume=int(bar["volume"]),
                    knowable_time=knowable_time,
                    source=_SOURCE,
                )
            )
            prev_close = bar["close"]
        else:
            quarantined.append(_quarantine_row(bar, reason, knowable_time))

    return valid, quarantined


def ingest(
    tickers: Sequence[str],
    db_path: store.DbPath,
    start: str | None = None,
    end: str | None = None,
) -> ReconciliationSummary:
    """Fetch, check, and store daily RAW bars for ``tickers``; return the summary.

    ``knowable_time`` is stamped once, at the start of the run, so every row from
    this run shares one consistent "as of" instant. A fetch failure for one
    ticker is logged and recorded in ``failed_tickers`` -- it never aborts the run
    or other tickers.
    """
    requested = tuple(tickers)
    knowable_time = now_utc_iso()
    store.init_db(db_path)  # idempotent; ensures price_raw + quarantine exist

    failed: list[str] = []
    rows_fetched = 0
    rows_valid = 0
    rows_quarantined = 0
    rows_written = 0

    conn = store.connect(db_path)
    try:
        for ticker in requested:
            try:
                bars = yfinance_source.fetch_daily(ticker, start=start, end=end)
            except FetchError as exc:
                logger.error("ingest fetch failed for %s: %s", ticker, exc)
                failed.append(ticker)
                continue

            rows_fetched += len(bars)
            valid, quarantined = _classify_ticker(ticker, bars, knowable_time)
            rows_valid += len(valid)
            rows_quarantined += len(quarantined)

            if quarantined:
                store.write_quarantine(conn, quarantined)
            if valid:
                rows_written += store.write_price_raw(conn, valid)
    finally:
        conn.close()

    summary = ReconciliationSummary(
        requested_tickers=requested,
        failed_tickers=tuple(failed),
        rows_fetched=rows_fetched,
        rows_valid=rows_valid,
        rows_quarantined=rows_quarantined,
        rows_written=rows_written,
        rows_skipped_duplicate=rows_valid - rows_written,
    )
    logger.info("ingest summary: %s", summary)
    return summary
