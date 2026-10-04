"""The killswitch, and the checks that stand between a signal and an order.

Three separate jobs, kept in one file because they are the same idea: things that
say NO.

**The killswitch.** A file named STOP_NEW_TRADES at the repo root. Present means
no new buying. SELLS ARE ALWAYS ALLOWED -- a killswitch that stopped us getting
out would be the opposite of safety.

**Flatten.** Sell the bot's holdings. It sells the BOT-TAGGED quantity and
nothing else: the advisor's positions and anything the operator bought by hand
are not the bot's to close, and PLAN_V3 P1 is explicit that the only automatic
act on his own holdings is moving a stop upward.

**The price checks (P14).** Trading 212 cannot price an instrument we do not hold
(docs/t212/FACTS.md row h), so there is no broker quote to check a new buy
against. Three checks stand in for it, and the third is the one that still works
when the first two are fooled:

1. is the quote young enough for that market?
2. is the price inside a sane band around recent bars?
3. is the order small enough that a wrong price is survivable?

Every threshold here is a STARTING FIGURE, to be replaced by measurement.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
KILLSWITCH_FILENAME = "STOP_NEW_TRADES"

BOT = "bot"
ADVISOR = "advisor"
MANUAL = "manual"

# --- starting figures, every one to be measured and replaced -----------------
# Quote must be younger than this. London's real delay is UNMEASURED
# (FACTS.md row o), so its allowance is generous on purpose.
MAX_QUOTE_AGE_SECONDS = {"US": 120.0, "LSE": 1_800.0}
QUOTE_AGE_MARGIN_SECONDS = 60.0
# Price must be within this fraction of the recent range.
PRICE_BAND_FRACTION = 0.05
# One order may not risk more than this slice of the pot on a bad price.
MAX_ORDER_FRACTION_OF_POT = 0.10
# A fill this far from expectation stops that market until a human looks.
MAX_FILL_GAP_FRACTION = 0.01


class Blocked(RuntimeError):
    """A check said no. The message says which, in words the operator can read."""


# ------------------------------------------------------------- killswitch ----

def killswitch_path(root: Path | None = None) -> Path:
    return (root or REPO_ROOT) / KILLSWITCH_FILENAME


def killswitch_armed(root: Path | None = None) -> bool:
    return killswitch_path(root).exists()


def arm_killswitch(reason: str, root: Path | None = None) -> str:
    path = killswitch_path(root)
    if not path.exists():
        path.write_text(f"armed by qb2: {reason}\n", encoding="utf-8")
    return f"killswitch ARMED ({path.name}) -- no new buying: {reason}"


def disarm_killswitch(root: Path | None = None) -> str:
    path = killswitch_path(root)
    if path.exists():
        path.unlink()
    return f"killswitch DISARMED ({path.name} absent) -- buying allowed again"


def check_buying_allowed(root: Path | None = None) -> None:
    """Raises when the killswitch is armed. Never called for a sell."""
    if killswitch_armed(root):
        path = killswitch_path(root)
        detail = path.read_text(encoding="utf-8").strip() if path.is_file() else ""
        raise Blocked(f"the killswitch is armed, so no new buying: {detail}")


# ---------------------------------------------------------------- flatten ----

@dataclass(frozen=True, slots=True)
class Holding:
    """One line of the journal: who owns it matters as much as how much."""

    ticker: str
    quantity: float
    owner: str                       # BOT, ADVISOR or MANUAL


@dataclass(frozen=True, slots=True)
class SellInstruction:
    ticker: str
    quantity: float
    reason: str


def bot_view(broker_quantities: Mapping[str, float],
             anchor_quantities: Mapping[str, float]) -> dict[str, float]:
    """What the bot may treat as its own: the broker's position minus the anchor.

    PLAN_V3 P20: an anchor is measuring equipment, not a position. Trading 212
    keeps one position per share (FACTS row g), so a bot holding and an anchor in
    the same name are ONE number at the broker, and the anchor part has to be
    subtracted by us. Anchor quantities come from the anchor ledger
    (qb2/execution/anchor_ledger.py), never from the order module itself.
    """
    return {ticker: max(quantity - anchor_quantities.get(ticker, 0.0), 0.0)
            for ticker, quantity in broker_quantities.items()}


def flatten_bot(holdings: Sequence[Holding], reason: str, *,
                broker_quantities: Mapping[str, float] | None = None,
                anchor_quantities: Mapping[str, float] | None = None,
                ) -> list[SellInstruction]:
    """Sell the bot's quantity, and only the bot's.

    If one ticker somehow has both a bot and an advisor holding -- which P6's
    no-overlap rule exists to prevent -- only the bot's share is sold. The
    advisor's is left exactly as it was.

    Given the broker's positions and the anchor ledger's quantities, a sell is
    also capped at position minus anchor, so a bot record that wrongly absorbed
    an anchor still cannot sell it (P20: flatten leaves anchors alone).
    """
    sellable = (bot_view(broker_quantities, anchor_quantities or {})
                if broker_quantities is not None else None)
    instructions: list[SellInstruction] = []
    for holding in holdings:
        if holding.owner != BOT:
            continue
        quantity = holding.quantity
        if sellable is not None:
            quantity = min(quantity, sellable.get(holding.ticker, 0.0))
        if quantity <= 0:
            continue
        instructions.append(SellInstruction(
            ticker=holding.ticker, quantity=quantity, reason=reason))
    return instructions


def bot_is_flat(holdings: Sequence[Holding],
                pending_bot_orders: Sequence[str] = ()) -> bool:
    """PLAN_V3 P4's flat check: nothing held, nothing pending."""
    held = any(h.owner == BOT and h.quantity > 0 for h in holdings)
    return not held and not pending_bot_orders


# ----------------------------------------------------------- price checks ----

def check_quote_age(market: str, age_seconds: float,
                    limits: Mapping[str, float] | None = None) -> None:
    """A stale price is the cheapest way to lose money on a good signal."""
    table = limits if limits is not None else MAX_QUOTE_AGE_SECONDS
    allowed = table.get(market)
    if allowed is None:
        raise Blocked(
            f"no quote-age limit set for market {market!r} -- refusing rather "
            f"than guessing one")
    allowed += QUOTE_AGE_MARGIN_SECONDS
    if age_seconds > allowed:
        raise Blocked(
            f"the price is {age_seconds:.0f}s old and {market} allows "
            f"{allowed:.0f}s -- too stale to trade on")


def check_price_in_band(price: float, recent_prices: Sequence[float],
                        band: float = PRICE_BAND_FRACTION) -> None:
    """Catches a decimal-point error or yesterday's price arriving as today's."""
    if price <= 0:
        raise Blocked(f"a price of {price} is not a price")
    if not recent_prices:
        raise Blocked("no recent prices to compare against -- refusing to trade blind")
    low, high = min(recent_prices), max(recent_prices)
    floor, ceiling = low * (1 - band), high * (1 + band)
    if not (floor <= price <= ceiling):
        raise Blocked(
            f"price {price:,.4f} is outside the sane band "
            f"{floor:,.4f}-{ceiling:,.4f} built from recent bars")


def check_order_size(consideration_gbp: float, pot_gbp: float,
                     cap: float = MAX_ORDER_FRACTION_OF_POT) -> None:
    """The check that still works when the price itself is wrong."""
    if consideration_gbp <= 0:
        raise Blocked("an order for nothing is not an order")
    if pot_gbp <= 0:
        raise Blocked("the pot has no value, so no order can be sized against it")
    fraction = consideration_gbp / pot_gbp
    if fraction > cap:
        raise Blocked(
            f"£{consideration_gbp:,.2f} is {fraction * 100:.1f}% of the "
            f"£{pot_gbp:,.2f} pot, over the {cap * 100:.0f}% cap")


def check_fill_gap(expected_price: float, fill_price: float,
                   limit: float = MAX_FILL_GAP_FRACTION) -> float:
    """After the fill: how far off were we? Too far stops that market.

    Returns the gap as a signed fraction so the caller can record it; raises when
    it is beyond the limit, which PLAN_V3 P14 turns into STOP_NEW_TRADES for that
    market only, because a bad feed is usually one market's problem.
    """
    if expected_price <= 0 or fill_price <= 0:
        raise Blocked("cannot compare a fill against a missing expected price")
    gap = (fill_price - expected_price) / expected_price
    if abs(gap) > limit:
        raise Blocked(
            f"filled at {fill_price:,.4f} against an expected "
            f"{expected_price:,.4f} -- {gap * 100:+.2f}%, beyond the "
            f"{limit * 100:.2f}% limit")
    return gap
