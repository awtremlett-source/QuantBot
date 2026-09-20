import re

from manual.scout.scoring import buy_score, sell_score
from tests.manual.conftest import base_snap


def bull(**over):
    s = base_snap(
        close=500.0, sma20=490.0, sma50=470.0, sma200=430.0,
        sma50_slope=0.03, rsi=60.0, macd_hist=1.5, macd_hist_delta=0.2,
        roc21=4.0, roc63=9.0, dist_to_hi_pct=1.0, dist_to_lo_pct=40.0,
        vol_ratio=1.6, up_day=True, down_day=False)
    s.update(over)
    return s


def bear(**over):
    s = base_snap(
        close=300.0, close_gbp=3.0, sma20=310.0, sma50=330.0, sma200=380.0,
        sma50_slope=-0.03, rsi=40.0, macd_hist=-1.5, macd_hist_delta=-0.2,
        roc21=-4.0, roc63=-9.0, dist_to_hi_pct=30.0, dist_to_lo_pct=1.0,
        vol_ratio=1.6, up_day=False, down_day=True)
    s.update(over)
    return s


def reason_sum(res) -> float:
    total = 0.0
    for r in res.reasons:
        m = re.match(r"([+-])([\d.]+)", r)
        assert m, f"reason without points: {r}"
        total += float(m.group(2)) * (1 if m.group(1) == "+" else -1)
    return total


def test_full_bull_scores_high_with_breakout_label(cfg):
    res = buy_score(bull(), cfg)
    assert res.score == 100  # 110 raw, clamped
    assert res.setup == "Breakout"
    assert any("52-week high" in r for r in res.reasons)


def test_score_equals_clamped_reason_sum(cfg):
    for snap in (bull(), bear(), bull(rsi=80.0, gap_pct=9.0),
                 bear(turnover_gbp=100.0), bull(vol_ratio=1.0)):
        for fn in (buy_score, sell_score):
            res = fn(snap, cfg)
            assert res.score == int(round(max(0, min(100, reason_sum(res)))))


def test_trend_component_monotonic_plus_ten(cfg):
    below = bull(close=420.0, dist_to_hi_pct=20.0, vol_ratio=1.0)
    above = bull(close=440.0, dist_to_hi_pct=20.0, vol_ratio=1.0)
    assert buy_score(above, cfg).score - buy_score(below, cfg).score == 10


def test_rsi_power_zone_peaks_at_sixty(cfg):
    lonely = base_snap()          # only tradeability scores: 5 + 5
    assert buy_score(lonely, cfg).score == 10
    assert buy_score(base_snap(rsi=60.0), cfg).score == 20
    assert buy_score(base_snap(rsi=65.0), cfg).score == 15
    assert buy_score(base_snap(rsi=50.0), cfg).score == 10  # zone edge = 0 pts


def test_pullback_label_and_points(cfg):
    snap = bull(close=474.0, rsi=40.0, dist_to_hi_pct=20.0, vol_ratio=1.0)
    res = buy_score(snap, cfg)
    assert res.setup == "Pullback"
    assert any(r.startswith("+20") and "Pullback" in r for r in res.reasons)


def test_breakout_beats_pullback_when_both_fire(cfg):
    snap = bull(close=474.0, rsi=40.0, dist_to_hi_pct=2.0, vol_ratio=1.5)
    res = buy_score(snap, cfg)
    assert res.setup == "Breakout"
    joined = " ".join(res.reasons)
    assert "+25" in joined and "+20" not in joined


def test_trend_follow_label_without_setup(cfg):
    snap = bull(rsi=None, dist_to_hi_pct=20.0, vol_ratio=1.0)
    assert buy_score(snap, cfg).setup == "Trend-follow"


def test_penalties_floor_at_zero(cfg):
    snap = base_snap(rsi=85.0, turnover_gbp=1000.0, close_gbp=0.10)
    res = buy_score(snap, cfg)
    assert res.score == 0
    assert reason_sum(res) < 0


def test_gap_penalty_costs_ten(cfg):
    calm = bull(vol_ratio=1.0)               # raw 65, no clamp
    gappy = bull(vol_ratio=1.0, gap_pct=9.0)
    r1, r2 = buy_score(calm, cfg), buy_score(gappy, cfg)
    assert r1.score - r2.score == 10
    assert any("Gapped up" in r for r in r2.reasons)


def test_overheated_rsi_penalty(cfg):
    hot = buy_score(bull(vol_ratio=1.0, rsi=80.0), cfg)
    assert any("Overheated" in r for r in hot.reasons)
    assert hot.score == 45  # 65 - 10 zone points lost - 10 penalty


def test_illiquid_penalty_both_sides(cfg):
    b = buy_score(bull(turnover_gbp=1000.0), cfg)
    s = sell_score(bear(turnover_gbp=1000.0), cfg)
    assert any("Thin trading" in r for r in b.reasons)
    assert any("Thin trading" in r for r in s.reasons)


def test_full_bear_scores_high_with_breakdown_label(cfg):
    res = sell_score(bear(), cfg)
    assert res.score >= 90
    assert res.setup == "Breakdown"


def test_death_cross_scores_fifteen(cfg):
    snap = bear(dist_to_lo_pct=10.0, vol_ratio=1.0, death_cross_recent=True)
    res = sell_score(snap, cfg)
    assert res.setup == "Death cross"
    assert res.score == 80  # 30 trend + 25 momentum + 15 cross + 10 tradeability


def test_washed_out_penalty(cfg):
    res = sell_score(bear(rsi=18.0, vol_ratio=1.0), cfg)
    assert any("Washed out" in r for r in res.reasons)


def test_non_sterling_snapshot_does_not_crash(cfg):
    res = buy_score(bull(close_gbp=None, turnover_gbp=None), cfg)
    assert 0 <= res.score <= 100


def test_non_sterling_skips_thin_trading_penalty(cfg):
    res = buy_score(bull(close_gbp=None, turnover_gbp=None), cfg)
    assert not any("Thin trading" in r for r in res.reasons)
