"""One name's data as every book reads it, and its instrument (S4; QT-23: moved out of firewall.py).

Kept apart from the firewall so the LIVE advisor builds the same NameData without importing anything
that reaches the back-test-only P15 history rule (wall: tests/wall/test_p15_history_wall.py).
firewall re-exports both, so research code reads them as before: one copy.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from qb2.data import universe
from qb2.execution import costs
from qb2.research import fills, pounds


@dataclass(frozen=True, slots=True)
class NameData:
    symbol: str
    market: str
    instrument: costs.Instrument
    bars: pd.DataFrame
    plan: fills.Schedule
    bet: int                                  # index of its bet group
    fx: pounds.Rates | None = None            # GBPUSD on these bars (dollar lines only)
    income: np.ndarray | None = None          # QT-19: payout / previous close (P3)
    weight: pd.Series | None = None           # QT-19: its share of the pot per bar (slots)


def instrument_of(entry: Mapping[str, Any]) -> costs.Instrument:
    return costs.Instrument(str(entry["t212_ticker"]), str(entry["quote_currency"]),
                            universe.market_of(entry), str(entry["kind"]), bool(entry.get("aim", False)))
