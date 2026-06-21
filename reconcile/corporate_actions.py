"""Fetch corporate actions (splits & dividends) from yfinance.

Like :mod:`ingest.yfinance_source`, this module is deliberately thin and the ONLY
place that talks to yfinance for corporate actions. The reconciler depends on the
plain-dict contract of :func:`fetch_actions` rather than on yfinance itself, so
tests mock :func:`fetch_actions` and run fully offline.

Contract: :func:`fetch_actions` returns a list of :class:`ActionRecord` dicts
(possibly empty -- a ticker may legitimately have no actions), or raises
:class:`ActionsFetchError`. Both splits and dividends are returned; the caller
decides what to do with each ``action_type`` (the current cleaner adjusts on
splits only and merely persists dividends).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TypedDict

import pandas as pd
import yfinance as yf

from data_store.timeutils import to_utc_iso

# action_type values, matching the strings stored in corporate_actions.value's
# sibling column. Kept here next to the only code that produces them.
ACTION_SPLIT = "split"
ACTION_DIVIDEND = "dividend"

_SOURCE = "yfinance"


class ActionRecord(TypedDict):
    """One corporate action as handed to the reconciler.

    ``value`` is a split ratio when ``action_type == 'split'`` (e.g. ``10.0`` for
    a 10-for-1 split) and a cash dividend amount when ``action_type ==
    'dividend'``.
    """

    ticker: str
    event_time: str  # canonical UTC ISO-8601, e.g. "2024-06-10T00:00:00Z"
    action_type: str
    value: float
    source: str


class ActionsFetchError(RuntimeError):
    """Raised when fetching corporate actions fails.

    The caller logs and re-raises (or lets this propagate) -- it is never
    swallowed silently.
    """


def _index_to_event_time(index_value: object) -> str:
    """Convert a pandas index entry (a date/Timestamp) to canonical 00:00:00Z ISO."""
    ts = pd.Timestamp(index_value)
    return to_utc_iso(datetime(ts.year, ts.month, ts.day, tzinfo=timezone.utc))


def fetch_actions(ticker: str) -> list[ActionRecord]:
    """Fetch splits and dividends for ``ticker`` from yfinance.

    Returns one :class:`ActionRecord` per split and per dividend, with the action
    date rendered as canonical UTC ISO-8601 at midnight. An empty list is a valid
    result (the ticker has no recorded actions). Any download/parse failure is
    raised as :class:`ActionsFetchError` (chained, never swallowed).
    """
    try:
        handle = yf.Ticker(ticker)
        splits = handle.splits
        dividends = handle.dividends
    except Exception as exc:
        # Isolation boundary: any yfinance failure becomes an ActionsFetchError.
        raise ActionsFetchError(
            f"yfinance corporate-action fetch failed for {ticker!r}: {exc}"
        ) from exc

    actions: list[ActionRecord] = []
    for index_value, ratio in splits.items():
        actions.append(
            ActionRecord(
                ticker=ticker,
                event_time=_index_to_event_time(index_value),
                action_type=ACTION_SPLIT,
                value=float(ratio),
                source=_SOURCE,
            )
        )
    for index_value, amount in dividends.items():
        actions.append(
            ActionRecord(
                ticker=ticker,
                event_time=_index_to_event_time(index_value),
                action_type=ACTION_DIVIDEND,
                value=float(amount),
                source=_SOURCE,
            )
        )
    return actions
