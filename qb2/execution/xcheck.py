"""P20: our price against Trading 212's, before a trade -- pure functions (QT-14A).

PLAN_V3 P20, agreed 2026-10-04: *"Compare yfinance with Trading 212 prices: hold one
share of each bot name in the practice account so Trading 212 prices all 50, and
cross-check before every trade."* The anchors exist (QT-12); this is the check.

**Units first.** Trading 212 quotes London in pence, pounds or dollars per line
(FACTS row r); the clean store is in pounds. Both sides are converted to the
instrument's own quote currency before anything is compared, or every pence line
would disagree by 100x and halt the market every morning.

**The rule** (``gap`` = |ours - broker's| / broker's), four outcomes:

* WARN over the warn line -- recorded, the trade proceeds;
* BLOCK over max(block floor, ATR(5m)/price, each times the scale) -- that name;
* STOP for the whole market if one name is over 5%, or 3+ names in one sweep are
  over their block line -- a feed problem is not something to trade through;
* NO_COMPARISON -- anchor missing, a price missing, unconvertible units, or a
  price past its age limit -- BLOCKS, naming why. A check that did not run must
  never read like a check that passed.

**Scaling (starting figures, STANDING GO 2026-10-07).** P20's warn and block lines
were written for a 1.6-minute feed delay. Row o measured US 1.25 and London 16.66
minutes, so each market's lines are multiplied by sqrt(delay / 1.6): a price that
is older can honestly have drifted further. The 5% single-name stop is a
feed-error bound, not a drift allowance, so it is NOT scaled (the strict side).

SHADOW until S10: the recorder logs these verdicts and counts how often each would
have fired; the sender's chain carries the check, but the sender is disarmed.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from qb2.execution import safety

BASE_DELAY_MINUTES = 1.6                         # what P20's figures assumed
ROW_O_DELAY_MINUTES = {"US": 1.25, "LSE": 16.66}  # FACTS row o, VERIFIED 2026-10-09
BASE_WARN = 0.0025                               # P20 starting figures
BASE_BLOCK = 0.005
ATR_MULTIPLE = 1.0
STOP_ONE_NAME = 0.05                             # not scaled -- see the docstring
STOP_NAMES = 3
# STARTING FIGURE: the broker's price is read by us, so its age is our own poll's.
BROKER_MAX_AGE_SECONDS = 60.0

OK = "OK"
WARN = "WARN"
BLOCK = "BLOCK"
STOP = "STOP"
NO_COMPARISON = "NO_COMPARISON"
BLOCKING = frozenset({BLOCK, STOP, NO_COMPARISON})

PENCE = frozenset({"GBX", "GBp"})
POUNDS = frozenset({"GBP"})


@dataclass(frozen=True, slots=True)
class Thresholds:
    market: str
    scale: float
    warn: float
    block_floor: float
    stop_one_name: float


def scale(market: str) -> float:
    """sqrt(row-o delay / 1.6) for that market; unknown market = refuse."""
    delay = ROW_O_DELAY_MINUTES.get(market)
    if delay is None:
        raise ValueError(f"no row-o delay for market {market!r}")
    return math.sqrt(delay / BASE_DELAY_MINUTES)


def thresholds(market: str) -> Thresholds:
    factor = scale(market)
    return Thresholds(market=market, scale=factor, warn=BASE_WARN * factor,
                      block_floor=BASE_BLOCK * factor, stop_one_name=STOP_ONE_NAME)


def to_quote(price: float | None, currency: str, quote_currency: str) -> float | None:
    """A price in ``currency`` expressed in ``quote_currency``; None if it cannot be.

    Only sterling's two spellings convert (x100 / /100). Anything else must match
    exactly: without an exchange rate a dollar price is not a pound price.
    """
    if price is None or not math.isfinite(price) or price <= 0:
        return None
    if currency == quote_currency or ({currency, quote_currency} <= PENCE):
        return float(price)
    if currency in POUNDS and quote_currency in PENCE:
        return float(price) * 100.0
    if currency in PENCE and quote_currency in POUNDS:
        return float(price) / 100.0
    return None


@dataclass(frozen=True, slots=True)
class Rating:
    ticker: str
    market: str
    level: str
    gap: float | None
    block_at: float | None
    reason: str

    @property
    def blocks(self) -> bool:
        return self.level in BLOCKING

    def as_dict(self) -> dict[str, object]:
        return {"ticker": self.ticker, "market": self.market, "level": self.level,
                "gap": self.gap, "block_at": self.block_at, "reason": self.reason}


def rate(ticker: str, market: str, *, quote_currency: str,
         broker_price: float | None, broker_currency: str,
         our_price: float | None, our_currency: str,
         our_age_seconds: float | None, atr: float | None = None,
         broker_age_seconds: float = 0.0) -> Rating:
    """One name's verdict. Never raises on bad input -- bad input is NO_COMPARISON."""
    def none(why: str) -> Rating:
        return Rating(ticker, market, NO_COMPARISON, None, None, why)

    if broker_price is None:
        return none("no Trading 212 price (anchor missing or broker unreachable)")
    if our_price is None or our_age_seconds is None:
        return none("no price of our own to compare")
    try:
        lines = thresholds(market)
        safety.check_quote_age(market, our_age_seconds)
    except (ValueError, safety.Blocked) as why:
        return none(str(why))
    if broker_age_seconds > BROKER_MAX_AGE_SECONDS:
        return none(f"Trading 212's price is {broker_age_seconds:.0f}s old")
    theirs = to_quote(broker_price, broker_currency, quote_currency)
    ours = to_quote(our_price, our_currency, quote_currency)
    if theirs is None or ours is None:
        return none(f"cannot express {broker_currency}/{our_currency} in "
                    f"{quote_currency} without an exchange rate")
    gap = abs(ours - theirs) / theirs
    atr_term = (ATR_MULTIPLE * (to_quote(atr, our_currency, quote_currency) or 0.0)
                / theirs * lines.scale) if atr else 0.0
    block_at = max(lines.block_floor, atr_term)
    if gap > lines.stop_one_name:
        return Rating(ticker, market, STOP, gap, block_at,
                      f"gap {gap:.2%} over {lines.stop_one_name:.0%}: feed or ticker problem")
    if gap > block_at:
        return Rating(ticker, market, BLOCK, gap, block_at,
                      f"gap {gap:.2%} over the block line {block_at:.2%}")
    if gap > lines.warn:
        return Rating(ticker, market, WARN, gap, block_at,
                      f"gap {gap:.2%} over the warn line {lines.warn:.2%}")
    return Rating(ticker, market, OK, gap, block_at, f"gap {gap:.2%}")


def stopped_markets(ratings: Sequence[Rating]) -> dict[str, str]:
    """Market -> why it stops: one name over 5%, or 3+ names over their block line."""
    out: dict[str, str] = {}
    by_market: dict[str, list[Rating]] = {}
    for rating in ratings:
        by_market.setdefault(rating.market, []).append(rating)
    for market, rows in by_market.items():
        huge = [r.ticker for r in rows if r.level == STOP]
        over = [r.ticker for r in rows if r.level in (BLOCK, STOP)]
        if huge:
            out[market] = f"{', '.join(huge)} over {STOP_ONE_NAME:.0%}"
        elif len(over) >= STOP_NAMES:
            out[market] = f"{len(over)} names over their block line: {', '.join(over)}"
    return out


def sweep(ratings: Sequence[Rating]) -> list[Rating]:
    """The sweep's final verdicts: every name in a stopped market becomes STOP."""
    stops = stopped_markets(ratings)
    return [replace(r, level=STOP, reason=f"{r.market} stopped: {stops[r.market]}")
            if r.market in stops else r for r in ratings]


def level_counts(ratings: Sequence[Rating]) -> Mapping[str, int]:
    counts = {level: 0 for level in (OK, WARN, BLOCK, STOP, NO_COMPARISON)}
    for rating in ratings:
        counts[rating.level] += 1
    return counts


def guard(ticker: str, rating: Rating | None) -> None:
    """The sender's step: no rating, or a blocking one, refuses -- naming why."""
    if rating is None:
        raise safety.Blocked(f"{ticker}: no price cross-check ran -- "
                             "no comparison possible = blocked (P20)")
    if rating.ticker != ticker:
        raise safety.Blocked(f"{ticker}: the cross-check given is for {rating.ticker}")
    if rating.blocks:
        raise safety.Blocked(f"{ticker}: price cross-check {rating.level}: {rating.reason}")
