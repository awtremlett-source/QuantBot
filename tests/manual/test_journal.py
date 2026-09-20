import pytest

from manual.scout import journal


def _open(store, ticker="TEST.L", entry=5.0, stop=4.5, shares=100,
          setup="Breakout"):
    return journal.open_trade(
        store, ticker=ticker, name="Test plc", entry_px=entry, stop_px=stop,
        shares=shares, risk_gbp=shares * (entry - stop), open_costs_gbp=2.5,
        setup_type=setup, thesis="test thesis", checklist={"a": True})


def test_round_trip_pnl_and_r(tmp_store):
    tid = _open(tmp_store)
    closed = journal.close_trade(tmp_store, tid, exit_px=6.0,
                                 exit_reason="Strength faded / target",
                                 lessons="let winners run")
    assert closed["pnl_gbp"] == pytest.approx(100 * 1.0 - 2.5)
    assert closed["r_multiple"] == pytest.approx((6.0 - 5.0) / 0.5)
    assert closed["closed_at"]
    assert tmp_store.list_trades(open_only=True) == []


def test_stop_equals_entry_gives_none_r(tmp_store):
    tid = _open(tmp_store, entry=5.0, stop=5.0)
    closed = journal.close_trade(tmp_store, tid, exit_px=5.5,
                                 exit_reason="Other")
    assert closed["r_multiple"] is None


def test_double_close_raises(tmp_store):
    tid = _open(tmp_store)
    journal.close_trade(tmp_store, tid, exit_px=5.5, exit_reason="Other")
    with pytest.raises(ValueError):
        journal.close_trade(tmp_store, tid, exit_px=5.5, exit_reason="Other")


def test_stats_expectancy_and_by_setup(tmp_store):
    t1 = _open(tmp_store, entry=5.0, stop=4.5, setup="Breakout")
    journal.close_trade(tmp_store, t1, exit_px=6.0, exit_reason="Target")  # +2R
    t2 = _open(tmp_store, entry=5.0, stop=4.5, setup="Pullback")
    journal.close_trade(tmp_store, t2, exit_px=4.5, exit_reason="Stop hit")  # -1R
    _open(tmp_store, setup="Breakout")  # still open, excluded

    s = journal.stats(tmp_store.list_trades())
    assert s["count"] == 2
    assert s["wins"] == 1
    assert s["win_rate"] == pytest.approx(50.0)
    assert s["expectancy_r"] == pytest.approx((2.0 - 1.0) / 2)
    assert s["by_setup"]["Breakout"]["count"] == 1
    assert s["by_setup"]["Breakout"]["avg_r"] == pytest.approx(2.0)
    assert s["by_setup"]["Pullback"]["win_rate"] == 0.0


def test_stats_empty(tmp_store):
    s = journal.stats(tmp_store.list_trades())
    assert s["count"] == 0 and s["expectancy_r"] is None


def test_fractional_shares_round_trip(tmp_store):
    tid = journal.open_trade(
        tmp_store, ticker="FRAC.L", name="Frac plc", entry_px=100.0,
        stop_px=90.0, shares=0.5, risk_gbp=5.0, open_costs_gbp=0.0,
        setup_type="Manual", thesis="fractional", checklist={})
    closed = journal.close_trade(tmp_store, tid, exit_px=120.0,
                                 exit_reason="Target")
    assert closed["pnl_gbp"] == pytest.approx(0.5 * 20.0)
    assert closed["r_multiple"] == pytest.approx(2.0)


def test_stop_above_entry_gives_none_r_but_correct_pnl(tmp_store):
    tid = journal.open_trade(
        tmp_store, ticker="GLD.L", name="Gold", entry_px=62.87,
        stop_px=94.25, shares=1.64, risk_gbp=0.0, open_costs_gbp=0.0,
        setup_type="Manual", thesis="profit stop", checklist={})
    closed = journal.close_trade(tmp_store, tid, exit_px=100.0,
                                 exit_reason="Stop hit")
    assert closed["r_multiple"] is None
    assert closed["pnl_gbp"] == pytest.approx(1.64 * (100.0 - 62.87))
