"""Spotlight: the durable climbers.

Large, liquid names that have spent at least 80% of the last six months
above their 200-day average and are up over the past year -- "long-lasting
high value" rather than this week's excitement. Recomputed every scan, so
the list quietly tracks itself.
"""
from __future__ import annotations

MIN_STEADY = 0.80          # share of last 6 months above the 200-day
MIN_TURNOVER = 5_000_000   # non-FTSE100 names must be at least this liquid
TOP_N = 20


def spotlight_rows(rows: list[dict], top: int = TOP_N) -> list[dict]:
    out = []
    for r in rows:
        s = r["snap"]
        steady = s.get("above200_frac")
        if steady is None or steady < MIN_STEADY:
            continue
        if not (s.get("sma200") and s["close"] > s["sma200"]):
            continue
        if r.get("index") != "FTSE100" and \
                (s.get("turnover_gbp") or 0) < MIN_TURNOVER:
            continue
        year = s.get("roc252")
        half = s.get("roc126")
        climb = year if year is not None else half
        if climb is None or climb <= 0:
            continue
        out.append({
            "ticker": r["ticker"], "name": r["name"],
            "sector": r.get("sector", ""),
            "steady_pct": steady * 100.0,
            "year_pct": year, "half_pct": half,
            "close": s["close"], "currency": s.get("currency", "GBp"),
        })
    out.sort(key=lambda x: (x["steady_pct"],
                            x["year_pct"] if x["year_pct"] is not None
                            else x["half_pct"] or 0), reverse=True)
    return out[:top]
