import numpy as np

from manual.scout.hiccups import hiccup_scan
from manual.scout.scoring import ScoreResult
from tests.manual.conftest import make_ohlcv


def row(ticker, sector, close, sma20, sma200, roc63):
    return {"ticker": ticker, "name": ticker, "sector": sector,
            "index": "FTSE100", "stamp_duty": "Y",
            "snap": {"close": close, "sma20": sma20, "sma200": sma200,
                     "roc63": roc63},
            "buy": ScoreResult(), "sell": ScoreResult()}


def breadth_rows(above20, below20, above200_share=0.7):
    """60 rows: control short-term vs long-term breadth independently."""
    rows = []
    total = above20 + below20
    n200 = int(total * above200_share)
    for i in range(total):
        c_vs_20 = 110.0 if i < above20 else 90.0
        sma200 = 80.0 if i < n200 else 130.0     # above/below 200-day
        rows.append(row(f"T{i}.L", "Industrials", c_vs_20, 100.0,
                        sma200, 1.0))
    return rows


def seed_uptrend_index(store):
    store.upsert_prices("^FTSE", make_ohlcv(7000 + 5 * np.arange(300)))


def seed_dipping_index(store, dip_pct=3.5):
    closes = 7000 + 5 * np.arange(300)
    peak = closes[-1]
    closes = np.concatenate([closes[:-5],
                             np.linspace(peak, peak * (1 - dip_pct / 100), 5)])
    store.upsert_prices("^FTSE", make_ohlcv(closes))


def seed_broken_index(store):
    up = 7000 + 5 * np.arange(200)
    down = np.linspace(up[-1], up[-1] * 0.80, 100)   # 20% slide
    store.upsert_prices("^FTSE", make_ohlcv(np.concatenate([up, down])))


def seed_vix(store, level, pop_from=None):
    if pop_from:
        closes = np.concatenate([np.full(40, pop_from),
                                 np.linspace(pop_from, level, 20)])
    else:
        closes = np.full(60, float(level))
    store.upsert_prices("^VIX", make_ohlcv(closes))


def test_quiet_market_no_hiccups(tmp_store):
    seed_uptrend_index(tmp_store)
    seed_vix(tmp_store, 15.0)
    scan = hiccup_scan(tmp_store, breadth_rows(45, 15))
    assert not scan["small"]["active"]
    assert not scan["large"]["active"]


def test_small_hiccup_shakeout(tmp_store):
    seed_dipping_index(tmp_store, dip_pct=3.5)     # off 20d high, above 200d
    seed_vix(tmp_store, 22.0, pop_from=14.0)       # ~57% pop, no storm
    rows = breadth_rows(above20=15, below20=45, above200_share=0.65)
    scan = hiccup_scan(tmp_store, rows)
    assert scan["small"]["active"]
    assert not scan["large"]["active"]
    assert len(scan["small"]["evidence"]) >= 2
    assert any("dipped" in e for e in scan["small"]["evidence"])


def test_large_hiccup_correction(tmp_store):
    seed_broken_index(tmp_store)                   # deep below 52wk + 200d
    seed_vix(tmp_store, 33.0)
    rows = breadth_rows(above20=10, below20=50, above200_share=0.30)
    scan = hiccup_scan(tmp_store, rows)
    assert scan["large"]["active"]
    assert not scan["small"]["active"]             # large outranks small
    joined = " ".join(scan["large"]["evidence"])
    assert "52-week" in joined and "200-day" in joined


def test_large_needs_two_pieces_of_evidence(tmp_store):
    seed_uptrend_index(tmp_store)                  # index healthy
    seed_vix(tmp_store, 33.0)                      # storm alone isn't enough
    scan = hiccup_scan(tmp_store, breadth_rows(40, 20))
    assert not scan["large"]["active"]
