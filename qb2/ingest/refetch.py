"""A re-fetch meets the stored file (QT-26 B): a closed session's sane stored row is never lost.

Every top-up re-fetches each name's whole history (daily.HISTORY_START) and wrote the file whole.
On Mon 26 Oct 06:17 UTC the provider sent VWRL.L's Fri 23 Oct bar with no close: the door set it
aside and the rewrite dropped the sane row stored on Friday after London's close, so the advisor
lost Friday for a day. Now, per session, at the front door (daily.ingest, the one writer):
* re-fetched sane -> stored; if a sane stored close differs, the NEWER one wins and the change is
  named with both figures (a provider correction);
* re-fetched broken, stored sane, the session closed -> the stored row is KEPT and named; the
  broken one is set aside in the quarantine as before;
* re-fetched broken, nothing sane stored -> nothing stored, as before;
* a session not closed when fetched: refused before this (QT-25 B); a stored row for it is not
  kept either. A row the provider leaves out altogether is not judged here.
The quarantine file is added to, never rewritten: the broken 23 Oct bar vanished from it at Mon
20:11 UTC, when the re-fetch came back sane and the file was rewritten with that fetch's bad rows.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from qb2.data.front_door import _append_manifest, _write_parquet_atomically, impossible_rows

NAMED = 50                         # changes written to one manifest line (a split moves them all)
PRICES = ("open", "high", "low", "close", "volume")              # what impossible_rows reads


@dataclass(frozen=True, slots=True)
class Merged:
    """The frame to store, and what the stored file changed in it."""

    frame: pd.DataFrame
    kept: list[str] = field(default_factory=list)                     # sessions: the stored row kept
    corrected: list[list[object]] = field(default_factory=list)       # [session, stored, re-fetched]


def merge(fresh: pd.DataFrame, stored: pd.DataFrame | None, broken: Collection[date], *,
          judged: bool = True) -> Merged:
    """``fresh``: the re-fetch's sane, closed rows; ``broken``: the closed sessions it sent broken.
    ``judged`` False (the pound/dollar rate: no exchange close, its newest row a moving rate,
    QT-25 B) -> a changed close is taken, never named a correction."""
    if stored is None or stored.empty or str(getattr(stored.index, "tz", None)) != str(getattr(fresh.index, "tz", None)):
        return Merged(fresh)              # nothing stored, or on another clock: dates not comparable
    old_days, new_days = pd.DatetimeIndex(stored.index).date, set(pd.DatetimeIndex(fresh.index).date)
    sane = ~impossible_rows(stored).to_numpy() if set(PRICES) <= set(stored.columns) \
        else np.zeros(len(stored), dtype=bool)                   # unjudgeable: never kept, never named
    keep = sane & np.array([d in broken and d not in new_days for d in old_days], dtype=bool)
    both = stored[sane].join(fresh[["close"]], how="inner", rsuffix="_new")
    moved = both[~np.isclose(both["close"].astype(float), both["close_new"].astype(float), rtol=1e-9, atol=0)]
    corrected = [[str(pd.Timestamp(i).date()), float(r["close"]), float(r["close_new"])] for i, r in moved.iterrows()]
    frame = pd.concat([fresh, stored[keep].reindex(columns=fresh.columns)]).sort_index() if keep.any() else fresh
    return Merged(frame, [str(d) for d in old_days[keep]], corrected if judged else [])


def say(merged: Merged, symbol: str, at: datetime, clean_root: Path | None) -> None:
    """The manifest lines: every kept row with its close, every correction with both figures."""
    stamp = at.isoformat(timespec="seconds")
    if merged.kept:
        rows = merged.frame[[str(d) in merged.kept for d in pd.DatetimeIndex(merged.frame.index).date]]
        _append_manifest({"event": "kept", "table": "daily", "symbol": symbol, "at": stamp,
                          "sessions": merged.kept, "closes": [float(x) for x in rows["close"]],
                          "reason": "re-fetched broken; the stored sane row kept (QT-26 B)"}, clean_root)
    if merged.corrected:
        _append_manifest({"event": "corrected", "table": "daily", "symbol": symbol, "at": stamp,
                          "count": len(merged.corrected), "changes": merged.corrected[-NAMED:],
                          "reason": "a stored sane close re-fetched different: the newer one kept"}, clean_root)


def set_aside(bad: pd.DataFrame, path: Path) -> None:
    """Add the fetch's broken rows to the quarantine file, never rewriting what it holds (the same
    bar sent again is held once)."""
    held = pd.read_parquet(path) if path.is_file() else None
    rows = bad if held is None else pd.concat([held, bad])
    rows = rows[~rows.reset_index().duplicated(keep="first").to_numpy()].sort_index()
    _write_parquet_atomically(rows, path)
