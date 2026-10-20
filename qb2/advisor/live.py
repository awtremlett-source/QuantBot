"""The advisor's ONE door to live bars (QT-23 C): final bars only, each figure with its age.

The advisor is live operation, not research, so it reads past the holdout seal: its forward
record from the arm date IS its test (ADV-0's register; PLAN_V3 S12). Two rules keep that honest:
* only bars FINAL when read -- dated on or before the daily top-up's ``fetched_through`` session
  (data/clean/daily_step.json), never a session that may still be trading;
* every figure carries its date, so a page can say its age; a figure older than its last
  finished session leaves the stop UNCHECKED (daily.py).
The read mirrors holdout.research_bars' daily branch (the store's own loader, the exchange-clock
check) without the seal. Every other module in qb2/advisor reads bars through here (wall:
tests/qb2/test_qt23_advisor.py). The shadows' lookback reads history to DECIDE; their SCORE
starts at the arm date (R8, shadow.py).
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qb2.data import daily_step, universe
from qb2.data.front_door import CLEAN
from qb2.ingest import daily
from qb2.research import advisor_rules, bet_groups, fills, holdout, pounds
from qb2.research.names import NameData, instrument_of

VIX = advisor_rules.VIX
VIX_MAX_AGE_DAYS = 5          # ADV-0: no VIX close within 5 calendar days before the day = missing
COLUMNS = ["open", "high", "low", "close", "volume"]


def final_through(clean_root: Path | None = None) -> date | None:
    """The newest session the daily top-up has fetched as FINAL; None before its first run."""
    path = (clean_root or CLEAN) / daily_step.MARKER
    if not path.is_file():
        return None
    seen = json.loads(path.read_text(encoding="utf-8")).get("fetched_through")
    return date.fromisoformat(str(seen)) if seen else None


def days_of(index: pd.Index, market: str) -> np.ndarray:
    """Each bar's date on its exchange's own calendar."""
    return np.asarray(holdout.local_index(index, market).date)


def bars(symbol: str, market: str, through: date, *, since: date | None = None,
         clean_root: Path | None = None) -> pd.DataFrame:
    """One name's final daily bars, dated ``since`` .. ``through`` (exchange dates)."""
    frame = daily.load(symbol, clean_root)
    if frame is None or frame.empty:
        return pd.DataFrame(columns=COLUMNS, index=pd.DatetimeIndex([], tz=holdout.EXCHANGE_TZ[market]))
    if str(getattr(frame.index, "tz", None)) != holdout.EXCHANGE_TZ[market]:
        raise ValueError(f"{symbol} daily bars are stamped {frame.index.tz}, not "
                         f"{holdout.EXCHANGE_TZ[market]}: re-clean it, never normalise here")
    days = days_of(frame.index, market)
    keep = (days <= through) & (days >= since if since is not None else True)
    return frame[keep]


def vix_before(day: date, through: date, clean_root: Path | None = None
               ) -> tuple[float | None, date | None]:
    """VIX's latest close dated BEFORE ``day``, and its date; the close is None when there is
    none within 5 calendar days (P10: missing counts as unsettled)."""
    closes = bars(VIX, "US", through, clean_root=clean_root)["close"].astype(float)
    days = days_of(closes.index, "US")
    before = np.flatnonzero(days < day)
    if not len(before):
        return None, None
    j = int(before[-1])
    when, value = days[j], float(closes.iloc[j])
    if (day - when).days > VIX_MAX_AGE_DAYS or not math.isfinite(value):
        return None, when
    return value, when


def vix_series(through: date, clean_root: Path | None = None) -> pd.Series:
    """The VIX closes the shadows' books read (advisor_book's k_at: the close before the day)."""
    return bars(VIX, "US", through, clean_root=clean_root)["close"].astype(float)


def fx(through: date, *, since: date | None = None, clean_root: Path | None = None) -> pd.DataFrame:
    """GBPUSD daily bars, final, on the clock the store stamps them on (pounds.FX_CLOCK)."""
    frame = bars(pounds.FX_SYMBOL, pounds.FX_CLOCK["1d"], through, since=since, clean_root=clean_root)
    return frame[["open", "close"]].astype(float)


def names(entries: Sequence[Mapping[str, Any]], through: date, *, since: date,
          clean_root: Path | None = None) -> tuple[list[NameData], list[str]]:
    """The advisor list as the books' NameData on live final bars: firewall.load's assembly
    (instrument, P3 pounds, bet index, dividend income), through this door."""
    groups = bet_groups.load()
    rows = list(entries)
    bets = sorted({bet_groups.group_of(str(e["yfinance"]), groups) for e in rows})
    rates = fx(through, since=since, clean_root=clean_root)
    out, skipped = [], []
    for entry in rows:
        symbol, market = str(entry["yfinance"]), universe.market_of(entry)
        instrument = instrument_of(entry)
        try:
            dollars = pounds.needs_rate(instrument.currency)
        except pounds.NoRate as why:
            skipped.append(f"{symbol}: {why}")
            continue
        b = bars(symbol, market, through, since=since, clean_root=clean_root)
        if len(b) < 2:
            skipped.append(f"{symbol}: no final daily bars")
            continue
        income, _ = advisor_rules.income(symbol, market, b, clean_root)
        out.append(NameData(symbol, market, instrument, b, fills.schedule(b.index, "1d", market),
                                     bets.index(bet_groups.group_of(symbol, groups)),
                                     pounds.align(b.index, rates, "1d") if dollars else None, income))
    return out, skipped
