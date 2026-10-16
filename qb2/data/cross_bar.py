"""Cross-bar checks on a daily line, run on EVERY daily write (QT-21 A1).

A one-bar sanity check (front_door.impossible_rows) cannot see these; QT-20's census
found both in the advisor trials' data, and a book could hold one of them.

**Unit break.** A bar whose open is >= 3x or <= 1/3 of the previous close: the feed
changed unit or line overnight (SMEA.L 2023-11-27, x114.6; FWRG.L's first rows at 1/77).
No real overnight move on the lists comes near: the largest since 2010 is x0.62 (VRT,
2022-02-23), then the Brexit vote (x0.65). The line is cut at every break; stretches
whose unit agrees (the product of the breaks between them inside 1/3..3) are one unit;
the unit with the most rows is the line's own (a tie: the latest), and every other
stretch is quarantined -- never multiplied back (SCARS #22).

**Filler.** Rows before the line's first traded bar. A listed share trades every
session, so its line starts at its first 20 sessions in a row with trades; before that
are placeholders and another venue's prices (EDV.L before its London listing on
2021-06-14: flat zero-volume rows and sporadic Toronto-dollar trades). A London ETF is
quoted by market makers, so a later no-trade day still carries a real quote (QT-21 M3):
its line starts at its first trade. A line with no such start yet keeps every row.
Rates and indices have no volume: no filler rule.

**Sticky.** Every row ever quarantined is kept in quarantine/daily/<symbol>-crossbar.parquet
with its reason and the UTC date it was found, and stays out of the series on every
later write: the nightly full re-fetch cannot bring it back. Lifting one = the
operator's words. Starting figures (standing GO 2026-10-07): 3x, 20 sessions.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from qb2.data.front_door import CLEAN, _append_manifest, _write_parquet_atomically

UNIT_BREAK = 3.0                 # STARTING FIGURE: open vs previous close, either way
SHARE_RUN = 20                   # STARTING FIGURE: a share's line starts at 20 traded sessions
TRADED_KINDS = frozenset({"STOCK", "ETF"})
UNIT, FILLER = "unit_break", "filler"


def _units(o: np.ndarray, c: np.ndarray) -> np.ndarray:
    """True on rows outside the line's own unit (one pass; see unit_break_rows)."""
    n = len(o)
    ratio = o[1:] / c[:-1]
    cut = np.flatnonzero((ratio >= UNIT_BREAK) | (ratio <= 1.0 / UNIT_BREAK)) + 1
    out = np.zeros(n, dtype=bool)
    if not cut.size:
        return out
    starts, ends = np.r_[0, cut], np.r_[cut, n]
    level = np.r_[0.0, np.cumsum(np.log(ratio[cut - 1]))]        # each stretch's unit, logged
    same = np.abs(level[:, None] - level[None, :]) < np.log(UNIT_BREAK)
    rows = same @ (ends - starts)
    ref = int(np.flatnonzero(rows == rows.max())[-1])            # most rows; a tie: the latest
    for i in np.flatnonzero(~same[ref]):
        out[starts[i]:ends[i]] = True
    return out


def unit_break_rows(frame: pd.DataFrame) -> np.ndarray:
    """Rows on the wrong side of a unit break, repeated until the kept rows have none."""
    out = np.zeros(len(frame), dtype=bool)
    o, c = frame["open"].to_numpy(dtype=float), frame["close"].to_numpy(dtype=float)
    while True:
        keep = np.flatnonzero(~out)
        if len(keep) < 2:
            return out
        more = _units(o[keep], c[keep])
        if not more.any():
            return out
        out[keep[more]] = True


def filler_rows(frame: pd.DataFrame, kind: str) -> np.ndarray:
    """Rows before the line's first traded bar (a share: its first 20-session run)."""
    out = np.zeros(len(frame), dtype=bool)
    if kind not in TRADED_KINDS or "volume" not in frame.columns:
        return out
    traded = frame["volume"].to_numpy(dtype=float) > 0
    run = 1 if kind == "ETF" else SHARE_RUN
    if len(traded) < run:
        return out
    full = np.convolve(traded.astype(int), np.ones(run, dtype=int), "valid") == run
    if full.any():
        out[:int(np.argmax(full))] = True
    return out


def found(frame: pd.DataFrame, kind: str) -> pd.Series:
    """Each quarantined row's reason ("" = kept): unit breaks first, then filler on the
    line that is left (the first traded bar ON THAT LINE)."""
    reason = np.full(len(frame), "", dtype=object)
    unit = unit_break_rows(frame)
    reason[unit] = UNIT
    rest = np.flatnonzero(~unit)
    reason[rest[filler_rows(frame.iloc[rest], kind)]] = FILLER
    return pd.Series(reason, index=frame.index, dtype=object)


def ledger_path(symbol: str, clean_root: Path | None = None) -> Path:
    return (clean_root or CLEAN) / "quarantine" / "daily" / f"{symbol}-crossbar.parquet"


def load_ledger(symbol: str, clean_root: Path | None = None) -> pd.DataFrame | None:
    path = ledger_path(symbol, clean_root)
    return pd.read_parquet(path) if path.is_file() else None


def _days(index: pd.Index) -> np.ndarray:
    return np.asarray(pd.DatetimeIndex(index).date)


def apply(frame: pd.DataFrame, symbol: str, kind: str, *, now: datetime,
          clean_root: Path | None = None) -> tuple[pd.DataFrame, int]:
    """The series without its quarantined rows, and how many were found NEW this time.

    The rules run on the frame as handed in; their rows join the ledger (with today's
    date), and every row already in the ledger stays out, found again or not."""
    frame = frame.sort_index()
    why = found(frame, kind)
    old = load_ledger(symbol, clean_root)
    seen = set(_days(old.index)) if old is not None else set()
    days = _days(frame.index)
    known = np.array([d in seen for d in days], dtype=bool)
    new = (why != "").to_numpy() & ~known
    if new.any():
        add = frame[new].copy()
        add["reason"], add["found"] = why[new].to_numpy(), now.date().isoformat()
        ledger = add if old is None else pd.concat([old, add]).sort_index()
        _write_parquet_atomically(ledger, ledger_path(symbol, clean_root))
        for reason in sorted(set(add["reason"])):
            mine = add[add["reason"] == reason]
            _append_manifest({
                "event": "quarantine", "table": "daily", "symbol": symbol,
                "at": now.isoformat(timespec="seconds"), "rows": int(len(mine)),
                "reason": reason, "first": str(mine.index.min()), "last": str(mine.index.max()),
                "note": "kept in the ledger; never back in the series (cross_bar.py)"}, clean_root)
    return frame[~(known | (why != "").to_numpy())], int(new.sum())
