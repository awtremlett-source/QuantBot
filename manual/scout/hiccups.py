"""Hiccup radar: two detectors on two clocks.

SMALL hiccup (short-term radar) -- a routine shakeout inside an intact
uptrend: the index a few percent off its recent high but above its 200-day,
a volatility pop short of a storm, short-term breadth washed out while
long-term breadth holds. Historically a BUYING window for pullback setups,
not a reason to dump winners.

LARGE hiccup (long-haul radar) -- correction/bear risk: deep off the
52-week high or living below a flat-to-falling 200-day, long-term breadth
broken, volatility in storm, money hiding in defensives. Protect first;
no new buys until the Timing Dial recovers.

All thresholds live in the constants below -- tune freely.
"""
from __future__ import annotations

import pandas as pd

from .store import Store
from .timing import CYCLICAL_SECTORS, DEFENSIVE_SECTORS, VIX_TICKER

# ---- small-hiccup knobs ----
SMALL_DIP_MIN_PCT = 2.0      # index % below its 20-day high (at least)
SMALL_DIP_MAX_PCT = 6.0      # ...but no deeper than this
SMALL_VIX_POP = 1.20         # VIX vs its own 20-day average
SMALL_BREADTH20_MAX = 45.0   # % of stocks above 20-day: washed out below
SMALL_BREADTH200_MIN = 55.0  # ...while long-term breadth still healthy

# ---- large-hiccup knobs ----
LARGE_DIP_PCT = 8.0          # index % below its 52-week high
LARGE_VIX_STORM = 28.0
LARGE_BREADTH200_MAX = 40.0
LARGE_DEFENSIVE_LEAD = 4.0   # defensives beating cyclicals by this % (3m)


def _index_stats(df: pd.DataFrame) -> dict | None:
    if df is None or len(df) < 220:
        return None
    close = df["close"]
    last = float(close.iloc[-1])
    hi20 = float(close.rolling(20).max().iloc[-1])
    hi252 = float(close.rolling(252, min_periods=200).max().iloc[-1])
    sma200 = close.rolling(200).mean()
    sma200_now = float(sma200.iloc[-1])
    sma200_slope = float(sma200.iloc[-1] / sma200.iloc[-11] - 1.0) \
        if pd.notna(sma200.iloc[-11]) else 0.0
    return {
        "off_hi20_pct": (hi20 - last) / hi20 * 100.0 if hi20 else 0.0,
        "off_hi52_pct": (hi252 - last) / hi252 * 100.0 if hi252 else 0.0,
        "above_200": last > sma200_now,
        "sma200_falling": sma200_slope < 0,
    }


def _breadth(rows: list[dict], key: str) -> float | None:
    counted = above = 0
    for r in rows:
        snap = r["snap"]
        if snap.get(key) is not None:
            counted += 1
            if snap["close"] > snap[key]:
                above += 1
    return above / counted * 100.0 if counted >= 50 else None


def _vix(store: Store) -> tuple[float | None, float | None]:
    df = store.get_prices(VIX_TICKER)
    if len(df) < 21:
        return None, None
    level = float(df["close"].iloc[-1])
    avg20 = float(df["close"].rolling(20).mean().iloc[-1])
    return level, (level / avg20 if avg20 else None)


def _defensive_lead(rows: list[dict]) -> float | None:
    def avg(sectors):
        vals = [r["snap"]["roc63"] for r in rows
                if r.get("sector") in sectors
                and r["snap"].get("roc63") is not None]
        return (sum(vals) / len(vals)) if len(vals) >= 5 else None
    cyc, dfn = avg(CYCLICAL_SECTORS), avg(DEFENSIVE_SECTORS)
    if cyc is None or dfn is None:
        return None
    return dfn - cyc


def hiccup_scan(store: Store, rows: list[dict]) -> dict:
    """Returns {'small': {...}, 'large': {...}} each with
    active / headline / evidence (plain-English lines)."""
    ftse = _index_stats(store.get_prices("^FTSE"))
    vix_level, vix_ratio = _vix(store)
    b20 = _breadth(rows, "sma20")
    b200 = _breadth(rows, "sma200")
    dlead = _defensive_lead(rows)

    # ---------- LARGE first: it outranks small ----------
    large_ev: list[str] = []
    if ftse:
        if ftse["off_hi52_pct"] >= LARGE_DIP_PCT:
            large_ev.append(f"FTSE 100 is {ftse['off_hi52_pct']:.1f}% below "
                            f"its 52-week high.")
        if not ftse["above_200"] and ftse["sma200_falling"]:
            large_ev.append("FTSE 100 is below a falling 200-day average.")
    if b200 is not None and b200 < LARGE_BREADTH200_MAX:
        large_ev.append(f"Only {b200:.0f}% of stocks remain above their "
                        f"200-day average.")
    if vix_level is not None and vix_level > LARGE_VIX_STORM:
        large_ev.append(f"VIX {vix_level:.0f} \u2014 storm conditions.")
    if dlead is not None and dlead > LARGE_DEFENSIVE_LEAD:
        large_ev.append(f"Money is hiding: defensives beating cyclicals by "
                        f"{dlead:.1f}% over 3 months.")
    large_active = len(large_ev) >= 2

    # ---------- SMALL: only meaningful when large isn't in charge ----------
    small_ev: list[str] = []
    if ftse and SMALL_DIP_MIN_PCT <= ftse["off_hi20_pct"] <= SMALL_DIP_MAX_PCT \
            and ftse["above_200"]:
        small_ev.append(f"FTSE 100 has dipped {ftse['off_hi20_pct']:.1f}% "
                        f"from its 20-day high while holding its 200-day.")
    if vix_ratio is not None and vix_ratio >= SMALL_VIX_POP \
            and (vix_level or 0) <= LARGE_VIX_STORM:
        small_ev.append(f"VIX popped to {vix_level:.0f} \u2014 "
                        f"{(vix_ratio - 1) * 100:.0f}% above its 20-day "
                        f"norm, short of a storm.")
    if (b20 is not None and b200 is not None
            and b20 < SMALL_BREADTH20_MAX and b200 > SMALL_BREADTH200_MIN):
        small_ev.append(f"Short-term washout: {b20:.0f}% of stocks above "
                        f"their 20-day, yet {b200:.0f}% still above their "
                        f"200-day.")
    small_active = (not large_active) and len(small_ev) >= 2

    return {
        "small": {
            "active": small_active,
            "headline": ("Small hiccup \u2014 a routine shakeout inside an "
                         "uptrend. Historically a buying window for "
                         "pullback setups, not a reason to dump winners."),
            "evidence": small_ev,
        },
        "large": {
            "active": large_active,
            "headline": ("LARGE hiccup \u2014 correction risk. Protect "
                         "first: honour every sell alert, no new buys "
                         "until the dial recovers."),
            "evidence": large_ev,
        },
    }
