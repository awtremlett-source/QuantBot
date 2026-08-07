"""The catch-up-safe daily paper loop: decide -> journal -> settle -> mark.

Safe to run at any time, on any day, as many times as you like (sometimes-off
laptop law). Each run:

1. KILLSWITCH -- if ``STOP_NEW_TRADES`` exists at the repo root, the fact is
   journaled to the log and NO new orders are placed; pending fills still settle
   and equity still marks (stopping the book blind would be worse).
2. SYNC -- ingest with ``end = today`` (EXCLUSIVE, so only COMPLETED daily bars
   ever enter; today's in-progress bar arrives tomorrow), then reconcile RAW ->
   CLEAN. Skipped under ``--dry-run``.
3. STATE -- load the book; on the very first run, start all-cash with the
   decision cursor at the SECOND-LATEST completed bar, so exactly one decision
   (the latest bar) happens and 2015->now is never replayed as live trades.
4-6. PER BAR, in order, one transaction per bar (crash = resume mid-catch-up):
   settle pending orders at this bar's open, mark equity at its close, then
   decide from history up to AND INCLUDING this bar only -- the backtester's
   exact discipline. N dark days = N honest replayed decisions, each order
   filling at its own historical next open.
7. DIGEST -- one line: date, position, equity, drawdown-from-peak, orders.
8. BACKUP -- live runs (never --dry-run) snapshot the journal via
   :func:`tools.backup.run_backup`; a backup failure warns loudly in the
   digest but NEVER blocks trading.
9. MONITORS -- live runs end with the observe-only meters block (one line per
   meter + OVERALL = worst); the drawdown meter is the single source of truth
   for the validated-worst warning (:mod:`monitors.meters`).
10. TELEGRAM -- live runs push the digest + MONITORS text to the operator's
    phone if configured (:mod:`monitors.notify`; secrets in .env). A send
    failure warns (sanitized) but NEVER blocks the loop -- backup's contract.

Belt-and-braces: bars dated today or later are excluded from decisions even if
they somehow reached CLEAN (defense in depth against partial bars).
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pandas as pd
import requests

from data_store import store
from data_store.timeutils import now_utc_iso
from execution import paper_book
from execution.config import CONFIG, PaperConfig
from monitors import meters, notify
from research.strategy import Strategy
from tools.backup import (
    LOCAL_ONLY_WARNING,
    BackupReport,
    BackupVerificationError,
    run_backup,
)

logger = logging.getLogger(__name__)

# Presence of this file at the repo root stops all NEW orders (killswitch).
KILLSWITCH_FILE = "STOP_NEW_TRADES"


class IngestFn(Protocol):
    """Anything shaped like ingest.front_door.ingest (tests inject fakes)."""

    def __call__(
        self,
        tickers: Sequence[str],
        db_path: store.DbPath,
        start: str | None = None,
        end: str | None = None,
    ) -> object: ...


class ReconcileFn(Protocol):
    """Anything shaped like reconcile.clean_prices.reconcile."""

    def __call__(self, tickers: Sequence[str], db_path: store.DbPath) -> object: ...


@dataclass(frozen=True, slots=True)
class LoopDigest:
    """What one loop run did, in numbers. ``as_of_bar`` is the latest decided bar."""

    ticker: str
    as_of_bar: str
    shares: float
    cash: float
    equity: float
    drawdown_from_peak: float
    bars_processed: int
    orders_placed: int
    orders_filled: int
    killswitch: bool
    dry_run: bool

    def line(self) -> str:
        """The one-line human digest."""
        flags = ("  KILLSWITCH" if self.killswitch else "") + (
            "  DRY-RUN (rolled back)" if self.dry_run else ""
        )
        return (
            f"PAPER {self.ticker} @ {self.as_of_bar[:10]} | "
            f"shares={self.shares:.6f} cash={self.cash:.2f} "
            f"equity={self.equity:.2f} | dd_from_peak={self.drawdown_from_peak:+.2%} | "
            f"bars={self.bars_processed} placed={self.orders_placed} "
            f"filled={self.orders_filled}{flags}"
        )


def _default_ingest(
    tickers: Sequence[str],
    db_path: store.DbPath,
    start: str | None = None,
    end: str | None = None,
) -> object:
    """Live ingest, imported lazily so offline tests never touch yfinance."""
    from ingest.front_door import ingest

    return ingest(tickers, db_path, start=start, end=end)


def _default_reconcile(tickers: Sequence[str], db_path: store.DbPath) -> object:
    """Live RAW->CLEAN reconcile, imported lazily (offline tests inject fakes)."""
    from reconcile.clean_prices import reconcile

    return reconcile(tickers, db_path)


def _completed_bars(
    conn: sqlite3.Connection, ticker: str, now: str, today: str
) -> pd.DataFrame:
    """Point-in-time CLEAN bars, restricted to bars from BEFORE today (UTC).

    ``read_price_asof`` enforces the knowable_time guard; the extra calendar
    filter guarantees no decision is ever made on today's (possibly partial)
    bar even if one reached the store.
    """
    prices = store.read_price_asof(conn, ticker, now)
    completed = prices[prices["event_time"].str[:10] < today]
    return completed.reset_index(drop=True)


def run_once(
    conn: sqlite3.Connection,
    config: PaperConfig,
    now: str,
    *,
    today: str | None = None,
    killswitch: bool = False,
    dry_run: bool = False,
    strategy: Strategy | None = None,
) -> LoopDigest:
    """Run one loop pass against an open connection; return the digest.

    Pure paper logic: no network, no filesystem checks -- callers supply ``now``
    (canonical UTC ISO; also the as-of instant for the CLEAN read), the
    killswitch verdict, and optionally a strategy override (tests). ``today``
    (``YYYY-MM-DD``) is the partial-bar exclusion day; it defaults to ``now``'s
    date but callers that sync first pass their PRE-sync day so the exclusion
    matches what ingest was asked for. Transactions: one commit per processed
    bar in live mode; ``dry_run`` rolls everything back at the end and reports
    what WOULD happen.
    """
    ticker = config.ticker
    the_today = today if today is not None else now[:10]
    the_strategy = strategy if strategy is not None else config.build_strategy()
    if killswitch:
        # Journal the fact loudly; the run continues (settles + marks) below.
        logger.warning(
            "KILLSWITCH active (%s present): placing NO new orders for %s",
            KILLSWITCH_FILE,
            ticker,
        )

    prices = _completed_bars(conn, ticker, now, the_today)
    state = store.read_paper_state(conn, ticker)
    if state is None:
        state = paper_book.init_state(conn, ticker, config.starting_equity, prices)
        if not dry_run:
            conn.commit()

    # Positions (not labels) of every completed bar still owing a decision.
    pending_positions = prices.index[
        prices["event_time"] > state.last_decided_event_time
    ]

    orders_placed = 0
    orders_filled = 0
    current_weight = paper_book.commanded_weight(conn, ticker)

    for pos in pending_positions:
        bar = prices.iloc[pos]
        bar_event_time = str(bar["event_time"])

        # (a) Settle orders decided before this bar at THIS bar's open.
        state, fills = paper_book.settle_pending_at_bar(
            conn,
            ticker,
            bar_event_time,
            float(bar["open"]),
            state,
            config.slippage_pct,
            now,
        )
        orders_filled += fills

        # (b) Mark equity at this bar's close (after the day's fills, like the
        # backtester).
        paper_book.mark_equity(conn, state, bar_event_time, float(bar["close"]))

        # (c) Decide for the NEXT bar from history up to AND INCLUDING this bar
        # ONLY -- the same no-lookahead slice the backtester uses.
        weight = paper_book.clamp_weight(the_strategy.decide(prices.iloc[: pos + 1]))
        if not killswitch and abs(weight - current_weight) > paper_book.WEIGHT_EPS:
            if paper_book.place_order(conn, ticker, bar_event_time, weight, now):
                orders_placed += 1
            current_weight = weight

        # (d) Advance the cursor; commit the whole bar atomically.
        state = store.PaperState(
            ticker=ticker,
            shares=state.shares,
            cash=state.cash,
            last_decided_event_time=bar_event_time,
        )
        store.write_paper_state(conn, state)
        if not dry_run:
            conn.commit()

    # Digest numbers are computed BEFORE a dry-run rollback so they describe
    # what the run would have journaled.
    last_close = float(prices["close"].iloc[-1]) if len(prices) else 0.0
    equity = state.cash + state.shares * last_close
    drawdown = paper_book.drawdown_from_peak(conn, ticker)
    digest = LoopDigest(
        ticker=ticker,
        as_of_bar=state.last_decided_event_time,
        shares=state.shares,
        cash=state.cash,
        equity=equity,
        drawdown_from_peak=drawdown,
        bars_processed=len(pending_positions),
        orders_placed=orders_placed,
        orders_filled=orders_filled,
        killswitch=killswitch,
        dry_run=dry_run,
    )
    if dry_run:
        conn.rollback()
    return digest


def run_paper(
    db_path: store.DbPath,
    config: PaperConfig = CONFIG,
    *,
    dry_run: bool = False,
    strategy: Strategy | None = None,
    ingest_fn: IngestFn = _default_ingest,
    reconcile_fn: ReconcileFn = _default_reconcile,
    now_fn: Callable[[], str] = now_utc_iso,
    killswitch_dir: Path = Path("."),
) -> LoopDigest:
    """One full loop run: killswitch check, data sync, book pass, digest.

    ``now_fn`` is the clock (tests inject a fixed one). It is read TWICE: once
    before the sync (that instant's date is 'today' -- the ingest end and the
    partial-bar exclusion day) and once AFTER the sync, as the as-of instant for
    the CLEAN read. The second read is load-bearing: ingest/reconcile stamp
    their rows with knowable_times LATER than the loop's start, so reading
    as-of the pre-sync instant would miss the very bars this run just synced
    (a rebuild made that a total miss on 2026-07-15 -- see the fail-first test).
    ``ingest_fn`` / ``reconcile_fn`` are the live network sync by default; tests
    inject fakes. Sync is skipped entirely under ``dry_run`` (offline what-if).
    """
    t_start = now_fn()
    today = t_start[:10]
    killswitch = (killswitch_dir / KILLSWITCH_FILE).exists()

    if not dry_run:
        # end = today EXCLUSIVE: today's in-progress bar must never enter RAW.
        ingest_fn([config.ticker], db_path, start=None, end=today)
        reconcile_fn([config.ticker], db_path)

    # Re-read the clock AFTER the sync so freshly-synced rows are visible.
    read_now = now_fn()

    store.init_db(db_path)  # idempotent; ensures the paper tables exist
    conn = store.connect(db_path)
    try:
        digest = run_once(
            conn,
            config,
            read_now,
            today=today,
            killswitch=killswitch,
            dry_run=dry_run,
            strategy=strategy,
        )
    finally:
        conn.close()

    print(digest.line())

    if not dry_run:
        # Rubric condition 7: every LIVE run backs up the journal it just wrote.
        # A failed backup must never block trading -- this catch is SCOPED to
        # the backup call only and logs the full error (no-silent-exceptions
        # law: handle+log; anything unexpected still propagates).
        backup_report: BackupReport | None = None
        try:
            backup_report = run_backup(db_path)
        except (BackupVerificationError, OSError):
            logger.exception("journal backup failed")
            print("WARNING: BACKUP FAILED — journal is unprotected")
        else:
            print(f"backup: OK -> {backup_report.dest_dir}")
            if backup_report.local_only:
                print(LOCAL_ONLY_WARNING)

        # Rubric condition 6: the MONITORS block -- observe-only meters, one
        # line each + OVERALL = worst. The drawdown meter replaced the old
        # inline validated-worst warning as the single source of truth.
        mconn = store.connect(db_path)
        try:
            results, overall = meters.run_all(
                mconn, backup_report, today, ticker=config.ticker
            )
        finally:
            mconn.close()
        monitor_lines = (
            ["MONITORS:"]
            + [f"{r.name}: {r.status} - {r.detail}" for r in results]
            + [f"OVERALL: {overall}"]
        )
        for line in monitor_lines:
            print(line)

        # Telegram push: the exact digest + MONITORS text, to the operator's
        # phone. Same contract as backup: a failure warns but NEVER blocks the
        # loop; the catch is SCOPED to the send. All failure text is sanitized
        # (the API URL embeds the bot token -- SCARS #1).
        message = "\n".join([digest.line(), *monitor_lines])
        try:
            telegram_config = notify.load_config()
            if telegram_config is None:
                print("telegram: unconfigured")
            else:
                outcome = notify.send_digest(message, telegram_config)
                if outcome.sent:
                    print("telegram: OK")
                else:
                    logger.warning("telegram send failed: %s", outcome.detail)
                    print(f"telegram: WARN - {outcome.detail}")
        except (requests.RequestException, OSError) as exc:
            detail = notify.sanitize(str(exc))
            logger.warning("telegram send failed: %s", detail)
            print(f"telegram: WARN - {detail}")
    return digest


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: ``python -m execution.paper_loop --db data/quantbot.db [--dry-run]``."""
    parser = argparse.ArgumentParser(
        prog="paper_loop",
        description="Catch-up-safe daily paper-trading loop (local book).",
    )
    parser.add_argument(
        "--db",
        required=True,
        metavar="PATH",
        help="Path to the SQLite database, e.g. data/quantbot.db",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="No data sync; run the book pass but roll back every write.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    run_paper(db_path, dry_run=bool(args.dry_run))
    return 0


if __name__ == "__main__":  # pragma: no cover -- covered via execution.__main__
    raise SystemExit(main())
