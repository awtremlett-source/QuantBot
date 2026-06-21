"""Fetch daily OHLCV bars from yfinance.

This module is deliberately thin and isolated: it is the ONLY place that talks
to yfinance, so the rest of the pipeline depends on the plain-dict contract of
:func:`fetch_daily` rather than on yfinance itself. Tests mock :func:`fetch_daily`
and therefore run fully offline.

Contract: :func:`fetch_daily` returns a list of :class:`DailyBar` dicts, or
raises :class:`FetchError`. It never returns an empty list silently -- an empty
result is an error the front door should see and log.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TypedDict

import pandas as pd
import yfinance as yf

from data_store.timeutils import to_utc_iso


class DailyBar(TypedDict):
    """One raw daily bar as handed to the front door.

    Numeric fields are ``float`` -- including ``volume`` -- so that missing or
    malformed source values (NaN/inf) survive transport intact and can be
    *rejected* by the front door rather than blowing up here. The front door
    casts ``volume`` to ``int`` only once a bar has passed its checks.
    """

    ticker: str
    event_time: str  # canonical UTC ISO-8601, e.g. "2026-06-15T00:00:00Z"
    open: float
    high: float
    low: float
    close: float
    volume: float


class FetchError(RuntimeError):
    """Raised when a fetch fails or returns no usable data.

    The front door catches this per ticker, logs it, and records the ticker as
    failed -- it is never swallowed silently.
    """


def _bar_date_to_event_time(index_value: object) -> str:
    """Convert a pandas row index (a date/Timestamp) to canonical 00:00:00Z ISO."""
    ts = pd.Timestamp(index_value)
    return to_utc_iso(datetime(ts.year, ts.month, ts.day, tzinfo=timezone.utc))


def fetch_daily(
    ticker: str,
    start: str | None = None,
    end: str | None = None,
) -> list[DailyBar]:
    """Fetch daily OHLCV bars for ``ticker`` over ``[start, end]`` from yfinance.

    Uses ``auto_adjust=False`` (we ingest RAW, unadjusted bars; adjustment is a
    later brick) at daily interval. The bar's session date becomes ``event_time``
    as canonical UTC ISO-8601 at midnight (``...T00:00:00Z``).

    Raises :class:`FetchError` on any download failure or empty result.
    """
    try:
        frame = yf.download(
            ticker,
            start=start,
            end=end,
            interval="1d",
            auto_adjust=False,
            actions=False,
            progress=False,
        )
    except Exception as exc:
        # Isolation boundary: any yfinance failure becomes a FetchError. This is
        # a re-raise (chained via `from`), not a swallow -- the front door logs it.
        raise FetchError(f"yfinance download failed for {ticker!r}: {exc}") from exc

    if frame is None or frame.empty:
        raise FetchError(
            f"yfinance returned no rows for {ticker!r} "
            f"(start={start!r}, end={end!r})"
        )

    # For a single ticker, recent yfinance returns MultiIndex columns
    # (field, ticker); flatten to plain field columns.
    if isinstance(frame.columns, pd.MultiIndex):
        frame = frame.droplevel(axis=1, level=-1)

    bars: list[DailyBar] = []
    for index_value, row in frame.iterrows():
        bars.append(
            DailyBar(
                ticker=ticker,
                event_time=_bar_date_to_event_time(index_value),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=float(row["Volume"]),
            )
        )
    return bars
