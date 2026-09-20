import numpy as np
import pandas as pd
import pytest

from manual.scout.indicators import (MIN_BARS, _recent_cross, atr_wilder, macd,
                              rsi_wilder, roc, sma, snapshot, to_gbp)
from tests.manual.conftest import make_ohlcv, uptrend_df, downtrend_df


def test_sma_matches_manual_mean():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    out = sma(s, 3)
    assert np.isnan(out.iloc[1])
    assert out.iloc[2] == pytest.approx(2.0)
    assert out.iloc[4] == pytest.approx(4.0)


def test_rsi_extremes():
    up = pd.Series(np.arange(1, 60, dtype=float))
    down = pd.Series(np.arange(60, 1, -1, dtype=float))
    assert rsi_wilder(up).iloc[-1] > 99
    assert rsi_wilder(down).iloc[-1] < 1


def test_rsi_matches_wilder_reference_loop():
    rng = np.random.default_rng(42)
    close = pd.Series(100 + np.cumsum(rng.normal(0, 1, 200)))
    ours = rsi_wilder(close, 14)
    # independent recursive Wilder implementation
    delta = close.diff().to_numpy()
    ag = al = None
    ref = np.full(len(close), np.nan)
    for i in range(1, len(close)):
        gain = max(delta[i], 0.0)
        loss = max(-delta[i], 0.0)
        if ag is None:               # ewm(adjust=False) seeds with first obs
            ag, al = gain, loss
        else:
            ag = (ag * 13 + gain) / 14
            al = (al * 13 + loss) / 14
        ref[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    assert ours.iloc[-1] == pytest.approx(ref[-1], abs=1e-6)
    assert ours.iloc[100] == pytest.approx(ref[100], abs=1e-6)


def test_atr_constant_range_converges():
    n = 300
    df = pd.DataFrame({
        "open": np.full(n, 100.0), "close": np.full(n, 100.0),
        "high": np.full(n, 101.0), "low": np.full(n, 99.0),
        "volume": np.full(n, 1e6)})
    assert atr_wilder(df).iloc[-1] == pytest.approx(2.0, abs=1e-6)


def test_atr_matches_wilder_reference_loop():
    df = uptrend_df(150)
    ours = atr_wilder(df, 14)
    h, l, c = (df[k].to_numpy() for k in ("high", "low", "close"))
    ref = 0.0
    for i in range(len(df)):
        if i == 0:
            tr = h[i] - l[i]
        else:
            tr = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
        ref = tr if i == 0 else (ref * 13 + tr) / 14
    assert ours.iloc[-1] == pytest.approx(ref, rel=1e-9)


def test_macd_zero_on_constant_series():
    line, sig, hist = macd(pd.Series(np.full(100, 50.0)))
    assert abs(line.iloc[-1]) < 1e-9
    assert abs(hist.iloc[-1]) < 1e-9


def test_roc_exact():
    s = pd.Series(np.concatenate([np.full(30, 100.0), [110.0]]))
    assert roc(s, 21).iloc[-1] == pytest.approx(10.0)


def test_to_gbp_conversions():
    assert to_gbp(350.0, "GBp") == pytest.approx(3.50)
    assert to_gbp(3.50, "GBP") == pytest.approx(3.50)
    assert to_gbp(100.0, "USD") is None


def test_snapshot_requires_min_bars():
    assert snapshot(uptrend_df(MIN_BARS - 1)) is None
    assert snapshot(uptrend_df(MIN_BARS)) is not None


def test_snapshot_uptrend_shape():
    snap = snapshot(uptrend_df(300), "GBp")
    assert snap["close"] > snap["sma50"] > snap["sma200"]
    assert snap["sma50_slope"] > 0
    assert snap["pos52"] == pytest.approx(1.0)
    assert snap["dist_to_hi_pct"] == pytest.approx(0.0, abs=1e-9)
    assert snap["close_gbp"] == pytest.approx(snap["close"] / 100)
    assert snap["up_day"] and not snap["down_day"]
    assert snap["turnover_gbp"] > 0


def test_snapshot_gap_pct_exact():
    df = uptrend_df(300)
    df.iloc[-1, df.columns.get_loc("open")] = df["close"].iloc[-2] * 1.10
    snap = snapshot(df)
    assert snap["gap_pct"] == pytest.approx(10.0, abs=1e-6)


def test_snapshot_vol_ratio_consistent():
    df = uptrend_df(300)
    df.iloc[-1, df.columns.get_loc("volume")] = 2_000_000.0
    snap = snapshot(df)
    manual = 2_000_000.0 / df["volume"].tail(20).mean()
    assert snap["vol_ratio"] == pytest.approx(manual)


def test_recent_cross_detection():
    n = 60
    slow = pd.Series(np.full(n, 100.0))
    fast = pd.Series(np.concatenate([np.full(n - 5, 99.0), np.full(5, 101.0)]))
    assert _recent_cross(fast, slow, 15, golden=True)
    assert not _recent_cross(fast, slow, 15, golden=False)
    assert _recent_cross(-fast + 200, slow, 15, golden=False)


def test_snapshot_death_cross_flag_on_rollover():
    closes = np.concatenate([100 + 0.5 * np.arange(250),
                             np.linspace(225, 120, 90)])
    snap = snapshot(make_ohlcv(closes))
    assert snap["death_cross_recent"] or snap["sma50"] < snap["sma200"]


def test_downtrend_snapshot_shape():
    snap = snapshot(downtrend_df(300))
    assert snap["close"] < snap["sma50"] < snap["sma200"]
    assert snap["sma50_slope"] < 0
    assert snap["dist_to_lo_pct"] == pytest.approx(0.0, abs=1e-9)


def test_durability_fields():
    up = snapshot(uptrend_df(300))
    assert up["above200_frac"] == pytest.approx(1.0)
    assert up["roc126"] > 0
    assert up["roc252"] > 0
    down = snapshot(downtrend_df(300))
    assert down["above200_frac"] == pytest.approx(0.0)
