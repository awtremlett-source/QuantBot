"""S-07's rule, its ONE copy (QT-24 D): the slow trend filter on VWRL's month-end closes.

Registered cd3e863 (docs/research/preregistered.json, S-07) before this code existed. At each
MONTH-END close -- the bar on London's last session of the calendar month, by the exchange's own
calendar, so a month still trading has none -- hold VWRL if that close is ABOVE the mean of the last
10 month-end closes (this one included), else cash; a change fills at the next bar's open. The first
decision is ADV-0's first weekly review (the first week's last London session on or after the
start): BUY at the next open if the latest month-end on or before it said above. No percentage stop,
no re-buy; before 10 month-end closes there is no decision (cash). Pure: days and closes in, the
fills out -- shared by the description (s07_describe, through adv0_describe.describe) and the live
shadow (qb2/advisor/shadow.py). Free of the back-test-only P15 history rule (the live path imports
it; wall: tests/wall/test_p15_history_wall.py).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta

import numpy as np
import pandas as pd

from qb2.research import advisor_book

SMA_MONTHS = 10
BUY, SELL = "BUY", "SELL"


def calendar_ends(days: Sequence[date]) -> tuple[np.ndarray, np.ndarray]:
    """(month-end, week-end) per bar: is it London's LAST session of its month / ISO week?"""
    cal = pd.DatetimeIndex(advisor_book.sessions("LSE", days[0], days[-1] + timedelta(days=40))).date
    weeks: dict[tuple[int, int], date] = {}
    for d in cal:
        weeks[d.isocalendar()[:2]] = d                         # in order: the week's last one wins
    months, week_ends = set(advisor_book.last_sessions(np.asarray(cal)).values()), set(weeks.values())
    return np.array([d in months for d in days]), np.array([d in week_ends for d in days])


def above(closes: np.ndarray, month_end: np.ndarray) -> np.ndarray:
    """Per bar: 1.0 if the latest month-end close on or before it is above the mean of the last 10
    month-end closes (that one included), 0.0 if at or below, NaN before there are 10."""
    out, ends, state = np.full(len(closes), np.nan), list[float](), np.nan
    for t in range(len(closes)):
        if month_end[t]:
            ends.append(float(closes[t]))
            if len(ends) >= SMA_MONTHS:
                state = 1.0 if ends[-1] > float(np.mean(ends[-SMA_MONTHS:])) else 0.0
        out[t] = state
    return out


def fills(days: Sequence[date], month_end: np.ndarray, week_end: np.ndarray, up: np.ndarray,
          start: date) -> list[tuple[int, str]]:
    """S-07's as-if fills, (bar, BUY/SELL), each at the open of the bar after its decision."""
    n, out, on = len(days), list[tuple[int, str]](), False
    first = next((t for t in range(n) if days[t] >= start and week_end[t]), None)
    if first is None:
        return out
    for t in range(first, n - 1):
        if t == first or month_end[t]:
            if (want := bool(up[t] == 1.0)) != on:
                out.append((t + 1, BUY if want else SELL))
                on = want
    return out


def held(n: int, book: Sequence[tuple[int, str]]) -> np.ndarray:
    """1.0 for each bar held through its close: from a BUY's bar up to (not into) the next SELL's."""
    out, on, k = np.zeros(n), False, 0
    for t in range(n):
        while k < len(book) and book[k][0] == t:
            on = book[k][1] == BUY
            k += 1
        out[t] = 1.0 if on else 0.0
    return out
