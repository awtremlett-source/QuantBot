from manual.scout.scan import position_verdict
from tests.manual.conftest import base_snap


def trade(stop=4.0, entry=5.0):
    return {"ticker": "T.L", "entry_px": entry, "stop_px": stop,
            "shares": 10, "open_costs_gbp": 0.0}


def healthy():
    return base_snap(close=500.0, close_gbp=5.0, sma50=470.0, sma200=430.0,
                     rsi=60.0, macd_hist=1.0, macd_hist_delta=0.1)


def test_hold_when_trend_intact():
    v = position_verdict(healthy(), trade(), sell_score_val=10)
    assert v["verdict"] == "HOLD"
    assert "nothing to do" in v["headline"]


def test_sell_out_when_alert_hit():
    snap = healthy()
    snap["close_gbp"] = 3.9                       # below the 4.0 stop
    v = position_verdict(snap, trade(), sell_score_val=10)
    assert v["verdict"] == "SELL OUT"
    assert "sell alert" in v["headline"]


def test_sell_out_when_stock_turns_very_weak():
    v = position_verdict(healthy(), trade(), sell_score_val=70)
    assert v["verdict"] == "SELL OUT"


def test_beware_below_fifty_day():
    snap = healthy()
    snap["close"] = 460.0                          # under sma50 470
    snap["close_gbp"] = 4.6
    v = position_verdict(snap, trade(), sell_score_val=10)
    assert v["verdict"] == "BEWARE"
    assert "50-day" in v["headline"]


def test_trail_tip_in_details():
    snap = healthy()
    snap["atr_gbp"] = 0.10                         # trail 5.0-0.2=4.8 > 4.0
    v = position_verdict(snap, trade(), sell_score_val=10)
    assert any("raise your sell alert" in d for d in v["details"])
