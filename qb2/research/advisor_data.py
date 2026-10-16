"""What S9 batch 1 reads, loaded once and fingerprinted (QT-19 B2).

* the advisor list's daily bars through the holdout door, each cut to start 253 of its
  own bars before its first bar dated on/after 2014-04-01 (the register's warm-up);
* each name's dividend income (P3): payouts the dividend check marks OK, / the
  previous close, US net of 15% withholding (total_return.WITHHOLDING), credited on
  the first bar on or after the ex-date; SUSPECT and UNCHECKED rows get nothing;
* VIX daily closes (P10's "unsettled"), and A-06's market filter per month: VWRP's
  close above the mean of its last 200 (VWRL's while VWRP has fewer than 200);
* fingerprints (a) the bars, dividends and earnings rows the trials read, (b) the
  sealed daily year the holdout run would read -- by content, so the after-hours
  top-up appending a day is not a change and a revised price is.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qb2.data import data_fingerprint, universe
from qb2.execution import costs
from qb2.ingest import dividends
from qb2.research import advisor_book, benchmark, firewall, holdout, total_return

OOS_FROM = date(2014, 4, 1)
WARMUP = 253
UNSEALED_END = date(2025, 10, 9)
HOLDOUT_END = date(2026, 10, 9)
VIX = "^VIX"
FILTER_BARS = 200


def trim(bars: pd.DataFrame, instrument: costs.Instrument | None = None,
         market: str = "") -> pd.DataFrame:
    """The register's cut: 253 of the name's own bars before its first on/after 2014-04-01."""
    j = int((pd.DatetimeIndex(bars.index).date < OOS_FROM).sum())          # bars are in order
    return bars.iloc[max(0, j - WARMUP):]


def income(symbol: str, market: str, bars: pd.DataFrame, clean_root: Path | None = None,
           ) -> tuple[np.ndarray, dict[str, int]]:
    """Payout / previous close on the first bar on or after each OK ex-date."""
    out = np.zeros(len(bars))
    seen = {"credited": 0, "not_ok": 0}
    rows = dividends.load(symbol, clean_root)
    if rows is None or rows.empty or len(bars) < 2:
        return out, seen
    days = pd.DatetimeIndex(bars.index).date
    close = bars["close"].to_numpy(dtype=float)
    keep = 1.0 - total_return.WITHHOLDING.get(market, 0.0)
    for _, row in rows.iterrows():
        t = int((days < date.fromisoformat(str(row["ex_date"]))).sum())   # first bar on/after
        if not 1 <= t < len(bars):
            continue
        if str(row["verdict"]) != "OK":
            seen["not_ok"] += 1
            continue
        out[t] += float(row["amount"]) / close[t - 1] * keep
        seen["credited"] += 1
    return out, seen


def entries() -> list[dict[str, Any]]:
    return universe.advisor_entries()


def load(clean_root: Path | None = None) -> tuple[list[firewall.NameData], list[str],
                                                  dict[str, int]]:
    """The arm, each name with its income; and the dividend counts."""
    data, skipped = firewall.load("1d", entries=entries(), transform=trim, clean_root=clean_root)
    counts = {"credited": 0, "not_ok": 0}
    out = []
    for name in data:
        inc, seen = income(name.symbol, name.market, name.bars, clean_root)
        counts = {k: counts[k] + seen[k] for k in counts}
        out.append(replace(name, income=inc))
    return out, skipped, counts


def closes(symbol: str, market: str, final: holdout.HoldoutPass | None = None,
           clean_root: Path | None = None) -> pd.Series:
    bars = holdout.bars_through(symbol, "1d", market, through=HOLDOUT_END if final else None,
                                final=final, clean_root=clean_root)
    return bars["close"].astype(float)


def market_filter(final: holdout.HoldoutPass | None = None,
                  clean_root: Path | None = None) -> dict[int, bool]:
    """A-06, per month: on when D3 closes above the mean of its last 200 closes."""
    vwrp = closes(benchmark.D3, "LSE", final, clean_root)
    vwrl = closes(benchmark.D3_FALLBACK, "LSE", final, clean_root)
    last = max(pd.DatetimeIndex(vwrp.index).date[-1], pd.DatetimeIndex(vwrl.index).date[-1])
    ends = advisor_book.last_sessions(advisor_book.sessions("LSE", date(2012, 1, 1), last))
    out: dict[int, bool] = {}
    for m, end in ends.items():
        for series in (vwrp, vwrl):
            upto = series[pd.DatetimeIndex(series.index).date <= end]
            if len(upto) >= FILTER_BARS:
                out[m] = bool(upto.iloc[-1] > upto.iloc[-FILTER_BARS:].mean())
                break
    return out


def vix(final: holdout.HoldoutPass | None = None, clean_root: Path | None = None) -> pd.Series:
    return closes(VIX, "US", final, clean_root)


def sealed(data: Sequence[firewall.NameData], final: holdout.HoldoutPass,
           clean_root: Path | None = None) -> list[firewall.NameData]:
    """The holdout run's names: unsealed warm-up + sealed bars to 2026-10-09, re-incomed."""
    from qb2.research import p19_run
    out = []
    for name in p19_run.sealed_names(data, "1d", final, clean_root):
        inc, _ = income(name.symbol, name.market, name.bars, clean_root)
        out.append(replace(name, income=inc, weight=None))
    return out


def fingerprints(clean_root: Path | None = None) -> dict[str, str]:
    rows = entries()
    names = [str(e["yfinance"]) for e in rows] + [benchmark.D3, data_fingerprint.FX, VIX]
    shares = [str(e["yfinance"]) for e in rows if str(e["kind"]) != "ETF"]
    a = "|".join((data_fingerprint.daily_digest(names, None, UNSEALED_END, clean_root),
                  data_fingerprint.dividends_digest([str(e["yfinance"]) for e in rows], clean_root),
                  data_fingerprint.earnings_digest(shares, clean_root)))
    return {"a": hashlib.sha256(a.encode()).hexdigest(),
            "b": data_fingerprint.daily_digest(names, date(2025, 10, 10), HOLDOUT_END, clean_root)}


def counts_text(counts: Mapping[str, int]) -> str:
    return (f"{counts['credited']:,} payouts credited; {counts['not_ok']:,} not credited "
            "(SUSPECT or UNCHECKED)")
