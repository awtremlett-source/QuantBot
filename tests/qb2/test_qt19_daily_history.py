"""QT-19 Step 0.2: the daily store holds history back to 2010-01-01, and keeps it.

The routine top-up REWRITES each daily file from one fetch (one consistent split
adjustment), so the fetch itself must start at 2010-01-01: a one-off long fetch
followed by the old 3-year top-up would have cut the history back to 3 years.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pandas as pd
import pytest

from qb2.ingest import daily


def test_the_routine_fetch_starts_at_2010(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    class Ticker:
        def __init__(self, symbol: str) -> None:
            self.symbol = symbol

        def history(self, **kw: Any) -> pd.DataFrame:
            calls.append(kw)
            return pd.DataFrame()

    monkeypatch.setitem(sys.modules, "yfinance", types.SimpleNamespace(Ticker=Ticker))
    assert daily.fetch_daily("ABT") is None
    assert calls == [{"start": "2010-01-01", "interval": "1d", "auto_adjust": False}]
    assert daily.HISTORY_START == "2010-01-01"
