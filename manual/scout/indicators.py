"""Indicator engine. Pure functions: OHLCV DataFrame in, values out.

Conventions: Wilder smoothing (ewm alpha=1/n, adjust=False) for RSI and ATR;
standard 12/26/9 EMAs for MACD; 252 trading days for the 52-week window.
Prices arrive in the instrument's quote currency (usually GBp = pence);
close_gbp / atr_gbp are the pounds conversions used for money maths.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

MIN_BARS = 220          # below this a ticker is excluded from scoring
WK52 = 252
CROSS_LOOKBACK = 15     # bars for "recent" golden/death cross


def to_gbp(value: float, currency: str) -> float | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    cur = (currency or "GBp").strip()
    if cur.lower() == "gbp" and cur != "GBp":      # 'GBP' pounds
        return float(value)
    if cur == "GBp" or cur.lower() in ("gbx", "gbp_pence"):
        return float(value) / 100.0
    if cur.upper() == "GBP":
        return float(value)
    return None  # non-sterling line: money maths not available offline


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def rsi_wilder(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / n, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / n, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - 100.0 / (1.0 + rs)
    return rsi.fillna(100.0).where(close.notna())


def macd(close: pd.Series, fast: int = 12, slow: int = 26, sig: int = 9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    line = ema_fast - ema_slow
    signal = line.ewm(span=sig, adjust=False).mean()
    hist = line - signal
    return line, signal, hist


def atr_wilder(df: pd.DataFrame, n: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def roc(close: pd.Series, n: int) -> pd.Series:
    return close.pct_change(n) * 100.0


def compute_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of df with all indicator columns added."""
    out = df.copy()
    c = out["close"]
    out["sma20"] = sma(c, 20)
    out["sma50"] = sma(c, 50)
    out["sma200"] = sma(c, 200)
    out["sma50_slope"] = out["sma50"] / out["sma50"].shift(10) - 1.0
    out["rsi"] = rsi_wilder(c)
    _, _, hist = macd(c)
    out["macd_hist"] = hist
    out["macd_hist_delta"] = hist.diff()
    out["atr"] = atr_wilder(out)
    out["atr_pct"] = out["atr"] / c * 100.0
    out["roc21"] = roc(c, 21)
    out["roc63"] = roc(c, 63)
    out["vol_ratio"] = out["volume"] / out["volume"].rolling(20, min_periods=20).mean()
    out["hi52"] = c.rolling(WK52, min_periods=200).max()
    out["lo52"] = c.rolling(WK52, min_periods=200).min()
    out["roc126"] = roc(c, 126)
    out["roc252"] = roc(c, 252) if len(c) > 252 else float("nan")
    return out


def _recent_cross(sma_fast: pd.Series, sma_slow: pd.Series,
                  lookback: int, golden: bool) -> bool:
    rel = (sma_fast > sma_slow).astype("float64")
    rel = rel.where(sma_fast.notna() & sma_slow.notna())
    tail = rel.dropna().tail(lookback + 1)
    if len(tail) < 2:
        return False
    diffs = tail.diff().dropna()
    return bool((diffs > 0).any()) if golden else bool((diffs < 0).any())


def snapshot(df: pd.DataFrame, currency: str = "GBp") -> dict | None:
    """Latest-bar snapshot of everything scoring/risk needs, or None if the
    history is too short."""
    if df is None or len(df) < MIN_BARS:
        return None
    f = compute_frame(df)
    last = f.iloc[-1]
    prev = f.iloc[-2]
    close = float(last["close"])
    if not np.isfinite(close) or close <= 0:
        return None
    hi52 = float(last["hi52"]) if pd.notna(last["hi52"]) else None
    lo52 = float(last["lo52"]) if pd.notna(last["lo52"]) else None
    pos52 = dist_hi = dist_lo = None
    if hi52 and lo52 is not None:
        rng = hi52 - lo52
        pos52 = (close - lo52) / rng if rng > 0 else 1.0
        dist_hi = (hi52 - close) / hi52 * 100.0
        dist_lo = (close - lo52) / lo52 * 100.0 if lo52 > 0 else None
    prev_close = float(prev["close"])
    open_px = float(last["open"]) if pd.notna(last["open"]) else close
    gap_pct = (open_px - prev_close) / prev_close * 100.0 if prev_close else 0.0

    close_gbp = to_gbp(close, currency)
    atr = float(last["atr"]) if pd.notna(last["atr"]) else None
    atr_gbp = to_gbp(atr, currency) if atr is not None else None
    volume = float(last["volume"]) if pd.notna(last["volume"]) else 0.0
    turnover = None
    if close_gbp is not None:
        gbp_close_series = f["close"] / (100.0 if close_gbp != close else 1.0)
        turnover_series = (gbp_close_series * f["volume"]).rolling(20, min_periods=20).mean()
        tv = turnover_series.iloc[-1]
        turnover = float(tv) if pd.notna(tv) else None

    def _v(name):
        v = last[name]
        return float(v) if pd.notna(v) else None

    return {
        "close": close, "close_gbp": close_gbp, "prev_close": prev_close,
        "sma20": _v("sma20"), "sma50": _v("sma50"), "sma200": _v("sma200"),
        "sma50_slope": _v("sma50_slope"), "rsi": _v("rsi"),
        "macd_hist": _v("macd_hist"), "macd_hist_delta": _v("macd_hist_delta"),
        "roc21": _v("roc21"), "roc63": _v("roc63"),
        "atr": atr, "atr_gbp": atr_gbp, "atr_pct": _v("atr_pct"),
        "vol_ratio": _v("vol_ratio"), "volume": volume,
        "hi52": hi52, "lo52": lo52, "pos52": pos52,
        "dist_to_hi_pct": dist_hi, "dist_to_lo_pct": dist_lo,
        "gap_pct": gap_pct, "turnover_gbp": turnover,
        "up_day": close > prev_close, "down_day": close < prev_close,
        "golden_cross_recent": _recent_cross(f["sma50"], f["sma200"],
                                             CROSS_LOOKBACK, golden=True),
        "death_cross_recent": _recent_cross(f["sma50"], f["sma200"],
                                            CROSS_LOOKBACK, golden=False),
        "bars": len(df), "currency": currency,
        "roc126": _v("roc126"),
        "roc252": _v("roc252") if len(df) > 252 else None,
        "above200_frac": _above_frac(f),
    }


def _above_frac(f: pd.DataFrame, window: int = 126) -> float | None:
    """Share of the last `window` bars spent above the 200-day average."""
    valid = f.dropna(subset=["sma200"]).tail(window)
    if len(valid) < window // 2:
        return None
    return float((valid["close"] > valid["sma200"]).mean())
