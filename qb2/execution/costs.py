"""What a trade really costs, per instrument, in pounds.

A strategy that ignores costs is a strategy that has not been tested. At the
sizes this account trades, the costs below are often larger than the edge being
hunted, which is the whole reason PLAN_V3 P17 exists: the bot's market is decided
by what survives these numbers, not by preference.

Every rate here traces to a checked row in docs/t212/FACTS.md:

* **FX 0.15% per leg** (row l) -- "whenever you buy or sell a share priced in a
  currency you do not hold". A US round trip therefore pays it TWICE: 0.30% gone
  before any edge appears.
* **Stamp duty 0.5%** (rows m1-m3) -- UK share purchases only. Never on a sell,
  never on an ETF, never on an AIM share. That last one depends on the
  instrument, not on the ticker's shape, so it is carried as a flag we must be
  told rather than something we guess.
* **PTM levy GBP 1.50** (row m4) on orders over GBP 10,000, on both buy and sell.

Spread and slippage are NOT broker-published figures. They are STARTING FIGURES,
to be replaced by measurements from the fill recorder once real fills exist. They
are deliberately pessimistic, and the ``stress`` multiplier doubles everything for
the 2x test the firewall requires.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- checked rates (docs/t212/FACTS.md) --------------------------------------
FX_FEE_RATE = 0.0015                 # row l, EACH leg
STAMP_DUTY_RATE = 0.005              # rows m1-m3, UK share BUY only
PTM_LEVY_GBP = 1.50                  # row m4
PTM_THRESHOLD_GBP = 10_000.0         # row m4

# --- starting figures: pessimistic guesses, to be measured and replaced ------
# STARTING FIGURE, tested first -- half-spread paid on each leg, in basis points
# (1 bp = 0.01%). London is wider than large-cap US on purpose.
SPREAD_BPS_BY_MARKET = {"US": 3.0, "LSE": 8.0}
# STARTING FIGURE -- extended hours are thinner, so the spread is worse (row k2
# warns of "wider spreads" and "less liquidity").
EXTENDED_HOURS_SPREAD_MULTIPLIER = 3.0
# STARTING FIGURE -- what we lose to the market moving while the order travels.
SLIPPAGE_BPS = 2.0

BASIS_POINT = 1e-4


# The vocabulary is Trading 212's, read off the saved instrument list on
# 2026-10-01 (FACTS row q): 12,177 STOCK, 6,283 ETF, 23 WARRANT. We used to say
# "SHARE", which no broker field ever contains -- see the validation below for
# why that mattered so much.
KINDS = frozenset({"STOCK", "ETF", "WARRANT"})
MARKETS = frozenset({"US", "LSE"})
# All sterling, all the same money. T212 writes pence "GBX" and yfinance writes it
# "GBp" (FACTS row r); a London share quoted in pence needs no conversion from a
# sterling account, so it must not be charged the row-l fee.
STERLING = frozenset({"GBP", "GBX", "GBp"})


@dataclass(frozen=True, slots=True)
class Instrument:
    """The facts about an instrument that change what it costs to trade.

    ``aim`` cannot be inferred from a ticker, and neither can ``kind`` reliably,
    so both are carried explicitly. Getting one wrong makes a strategy look
    cheaper than it is, which is the expensive direction to be wrong in.

    ``kind`` and ``market`` are checked here rather than trusted, because both
    of this model's real defects worked the same way: an unrecognised value fell
    through a comparison and the charge silently became zero. A model that is
    quietly optimistic is worse than one that stops.
    """

    ticker: str
    currency: str                    # "GBP", "GBX"/"GBp" (pence), "USD", ...
    market: str                      # "LSE" or "US"
    kind: str                        # T212's own word: "STOCK", "ETF", "WARRANT"
    aim: bool = False                # AIM shares are exempt from stamp duty

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(
                f"unknown instrument kind {self.kind!r} for {self.ticker!r}: "
                f"use one of Trading 212's own words {sorted(KINDS)}. Refusing "
                "rather than costing this trade at zero stamp duty")
        if self.market not in MARKETS:
            raise ValueError(
                f"unknown market {self.market!r} for {self.ticker!r}: "
                f"use one of {sorted(MARKETS)}")

    @property
    def pays_stamp_duty_on_buy(self) -> bool:
        """UK shares only -- not ETFs (row m2), not AIM (row m3)."""
        return (self.market == "LSE" and self.kind == "STOCK" and not self.aim)

    @property
    def pays_fx_fee(self) -> bool:
        """Anything not priced in sterling, whatever sterling is spelled (row l).

        This is true of some LONDON lines too: T212 quotes AGGG.L, IGLN.L,
        XDWD.L and even CPG.L -- a FTSE 100 member -- in US dollars, so a UK
        name can pay the conversion fee on both legs (FACTS row r).
        """
        return self.currency not in STERLING


@dataclass(frozen=True, slots=True)
class LegCost:
    """What one buy or one sell costs, in pounds, itemised so it can be argued with."""

    side: str                        # "BUY" or "SELL"
    consideration_gbp: float
    spread_gbp: float
    slippage_gbp: float
    fx_fee_gbp: float
    stamp_duty_gbp: float
    ptm_levy_gbp: float

    @property
    def total_gbp(self) -> float:
        return (self.spread_gbp + self.slippage_gbp + self.fx_fee_gbp
                + self.stamp_duty_gbp + self.ptm_levy_gbp)

    @property
    def fraction_of_consideration(self) -> float:
        if self.consideration_gbp <= 0:
            return 0.0
        return self.total_gbp / self.consideration_gbp


@dataclass(frozen=True, slots=True)
class RoundTrip:
    """Buy plus sell. The number a strategy has to beat before it is an edge."""

    instrument: Instrument
    buy: LegCost
    sell: LegCost
    stress: float

    @property
    def total_gbp(self) -> float:
        return self.buy.total_gbp + self.sell.total_gbp

    @property
    def fraction(self) -> float:
        if self.buy.consideration_gbp <= 0:
            return 0.0
        return self.total_gbp / self.buy.consideration_gbp


def leg_cost(instrument: Instrument, consideration_gbp: float, side: str,
             *, extended_hours: bool = False, stress: float = 1.0) -> LegCost:
    """Cost of one leg. ``stress=2.0`` is the doubling the firewall demands.

    The statutory charges are doubled too. That is deliberate and slightly
    unfair to the strategy: stamp duty will not really double, but a cost model
    that stresses only the parts we guessed would flatter exactly the trades
    whose costs are certain.
    """
    if side not in ("BUY", "SELL"):
        raise ValueError(f"side must be BUY or SELL, not {side!r}")
    if consideration_gbp < 0:
        raise ValueError("consideration cannot be negative")

    spread_bps = SPREAD_BPS_BY_MARKET.get(instrument.market)
    if spread_bps is None:
        raise ValueError(
            f"no spread figure for market {instrument.market!r} -- add one to "
            f"SPREAD_BPS_BY_MARKET rather than letting a trade be costed at zero")
    if extended_hours:
        spread_bps *= EXTENDED_HOURS_SPREAD_MULTIPLIER

    spread = consideration_gbp * spread_bps * BASIS_POINT
    slippage = consideration_gbp * SLIPPAGE_BPS * BASIS_POINT
    fx = consideration_gbp * FX_FEE_RATE if instrument.pays_fx_fee else 0.0
    duty = (consideration_gbp * STAMP_DUTY_RATE
            if side == "BUY" and instrument.pays_stamp_duty_on_buy else 0.0)
    ptm = PTM_LEVY_GBP if consideration_gbp > PTM_THRESHOLD_GBP else 0.0

    return LegCost(side=side, consideration_gbp=consideration_gbp,
                   spread_gbp=spread * stress, slippage_gbp=slippage * stress,
                   fx_fee_gbp=fx * stress, stamp_duty_gbp=duty * stress,
                   ptm_levy_gbp=ptm * stress)


def round_trip(instrument: Instrument, consideration_gbp: float, *,
               extended_hours: bool = False, stress: float = 1.0) -> RoundTrip:
    """Buy then sell the same value. What the bot must clear to make a penny."""
    return RoundTrip(
        instrument=instrument,
        buy=leg_cost(instrument, consideration_gbp, "BUY",
                     extended_hours=extended_hours, stress=stress),
        sell=leg_cost(instrument, consideration_gbp, "SELL",
                      extended_hours=extended_hours, stress=stress),
        stress=stress)


def describe(trip: RoundTrip) -> str:
    """One readable line, because a cost nobody looks at is a cost nobody fixes."""
    return (f"{trip.instrument.ticker}: round trip on "
            f"£{trip.buy.consideration_gbp:,.0f} costs £{trip.total_gbp:,.2f} "
            f"({trip.fraction * 100:.3f}%) at {trip.stress:g}x costs")
