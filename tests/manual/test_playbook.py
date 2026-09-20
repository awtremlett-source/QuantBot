from manual.scout.playbook import manage_path, recommend_new
from manual.scout.scoring import ScoreResult
from tests.manual.conftest import base_snap

PLAN = {"ok": True, "entry_gbp": 5.0, "stop_gbp": 4.6}


def res(score=60, setup="\u2014"):
    return ScoreResult(score=score, setup=setup)


def hic(small=False, large=False):
    return {"small": {"active": small}, "large": {"active": large}}


def test_rough_or_large_hiccup_vetoes_everything():
    for env in (("ROUGH", hic()), ("GOOD", hic(large=True))):
        rec = recommend_new(base_snap(), res(90, "Breakout"), res(0),
                            PLAN, env[0], env[1])
        assert not rec["tradeable"]
        assert rec["play"] == "Cash is a position"


def test_breakout_play_with_numbers():
    rec = recommend_new(base_snap(atr_gbp=0.10), res(85, "Breakout"),
                        res(5), PLAN, "GOOD", hic())
    assert rec["tradeable"] and rec["play"] == "52-week breakout"
    joined = " ".join(t for _l, t in rec["steps"])
    assert "\u00a35.00" in joined and "\u00a34.60" in joined
    assert "50-day" in joined


def test_mixed_dial_suggests_half_size():
    rec = recommend_new(base_snap(), res(85, "Breakout"), res(5),
                        PLAN, "MIXED", hic())
    assert "half your normal size" in rec["steps"][0][1]


def test_pullback_notes_small_hiccup_window():
    rec = recommend_new(base_snap(dist_to_hi_pct=6.0), res(70, "Pullback"),
                        res(5), PLAN, "MIXED", hic(small=True))
    assert rec["play"] == "Pullback in uptrend"
    assert "prime window" in rec["why"]
    assert any("20-day" in t for _l, t in rec["steps"])


def test_golden_cross_play():
    snap = base_snap(golden_cross_recent=True, sma200=430.0, close=500.0)
    rec = recommend_new(snap, res(40, "\u2014"), res(5), PLAN, "GOOD", hic())
    assert rec["play"] == "Golden cross"


def test_weak_stock_gets_avoid():
    rec = recommend_new(base_snap(), res(10), res(60, "Breakdown"),
                        PLAN, "GOOD", hic())
    assert not rec["tradeable"] and "avoid" in rec["play"]


def test_nothing_fits_waits():
    rec = recommend_new(base_snap(), res(10), res(10), PLAN, "GOOD", hic())
    assert not rec["tradeable"]
    assert any("breakout" in t.lower() for _l, t in rec["steps"])


def trade(stop=4.0):
    return {"ticker": "T.L", "entry_px": 5.0, "stop_px": stop, "shares": 10}


def test_manage_trend_ride_with_trail():
    snap = base_snap(close=500.0, close_gbp=5.0, sma50=470.0, sma200=430.0,
                     atr_gbp=0.10)
    line = manage_path(snap, trade(stop=4.0))
    assert "trend-ride" in line and "\u00a34.80" in line


def test_manage_breached_says_sell():
    snap = base_snap(close_gbp=3.9)
    assert "sell today" in manage_path(snap, trade(stop=4.0)).lower()


def test_manage_below_fifty_tightens():
    snap = base_snap(close=460.0, close_gbp=4.6, sma50=470.0, sma200=430.0)
    assert "tighten" in manage_path(snap, trade()).lower()
