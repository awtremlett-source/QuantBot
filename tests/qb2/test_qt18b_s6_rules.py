"""QT-18 B1: S6 batch 1's eight rules do exactly what the register says. Offline, synthetic bars.

Each test reads a REAL register entry (docs/research/preregistered.json) and checks
where the position lands after QT-17's fill rule and P4 (fills.positions). US days:
bars 09:30 ... 15:30 = positions 0 ... 6; E = 15:30 (position 6); E-1 = 14:30.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
import pandas as pd
import pytest

from qb2.research import fills, preregister
from qb2.research.strategy import checked_weights
from qb2.signals import s6_rules
from tests.qb2.test_qt17a_bench import _hours

DAYS = ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04", "2026-06-05"]
LDAYS = DAYS


@dataclass(frozen=True)
class FakeName:
    symbol: str
    market: str
    bars: pd.DataFrame
    plan: fills.Schedule


def _entry(cid: str) -> dict[str, Any]:
    return dict(preregister.entries()[cid])


def _name(symbol: str, close: np.ndarray, market: str = "US", opens: np.ndarray | None = None,
          spread: float = 0.5, may_enter: np.ndarray | None = None,
          days: list[str] = DAYS) -> FakeName:
    index = _hours(market, days)
    assert len(index) == len(close)
    o = np.r_[close[0], close[:-1]] if opens is None else opens
    bars = pd.DataFrame({"open": o, "high": np.maximum(o, close) + spread,
                         "low": np.minimum(o, close) - spread, "close": close,
                         "volume": 1.0}, index=index)
    return FakeName(symbol, market, bars, fills.schedule(index, "1h", market, may_enter))


def _held(cid: str, data: list[FakeName], who: int = 0) -> np.ndarray:
    make = s6_rules.maker(_entry(cid), data)
    name = data[who]
    weights = checked_weights(make(name), name.bars)        # look-ahead check runs too
    return fills.positions(name.plan, weights)


def _day(held: np.ndarray, k: int, per: int = 7) -> list[int]:
    return [int(x) for x in held[k * per:(k + 1) * per]]


def _flat(n_days: int = 5, per: int = 7, level: float = 100.0) -> np.ndarray:
    return np.full(n_days * per, level)


def test_intraday_mom_holds_only_bar_e_minus_1_after_an_up_first_bar() -> None:
    c = _flat()
    c[7:14] = 101.0                                  # day 2: first bar closes above 100
    c[14:21] = 100.0                                 # day 3: first bar back at 100 (not > 101)
    c[21:28] = 99.0                                  # day 4: first bar down
    held = _held("S6-01-US", [_name("AAPL", c)])
    assert _day(held, 1) == [0, 0, 0, 0, 0, 1, 0]
    assert _day(held, 2) == _day(held, 3) == [0] * 7


def test_gap_fade_buys_at_bar_3_after_a_gap_down_of_one_percent() -> None:
    c, o = _flat(), _flat()
    o[7] = 98.9                                      # day 2 opens -1.1% vs 100
    o[14] = 99.5                                     # day 3 opens -0.5%: no
    held = _held("S6-02-US", [_name("AAPL", c, opens=o)])
    assert _day(held, 1) == [0, 0, 1, 1, 1, 1, 0]
    assert _day(held, 2) == [0] * 7


def test_gap_go_needs_the_gap_and_an_up_first_bar() -> None:
    c, o = _flat(), _flat()
    o[7], c[7:14] = 101.2, 101.5                     # day 2: gap up, first bar up
    o[14], c[14] = 102.6, 102.0                      # day 3: gap up vs 101.5, first bar DOWN
    c[15:21] = 102.0
    held = _held("S6-03-US", [_name("AAPL", c, opens=o)])
    assert _day(held, 1) == [0, 0, 1, 1, 1, 1, 0]
    assert _day(held, 2) == [0] * 7


def test_range_breakout_buys_after_a_close_above_the_first_bars_high() -> None:
    c = _flat()
    c[9] = 101.0                                     # day 2, bar 3 closes above 100.5
    c[10:14] = 101.0
    c[18] = 101.0                                    # day 3: only bar 5 (pos 4) breaks out
    held = _held("S6-04-US", [_name("AAPL", c, spread=0.5)])
    assert _day(held, 1) == [0, 0, 0, 0, 1, 1, 0]
    assert _day(held, 2) == [0] * 7                  # its fill would be E itself


def test_the_stop_sells_at_the_next_allowed_open_and_only_rises() -> None:
    c = _flat()
    c[8], c[9] = 101.0, 101.0                        # day 2: bar 2 breaks out -> entry pos 3
    c[10] = 96.0                                     # pos 3 closes below 101 - 3 x ATR(~1)
    c[11:14] = 96.0
    held = _held("S6-04-US", [_name("AAPL", c, spread=0.5)])
    assert _day(held, 1) == [0, 0, 0, 1, 1, 0, 0]    # sold at pos 5's open
    no_stop = _held("S6-04-US", [_name("AAPL", np.where(np.arange(35) == 10, 100.9, c))])
    assert _day(no_stop, 1)[3:6] == [1, 1, 1]


def test_trailing_buy_needs_the_running_low_plus_one_atr() -> None:
    c = _flat()
    c[7], c[8], c[9] = 100.0, 100.4, 100.6           # low 99.5; ATR ~1: bar 3 closes >= 100.5
    c[10:14] = 100.6
    held = _held("S6-05-US", [_name("AAPL", c)])
    assert _day(held, 1) == [0, 0, 0, 0, 1, 1, 0]


def _xs(returns: dict[str, float], market: str = "US", day: int = 1) -> list[FakeName]:
    """Names whose bar 2 on ``day`` closes at 100 x (1 + r); all else at 100."""
    per = 7 if market == "US" else 9
    out = []
    for symbol, r in returns.items():
        c = np.full(5 * per, 100.0)
        c[day * per + 1:(day + 1) * per] = 100.0 * (1 + r)
        out.append(_name(symbol, c, market))
    return out


def test_xs_reversal_buys_the_bottom_bet_at_bar_4_and_a_bet_group_counts_once() -> None:
    data = _xs({"GOOG": -0.03, "GOOGL": -0.02, "AAPL": 0.01, "MSFT": 0.0, "NVDA": 0.02,
                "AMD": -0.005})                       # 5 bets: GOOG(L) is the lowest
    assert [_day(_held("S6-06-US", data, i), 1) for i in range(6)] == \
        [[0, 0, 0, 1, 1, 1, 0]] * 2 + [[0] * 7] * 4
    top = [_day(_held("S6-07-US", data, i), 1)[3] for i in range(6)]
    assert top == [0, 0, 0, 0, 1, 0]                  # NVDA


def test_xs_picks_never_read_a_later_bar() -> None:
    data = _xs({"AAPL": -0.02, "MSFT": 0.01, "NVDA": 0.0, "AMD": 0.02, "INTC": 0.015})
    before = s6_rules.picks(_entry("S6-06-US"), data)
    moved, rng = [], np.random.default_rng(7)
    for name in data:                                 # change every bar after day 2's bar 2,
        bars = name.bars.copy()                       # differently for each name
        bars.iloc[9:, bars.columns.get_loc("close")] *= rng.uniform(0.9, 1.1, len(bars) - 9)
        moved.append(FakeName(name.symbol, name.market, bars, name.plan))
    after = s6_rules.picks(_entry("S6-06-US"), moved)
    assert {p for p in before if p[1] <= date(2026, 6, 2)} == \
        {p for p in after if p[1] <= date(2026, 6, 2)} and ("AAPL", date(2026, 6, 2)) in before


def test_mix_ranks_each_market_alone_at_bar_2_but_s6_08_ranks_the_whole_arm() -> None:
    us = _xs({"AAPL": -0.03, "MSFT": -0.02, "NVDA": 0.01, "AMD": 0.02, "INTC": 0.015})
    lon = _xs({"BP.L": -0.001, "SHEL.L": 0.0, "AZN.L": 0.01, "HSBA.L": 0.02, "BARC.L": 0.015},
              "LSE")
    picked = s6_rules.picks(_entry("S6-06-MIX"), us + lon)
    assert {s for s, d in picked if d == date(2026, 6, 2)} == {"AAPL", "BP.L"}   # one per market
    # (ranked together, round(0.2 x 10) = 2 would be AAPL and MSFT)
    # S6-08: prior-day returns, one ranking over all ten bets -> round(0.2 x 10) = 2
    c = {s: np.full(35, 100.0) for s in ("AAPL", "MSFT", "NVDA", "AMD", "INTC")}
    c["AAPL"][7:14], c["MSFT"][7:14] = 97.0, 98.0     # day 2 closes low
    lc = {s: np.full(45, 100.0) for s in ("BP.L", "SHEL.L", "AZN.L", "HSBA.L", "BARC.L")}
    lc["BP.L"][9:18] = 99.5
    data = [_name(s, v) for s, v in c.items()] + [_name(s, v, "LSE") for s, v in lc.items()]
    chosen = s6_rules.picks(_entry("S6-08-MIX"), data)
    assert {s for s, d in chosen if d == date(2026, 6, 3)} == {"AAPL", "MSFT"}
    held = _held("S6-08-MIX", data, 0)
    assert _day(held, 2) == [0, 0, 1, 1, 1, 1, 0]     # decided at bar 1's close, in at bar 3


def test_a_p15_refusal_at_the_decision_bar_skips_the_day_with_no_retry() -> None:
    c, o = _flat(), _flat()
    o[7] = 98.9
    may = np.ones(35, dtype=bool)
    may[7] = False                                    # refused at the decision bar only
    held = _held("S6-02-US", [_name("AAPL", c, opens=o, may_enter=may)])
    assert _day(held, 1) == [0] * 7


def test_the_maker_refuses_anything_not_implemented_exactly() -> None:
    entry = _entry("S6-02-US")
    data = [_name("AAPL", _flat())]
    s6_rules.maker(entry, data)
    for change in ({"gap_max": -0.02}, {"lookback": 3}, {"stop": True}, {"decide_at_bar": 2}):
        bad = dict(entry, parameters={**entry["parameters"], **change})
        with pytest.raises(ValueError):
            s6_rules.maker(bad, data)


def test_every_registered_trial_builds_and_passes_the_look_ahead_check() -> None:
    rng = np.random.default_rng(18)
    data = [_name(s, 100 * np.exp(np.cumsum(rng.normal(0, 0.006, 35))))
            for s in ("AAPL", "MSFT", "NVDA", "AMD", "INTC")]
    for cid in [k for k in preregister.entries() if k.startswith("S6-")]:
        make = s6_rules.maker(_entry(cid), data)
        for name in data:
            checked_weights(make(name), name.bars)


def test_an_s6_trial_scores_end_to_end_through_the_firewall_on_synthetic_hours() -> None:
    """The real scoring path (no real data): walk-forward, nulls, DSR, verdict."""
    import exchange_calendars as xcals  # type: ignore[import-untyped]

    from qb2.execution import costs
    from qb2.research import benchmark, firewall, pounds
    cal = xcals.get_calendar("XNYS")
    days = [str(d.date()) for d in cal.sessions_in_range("2025-01-02", "2025-06-30")]
    index = _hours("US", days)
    rng = np.random.default_rng(3)
    data = []
    for bet, symbol in enumerate(("AAPL", "MSFT", "NVDA")):
        close = 100 * np.exp(np.cumsum(rng.normal(0, 0.004, len(index))))
        bars = pd.DataFrame({"open": np.r_[100.0, close[:-1]], "high": close * 1.002,
                             "low": close * 0.998, "close": close, "volume": 1.0}, index=index)
        n = len(bars)
        data.append(firewall.NameData(symbol, "US", costs.Instrument(f"{symbol}_US_EQ", "USD",
                                                                     "US", "STOCK"),
                                      bars, fills.schedule(index, "1h", "US"), bet,
                                      pounds.Rates(np.ones(n), np.ones(n), np.zeros(n, bool))))
    for cid in ("S6-02-US", "S6-05-US", "S6-06-US"):
        token = preregister.require(cid)
        result = firewall.score(token, s6_rules.maker(token.entry, data), data, interval="1h",
                                stress=2.0, n_null=10, log_path=None, n_trials=42,
                                bench=lambda a, b: benchmark.Benchmark("VWRP.L", "stub", a, b, 0.0))
        assert result.verdict.outcome in ("PASS", "FAIL", "INSUFFICIENT")
        assert result.observed_1x is not None and result.start is not None
