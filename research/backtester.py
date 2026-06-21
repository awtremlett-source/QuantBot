"""The backtester: an honest, lookahead-free track-record engine (long-only).

Given a :class:`~research.strategy.Strategy` and a CLEAN price series, it
simulates trading bar by bar and returns a :class:`BacktestResult` with the
equity curve and the headline stats. Two rules make the track record honest:

* NO LOOKAHEAD. On bar ``i`` the strategy is shown history up to AND INCLUDING
  bar ``i`` and returns a target weight for the NEXT bar. That weight is filled
  at bar ``i+1``'s OPEN -- a decision is NEVER filled on the bar it was made.
* COSTS ARE INSIDE. Fills cross the spread (slippage) and pay commission, both
  deducted from equity as the trade happens; results are reported gross AND net.

Stats are computed on the NET equity curve. ``annualized_*`` assume daily bars
(252 trading days/year). Marking is at each bar's ``close``; fills are at ``open``.

LIVE SMOKE TEST (manual -- reads the DB, writes NOTHING; NOT part of the suite)::

    from data_store import store
    from data_store.timeutils import now_utc_iso
    from research.backtester import run_backtest
    from research.strategy import BuyAndHold

    conn = store.connect("data/quantbot.db")
    prices = store.read_price_asof(conn, "NVDA", now_utc_iso())
    conn.close()
    r = run_backtest(BuyAndHold(), prices)
    print(r.total_return_net, r.annualized_return_net, r.max_drawdown, r.num_trades)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import pandas as pd

from research.strategy import Strategy

logger = logging.getLogger(__name__)

# Daily-bar annualization factor.
_TRADING_DAYS = 252
# Below this, two target weights are treated as equal (no rebalance trade).
_WEIGHT_EPS = 1e-9


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """The outcome of one backtest run.

    ``equity_curve`` and ``returns`` are pandas Series indexed by ``event_time``;
    ``returns`` is the per-bar fractional change of the net equity curve (first
    bar 0.0). All ``*_net`` figures include costs; ``total_return_gross`` is the
    same strategy run with zero costs, for comparison. ``max_drawdown`` is the
    worst peak-to-trough drop as a negative fraction (0.0 if never underwater).
    """

    equity_curve: pd.Series
    returns: pd.Series
    total_return_net: float
    total_return_gross: float
    annualized_return_net: float
    annualized_sharpe_net: float
    max_drawdown: float
    num_trades: int
    final_equity: float


@dataclass(frozen=True, slots=True)
class _SimResult:
    """Internal: the net and gross equity curves from one simulation pass."""

    net_equity_curve: list[float]
    gross_equity_curve: list[float]
    num_trades: int


def _clamp_weight(weight: float) -> float:
    """Validate and clamp a strategy's target weight into ``[0, 1]``.

    A non-finite weight is a strategy bug, not a tradable instruction -- raise
    loudly rather than silently coercing it.
    """
    if not math.isfinite(weight):
        raise ValueError(f"strategy returned a non-finite target weight: {weight!r}")
    return min(1.0, max(0.0, float(weight)))


def _validate(prices: pd.DataFrame) -> None:
    """Reject input the engine cannot honestly backtest."""
    if len(prices) == 0:
        raise ValueError("prices is empty; nothing to backtest")
    missing = [c for c in ("event_time", "open", "close") if c not in prices.columns]
    if missing:
        raise ValueError(f"prices missing required column(s): {missing}")
    if not prices["event_time"].is_monotonic_increasing:
        raise ValueError("prices.event_time must be in ascending order")


def _simulate(
    strategy: Strategy,
    prices: pd.DataFrame,
    commission_pct: float,
    slippage_pct: float,
    cost_multiplier: float,
    starting_equity: float,
) -> _SimResult:
    """Run the simulation once, tracking NET (with costs) and GROSS (zero-cost)
    equity in parallel off the SAME decisions (so the strategy decides once/bar).

    The strategy decides on bar ``i`` from ``prices[: i + 1]`` and that weight is
    executed at bar ``i + 1``'s open -- a decision is never filled on the bar it
    was made. Changing the slice to include bar ``i + 1`` would be lookahead and
    MUST fail ``test_no_lookahead_birth_certificate``.
    """
    opens = prices["open"].to_numpy(dtype=float)
    closes = prices["close"].to_numpy(dtype=float)
    n = len(prices)

    net_cash = gross_cash = float(starting_equity)
    net_shares = gross_shares = 0.0
    current_weight = 0.0
    pending_weight: float | None = None  # decided last bar, filled at this bar's open
    num_trades = 0
    net_curve: list[float] = []
    gross_curve: list[float] = []

    slip = slippage_pct * cost_multiplier
    comm = commission_pct * cost_multiplier

    for i in range(n):
        # Execute the PREVIOUS bar's decision at THIS bar's open. We only trade
        # when the target weight actually changed, so buy-and-hold trades once.
        if pending_weight is not None:
            if abs(pending_weight - current_weight) > _WEIGHT_EPS:
                open_px = opens[i]
                # NET track: fills cross the spread and pay commission.
                net_target = pending_weight * (net_cash + net_shares * open_px) / open_px
                net_delta = net_target - net_shares
                fill = (
                    open_px * (1.0 + slip)
                    if net_delta > 0
                    else open_px * (1.0 - slip)
                )
                net_cash -= net_delta * fill + comm * abs(net_delta) * fill
                net_shares = net_target
                # GROSS track: same decision, zero costs (the cost-free benchmark).
                gross_target = (
                    pending_weight * (gross_cash + gross_shares * open_px) / open_px
                )
                gross_cash -= (gross_target - gross_shares) * open_px
                gross_shares = gross_target
                current_weight = pending_weight
                num_trades += 1

        # Mark both tracks to market at this bar's close.
        net_curve.append(float(net_cash + net_shares * closes[i]))
        gross_curve.append(float(gross_cash + gross_shares * closes[i]))

        # Decide for the NEXT bar from history up to AND INCLUDING bar i.
        pending_weight = _clamp_weight(strategy.decide(prices.iloc[: i + 1]))

    return _SimResult(
        net_equity_curve=net_curve,
        gross_equity_curve=gross_curve,
        num_trades=num_trades,
    )


def _annualized_return(total_growth: float, periods: int) -> float:
    """Compound the total growth factor to a per-year rate (daily bars)."""
    if total_growth <= 0.0:
        return -1.0  # wiped out; a fractional power of a non-positive base is moot
    if periods <= 0:
        return 0.0
    return math.pow(total_growth, _TRADING_DAYS / periods) - 1.0


def _annualized_sharpe(returns: pd.Series) -> float:
    """Mean/std of per-bar returns, annualized; 0.0 if std is 0 or too few bars."""
    if len(returns) < 2:
        return 0.0
    std = float(returns.std())
    if std <= 0.0 or not math.isfinite(std):
        return 0.0
    return float(returns.mean()) / std * math.sqrt(_TRADING_DAYS)


def _max_drawdown(equity: pd.Series) -> float:
    """Worst peak-to-trough drop as a negative fraction (0.0 if never underwater)."""
    drawdown = equity / equity.cummax() - 1.0
    return float(drawdown.min())


def run_backtest(
    strategy: Strategy,
    prices: pd.DataFrame,
    commission_pct: float = 0.0,
    slippage_pct: float = 0.0005,
    cost_multiplier: float = 1.0,
    starting_equity: float = 10000.0,
) -> BacktestResult:
    """Backtest ``strategy`` over ``prices`` (CLEAN series); return the result.

    ``prices`` must be the CLEAN layout (``event_time, open, high, low, close,
    volume, adj_close``) in ascending ``event_time`` order; live callers pass the
    output of :func:`data_store.store.read_price_asof`. Costs (``slippage_pct``,
    ``commission_pct``, scaled by ``cost_multiplier``) are charged inside the run;
    the gross figure re-runs the identical decisions with zero costs.
    """
    _validate(prices)

    sim = _simulate(
        strategy, prices, commission_pct, slippage_pct, cost_multiplier, starting_equity
    )

    event_times = prices["event_time"].to_numpy()
    equity_curve = pd.Series(sim.net_equity_curve, index=event_times, name="equity")
    returns = equity_curve.pct_change().fillna(0.0)
    returns.name = "return"

    final_equity = float(sim.net_equity_curve[-1])
    total_return_net = final_equity / starting_equity - 1.0
    total_return_gross = float(sim.gross_equity_curve[-1]) / starting_equity - 1.0
    annualized_return_net = _annualized_return(
        final_equity / starting_equity, len(equity_curve) - 1
    )
    # Sharpe over the genuine bar-to-bar returns (drop the leading 0.0).
    annualized_sharpe_net = _annualized_sharpe(returns.iloc[1:])
    max_drawdown = _max_drawdown(equity_curve)

    logger.info(
        "backtest: net=%.4f gross=%.4f sharpe=%.2f max_dd=%.4f trades=%d final=%.2f",
        total_return_net,
        total_return_gross,
        annualized_sharpe_net,
        max_drawdown,
        sim.num_trades,
        final_equity,
    )

    return BacktestResult(
        equity_curve=equity_curve,
        returns=returns,
        total_return_net=total_return_net,
        total_return_gross=total_return_gross,
        annualized_return_net=annualized_return_net,
        annualized_sharpe_net=annualized_sharpe_net,
        max_drawdown=max_drawdown,
        num_trades=sim.num_trades,
        final_equity=final_equity,
    )
