"""A London session the as-if record passed over (QT-26 C): named by date, never a silent gap.

VWRL's store can lack a session that a later one follows: the provider sent its bar broken (QT-25:
Fri 23 Oct, no close). The advisor cannot wait for ever, so it checks the stop on the newest sane
close and processes the later session -- and the one it passed over becomes a SKIPPED row in
days.jsonl, named UNCHECKED on every run and on the page while no sane close for it is stored. A
close that comes later is too late to use: a later day was recorded without it, and a processed
day is never re-done (its bar is held out of the record, so the reconciliation still holds). The
run's lines and the page then say it is final, while the row is among the page's last rows.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date

import numpy as np
import pandas as pd

from qb2.advisor import live
from qb2.advisor.page import ROWS
from qb2.guard import stops

SKIPPED = "skipped"
Row = Mapping[str, object]


def is_skip(row: Row) -> bool:
    return bool(row.get(SKIPPED))


def split(bars: pd.DataFrame, written: Sequence[Row]) -> tuple[pd.DataFrame, dict[date, float]]:
    """The bars without any skipped session's (a late one stays out of the record), and those closes."""
    skipped = {date.fromisoformat(str(r["session"])) for r in written if is_skip(r)}
    out = np.array([d in skipped for d in live.days_of(bars.index, "LSE")], dtype=bool)
    return bars[~out], {d: float(c) for d, c in zip(live.days_of(bars.index[out], "LSE"), bars["close"][out])}


def holes(calendar: Sequence[date], have: Sequence[date], written: Sequence[Row]) -> list[date]:
    """London sessions with no VWRL bar though a later one has, not yet written: passed over."""
    done, there = {str(r["session"]) for r in written}, set(have)
    return [d for d in calendar if have and d < max(have) and d not in there and d.isoformat() not in done]


def row(day: date, held: stops.Stop | None) -> dict[str, object]:
    return {"session": day.isoformat(), SKIPPED: True, "held": held is not None, "close": None,
            "stop": held.level if held else None,
            "reason": "no sane VWRL close in the store when a later session was processed"}


def lines(written: Sequence[Row], late: Mapping[date, float]) -> list[str]:
    """UNCHECKED for each skipped session still without a sane close; final once one came late."""
    out, shown = [], {str(r["session"]) for r in written[-ROWS:]}
    for r in (r for r in written if is_skip(r)):
        d = date.fromisoformat(str(r["session"]))
        if (close := late.get(d)) is None:
            out.append(f"UNCHECKED: {d:%a %d %b} ({d}) has no sane VWRL close -- the as-if record skips that "
                       "session, and the stop was checked only against later closes. Look at VWRL's close "
                       "that day yourself.")
        elif d.isoformat() in shown:
            level = r.get("stop")
            then = (f", {'above' if close > level else 'AT OR BELOW'} the stop of £{level:,.2f} then"
                    if isinstance(level, (int, float)) else "")
            out.append(f"SKIPPED for good: {d:%a %d %b} ({d})'s VWRL close came after a later session was "
                       f"processed (£{close:,.2f}{then}) -- the as-if record keeps it skipped; nothing "
                       "recorded changes.")
    return out
