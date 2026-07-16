"""Birth certificate for the frozen paper config (see execution/config.py law).

The loop-mechanics tests inject their own small strategies, so THIS file is the
only place that proves what the live paper loop actually trades: the config must
build the validated regime switcher at the deployment threshold, and a decision
on a warmed-up series must be a tradable weight.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from execution.config import CONFIG
from strategies.regime_switcher import RegimeSwitcherStrategy


def test_config_builds_switcher_at_deployment_threshold() -> None:
    strategy = CONFIG.build_strategy()
    assert isinstance(strategy, RegimeSwitcherStrategy)
    # Deployment fit 2026-07-16 on full history: threshold 1.5 (3 trials logged).
    assert CONFIG.threshold == 1.5
    assert strategy._threshold == CONFIG.threshold


def test_config_strategy_smoke_decide_returns_weight_in_range() -> None:
    # 300 synthetic bars (past the switcher's 273-bar warmup): decide() must
    # return a plain float weight the backtester/book can trade, in [0, 1].
    rng = np.random.default_rng(0)
    closes = 100.0 * np.cumprod(1.0 + rng.normal(0.0005, 0.02, size=300))
    frame = pd.DataFrame(
        {
            "event_time": [f"t{i:04d}" for i in range(300)],
            "open": closes,
            "high": closes * 1.01,
            "low": closes * 0.99,
            "close": closes,
            "volume": [1_000_000] * 300,
            "adj_close": closes,
        }
    )
    weight = CONFIG.build_strategy().decide(frame)
    assert isinstance(weight, float)
    assert 0.0 <= weight <= 1.0
