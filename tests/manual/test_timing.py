import numpy as np

from manual.scout.scoring import ScoreResult
from manual.scout.timing import timing_checks, timing_dial
from tests.manual.conftest import make_ohlcv


def row(ticker, sector, close, sma200, roc63):
    return {"ticker": ticker, "name": ticker, "sector": sector,
            "index": "FTSE100", "stamp_duty": "Y",
            "snap": {"close": close, "sma200": sma200, "roc63": roc63},
            "buy": ScoreResult(), "sell": ScoreResult()}


def seed_indices(store, rising=True):
    step = 5 if rising else -5
    base = 7000 if rising else 9000
    df = make_ohlcv(base + step * np.arange(300))
    store.upsert_prices("^FTSE", df)
    store.upsert_prices("^FTMC", df)


def many_rows(n_above, n_below, sector="Industrials"):
    rows = []
    for i in range(n_above):
        rows.append(row(f"A{i}.L", sector, 110.0, 100.0, 5.0))
    for i in range(n_below):
        rows.append(row(f"B{i}.L", sector, 90.0, 100.0, -5.0))
    return rows


def find(checks, name):
    return next(c for c in checks if c["name"] == name)


def test_breadth_maths_and_bands(tmp_store, cfg):
    seed_indices(tmp_store)
    checks = timing_checks(tmp_store, many_rows(45, 15), cfg)  # 75% above
    b = find(checks, "Breadth")
    assert b["points"] == 25 and "75%" in b["line"]
    b = find(timing_checks(tmp_store, many_rows(30, 30), cfg), "Breadth")
    assert b["points"] == 12
    b = find(timing_checks(tmp_store, many_rows(15, 45), cfg), "Breadth")
    assert b["points"] == 0


def test_breadth_excluded_when_too_few(tmp_store, cfg):
    seed_indices(tmp_store)
    b = find(timing_checks(tmp_store, many_rows(10, 10), cfg), "Breadth")
    assert b["points"] is None


def test_trend_bands(tmp_store, cfg):
    seed_indices(tmp_store, rising=True)
    assert find(timing_checks(tmp_store, [], cfg), "Trend")["points"] == 25
    seed_indices(tmp_store, rising=False)
    assert find(timing_checks(tmp_store, [], cfg), "Trend")["points"] == 0


def test_fear_bands(tmp_store, cfg):
    seed_indices(tmp_store)
    for level, expected in ((15.0, 25), (24.0, 12), (32.0, 0)):
        tmp_store.upsert_prices("^VIX", make_ohlcv(np.full(60, level)))
        f = find(timing_checks(tmp_store, [], cfg), "Fear")
        assert f["points"] == expected, level


def test_fear_rising_fast_downgrades_calm(tmp_store, cfg):
    seed_indices(tmp_store)
    closes = np.concatenate([np.full(50, 13.0), np.linspace(13, 18, 11)])
    tmp_store.upsert_prices("^VIX", make_ohlcv(closes))
    f = find(timing_checks(tmp_store, [], cfg), "Fear")
    assert f["points"] == 12 and "climbing" in f["line"]


def test_flow_bands(tmp_store, cfg):
    seed_indices(tmp_store)
    rows = [row(f"C{i}.L", "Banks", 100, 90, 10.0) for i in range(6)] + \
           [row(f"D{i}.L", "Utilities", 100, 90, 2.0) for i in range(6)]
    f = find(timing_checks(tmp_store, rows, cfg), "Flow")
    assert f["points"] == 25 and "chasing growth" in f["line"]
    rows = [row(f"C{i}.L", "Banks", 100, 90, -6.0) for i in range(6)] + \
           [row(f"D{i}.L", "Utilities", 100, 90, 4.0) for i in range(6)]
    f = find(timing_checks(tmp_store, rows, cfg), "Flow")
    assert f["points"] == 0 and "hiding" in f["line"]


def test_dial_normalises_missing_checks(tmp_store, cfg):
    seed_indices(tmp_store)          # only Trend has data: 25/25 -> 100
    dial = timing_dial(tmp_store, [], cfg, on_date="2026-08-10")
    assert dial["score"] == 100
    assert dial["raw_state"] == "GOOD"


def test_persistence_slow_up_fast_down(tmp_store, cfg):
    seed_indices(tmp_store, rising=False)      # ROUGH raw
    d = timing_dial(tmp_store, [], cfg, on_date="2026-08-10")
    assert d["state"] == "ROUGH"               # first run adopts raw
    seed_indices(tmp_store, rising=True)       # raw flips to GOOD
    d = timing_dial(tmp_store, [], cfg, on_date="2026-08-11")
    assert d["raw_state"] == "GOOD" and d["state"] == "ROUGH"
    assert "needs a couple more days" in d["guidance"]
    d = timing_dial(tmp_store, [], cfg, on_date="2026-08-12")
    assert d["state"] == "ROUGH"               # two days: still waiting
    d = timing_dial(tmp_store, [], cfg, on_date="2026-08-13")
    assert d["state"] == "GOOD"                # third day earns the upgrade
    seed_indices(tmp_store, rising=False)      # bad day: instant downgrade
    d = timing_dial(tmp_store, [], cfg, on_date="2026-08-14")
    assert d["state"] == "ROUGH"


def test_same_day_rescan_idempotent(tmp_store, cfg):
    seed_indices(tmp_store, rising=True)
    for _ in range(3):                          # 3 scans, same day
        d = timing_dial(tmp_store, [], cfg, on_date="2026-08-10")
    seed_indices(tmp_store, rising=False)
    timing_dial(tmp_store, [], cfg, on_date="2026-08-10")
    seed_indices(tmp_store, rising=True)
    d = timing_dial(tmp_store, [], cfg, on_date="2026-08-11")
    assert d["state"] != "GOOD"                 # one day back up isn't enough
