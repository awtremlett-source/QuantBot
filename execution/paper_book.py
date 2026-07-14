"""The paper book: the backtester's fill discipline, live, against the journal.

Every mechanism here mirrors :mod:`research.backtester` deliberately and exactly:

* a decision on bar ``i`` fills at bar ``i+1``'s OPEN, never on bar ``i``;
* buys cross the spread at ``open * (1 + slippage)``, sells at
  ``open * (1 - slippage)``;
* an order is placed only when the target weight actually CHANGED (same epsilon),
  so buy-and-hold trades once;
* equity marks at each bar's close after that bar's fills.

The paper-vs-backtester birth certificate (tests/execution) feeds one synthetic
series through both engines and requires the equity curves to match -- any drift
between this file and the backtester MUST fail that test.

All journal writes go through the typed :mod:`data_store.store` API. Nothing here
commits: the loop owns the transaction (one commit per processed bar).
"""

from __future__ import annotations

import logging
import math
from sqlite3 import Connection

import pandas as pd

from data_store import store
from data_store.store import PaperEquity, PaperFill, PaperOrder, PaperState

logger = logging.getLogger(__name__)

# MUST match research.backtester._WEIGHT_EPS: below this, two target weights are
# equal and no order is placed. The birth certificate enforces the parity.
WEIGHT_EPS = 1e-9


def clamp_weight(weight: float) -> float:
    """Validate and clamp a target weight into ``[0, 1]``.

    MUST match ``research.backtester._clamp_weight``: a non-finite weight is a
    strategy bug and raises loudly; finite values clamp defensively.
    """
    if not math.isfinite(weight):
        raise ValueError(f"strategy returned a non-finite target weight: {weight!r}")
    return min(1.0, max(0.0, float(weight)))


def init_state(
    conn: Connection,
    ticker: str,
    starting_equity: float,
    prices: pd.DataFrame,
) -> PaperState:
    """Create first-run state: all cash, cursor at the SECOND-LATEST clean bar.

    The cursor placement means exactly ONE decision happens on the first run --
    the latest completed bar. Paper trading starts TODAY; it must never replay
    2015->now as if those were live trades (that story already exists, honestly,
    as the walk-forward OOS record).
    """
    if len(prices) < 2:
        raise ValueError(
            f"need at least 2 completed bars to start the paper book for "
            f"{ticker}, got {len(prices)}"
        )
    state = PaperState(
        ticker=ticker,
        shares=0.0,
        cash=float(starting_equity),
        last_decided_event_time=str(prices["event_time"].iloc[-2]),
    )
    store.write_paper_state(conn, state)
    logger.info(
        "paper book first run: %s starts with cash=%.2f, cursor at %s",
        ticker,
        state.cash,
        state.last_decided_event_time,
    )
    return state


def commanded_weight(conn: Connection, ticker: str) -> float:
    """The book's current TARGET weight: the latest non-cancelled order's, else 0.

    This mirrors the backtester's ``current_weight`` exactly: that variable only
    changes when a decision DIFFERS from it, so at any moment it equals the most
    recent differing decision -- which is precisely the most recent order.
    A book with no orders has never been commanded off 0 (all cash).
    """
    last = store.read_last_paper_order(conn, ticker)
    return last.target_weight if last is not None else 0.0


def settle_pending_at_bar(
    conn: Connection,
    ticker: str,
    bar_event_time: str,
    bar_open: float,
    state: PaperState,
    slippage_pct: float,
    knowable_time: str,
) -> tuple[PaperState, int]:
    """Fill every pending order decided STRICTLY BEFORE ``bar_event_time`` at this
    bar's open; return the updated state and the number of fills.

    Called once per bar in chronological order, so each order lands at the first
    bar after its decision -- its correct HISTORICAL next open, even in catch-up.
    Fill math is the backtester's, line for line: target shares from the target
    weight at the open, buys pay ``open*(1+slip)``, sells receive ``open*(1-slip)``.
    """
    shares, cash = state.shares, state.cash
    fills = 0
    for order in store.read_pending_paper_orders(conn, ticker):
        if order.decision_event_time >= bar_event_time:
            continue  # decided on/after this bar; fills at a LATER open
        assert order.id is not None  # read from the DB, so the id exists
        target_shares = order.target_weight * (cash + shares * bar_open) / bar_open
        delta = target_shares - shares
        fill_price = (
            bar_open * (1.0 + slippage_pct)
            if delta > 0
            else bar_open * (1.0 - slippage_pct)
        )
        cash_delta = -delta * fill_price
        store.fill_paper_order(
            conn,
            PaperFill(
                order_id=order.id,
                fill_event_time=bar_event_time,
                fill_price=fill_price,
                shares_delta=delta,
                cash_delta=cash_delta,
                knowable_time=knowable_time,
            ),
        )
        shares = target_shares
        cash += cash_delta
        fills += 1
        logger.info(
            "paper fill: %s order %d @ %s open %.4f -> shares %.6f cash %.2f",
            ticker,
            order.id,
            bar_event_time,
            fill_price,
            shares,
            cash,
        )
    if fills == 0:
        return state, 0
    new_state = PaperState(
        ticker=ticker,
        shares=shares,
        cash=cash,
        last_decided_event_time=state.last_decided_event_time,
    )
    store.write_paper_state(conn, new_state)
    return new_state, fills


def place_order(
    conn: Connection,
    ticker: str,
    decision_event_time: str,
    target_weight: float,
    knowable_time: str,
) -> bool:
    """Journal one pending order; return True if it was newly inserted.

    False means the decision bar already has an order (idempotent re-run over
    journaled ground) -- the original order stands.
    """
    order_id = store.insert_paper_order(
        conn,
        PaperOrder(
            ticker=ticker,
            decision_event_time=decision_event_time,
            target_weight=target_weight,
            created_knowable_time=knowable_time,
            status="pending",
        ),
    )
    return order_id is not None


def mark_equity(
    conn: Connection, state: PaperState, event_time: str, close: float
) -> bool:
    """Mark ``cash + shares * close`` into paper_equity; True if newly inserted."""
    return store.insert_paper_equity(
        conn,
        PaperEquity(
            ticker=state.ticker,
            event_time=event_time,
            equity=state.cash + state.shares * close,
            close=close,
        ),
    )


def drawdown_from_peak(conn: Connection, ticker: str) -> float:
    """Latest equity vs the running peak, as a non-positive fraction (0.0 = at peak)."""
    marks = store.read_paper_equity(conn, ticker)
    if not marks:
        return 0.0
    peak = max(m.equity for m in marks)
    if peak <= 0.0:
        return -1.0  # the book is wiped out; report the floor rather than divide
    return marks[-1].equity / peak - 1.0
