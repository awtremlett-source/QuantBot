"""Pot limits: neither part may spend past its own pot (PLAN_V3 P2; QT-16 B3).

Before every bot buy (sender check 7) and every advisor suggestion: refuse anything
that would take the pot's holdings, plus what is already on order, plus this spend,
past the pot's limit.

* **The bot's limit is 30% of the account's total value AT THE TIME OF THE CHECK.**
  That is this box's reading of P2's "not shrunk for a poor run": the bot's own
  losses do not cut its slice, because the slice is re-measured on the whole
  account every time, not on what the bot has left. The advisor's is the other 70%.
* **P20's anchors and his pre-existing (manual) holdings count in NEITHER pot**: an
  anchor is measuring equipment, and his own holdings were never either part's.
* **Fails closed:** no account value, or a holding in the pot with no value, is a
  refusal that says which figure was missing.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from qb2.execution.safety import ADVISOR, BOT, MANUAL, Blocked

ANCHOR = "anchor"
SHARE = {BOT: 0.30, ADVISOR: 0.70}           # P2
NEITHER = frozenset({ANCHOR, MANUAL})


@dataclass(frozen=True, slots=True)
class Line:
    ticker: str
    owner: str                               # bot, advisor, manual or anchor
    value_gbp: float | None


@dataclass(frozen=True, slots=True)
class View:
    """What the check needs, read at the moment of the check."""

    account_total_gbp: float | None
    lines: tuple[Line, ...] = ()
    pending_gbp: float = 0.0                 # this pot's orders not yet filled


def _figure(value: float | None, what: str) -> float:
    if value is None or not math.isfinite(value) or value < 0:
        raise Blocked(f"no usable {what} ({value!r}) -- no figure, no buy")
    return float(value)


def limit(pot: str, account_total_gbp: float | None) -> float:
    if pot not in SHARE:
        raise Blocked(f"no pot called {pot!r}: the pots are bot and advisor")
    total = _figure(account_total_gbp, "account total value")
    if total <= 0:
        raise Blocked("the account's total value is nothing -- no pot to spend from")
    return SHARE[pot] * total


def used(pot: str, lines: Sequence[Line]) -> float:
    """The pot's holdings in pounds. Anchors and manual holdings are not counted."""
    return sum(_figure(x.value_gbp, f"value of the {x.owner} holding {x.ticker}")
               for x in lines if x.owner == pot)


def check(pot: str, spend_gbp: float | None, view: View | None) -> None:
    if view is None:
        raise Blocked(f"no pot figures for the {pot} pot -- no buy")
    spend = _figure(spend_gbp, "order value in pounds")
    if spend <= 0:
        raise Blocked("an order for nothing is not an order")
    cap = limit(pot, view.account_total_gbp)
    after = used(pot, view.lines) + _figure(view.pending_gbp, "pending orders") + spend
    if after > cap:
        raise Blocked(f"£{spend:,.2f} would take the {pot} pot to £{after:,.2f}, past its "
                      f"£{cap:,.2f} limit ({SHARE[pot]:.0%} of the account's "
                      f"£{view.account_total_gbp:,.2f})")
