"""The one place an order could ever be sent from -- and it is DISARMED.

Nothing in this file can reach Trading 212. Two independent reasons:

1. ``ARMED`` is ``False`` and **there is no code path in qb2 that sets it True.**
   Arming is S10's job, deliberately not this box's. A wall test asserts that no
   assignment turning it on exists anywhere in qb2.
2. The function that would do the placing is ``_not_built_yet``, which raises.
   Even if something armed it, there is nothing behind the door.

So why write it at all? Because the REFUSALS are the valuable part, and they are
worth having tested long before anything can trade. The checks run in a fixed
order, cheapest and most certain first, and each one says why in words the
operator can read:

1. not armed;
2. the killswitch is on (buys only -- sells must always be possible);
3. the market for that instrument is shut;
4. there is already a pending bot order, or an unresolved intent, for that ticker.

That last one exists because the order endpoints are **not idempotent**
(docs/t212/FACTS.md row e): sending again because we are unsure is how one
intended trade becomes two real ones.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from qb2.execution import safety
from qb2.execution.fill_recorder import FillRecorder

# DISARMED. Nothing in qb2 may set this True; arming is S10, under its own box.
ARMED = False

BUY = "BUY"
SELL = "SELL"


class NotArmed(RuntimeError):
    """The sender is disarmed. This is the expected state until S10."""


@dataclass(frozen=True, slots=True)
class OrderRequest:
    """A market order -- the only kind the bot ever sends.

    Market orders only, because our stops are ours to run (FACTS.md rows d1/d2)
    and the bot is same-day (PLAN_V3 P4): there is never a resting order to
    manage, so there is never a reason for a type we cannot amend.
    """

    ticker: str
    side: str
    quantity: float
    market: str
    expected_price: float
    quote_age_seconds: float
    extended_hours: bool = False


def _not_built_yet(request: OrderRequest) -> str:
    """The door with nothing behind it. Replaced in S10, not here."""
    raise NotImplementedError(
        "placing orders is S10's work; S2b builds only the refusals")


def send(request: OrderRequest, *,
         market_is_open: bool,
         pending_bot_tickers: Sequence[str] = (),
         recorder: FillRecorder | None = None,
         root: Path | None = None,
         place: Callable[[OrderRequest], str] = _not_built_yet) -> str:
    """Refuse for the right reason, or hand over to ``place``.

    Every refusal is recorded against its intent, so a blocked trade can never be
    mistaken later for a trade that vanished.
    """
    if request.side not in (BUY, SELL):
        raise ValueError(f"side must be {BUY} or {SELL}, not {request.side!r}")
    if request.quantity <= 0:
        raise ValueError("quantity must be positive; a sell is still a positive "
                         "quantity with side=SELL")

    intent_id = f"{request.ticker}-{request.side}-{request.quote_age_seconds:.0f}"

    def refuse(reason: str) -> None:
        if recorder is not None:
            recorder.record_refusal(intent_id=intent_id, ticker=request.ticker,
                                    side=request.side, reason=reason)

    # 1. Disarmed. First, because it is the reason that always applies today.
    if not ARMED:
        refuse("sender is disarmed (S10 arms it)")
        raise NotArmed(
            "the order sender is disarmed: S2b builds the refusals, S10 builds "
            "the sending. Nothing was sent.")

    # 2. The killswitch stops buying, never selling.
    if request.side == BUY:
        try:
            safety.check_buying_allowed(root)
        except safety.Blocked as blocked:
            refuse(str(blocked))
            raise

    # 3. A buy into a shut market would queue and fill unwatched (P4).
    if request.side == BUY and not market_is_open:
        reason = (f"{request.market} is closed -- a queued buy would fill with "
                  f"nothing watching it")
        refuse(reason)
        raise safety.Blocked(reason)

    # 4. Never two orders for one intention (FACTS.md row e).
    if request.ticker in pending_bot_tickers:
        reason = f"a bot order for {request.ticker} is already pending"
        refuse(reason)
        raise safety.Blocked(reason)
    if recorder is not None and recorder.has_open_intent(request.ticker):
        reason = (f"an earlier intent for {request.ticker} has no outcome yet -- "
                  f"reconcile with the broker, never resend")
        refuse(reason)
        raise safety.Blocked(reason)

    return place(request)
