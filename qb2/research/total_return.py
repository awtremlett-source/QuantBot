"""What a holding actually made, in pounds, after dividends and currency.

PLAN_V3 P3: *"Returns are measured in pounds terms including the effect of currency
moves and dividends, so a US holding that rose while the dollar fell is not
reported as a win it was not."* This is the function that makes that true, and
there are exactly three ways to get it wrong -- each is guarded here.

**Counting dividends twice.** yfinance offers an ``Adj Close`` column with
dividends already reinvested. Adding our dividend table to that is double
counting, and it flatters every single back-test by roughly the dividend yield.
Nothing here touches Adj Close: the clean daily store never saved that column, and
:func:`refuse_adjusted_close` exists so the mistake fails loudly rather than
quietly inflating a number.

**Mixing units.** A London share is quoted in pence and pays in pence. The clean
store converts both to pounds at the boundary, so by the time anything reaches
here it is all pounds -- but a pence price with a pound dividend is a 100x error
that still looks plausible, so the test suite plants one and watches this go red.

**Converting at the wrong moment.** A dividend paid in March and one paid in
September met different exchange rates. Converting the total at today's rate
pretends otherwise, so each payment is converted at the rate on its own ex-date.

Withholding tax is a stated assumption, not a buried constant: see
:data:`WITHHOLDING`. Both figures are always reported -- gross, and net of it --
because which one is right depends on paperwork we have not done yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from qb2.ingest import daily, dividends

# A NAMED ASSUMPTION, not a fact about this account yet.
# * US 15% is the rate a UK resident pays on US dividends ONCE a W-8BEN form is on
#   file with the broker. Without it the rate is 30%.
# * UK 0%: UK companies pay dividends with no tax withheld at source.
# Neither has been confirmed for this account, which is why both the gross and the
# net figure are always reported rather than one "answer".
WITHHOLDING: dict[str, float] = {"US": 0.15, "LSE": 0.0}
WITHHOLDING_BASIS = (
    "US 15% assumes a W-8BEN is on file (30% without it); UK 0% is withheld at "
    "source. NEITHER IS CONFIRMED for this account -- gross and net are both shown."
)

STERLING = frozenset({"GBP", "GBp", "GBX"})


class TotalReturnError(RuntimeError):
    """Something needed was missing or wrong. Never guessed past."""


@dataclass(frozen=True, slots=True)
class Holding:
    """What one holding did over one period, itemised so it can be argued with."""

    symbol: str
    market: str
    currency: str
    start: str
    end: str
    close_start: float
    close_end: float
    dividends_local: float
    dividends_gbp_gross: float
    dividends_gbp_net: float
    rate_start: float
    rate_end: float
    start_value_gbp: float
    end_value_gbp_gross: float
    end_value_gbp_net: float
    payments: int
    suspect_payments: int

    @property
    def price_return_local(self) -> float:
        return self.close_end / self.close_start - 1.0

    @property
    def total_return_gross(self) -> float:
        return self.end_value_gbp_gross / self.start_value_gbp - 1.0

    @property
    def total_return_net(self) -> float:
        return self.end_value_gbp_net / self.start_value_gbp - 1.0

    @property
    def currency_effect(self) -> float:
        """How much of the pound return was the exchange rate, not the share.

        A US holding that rose 5% while the dollar fell 6% is a LOSS in pounds.
        This is the number that says so.
        """
        price_only_gbp = self.close_end / self.rate_end
        without_fx = self.close_end / self.rate_start
        return (price_only_gbp - without_fx) / self.start_value_gbp


def refuse_adjusted_close(frame: pd.DataFrame) -> None:
    """Stop if an adjusted-close column is present. Double counting is silent.

    A frame carrying "Adj Close" has dividends in it already. Adding the dividend
    table to that counts them twice, and the result looks entirely reasonable --
    just better than the truth, every time, for ever.
    """
    offenders = [str(c) for c in frame.columns
                 if str(c).strip().lower().replace("_", " ") in
                 ("adj close", "adjclose", "adjusted close")]
    if offenders:
        raise TotalReturnError(
            f"this frame carries {offenders}, which already includes dividends. "
            "Adding the dividend table to it would count every payout twice. Use "
            "the raw close.")


def _rate_on(day: object, fx: pd.DataFrame | None) -> float:
    """GBP/USD on a date: how many dollars one pound buys."""
    if fx is None or fx.empty:
        raise TotalReturnError(
            "no GBP/USD daily series in the clean store -- a pound figure for a "
            "dollar holding cannot be produced without it")
    wanted = pd.Timestamp(day)
    if wanted.tzinfo is not None:
        wanted = wanted.tz_convert(None)
    index = pd.DatetimeIndex(fx.index)
    naive = index.tz_convert(None) if index.tz is not None else index
    earlier = naive[naive <= wanted]
    if len(earlier) == 0:
        raise TotalReturnError(f"no exchange rate on or before {wanted.date()}")
    position = list(naive).index(earlier[-1])
    return float(fx["close"].to_numpy()[position])


def holding_return(symbol: str, start: object, end: object, *,
                   clean_root: Path | None = None,
                   prices: pd.DataFrame | None = None,
                   payouts: pd.DataFrame | None = None,
                   fx: pd.DataFrame | None = None,
                   knowable_at: datetime | None = None) -> Holding:
    """Total return for one holding between two dates, in pounds.

    ``knowable_at`` restricts the dividend table to what was publishable by that
    moment, so a back-test cannot be handed a payout that had not gone ex yet.
    """
    frame = prices if prices is not None else daily.load(symbol, clean_root)
    if frame is None or frame.empty:
        raise TotalReturnError(f"no daily prices for {symbol} in the clean store")
    refuse_adjusted_close(frame)

    market = "LSE" if symbol.endswith(".L") else "US"
    currency = str(frame["currency"].iloc[0]) if "currency" in frame.columns \
        else ("GBP" if market == "LSE" else "USD")
    sterling = currency in STERLING

    close_start = daily.close_on(symbol, start, clean_root) if prices is None \
        else _close_from(frame, start)
    close_end = daily.close_on(symbol, end, clean_root) if prices is None \
        else _close_from(frame, end)
    if close_start is None or close_end is None:
        raise TotalReturnError(
            f"{symbol}: no close on or near {start} / {end} -- refusing to guess")

    table = payouts if payouts is not None else dividends.load(symbol, clean_root)
    if table is not None and knowable_at is not None:
        table = dividends.knowable_at(table, knowable_at)

    rate_start = 1.0 if sterling else _rate_on(start, _fx(fx, clean_root))
    rate_end = 1.0 if sterling else _rate_on(end, _fx(fx, clean_root))

    local_total = 0.0
    gross_gbp = 0.0
    payments = 0
    suspect = 0
    withheld = WITHHOLDING.get(market, 0.0)
    if table is not None and not table.empty:
        window = table[(table["ex_date"] > str(pd.Timestamp(start).date()))
                       & (table["ex_date"] <= str(pd.Timestamp(end).date()))]
        for _, row in window.iterrows():
            amount = float(row["amount"])
            local_total += amount
            payments += 1
            if str(row.get("verdict")) == "SUSPECT":
                suspect += 1
            # Each payment meets the rate of ITS OWN ex-date, not today's.
            rate = 1.0 if sterling else _rate_on(row["ex_date"],
                                                 _fx(fx, clean_root))
            gross_gbp += amount / rate

    net_gbp = gross_gbp * (1.0 - withheld)
    start_value = close_start / rate_start
    return Holding(
        symbol=symbol, market=market, currency=currency,
        start=str(pd.Timestamp(start).date()), end=str(pd.Timestamp(end).date()),
        close_start=close_start, close_end=close_end,
        dividends_local=local_total,
        dividends_gbp_gross=gross_gbp, dividends_gbp_net=net_gbp,
        rate_start=rate_start, rate_end=rate_end,
        start_value_gbp=start_value,
        end_value_gbp_gross=close_end / rate_end + gross_gbp,
        end_value_gbp_net=close_end / rate_end + net_gbp,
        payments=payments, suspect_payments=suspect)


def _close_from(frame: pd.DataFrame, day: object) -> float | None:
    wanted = pd.Timestamp(day)
    if wanted.tzinfo is not None:
        wanted = wanted.tz_convert(None)
    index = pd.DatetimeIndex(frame.index)
    naive = index.tz_convert(None) if index.tz is not None else index
    earlier = naive[naive <= wanted]
    if len(earlier) == 0:
        return None
    return float(frame["close"].to_numpy()[list(naive).index(earlier[-1])])


_FX_CACHE: dict[str, pd.DataFrame | None] = {}


def _fx(given: pd.DataFrame | None, clean_root: Path | None) -> pd.DataFrame | None:
    if given is not None:
        return given
    key = str(clean_root)
    if key not in _FX_CACHE:
        _FX_CACHE[key] = daily.load(daily.FX_PAIR, clean_root)
    return _FX_CACHE[key]


def describe(holding: Holding) -> str:
    """Plain words, with both figures, because only one of them may apply."""
    return "\n".join([
        f"{holding.symbol} ({holding.market}, quoted {holding.currency}) "
        f"{holding.start} to {holding.end}",
        f"  price alone      {holding.price_return_local:+7.2%} "
        f"({holding.close_start:,.4f} -> {holding.close_end:,.4f})",
        f"  dividends        {holding.payments} payment(s), "
        f"{holding.dividends_local:,.4f} in the quote currency"
        + (f", {holding.suspect_payments} SUSPECT" if holding.suspect_payments
           else ""),
        f"  currency effect  {holding.currency_effect:+7.2%}",
        f"  TOTAL in pounds  gross {holding.total_return_gross:+7.2%} · "
        f"net {holding.total_return_net:+7.2%}",
        f"  withholding      {WITHHOLDING.get(holding.market, 0.0):.0%} — "
        f"{WITHHOLDING_BASIS}",
    ])
