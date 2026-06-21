"""Deterministic, fully-OFFLINE tests for the backtester.

All price data is synthetic, injected as DataFrames -- no DB, no network. The
key invariant under test is NO LOOKAHEAD: a decision made on bar i is filled at
bar i+1's open, and the strategy is never shown a future bar. The birth-
certificate test below proves the lookahead guard actually holds.
"""

from __future__ import annotations

import pandas as pd
import pytest

from research.backtester import run_backtest
from research.strategy import BuyAndHold, FlatStrategy


def _frame(
    opens: list[float],
    closes: list[float],
    *,
    start_day: int = 1,
) -> pd.DataFrame:
    """Build a CLEAN-shaped price frame from open/close lists (one bar per day)."""
    n = len(opens)
    assert len(closes) == n
    event_times = [f"2024-01-{start_day + i:02d}T00:00:00Z" for i in range(n)]
    return pd.DataFrame(
        {
            "event_time": event_times,
            "open": opens,
            "high": [max(o, c) + 1.0 for o, c in zip(opens, closes)],
            "low": [min(o, c) - 1.0 for o, c in zip(opens, closes)],
            "close": closes,
            "volume": [1_000_000] * n,
            "adj_close": closes,
        }
    )


# A rising series reused across several tests.
_RISING = _frame(
    opens=[100.0, 110.0, 120.0, 130.0],
    closes=[105.0, 115.0, 125.0, 135.0],
)


class _SpyStrategy:
    """Records the latest event_time it is shown on each decide() call.

    Used by the no-lookahead birth certificate: after a run, ``seen`` must equal
    the bar sequence exactly -- the k-th decision saw history ending on bar k and
    NEVER a later bar.
    """

    def __init__(self) -> None:
        self.seen: list[str] = []

    def decide(self, history: pd.DataFrame) -> float:
        self.seen.append(str(history["event_time"].iloc[-1]))
        return 0.0


class _LongThenFlat:
    """Long (weight 1) for the first two decisions, then flat (weight 0)."""

    def decide(self, history: pd.DataFrame) -> float:
        return 1.0 if len(history) <= 2 else 0.0


def test_flat_strategy_never_trades_and_equity_is_constant() -> None:
    result = run_backtest(FlatStrategy(), _RISING, starting_equity=10000.0)

    assert result.num_trades == 0
    assert result.final_equity == 10000.0
    assert result.total_return_net == 0.0
    assert result.total_return_gross == 0.0
    assert result.annualized_sharpe_net == 0.0
    assert result.max_drawdown == 0.0
    # Equity is exactly the starting equity on every bar; returns all zero.
    assert list(result.equity_curve) == [10000.0, 10000.0, 10000.0, 10000.0]
    assert list(result.returns) == [0.0, 0.0, 0.0, 0.0]


def test_buy_and_hold_matches_hand_computed_value_minus_entry_cost() -> None:
    starting = 10000.0
    slippage = 0.0005
    result = run_backtest(
        BuyAndHold(), _RISING, slippage_pct=slippage, starting_equity=starting
    )

    # Entry fills at bar 1's open (110) with slippage; held to bar 3's close (135).
    # shares = starting/open1; entry cost = starting*slippage (the slippage on the
    # one buy of notional == starting). final = shares*close_last - entry_cost.
    open1, close_last = 110.0, 135.0
    expected_final = (starting / open1) * close_last - starting * slippage

    assert result.num_trades == 1
    assert result.final_equity == pytest.approx(expected_final, rel=1e-12)
    # Net is below gross by exactly the entry cost; gross is the cost-free B&H.
    expected_gross_final = (starting / open1) * close_last
    assert result.total_return_gross == pytest.approx(
        expected_gross_final / starting - 1.0, rel=1e-12
    )
    assert result.total_return_net < result.total_return_gross


def test_no_lookahead_birth_certificate() -> None:
    # The spy records the last event_time it was handed on each decide() call.
    # It must see each bar exactly once, in order, never a future bar. If the
    # engine sliced prices[: i + 2] (lookahead), seen[k] would jump ahead and
    # this assertion would fail -- that is the point of this test.
    spy = _SpyStrategy()
    run_backtest(spy, _RISING)

    expected = list(_RISING["event_time"])
    assert spy.seen == expected
    # Belt and braces: every decision saw an event_time <= the bar it decided on.
    for decided_on, latest_seen in zip(expected, spy.seen):
        assert latest_seen <= decided_on


def test_costs_strictly_reduce_net_return() -> None:
    free = run_backtest(BuyAndHold(), _RISING, slippage_pct=0.0)
    costed = run_backtest(BuyAndHold(), _RISING, slippage_pct=0.001)
    double = run_backtest(
        BuyAndHold(), _RISING, slippage_pct=0.001, cost_multiplier=2.0
    )

    # No costs -> net equals gross.
    assert free.total_return_net == pytest.approx(free.total_return_gross, rel=1e-12)
    # Costs strictly reduce net return; doubling the cost is strictly worse again.
    assert costed.total_return_net < free.total_return_net
    assert double.total_return_net < costed.total_return_net


def test_single_round_trip_pnl_with_slippage_on_both_fills() -> None:
    # 5 bars; go long for the first two decisions then flat.
    prices = _frame(
        opens=[100.0, 200.0, 300.0, 400.0, 500.0],
        closes=[150.0, 250.0, 350.0, 450.0, 550.0],
    )
    # Decisions: bar0->1, bar1->1, bar2->0, bar3->0, bar4->0.
    # Entry fills at bar1 open=200 (decision from bar0); exit at bar3 open=400
    # (decision from bar2). Held across bars 1-2; flat thereafter.
    result = run_backtest(
        _LongThenFlat(),
        prices,
        slippage_pct=0.001,
        commission_pct=0.0,
        starting_equity=10000.0,
    )

    # Hand calc: buy 50 sh (=10000/200) paying 200.2 each -> spend 10010 (cash -10).
    # Sell 50 sh at 399.6 each -> receive 19980. Final cash = 19970, shares 0.
    assert result.num_trades == 2
    assert result.final_equity == pytest.approx(19970.0, rel=1e-12)
    assert result.total_return_net == pytest.approx(0.997, rel=1e-12)


def test_empty_prices_raises() -> None:
    empty = _frame(opens=[], closes=[])
    with pytest.raises(ValueError, match="empty"):
        run_backtest(BuyAndHold(), empty)


def test_unsorted_prices_raises() -> None:
    prices = _frame(opens=[100.0, 110.0, 120.0], closes=[105.0, 115.0, 125.0])
    shuffled = prices.iloc[[2, 0, 1]].reset_index(drop=True)
    with pytest.raises(ValueError, match="ascending"):
        run_backtest(BuyAndHold(), shuffled)
