"""Market regime banner: is the tide with you today?

Per index: Risk-On when price > 200-day and 50-day > 200-day;
Risk-Off when both are below; Neutral otherwise. The overall banner
combines FTSE 100 and FTSE 250.
"""
from __future__ import annotations

import pandas as pd

from .indicators import sma
from .store import Store
from .universe import INDEX_TICKERS

COLOURS = {"Risk-On": "#3fb950", "Neutral": "#d29922", "Risk-Off": "#f85149"}
GUIDANCE = {
    "Risk-On": "Tide is with you \u2014 breakouts favoured, normal size.",
    "Neutral": "Mixed tape \u2014 be selective, prefer pullbacks, smaller size.",
    "Risk-Off": "Headwind \u2014 fewer trades, half size, focus on exits.",
}


def classify_index(df: pd.DataFrame) -> str:
    if df is None or len(df) < 200:
        return "Neutral"
    close = df["close"]
    s50 = sma(close, 50).iloc[-1]
    s200 = sma(close, 200).iloc[-1]
    last = close.iloc[-1]
    if pd.isna(s50) or pd.isna(s200):
        return "Neutral"
    if last > s200 and s50 > s200:
        return "Risk-On"
    if last < s200 and s50 < s200:
        return "Risk-Off"
    return "Neutral"


def regime(store: Store) -> dict:
    states: dict[str, str] = {}
    for ticker, label in INDEX_TICKERS.items():
        states[label] = classify_index(store.get_prices(ticker))
    values = list(states.values())
    if all(v == "Risk-On" for v in values):
        overall = "Risk-On"
    elif all(v == "Risk-Off" for v in values):
        overall = "Risk-Off"
    else:
        overall = "Neutral"
    return {
        "overall": overall,
        "colour": COLOURS[overall],
        "guidance": GUIDANCE[overall],
        "per_index": states,
    }
