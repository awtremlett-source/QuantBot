"""The indicators P19 and P20 need: EMA, Wilder ATR, Keltner Channels.

PORTED, NOT IMPORTED. ``atr_wilder`` is copied from manual/scout/indicators.py
(SHA-256 of that file at copy time, 2026-10-10:
2f1b40b85b2747fdc061caf26bcdc7521450c065b2684e543d6e58b43ba57118) so qb2 has the
codebase's ONE Wilder ATR definition -- ewm(alpha=1/n, adjust=False) over the
true range -- without reaching into the operator's app.

PLAN_V3 P19, fixed 2026-10-03: Keltner's middle line is EMA 21 and its bands are
+/- 2.0 x Wilder ATR(14). Every function here is causal: the value on a bar uses
that bar and earlier bars only.
"""

from __future__ import annotations

import pandas as pd

KELTNER_EMA = 21
KELTNER_ATR = 14
KELTNER_MULTIPLE = 2.0


def ema(close: pd.Series, span: int) -> pd.Series:
    """Exponential moving average, adjust=False (the recursive, causal form)."""
    return close.ewm(span=span, adjust=False).mean()


def atr_wilder(df: pd.DataFrame, n: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def keltner(df: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
    """(lower, middle, upper): EMA 21 +/- 2.0 x Wilder ATR(14)."""
    middle = ema(df["close"], KELTNER_EMA)
    width = KELTNER_MULTIPLE * atr_wilder(df, KELTNER_ATR)
    return middle - width, middle, middle + width
