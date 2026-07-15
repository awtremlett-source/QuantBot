"""Deterministic, fully-OFFLINE tests for the paper-trading loop.

All bars are synthetic and installed straight into a temp store's CLEAN table;
ingest/reconcile are recording fakes (no network, no yfinance import). The
centrepiece is the paper-vs-backtester BIRTH CERTIFICATE: the paper book claims
to be the backtester's fill discipline running live, so the same series through
both engines must produce the same equity, bar for bar. Divergence MUST fail it.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from data_store import store
from data_store.store import PriceClean
from execution.config import PaperConfig
from execution.paper_loop import KILLSWITCH_FILE, LoopDigest, run_paper
from research.backtester import run_backtest
from research.strategy import SmaTrendStrategy, Strategy

# A fixed "now" strictly after every synthetic bar: all bars count as completed.
NOW = "2025-06-01T12:00:00Z"

# The birth-certificate series (SMA-3 crosses both ways -> four fills).
OPENS = [100.0, 101.0, 103.0, 104.0, 99.0, 92.0, 87.0, 90.0, 97.0, 104.0, 109.0, 106.0, 99.0, 92.0]
CLOSES = [100.0, 102.0, 104.0, 103.0, 96.0, 90.0, 88.0, 92.0, 99.0, 106.0, 108.0, 104.0, 96.0, 90.0]

_BASE_DAY = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _event_time(i: int) -> str:
    """Bar i's event_time: consecutive UTC days from 2024-01-01."""
    return (_BASE_DAY + timedelta(days=i)).strftime("%Y-%m-%dT00:00:00Z")


def _bars(
    opens: Sequence[float], closes: Sequence[float], ticker: str = "TEST"
) -> list[PriceClean]:
    """CLEAN-shaped synthetic bars; knowable one hour after the bar's event_time."""
    assert len(opens) == len(closes)
    return [
        PriceClean(
            ticker=ticker,
            event_time=_event_time(i),
            open=float(o),
            high=float(max(o, c)) + 1.0,
            low=float(min(o, c)) - 1.0,
            close=float(c),
            volume=1_000_000,
            adj_close=float(c),
            knowable_time=(_BASE_DAY + timedelta(days=i, hours=1)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            source="test",
        )
        for i, (o, c) in enumerate(zip(opens, closes))
    ]


def _frame(bars: Sequence[PriceClean]) -> pd.DataFrame:
    """The same bars as a CLEAN-layout DataFrame for run_backtest."""
    return pd.DataFrame(
        {
            "event_time": [b.event_time for b in bars],
            "open": [b.open for b in bars],
            "high": [b.high for b in bars],
            "low": [b.low for b in bars],
            "close": [b.close for b in bars],
            "volume": [b.volume for b in bars],
            "adj_close": [b.adj_close for b in bars],
        }
    )


def _install(db: Path, bars: Sequence[PriceClean]) -> None:
    """Reveal ``bars`` to the store (idempotent -- already-known bars skip)."""
    store.init_db(db)
    conn = store.connect(db)
    try:
        store.write_price_clean(conn, list(bars))
    finally:
        conn.close()


class _RecordingSync:
    """Fake ingest/reconcile that records calls and touches nothing."""

    def __init__(self) -> None:
        self.ingest_calls: list[tuple[tuple[str, ...], str | None, str | None]] = []
        self.reconcile_calls: list[tuple[str, ...]] = []

    def ingest(
        self,
        tickers: Sequence[str],
        db_path: store.DbPath,
        start: str | None = None,
        end: str | None = None,
    ) -> object:
        self.ingest_calls.append((tuple(tickers), start, end))
        return None

    def reconcile(self, tickers: Sequence[str], db_path: store.DbPath) -> object:
        self.reconcile_calls.append(tuple(tickers))
        return None


class _SpyStrategy:
    """Delegates to a real strategy while recording the last event_time of every
    history it is shown -- the paper loop's no-lookahead witness."""

    def __init__(self, inner: Strategy) -> None:
        self._inner = inner
        self.seen: list[str] = []

    def decide(self, history: pd.DataFrame) -> float:
        self.seen.append(str(history["event_time"].iloc[-1]))
        return self._inner.decide(history)


class _Alternator:
    """Target weight flips every bar (len(history) odd -> long). Guarantees the
    killswitch test a decision that WOULD place an order on every single bar."""

    def decide(self, history: pd.DataFrame) -> float:
        return float(len(history) % 2)


def _config(**overrides: object) -> PaperConfig:
    defaults: dict[str, object] = {"ticker": "TEST", "lookback": 3}
    defaults.update(overrides)
    return PaperConfig(**defaults)  # type: ignore[arg-type]


def _run(
    db: Path,
    config: PaperConfig,
    tmp: Path,
    *,
    now: str = NOW,
    strategy: Strategy | None = None,
    sync: _RecordingSync | None = None,
    dry_run: bool = False,
) -> LoopDigest:
    """run_paper with offline fakes; killswitch dir = tmp (create the file to arm)."""
    the_sync = sync if sync is not None else _RecordingSync()
    return run_paper(
        db,
        config,
        dry_run=dry_run,
        strategy=strategy,
        ingest_fn=the_sync.ingest,
        reconcile_fn=the_sync.reconcile,
        now_fn=lambda: now,
        killswitch_dir=tmp,
    )


def _journal(db: Path, ticker: str = "TEST") -> tuple[list[object], ...]:
    """The full journal + state, for exact run-vs-run comparisons."""
    conn = store.connect(db)
    try:
        return (
            list(store.read_pending_paper_orders(conn, ticker)),
            [store.read_last_paper_order(conn, ticker)],
            list(store.read_paper_fills(conn, ticker)),
            list(store.read_paper_equity(conn, ticker)),
            [store.read_paper_state(conn, ticker)],
            list(
                conn.execute(
                    "SELECT id, decision_event_time, target_weight, status "
                    "FROM paper_orders WHERE ticker = ? ORDER BY id",
                    (ticker,),
                ).fetchall()
            ),
        )
    finally:
        conn.close()


# ----------------------------------------------------------------------------- #
# THE BIRTH CERTIFICATE
# ----------------------------------------------------------------------------- #
def test_paper_book_matches_backtester_birth_certificate(tmp_path: Path) -> None:
    # The paper book IS the backtester's fill discipline, live: same decisions,
    # same next-open fills, same slippage, same marking. Feed one synthetic
    # series through run_backtest AND through the loop with bars revealed one at
    # a time; per-bar equity and final equity must match. If this test ever
    # fails, the paper book has drifted from the validated engine and NOTHING
    # the paper account reports can be trusted until it is fixed.
    bars = _bars(OPENS, CLOSES)
    config = _config()

    bt = run_backtest(
        SmaTrendStrategy([3]).build({"lookback": 3}),
        _frame(bars),
        slippage_pct=config.slippage_pct,
        starting_equity=config.starting_equity,
        log_path=None,
    )

    db = tmp_path / "book.db"
    for k in range(2, len(bars) + 1):  # reveal bars one at a time, run after each
        _install(db, bars[:k])
        _run(db, config, tmp_path)

    conn = store.connect(db)
    try:
        marks = store.read_paper_equity(conn, "TEST")
        fills = store.read_paper_fills(conn, "TEST")
        state = store.read_paper_state(conn, "TEST")
    finally:
        conn.close()

    # The paper book marks bars 1..n-1 (its first decision is on bar 1); the
    # backtester marks every bar. Compare the overlap, bar for bar.
    assert state is not None
    assert len(marks) == len(bars) - 1
    for mark, expected in zip(marks, bt.equity_curve.iloc[1:]):
        assert mark.equity == pytest.approx(float(expected), rel=1e-9)

    final_paper = state.cash + state.shares * bars[-1].close
    assert final_paper == pytest.approx(bt.final_equity, rel=1e-9)
    assert len(fills) == bt.num_trades  # every trade happened, none extra


def test_idempotent_day_writes_nothing_new(tmp_path: Path) -> None:
    bars = _bars(OPENS, CLOSES)
    db = tmp_path / "book.db"
    config = _config()
    _install(db, bars[:6])
    _run(db, config, tmp_path)

    before = _journal(db)
    _run(db, config, tmp_path)  # same day, no new bar
    _run(db, config, tmp_path)  # and again

    assert _journal(db) == before  # zero new orders / fills / equity rows


def test_catch_up_replays_per_bar_and_matches_never_dark_run(tmp_path: Path) -> None:
    bars = _bars(OPENS, CLOSES)
    config = _config()

    # Never-dark book: a run after every single new bar.
    db_a = tmp_path / "a.db"
    for k in range(2, len(bars) + 1):
        _install(db_a, bars[:k])
        _run(db_a, config, tmp_path)

    # Dark book: initialised on 2 bars, then the laptop sleeps; the remaining 12
    # bars arrive at once and a spy watches the catch-up decisions.
    db_b = tmp_path / "b.db"
    _install(db_b, bars[:2])
    _run(db_b, config, tmp_path)
    _install(db_b, bars)
    spy = _SpyStrategy(SmaTrendStrategy([3]).build({"lookback": 3}))
    _run(db_b, config, tmp_path, strategy=spy)

    # Decisions were replayed PER BAR, in order, never shown a future bar.
    assert spy.seen == [b.event_time for b in bars[2:]]

    # Each order filled at its own historical next open, so the whole journal --
    # orders, fills, equity marks, final state -- matches the never-dark run.
    assert _journal(db_b) == _journal(db_a)


def test_killswitch_blocks_new_orders_but_settles_and_marks(tmp_path: Path) -> None:
    bars = _bars(OPENS, CLOSES)
    db = tmp_path / "book.db"
    config = _config()
    alternator = _Alternator()

    # Bars 0-2: the alternator decides on bar 1 (len 2 -> 0.0 == current, no
    # order) and bar 2 (len 3 -> 1.0): one pending order exists.
    _install(db, bars[:3])
    _run(db, config, tmp_path, strategy=alternator)
    conn = store.connect(db)
    try:
        assert len(store.read_pending_paper_orders(conn, "TEST")) == 1
        fills_before = len(store.read_paper_fills(conn, "TEST"))
        equity_before = len(store.read_paper_equity(conn, "TEST"))
    finally:
        conn.close()

    # Arm the killswitch, then reveal bar 3 -- a bar the alternator would
    # certainly trade on (weight flips every bar).
    (tmp_path / KILLSWITCH_FILE).touch()
    _install(db, bars[:4])
    digest = _run(db, config, tmp_path, strategy=alternator)

    assert digest.killswitch is True
    assert digest.orders_placed == 0  # no NEW orders under the killswitch
    conn = store.connect(db)
    try:
        # ...but the pending order still settled at bar 3's open,
        assert store.read_pending_paper_orders(conn, "TEST") == []
        assert len(store.read_paper_fills(conn, "TEST")) == fills_before + 1
        # ...and equity still marked.
        assert len(store.read_paper_equity(conn, "TEST")) == equity_before + 1
    finally:
        conn.close()


def test_partial_bar_exclusion_and_end_exclusive_ingest(tmp_path: Path) -> None:
    # 'Today' is the day of the LAST installed bar: that bar is (potentially)
    # partial and must be invisible -- no decision, no order, no equity mark.
    bars = _bars(OPENS[:5], CLOSES[:5])
    now = bars[4].event_time[:10] + "T20:00:00Z"  # late on bar 4's calendar day
    db = tmp_path / "book.db"
    _install(db, bars)

    sync = _RecordingSync()
    spy = _SpyStrategy(SmaTrendStrategy([3]).build({"lookback": 3}))
    _run(db, _config(), tmp_path, now=now, strategy=spy, sync=sync)

    # Ingest was asked for end = today, which the source treats as EXCLUSIVE.
    assert sync.ingest_calls == [(("TEST",), None, bars[4].event_time[:10])]
    # No decision was made on today's bar; the cursor stopped at yesterday's.
    today = bars[4].event_time[:10]
    assert spy.seen and all(seen[:10] < today for seen in spy.seen)
    conn = store.connect(db)
    try:
        state = store.read_paper_state(conn, "TEST")
        assert state is not None
        assert state.last_decided_event_time == bars[3].event_time
        assert all(
            m.event_time[:10] < today for m in store.read_paper_equity(conn, "TEST")
        )
    finally:
        conn.close()


def test_state_resume_matches_uninterrupted_run(tmp_path: Path) -> None:
    bars = _bars(OPENS, CLOSES)
    config = _config()

    # Uninterrupted: init on 2 bars, then one catch-up over the rest.
    db_a = tmp_path / "a.db"
    _install(db_a, bars[:2])
    _run(db_a, config, tmp_path)
    _install(db_a, bars)
    _run(db_a, config, tmp_path)

    # Interrupted: stop after bar 7, "restart", continue to the end.
    db_b = tmp_path / "b.db"
    _install(db_b, bars[:2])
    _run(db_b, config, tmp_path)
    _install(db_b, bars[:8])
    _run(db_b, config, tmp_path)  # ...crash/stop here...
    _install(db_b, bars)
    _run(db_b, config, tmp_path)  # ...restart: resumes from the cursor

    assert _journal(db_b) == _journal(db_a)


def test_first_run_initialises_without_replaying_history(tmp_path: Path) -> None:
    # Full 2015-style history is already in CLEAN on day one. The book must
    # start all-cash with EXACTLY ONE decision (the latest completed bar) --
    # never replay the past as if it had been trading it.
    bars = _bars(OPENS, CLOSES)
    db = tmp_path / "book.db"
    _install(db, bars)

    spy = _SpyStrategy(SmaTrendStrategy([3]).build({"lookback": 3}))
    config = _config()
    digest = _run(db, config, tmp_path, strategy=spy)

    assert spy.seen == [bars[-1].event_time]  # one decision, on the latest bar
    assert digest.bars_processed == 1
    conn = store.connect(db)
    try:
        state = store.read_paper_state(conn, "TEST")
        assert state is not None
        assert state.cash == config.starting_equity
        assert state.shares == 0.0
        assert state.last_decided_event_time == bars[-1].event_time
        assert store.read_paper_fills(conn, "TEST") == []  # nothing replayed
        assert len(store.read_paper_equity(conn, "TEST")) == 1
    finally:
        conn.close()


def test_fewer_than_two_bars_raises(tmp_path: Path) -> None:
    db = tmp_path / "book.db"
    _install(db, _bars(OPENS[:1], CLOSES[:1]))
    with pytest.raises(ValueError, match="at least 2"):
        _run(db, _config(), tmp_path)


def test_bars_synced_after_loop_start_are_still_visible(tmp_path: Path) -> None:
    # FAIL-FIRST for the 2026-07-15 silent no-op: ingest/reconcile stamp their
    # rows AFTER the loop's start instant, so a loop that reads as-of its
    # PRE-sync clock cannot see the bars its own sync just wrote -- on a rebuild
    # night it sees an empty store and settles/decides NOTHING, without error.
    # The fix reads the clock again after the sync. This test's sync writes a
    # new bar stamped between the two clock readings: the old code missed it
    # (bars_processed == 0); the fixed loop must decide it.
    t_start = "2025-06-01T12:00:00Z"
    t_sync_stamp = "2025-06-01T12:03:00Z"  # after t_start: invisible to old code
    t_after_sync = "2025-06-01T12:05:00Z"

    bars = _bars(OPENS, CLOSES)
    db = tmp_path / "book.db"
    _install(db, bars[:4])
    _run(db, _config(), tmp_path)  # seed the book (cursor at bar 3)

    class _WritingSync(_RecordingSync):
        """A sync that delivers bar 4 stamped AFTER the loop started."""

        def reconcile(
            self, tickers: Sequence[str], db_path: store.DbPath
        ) -> object:
            late = bars[4]
            _install(
                db,
                [
                    PriceClean(
                        ticker=late.ticker,
                        event_time=late.event_time,
                        open=late.open,
                        high=late.high,
                        low=late.low,
                        close=late.close,
                        volume=late.volume,
                        adj_close=late.adj_close,
                        knowable_time=t_sync_stamp,
                        source=late.source,
                    )
                ],
            )
            return super().reconcile(tickers, db_path)

    clock_reads: list[str] = [t_start, t_after_sync]

    def _two_phase_clock() -> str:
        return clock_reads.pop(0) if clock_reads else t_after_sync

    sync = _WritingSync()
    digest = run_paper(
        db,
        _config(),
        ingest_fn=sync.ingest,
        reconcile_fn=sync.reconcile,
        now_fn=_two_phase_clock,
        killswitch_dir=tmp_path,
    )

    # The just-synced bar was seen, settled against, and decided.
    assert digest.bars_processed == 1
    assert digest.as_of_bar == bars[4].event_time


def test_dry_run_reports_but_writes_nothing(tmp_path: Path) -> None:
    bars = _bars(OPENS, CLOSES)
    db = tmp_path / "book.db"
    _install(db, bars)

    digest = _run(db, _config(), tmp_path, dry_run=True)

    assert digest.dry_run is True
    assert digest.bars_processed == 1  # it DID run the pass...
    conn = store.connect(db)
    try:  # ...but every write was rolled back.
        assert store.read_paper_state(conn, "TEST") is None
        assert store.read_paper_equity(conn, "TEST") == []
    finally:
        conn.close()
