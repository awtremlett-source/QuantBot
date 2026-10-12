"""Nothing is held longer than 12 months (PLAN_V3 P13; QT-16 B4) -- and the bot not
past its own session (P4).

* **Flag at 11 months** (a STARTING FIGURE): the review says "due next month".
* **At 12 months:** sell, or re-justify it as a brand-new buy. The ONLY way to do
  the second is :func:`rebuy`, which closes the old record and opens a NEW one --
  new id, new open date, fresh stop at today's price -- with a written reason. A
  silent roll-over (the same record carrying on, or re-opened under its own id) is
  refused, and a HOLD suggestion for it is refused (suggestion.py).
* **A bot position older than its own session is an INCIDENT** (P4: nothing held
  overnight): STOP_NEW_TRADES is armed and the incident written down.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from qb2.execution import safety
from qb2.execution.safety import BOT, Blocked
from qb2.guard import stops as stop_ledger
from qb2.research import fills

FLAG_MONTHS = 11              # STARTING FIGURE
LIMIT_MONTHS = 12             # P13
OK, FLAG, LIMIT = "OK", "FLAG-11", "LIMIT-12"
INCIDENTS = safety.REPO_ROOT / "logs" / "incidents" / "incidents.jsonl"


@dataclass(frozen=True, slots=True)
class Finding:
    position_id: str
    ticker: str
    pot: str
    status: str
    message: str


def _at(stamp: str | datetime) -> pd.Timestamp:
    moment = pd.Timestamp(stamp)
    return moment.tz_localize("UTC") if moment.tzinfo is None else moment.tz_convert("UTC")


def status(opened_at: str | datetime, now: datetime) -> str:
    opened, today = _at(opened_at), _at(now)
    if today >= opened + pd.DateOffset(months=LIMIT_MONTHS):
        return LIMIT
    if today >= opened + pd.DateOffset(months=FLAG_MONTHS):
        return FLAG
    return OK


def review(held: Iterable[stop_ledger.Stop], now: datetime) -> list[Finding]:
    """Every position at or past 11 months, with what has to happen."""
    out = []
    for stop in held:
        state = status(stop.opened_at, now)
        if state == LIMIT:
            out.append(Finding(stop.position_id, stop.ticker, stop.pot, state,
                               f"{stop.ticker} held 12 months: sell, or re-justify it as "
                               "a brand-new buy (P13)"))
        elif state == FLAG:
            out.append(Finding(stop.position_id, stop.ticker, stop.pot, state,
                               f"{stop.ticker} reaches 12 months within a month"))
    return out


def check_hold(stop: stop_ledger.Stop, now: datetime) -> None:
    """A position at 12 months may not simply be held on: that is a silent roll-over."""
    if status(stop.opened_at, now) == LIMIT:
        raise Blocked(f"{stop.ticker} has been held 12 months: sell it, or re-justify it "
                      "through the re-buy path -- a silent roll-over is refused (P13)")


def rebuy(ledger: stop_ledger.Ledger, position_id: str, *, new_position_id: str,
          price: float, atr: float, reason: str, now: datetime) -> stop_ledger.Stop:
    """The ONLY way past 12 months: a new record, a fresh stop, a new open date."""
    if not reason or not reason.strip():
        raise Blocked("a re-justified buy needs its reason written down")
    if new_position_id == position_id:
        raise Blocked("the same record cannot restart its own clock: a re-justified buy "
                      "is a NEW position with a new id")
    old = ledger.get(position_id)
    stop_ledger.plan(old.ticker, price, atr)              # refuse before closing anything
    ledger.close(position_id, f"re-justified as a new buy ({new_position_id}): {reason}")
    return ledger.open(position_id=new_position_id, pot=old.pot, ticker=old.ticker,
                       market=old.market, opened_at=_at(now).isoformat(), entry=price,
                       atr=atr, reason=f"re-justified after {position_id}: {reason}")


def session_close(opened_at: str | datetime, market: str) -> pd.Timestamp:
    day = _at(opened_at).tz_convert(fills.EXCHANGE_TZ[market]).date()
    return pd.Timestamp(fills._close_ns(day, market), tz="UTC")      # noqa: SLF001


def overnight(held: Iterable[stop_ledger.Stop], now: datetime, *,
              root: Path | None = None, incidents: Path | None = None) -> list[str]:
    """P4: a bot position still open after its own session's close is an incident."""
    found = [f"bot position {s.position_id} ({s.ticker}) opened {s.opened_at} is still "
             f"held after its session closed" for s in held
             if s.pot == BOT and _at(now) >= session_close(s.opened_at, s.market)]
    if found:
        safety.arm_killswitch("incident: " + "; ".join(found), root)
        target = incidents or INCIDENTS
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as handle:
            for line in found:
                handle.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(
                    timespec="seconds"), "kind": "bot held past its session",
                    "detail": line}) + "\n")
    return found
