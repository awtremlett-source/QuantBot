"""P22 (QT-30): a second price on every closing price that drives a stop. Paper only; not a trial.

His words, 2026-11-08: "cant you find the closing price to confirm it elsewhere?"; "it could use a
secondary confirmation, thoughts?" (PLAN_V3 P22 has them all, and the GO line he replied to.)

* The second price: Trading 212's first (its newest read from 10 minutes after that session's close
  until the next London open: the broker has no stored close and prices only what we hold), else
  the backup feed's close for that session. qb2/ingest/close_feeds.py gathers them; this reads them.
* CONFIRMED (within 0.5%), DISAGREE (beyond it), UNCONFIRMED (no second price).
* The stop RISES only on a CONFIRMED close. A HIT is never suppressed: a store close at or below the
  stop always issues the SELL, flagged unless CONFIRMED; on DISAGREE any price at or below it does.
* One journal line per stop-driving close, append-only: data/qb2/price_check/journal.jsonl.
Nothing here may stop the daily job: a fault reading the prices leaves the close UNCONFIRMED and says
why, because missing a real crash is worse than a false alarm.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from qb2.advisor import scorecard, state
from qb2.execution.safety import Blocked
from qb2.guard.stops import Stop
from qb2.research import advisor_book

TOLERANCE = 0.005                      # his mentor's proposal: within about 0.5% = CONFIRMED
AFTER_CLOSE = timedelta(minutes=10)    # London's closing auction is over by then
CONFIRMED, DISAGREE, UNCONFIRMED = "CONFIRMED", "DISAGREE", "UNCONFIRMED"
T212, BACKUP = "Trading 212", "the backup feed"
KIND_T212, KIND_BACKUP = "t212", "backup"
POUNDS = "GBP"
Seen = tuple[float, str]               # (price in pounds, when it was fetched)
UNREADABLE = (Blocked, OSError, ValueError, KeyError, TypeError, IndexError, AttributeError)


def folder(paths: state.Paths) -> Path:
    """Beside the advisor's and the bot pot's folders: both read the same second prices."""
    return paths.root.parent / "price_check"


def observations(paths: state.Paths) -> Path:
    return folder(paths) / "observations.jsonl"


def journal(paths: state.Paths) -> Path:
    return folder(paths) / "journal.jsonl"


@dataclass(frozen=True, slots=True)
class Check:
    ticker: str
    session: date
    store: float
    status: str
    second: float | None = None
    source: str = ""                   # who gave the second price: T212, BACKUP, or nobody
    gap: float | None = None
    fetched_at: str | None = None
    t212: float | None = None
    backup: float | None = None
    note: str = ""

    @property
    def may_raise(self) -> bool:
        return self.status == CONFIRMED

    def hit(self, level: float) -> bool:
        if self.store <= level:
            return True
        return self.status == DISAGREE and any(p is not None and p <= level for p in (self.t212, self.backup))

    def crossed(self, level: float, word: str = "safety stop") -> str:
        """Plain words for the alert. The second price's figure stays in the journal (public page)."""
        if self.store <= level:
            return f"closed at £{self.store:,.2f} on {self.session}, at or below its {word} of £{level:,.2f}"
        return (f"was priced by {self.source} for {self.session} at or below its {word} of £{level:,.2f} "
                f"(our store's close: £{self.store:,.2f})")

    @property
    def flag(self) -> str:
        """The mark on a SELL issued on anything but a CONFIRMED close."""
        if self.status == CONFIRMED:
            return ""
        differ = f" (the two prices differ by {self.gap:.2%})" if self.gap is not None else ""
        return f" UNCONFIRMED — check the price yourself{differ}."


def judge(ticker: str, session: date, store: float, *, t212: Seen | None = None,
          backup: Seen | None = None, note: str = "") -> Check:
    """One close's status. The rule itself: Trading 212 first, the backup only if it has no close."""
    chosen, source = (t212, T212) if t212 is not None else (backup, BACKUP)
    base = Check(ticker, session, store, UNCONFIRMED, t212=t212[0] if t212 else None,
                 backup=backup[0] if backup else None, note=note)
    if chosen is None:
        return base
    gap = abs(store - chosen[0]) / chosen[0]
    return replace(base, status=CONFIRMED if round(gap, 9) <= TOLERANCE else DISAGREE, second=chosen[0],
                   source=source, gap=gap, fetched_at=chosen[1])


def _at(row: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(str(row["fetched_at"]))


def _pounds(row: dict[str, Any], key: str) -> Seen | None:
    """close_feeds stores pounds; anything else is no price at all, so pence never read 100x off."""
    price = float(row[key]) if row["currency"] == POUNDS else math.nan
    return (price, str(row["fetched_at"])) if math.isfinite(price) and price > 0 else None


def next_open(session: date) -> datetime:
    days = advisor_book.sessions("LSE", session + timedelta(days=1), session + timedelta(days=10))
    return scorecard.xlon(pd.DatetimeIndex(days).date[0], "open")


def broker_close(rows: list[dict[str, Any]], ticker: str, session: date) -> Seen | None:
    """Trading 212's close for that session: its newest read inside the window, or nothing."""
    start, end = scorecard.xlon(session, "close") + AFTER_CLOSE, next_open(session)
    inside = [r for r in rows if r.get("kind") == KIND_T212 and r.get("ticker") == ticker
              and start <= _at(r) < end]
    return _pounds(max(inside, key=_at), "price") if inside else None


def backup_close(rows: list[dict[str, Any]], ticker: str, session: date) -> Seen | None:
    mine = [r for r in rows if r.get("kind") == KIND_BACKUP and r.get("ticker") == ticker
            and r.get("session") == session.isoformat()]
    return _pounds(max(mine, key=_at), "close") if mine else None


def check_of(paths: state.Paths, ticker: str, session: date, store: float) -> Check:
    """Never raises: a price we cannot read is a close we cannot confirm, said in its note."""
    try:
        rows = state.rows(observations(paths))
        return judge(ticker, session, store, t212=broker_close(rows, ticker, session),
                     backup=backup_close(rows, ticker, session))
    except UNREADABLE as why:
        return judge(ticker, session, store, note=f"second prices unreadable ({type(why).__name__}: {why})")


def _write(paths: state.Paths, check: Check, level: float, now: datetime) -> str:
    """One line per name and session, the journal's only writer. A failure is said, never fatal."""
    try:
        if any(r.get("session") == check.session.isoformat() and r.get("ticker") == check.ticker
               for r in state.rows(journal(paths))):
            return check.note
        state.append(journal(paths), {
            "at": now.astimezone(timezone.utc).isoformat(timespec="seconds"), "session": check.session.isoformat(),
            "ticker": check.ticker, "status": check.status, "store": check.store, "second": check.second,
            "source": check.source, "gap_pct": None if check.gap is None else round(check.gap * 100, 4),
            "fetched_at": check.fetched_at, "t212": check.t212, "backup": check.backup, "stop": level,
            "note": check.note})
        return check.note
    except (Blocked, OSError) as why:
        return f"{check.note} journal not written ({type(why).__name__}: {why})".strip()


def day(paths: state.Paths, ticker: str, session: date, store: float, now: datetime, held: Stop | None) -> Check:
    """The daily jobs' one call. A close with no stop behind it drives nothing, so it is not journalled."""
    check = check_of(paths, ticker, session, store)
    return check if held is None else replace(check, note=_write(paths, check, held.level, now))


def _name(ticker: str) -> str:
    return ticker.removesuffix(".L")


def _line(row: dict[str, Any], anchored: bool) -> str:
    """The page's line. The backup's figure is not printed: the status page is public (see the report)."""
    what = f"{_name(str(row['ticker']))} close of {row['session']} {row['status']}"
    only = "" if anchored or row["ticker"] != "VWRL.L" else "; backup feed only — Trading 212 anchor pending"
    note = f" ({row['note']})" if row.get("note") else ""
    if row["status"] == UNCONFIRMED:
        return f"Price check: 🔴 {what} — no second price; the stop was not raised{only}{note}"
    theirs = f"Trading 212 £{float(row['t212']):,.2f}" if row["source"] == T212 else "the backup feed"
    say = f"our store £{float(row['store']):,.2f}, {theirs}, gap {float(row['gap_pct']):.2f}%"
    if row["status"] == DISAGREE:
        return f"Price check: 🔴 {what} — {say}: the stop was not raised{only}{note}"
    return f"Price check: 🟢 {what} — {say}{only}{note}"


def page_lines(paths: state.Paths, ticker: str) -> list[str]:
    """The status page's lines for one name. Trading 212 has priced it = it is anchored."""
    try:
        anchored = any(r.get("kind") == KIND_T212 and r.get("ticker") == ticker for r in state.rows(observations(paths)))
        rows = [r for r in state.rows(journal(paths)) if r.get("ticker") == ticker]
    except (Blocked, OSError) as why:
        return [f"Price check: 🔴 {_name(ticker)} journal unreadable ({type(why).__name__}: {why})"]
    out = [_line(rows[-1], anchored)] if rows else [f"Price check: {_name(ticker)} — no close checked yet"]
    if _name(ticker) != "VWRL":
        return out
    return [*out, "VWRL anchor: in place — Trading 212 prices it" if anchored
            else "VWRL anchor: not set up — see the QT-32 report"]
