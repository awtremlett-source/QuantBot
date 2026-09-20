"""Fixtures for the manual (TradeScout) suite.

Qt runs OFFSCREEN: these tests must pass on a headless machine and must never
pop a window during a run. The setting is applied at import time, before any
QApplication can exist.

TWO ENVIRONMENTS, ON PURPOSE. The manual app's pins (requirements-ui.txt:
pandas 2.x, yfinance 0.2.x, PySide6) CONFLICT with the engine's pins
(requirements.txt: pandas 3.x, yfinance 1.x). They are never installed
together. So when this interpreter has no UI dependencies -- which is the
normal case inside the engine's .venv -- this suite is NOT COLLECTED and says
so on stderr, leaving the engine's own `python -m pytest -q` green and
unchanged. Run the manual suite with the UI interpreter instead:

    py -3.13 -m pytest tests/manual -q

See docs/merge/MERGE_PLAN.md ("two books, two environments").
"""
import importlib.util
import os
import sys

import numpy as np
import pandas as pd
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_MISSING = [name for name in ("PySide6", "mplfinance")
            if importlib.util.find_spec(name) is None]
if _MISSING:
    print(f"tests/manual NOT COLLECTED: this interpreter is missing "
          f"{', '.join(_MISSING)} -- install requirements-ui.txt in a "
          f"separate venv (never into .venv).", file=sys.stderr)
    collect_ignore_glob = ["test_*.py"]

from manual.scout.config import Config  # noqa: E402  (after the Qt setting)
from manual.scout.store import Store  # noqa: E402


def make_ohlcv(closes, volumes=None, start="2024-01-02",
               spread_pct=0.01) -> pd.DataFrame:
    closes = np.asarray(closes, dtype=float)
    n = len(closes)
    if volumes is None:
        volumes = np.full(n, 1_000_000.0)
    idx = pd.bdate_range(start=start, periods=n)
    opens = np.concatenate([[closes[0]], closes[:-1]])
    highs = np.maximum(opens, closes) * (1 + spread_pct)
    lows = np.minimum(opens, closes) * (1 - spread_pct)
    return pd.DataFrame({"open": opens, "high": highs, "low": lows,
                         "close": closes, "volume": np.asarray(volumes,
                                                               dtype=float)},
                        index=idx)


def uptrend_df(n=300, start_price=100.0, step=0.4):
    closes = start_price + step * np.arange(n)
    return make_ohlcv(closes)


def downtrend_df(n=300, start_price=400.0, step=0.5):
    closes = start_price - step * np.arange(n)
    closes = np.maximum(closes, 5.0)
    return make_ohlcv(closes)


def base_snap(**over) -> dict:
    s = {
        "close": 500.0, "close_gbp": 5.0, "prev_close": 495.0,
        "sma20": None, "sma50": None, "sma200": None, "sma50_slope": None,
        "rsi": None, "macd_hist": None, "macd_hist_delta": None,
        "roc21": None, "roc63": None,
        "atr": 10.0, "atr_gbp": 0.10, "atr_pct": 2.0,
        "vol_ratio": 1.0, "volume": 1_000_000,
        "hi52": None, "lo52": None, "pos52": None,
        "dist_to_hi_pct": None, "dist_to_lo_pct": None,
        "gap_pct": 0.0, "turnover_gbp": 5_000_000.0,
        "up_day": True, "down_day": False,
        "golden_cross_recent": False, "death_cross_recent": False,
        "bars": 300, "currency": "GBp",
    }
    s.update(over)
    return s


@pytest.fixture
def cfg() -> Config:
    return Config()


@pytest.fixture
def tmp_store(tmp_path) -> Store:
    s = Store(tmp_path / "test.db")
    yield s
    s.close()
