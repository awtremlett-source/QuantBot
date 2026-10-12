"""Returns in pounds: a dollar line's prices divided by GBPUSD (QT-16 A2, PLAN_V3 P3).

P3: returns are "measured in pounds terms including the effect of currency moves",
so a US holding that rose while the dollar fell is not reported as a win it was
not. QT-15 flagged that the trials marked US names in dollars: the FX FEE per leg
was charged, the FX MOVE over the holding was not.

While a dollar line is held, each bar's return is in pounds,
(1 + r_usd)(1 + r_fx) - 1, where r_fx is the dollar's move against the pound. It is
done by dividing each price by GBPUSD (dollars per pound) at the same moment -- the
open by the rate at the open, the close by the rate at the close -- which gives
exactly that product for the gap and for the body of every bar. The STRATEGY still
sees dollar prices (its signal is unchanged); only the money is in pounds. FX fees
per leg are unchanged (costs.py).

Rates are the clean store's GBPUSD=X bars of the same size. A bar takes the FX bar
that starts at the same moment (5m) or on the same date (daily). If that one is
missing it may take the latest earlier one within TOLERANCE, whose close stands for
both open and close -- a STARTING FIGURE under the STANDING GO: 10 minutes on
5-minute bars, 4 calendar days on daily bars (yfinance's daily GBPUSD skips the odd
weekday). The FX move is then booked a bar late, never lost: the next real rate
catches it up. No rate within the tolerance = MISSING, and a HELD bar with a
missing rate makes the whole trial INSUFFICIENT -- never a silent dollar figure.

Sterling lines (GBP, and GBX, which the front door stores in pounds) need nothing;
any other quote currency has no rate in the store and is refused.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from qb2.data import access
from qb2.ingest import daily

FX_SYMBOL = "GBPUSD=X"                 # dollars per pound
STERLING = frozenset({"GBP", "GBX", "GBp"})
CONVERTED = frozenset({"USD"})
TOLERANCE = {"5m": pd.Timedelta(minutes=10), "1d": pd.Timedelta(days=4)}   # starting figures


class NoRate(ValueError):
    """A line that cannot be put in pounds -- refused rather than left in its own money."""


@dataclass(frozen=True, slots=True)
class Rates:
    """GBPUSD aligned to one name's bars. NaN = missing; stale = an earlier bar's close."""

    open: NDArray[np.float64]
    close: NDArray[np.float64]
    stale: NDArray[np.bool_]

    @property
    def missing(self) -> NDArray[np.bool_]:
        return np.asarray(~(np.isfinite(self.open) & np.isfinite(self.close)))


def needs_rate(currency: str) -> bool:
    if currency in STERLING:
        return False
    if currency in CONVERTED:
        return True
    raise NoRate(f"no {currency}->GBP rate in the store, so a {currency} line cannot be "
                 "measured in pounds (P3)")


def load_fx(interval: str, clean_root: Path | None = None) -> pd.DataFrame:
    """The store's GBPUSD bars of this size, or an empty frame (every rate missing)."""
    try:
        frame = (access.bars(FX_SYMBOL, "5m", clean_root=clean_root) if interval == "5m"
                 else daily.load(FX_SYMBOL, clean_root))
    except access.AccessRefused:
        frame = None
    if frame is None or frame.empty:
        return pd.DataFrame({"open": [], "close": []}, index=pd.DatetimeIndex([], tz="UTC"))
    return frame[["open", "close"]].astype(float)


def _keys(index: pd.DatetimeIndex, interval: str) -> pd.Series:
    """5m: the bar's UTC start; daily: its date on its own exchange's calendar."""
    if interval == "5m":
        return pd.Series(pd.DatetimeIndex(index).tz_convert("UTC").tz_localize(None))
    return pd.Series(pd.to_datetime(pd.DatetimeIndex(index).date))


def align(index: pd.DatetimeIndex, fx: pd.DataFrame, interval: str) -> Rates:
    n = len(index)
    if fx.empty or n == 0:
        nan = np.full(n, np.nan)
        return Rates(nan, nan.copy(), np.zeros(n, dtype=bool))
    left = pd.DataFrame({"key": _keys(index, interval).astype("datetime64[ns]"),
                         "row": np.arange(n)})
    right = pd.DataFrame({"key": _keys(pd.DatetimeIndex(fx.index), interval)
                          .astype("datetime64[ns]").to_numpy(),
                          "fx_key": _keys(pd.DatetimeIndex(fx.index), interval)
                          .astype("datetime64[ns]").to_numpy(),
                          "o": fx["open"].to_numpy(), "c": fx["close"].to_numpy()})
    right = right.drop_duplicates("key", keep="last").sort_values("key")
    joined = pd.merge_asof(left.sort_values("key"), right, on="key", direction="backward",
                           tolerance=TOLERANCE[interval]).sort_values("row")
    exact = (joined["fx_key"] == joined["key"]).to_numpy()
    close = joined["c"].to_numpy(dtype=float)
    opened = np.where(exact, joined["o"].to_numpy(dtype=float), close)
    stale = np.isfinite(close) & ~exact
    return Rates(opened, close, stale)


def extend(rates: Rates | None, index: pd.DatetimeIndex, interval: str,
           clean_root: Path | None = None) -> Rates | None:
    """Rates re-read for a longer run of the same name's bars (the holdout pass)."""
    return None if rates is None else align(index, load_fx(interval, clean_root), interval)


def to_pounds(opens: NDArray[np.float64], closes: NDArray[np.float64],
              rates: Rates) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Dollar prices / dollars-per-pound = pound prices, moment by moment."""
    with np.errstate(invalid="ignore", divide="ignore"):
        return (np.asarray(opens, dtype=float) / rates.open,
                np.asarray(closes, dtype=float) / rates.close)
