import pandas as pd
import pytest

from manual.scout.config import Config
from manual.scout.picks import record_board, performance
from manual.scout.scoring import ScoreResult
from tests.manual.conftest import make_ohlcv


def fake_row(ticker, buy, sell, px=500.0):
    return {
        "ticker": ticker, "name": f"{ticker} plc", "sector": "Test",
        "index": "FTSE100", "stamp_duty": "Y",
        "snap": {"close": px, "close_gbp": px / 100},
        "buy": ScoreResult(score=buy, setup="Breakout" if buy else "\u2014"),
        "sell": ScoreResult(score=sell, setup="Breakdown" if sell else "\u2014"),
    }


def test_record_board_top_n_ranks_and_zero_filter(tmp_store):
    rows = [fake_row("A.L", 90, 0), fake_row("B.L", 50, 0),
            fake_row("C.L", 10, 0), fake_row("D.L", 0, 0)]
    n = record_board(tmp_store, rows, Config(top_n=2), on_date="2026-08-14")
    assert n == 2                       # SELL side all zero -> nothing stored
    picks = tmp_store.list_picks()
    assert [(p["ticker"], p["rank"]) for p in picks] == [("A.L", 1), ("B.L", 2)]
    assert all(p["side"] == "BUY" for p in picks)
    assert picks[0]["px"] == 500.0 and picks[0]["px_gbp"] == 5.0


def test_record_board_idempotent_same_day(tmp_store):
    rows = [fake_row("A.L", 90, 40)]
    record_board(tmp_store, rows, Config(), on_date="2026-08-14")
    record_board(tmp_store, rows, Config(), on_date="2026-08-14")
    assert len(tmp_store.list_picks()) == 2      # one BUY + one SELL, no dupes


def test_record_board_defaults_to_today(tmp_store):
    from manual.scout.picks import LONDON
    from datetime import datetime
    record_board(tmp_store, [fake_row("A.L", 60, 0)], Config())
    assert tmp_store.list_picks()[0]["date"] == \
        datetime.now(LONDON).date().isoformat()


def test_record_board_empty_rows_noop(tmp_store):
    assert record_board(tmp_store, [], Config()) == 0
    assert tmp_store.list_picks() == []


def test_performance_change_and_bars(tmp_store):
    closes = [100.0] * 95 + [102.0, 104.0, 106.0, 108.0, 110.0]
    df = make_ohlcv(closes)
    tmp_store.upsert_prices("A.L", df)
    pick_date = df.index[-6].strftime("%Y-%m-%d")   # px 100, 5 bars follow
    tmp_store.record_picks(pick_date, "BUY", [
        {"ticker": "A.L", "name": "A plc", "score": 80, "setup": "Breakout",
         "px": 100.0, "px_gbp": 1.0}])
    rows, agg = performance(tmp_store, tmp_store.list_picks())
    assert rows[0]["px_now"] == pytest.approx(110.0)
    assert rows[0]["change_pct"] == pytest.approx(10.0)
    assert rows[0]["bars_since"] == 5
    assert agg["buy_avg_pct"] == pytest.approx(10.0)
    assert agg["sell_avg_pct"] is None


def test_performance_handles_missing_history(tmp_store):
    tmp_store.record_picks("2026-08-14", "SELL", [
        {"ticker": "GONE.L", "name": "Gone", "score": 70,
         "setup": "Breakdown", "px": 50.0, "px_gbp": 0.5}])
    rows, agg = performance(tmp_store, tmp_store.list_picks())
    assert rows[0]["change_pct"] is None
    assert agg["sell_avg_pct"] is None and agg["n"] == 1
