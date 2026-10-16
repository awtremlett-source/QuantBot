"""The two data fingerprints of S6 batch 1 (QT-18 B2): proof the data did not move mid-run.

(a) **trial data** -- every 1h bar the walk-forward trials read (every bot name,
    GBPUSD included, bars dated before the 1h seal, 2026-07-13) and every earnings
    row the P15 history is built from (knowable by p15_history's cutoff);
(b) **holdout data** -- the sealed 1h bars and GBPUSD dated 2026-07-13 -> 2026-10-09,
    the bars the single holdout run reads.

Bars the recorder adds from 2026-10-10 on, and earnings snapshots knowable after the
cutoff, are in NEITHER: the recorder running during the box is expected and is not
a data change. A real change to a read bar is caught: each frame is hashed by its
CONTENT inside the date range (timestamps and every column, sorted), not by file
bytes, so an appended day leaves the hash alone and an altered bar does not.

The hash of (b) reads sealed bytes and shows only a SHA-256: no price is displayed,
nothing is scored. It lives in the data layer, beside access.bars, because research
code may not read bars around holdout.py's door (tests/wall/test_sealed_doors.py).
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from qb2.data import access
from qb2.ingest import daily, dividends, earnings

SEALED_FROM = date(2026, 7, 13)               # = holdout.SEALED_FROM["1h"] (a test pins it)
HOLDOUT_END = date(2026, 10, 9)
EARNINGS_CUTOFF = datetime(2026, 10, 9, 23, 59, 59, tzinfo=timezone.utc)
FX = "GBPUSD=X"
OHLC = ("open", "high", "low", "close")


def _frame_digest(frame: pd.DataFrame) -> str:
    frame = frame.sort_index(axis=1)
    body = pd.util.hash_pandas_object(frame, index=True).to_numpy().tobytes()
    head = ",".join(map(str, frame.columns)).encode()
    return hashlib.sha256(head + body).hexdigest()


def _in_range(frame: pd.DataFrame, first: date | None, last: date | None) -> pd.DataFrame:
    days = pd.Series(pd.DatetimeIndex(frame.index).date, index=frame.index)
    keep = pd.Series(True, index=frame.index)
    if first is not None:
        keep &= days >= first
    if last is not None:
        keep &= days <= last
    return frame[keep.to_numpy()]


def bars_digest(symbols: Iterable[str], first: date | None, last: date | None,
                clean_root: Path | None = None) -> str:
    """One hash over every name's 1h bars dated first..last (inclusive), by content."""
    parts = []
    for symbol in sorted(set(symbols)):
        try:
            frame = _in_range(access.bars(symbol, "1h", clean_root=clean_root), first, last)
        except access.AccessRefused:
            frame = pd.DataFrame()
        parts.append(f"{symbol}:{len(frame)}:{_frame_digest(frame) if len(frame) else '-'}")
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def daily_digest(symbols: Iterable[str], first: date | None, last: date | None,
                 clean_root: Path | None = None) -> str:
    """QT-19: one hash over every name's DAILY open/high/low/close dated first..last, by
    content -- the columns a daily run reads (a revised volume is not a data change)."""
    parts = []
    for symbol in sorted(set(symbols)):
        raw = daily.load(symbol, clean_root)
        frame = pd.DataFrame() if raw is None else _in_range(raw[list(OHLC)], first, last)
        parts.append(f"{symbol}:{len(frame)}:{_frame_digest(frame) if len(frame) else '-'}")
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def dividends_digest(symbols: Iterable[str], clean_root: Path | None = None) -> str:
    """QT-19: every dividend row a daily run may credit (verdict OK), per name, by content."""
    parts = []
    for symbol in sorted(set(symbols)):
        raw = dividends.load(symbol, clean_root)
        rows = pd.DataFrame() if raw is None else raw[raw["verdict"] == "OK"][
            ["ex_date", "amount", "currency"]].astype(str).reset_index(drop=True)
        parts.append(f"{symbol}:{len(rows)}:{_frame_digest(rows) if len(rows) else '-'}")
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def earnings_digest(symbols: Iterable[str], clean_root: Path | None = None) -> str:
    """Every earnings row knowable by the cutoff, per name, by content."""
    parts = []
    for symbol in sorted(set(symbols)):
        raw = earnings.load(symbol, clean_root)
        if raw is None:
            parts.append(f"{symbol}:none")
            continue
        known = raw[pd.to_datetime(raw["knowable_time"], utc=True) <= pd.Timestamp(EARNINGS_CUTOFF)]
        rows = known.astype(str).sort_values(list(known.columns)).reset_index(drop=True)
        parts.append(f"{symbol}:{len(rows)}:{_frame_digest(rows) if len(rows) else '-'}")
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def trial_data(symbols: Iterable[str], shares: Iterable[str],
               clean_root: Path | None = None) -> str:
    """(a): unsealed 1h bars of the names and GBPUSD, plus the shares' earnings rows."""
    names = list(symbols) + [FX]
    last = date.fromordinal(SEALED_FROM.toordinal() - 1)
    return hashlib.sha256((bars_digest(names, None, last, clean_root) + "|" +
                           earnings_digest(shares, clean_root)).encode()).hexdigest()


def holdout_data(symbols: Iterable[str], clean_root: Path | None = None) -> str:
    """(b): sealed 1h bars of the names and GBPUSD, 2026-07-13 -> 2026-10-09."""
    return bars_digest(list(symbols) + [FX], SEALED_FROM, HOLDOUT_END, clean_root)
