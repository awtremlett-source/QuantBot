"""The closes the daily store still lacks after a top-up (QT-32; PLAN_V3 S9, note 2026-11-11).

**Why.** On Tue 10 Nov 2026 Yahoo served Monday's London closes blank. The store rightly refused them
("no blank reaches a rule"), but the daily step still marked Monday done: nothing retried until
Wednesday, and the 08:00 line read "fresh to 2026-11-06 · OK" (QT-31 A2).

**The rule.** For each key -- a market (London, US: all its names together, so a session counts as
there if any name has it) and each name -- the sessions of its own exchange calendar it lacks in
(start, want]. ``want`` is the market's newest session on or before the top-up's target, so a
holiday is never missing. ``start`` is the earliest of: the stop path's floor (the last
``fetched_through``), the key's newest stored session, and the session it was already recorded on.
* A market, or a stop-driving name (VWRL.L, VWRP.L), that lacks one is BEHIND: RED in the line,
  retried on every run, and ``fetched_through`` -- the advisor's and the bot pot's one door
  (live.final_through) -- is held before its oldest missing session. Once the store holds a later
  session for it, the line calls it a gap, never delivered. Nothing fills it: the operator decides.
* Any other name lacking a session that its market has is SHORT: named and retried, never holding
  the stops back.
^VIX keeps its own rules (daily_step.gauge_lag, QT-24/QT-29) and the pound/dollar rate has no
exchange, so neither is judged here. Pure: the store's dates come in, the marker's entries go out.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import exchange_calendars as xcals  # type: ignore[import-untyped]
import pandas as pd

from qb2.data import universe

STOP_DRIVING = ("VWRL.L", "VWRP.L")      # the advisor's and the bot pot's stop closes
OWN_RULES = ("^VIX",)                    # QT-24/QT-29: judged by daily_step.gauge_lag
MARKETS = (universe.US, universe.LONDON)
Entry = dict[str, Any]                   # {"session", "since", "later"}: the marker's shape


@dataclass(frozen=True, slots=True)
class Found:
    """One scan: what the marker records and the next run retries."""

    behind: dict[str, Entry] = field(default_factory=dict)    # markets and stop names: RED, held
    short: dict[str, Entry] = field(default_factory=dict)     # any other name: named, retried
    retry: list[str] = field(default_factory=list)            # every name lacking a session
    final: str = ""                                           # the new fetched_through


def _calendar(market: str) -> Any:
    from qb2.data import clean_step            # clean_step -> earnings_step -> daily_step -> here

    return xcals.get_calendar(clean_step.CALENDARS[market])


def last_session(market: str, target: date) -> date:
    """The market's newest session on or before the top-up's target day."""
    day: date = _calendar(market).date_to_session(pd.Timestamp(target), direction="previous").date()
    return day


def sessions(market: str, after: date, through: date) -> list[date]:
    """The market's sessions after ``after`` up to and including ``through``."""
    if through <= after:
        return []
    found = _calendar(market).sessions_in_range(pd.Timestamp(after + timedelta(days=1)), pd.Timestamp(through))
    return list(pd.DatetimeIndex(found).date)


def _missing(market: str, have: set[date], floor: date, want: date, before: Entry | None) -> list[date]:
    starts = [floor, *([max(have)] if have else [])]
    if before is not None:
        starts.append(date.fromisoformat(str(before["session"])) - timedelta(days=1))
    return [d for d in sessions(market, min(starts), want) if d not in have]


def _entry(missing: Sequence[date], have: set[date], before: Entry | None, at: str) -> Entry:
    later = max((d for d in have if d > missing[0]), default=None)
    return {"session": missing[0].isoformat(), "since": str(before["since"]) if before else at,
            "later": later.isoformat() if later else None}


def scan(dates: Mapping[str, set[date]], markets: Mapping[str, str], before: Mapping[str, Entry], *,
         floor: date, target: date, topped_up: date, at: str) -> Found:
    """Every key's missing sessions, and the session the stop path may now call final."""
    behind: dict[str, Entry] = {}
    short: dict[str, Entry] = {}
    retry: list[str] = []
    for market in MARKETS:
        want = last_session(market, target)
        mine = sorted(s for s, m in markets.items() if m == market and s not in OWN_RULES)
        union: set[date] = set().union(*(dates[s] for s in mine)) if mine else set()
        whole = _missing(market, union, floor, want, before.get(market)) if mine else []
        if whole:
            behind[market] = _entry(whole, union, before.get(market), at)
        for symbol in mine:
            own = _missing(market, dates[symbol], floor, want, before.get(symbol))
            retry += [symbol] if own else []
            if own and symbol in STOP_DRIVING:
                behind[symbol] = _entry(own, dates[symbol], before.get(symbol), at)
            elif rest := [d for d in own if d not in whole]:
                short[symbol] = _entry(rest, dates[symbol], before.get(symbol), at)
    final = topped_up
    if behind:                                 # held before the oldest missing session, on London's clock
        oldest = min(date.fromisoformat(str(e["session"])) for e in behind.values())
        final = min(topped_up, last_session(universe.LONDON, oldest - timedelta(days=1)))
    return Found(behind, short, retry, final.isoformat())


def words(seen: Mapping[str, Any]) -> tuple[list[str], str]:
    """The line's words from the marker: the RED reasons (BEHIND, gaps), then the named shorts and the
    retry's time. A marker from before QT-32 has none of these keys and says nothing new."""
    behind: Mapping[str, Entry] = dict(seen.get("behind") or {})
    red = [f"gap: {k} {e['session']} never delivered" if e.get("later") else f"{k} {e['session']}"
           for k, e in behind.items()]
    if red:
        since = min(str(e["since"]) for e in behind.values())[:16].replace("T", " ")
        red = [f"BEHIND, retried every run: {', '.join(red)} -- missing since {since} UTC; the advisor and "
               f"the bot pot are held at {seen.get('fetched_through')}"]
    short = [f"{k} {e['session']}" for k, e in dict(seen.get("short") or {}).items()]
    tail = (f" · {len(short)} name{'s' if len(short) > 1 else ''} short of a session (named, retried, not "
            f"holding the stops back): {', '.join(short[:6])}") if short else ""
    if (red or short) and (n := int(seen.get("retried") or 0)):      # while anything is still missing
        tail += f" · retried {n} name{'s' if n > 1 else ''} in {float(seen.get('retry_s') or 0):.1f}s"
    return red, tail
