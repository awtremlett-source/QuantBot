"""The advisor's one front door to the S5 checks (QT-16 B6).

``check_suggestion`` runs the brake, the pot limit, the earnings warning and the
age check for one advisor suggestion. S9 builds the advisor; a wall test fails the
day qb2/advisor/ exists without calling this function.

* A SELL suggestion is never blocked -- getting out must always be possible.
* A BUY is refused while the advisor pot's brake is on (the message says "hold off"
  at 15%), or when it would spend past the pot. An earnings date close by, or
  unknown, is a WARNING for the advisor, not a refusal (P15).
* A HOLD of a position that has reached 12 months is refused (sell, or re-justify
  through age.rebuy); at 11 months it carries a warning.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from qb2.execution.safety import ADVISOR, Blocked
from qb2.guard import age, brakes, earnings_window, pots
from qb2.guard import stops as stop_ledger

BUY, HOLD, SELL = "BUY", "HOLD", "SELL"


@dataclass(frozen=True, slots=True)
class Suggestion:
    ticker: str
    action: str                              # BUY, HOLD or SELL
    kind: str                                # STOCK or ETF
    market: str
    spend_gbp: float | None = None           # BUY only
    held: stop_ledger.Stop | None = None     # HOLD / SELL: the position's stop record


@dataclass(frozen=True, slots=True)
class Checked:
    allowed: bool
    refusals: tuple[str, ...]
    warnings: tuple[str, ...]


def _why(check: Callable[[], None]) -> str | None:
    try:
        check()
    except Blocked as why:
        return str(why)
    return None


def check_suggestion(s: Suggestion, *, brake: brakes.State | None, pot: pots.View | None,
                     earnings: pd.DataFrame | None, now: datetime) -> Checked:
    if s.action == SELL:
        return Checked(True, (), ())
    if s.action not in (BUY, HOLD):
        return Checked(False, (f"unknown suggestion {s.action!r}",), ())
    refusals, warnings = [], []
    note = earnings_window.advisor_warning(s.ticker, s.kind, s.market, now, earnings)
    if note:
        warnings.append(note)
    if s.action == BUY:
        refusals += [why for why in (_why(lambda: brakes.check_buy(brake, ADVISOR)),
                                     _why(lambda: pots.check(ADVISOR, s.spend_gbp, pot)))
                     if why]
        message = brakes.advisor_message(brake)
        if message:
            warnings.append(message)
    else:
        if s.held is None:
            refusals.append(f"{s.ticker}: no stop record for the holding -- every position "
                            "has one (P10)")
        else:
            held = s.held
            refusals += [why for why in (_why(lambda: age.check_hold(held, now)),) if why]
            if age.status(held.opened_at, now) == age.FLAG:
                warnings.append(f"{s.ticker} reaches 12 months within a month")
    return Checked(not refusals, tuple(refusals), tuple(warnings))
