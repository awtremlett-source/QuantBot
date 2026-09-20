import pytest

from manual.scout import risk
from manual.scout.config import Config
from tests.manual.conftest import base_snap


def snap(close_gbp=5.0, atr_gbp=0.5):
    return base_snap(close_gbp=close_gbp, atr_gbp=atr_gbp)


def test_exact_sizing_and_costs():
    cfg = Config()  # 10k bankroll, 1% risk, 2x ATR, stamp 0.5%
    p = risk.plan(snap(), cfg, "Y")
    assert p["ok"]
    assert p["stop_gbp"] == pytest.approx(4.0)
    assert p["risk_per_share_gbp"] == pytest.approx(1.0)
    assert p["shares"] == 100
    assert p["risk_gbp"] == pytest.approx(100.0)
    assert p["value_gbp"] == pytest.approx(500.0)
    assert p["stamp_gbp"] == pytest.approx(2.50)
    assert p["ptm_gbp"] == 0.0
    assert p["costs_gbp"] == pytest.approx(2.50)
    assert p["breakeven_pct"] == pytest.approx(0.5)
    assert p["pct_bankroll"] == pytest.approx(5.0)
    assert p["warnings"] == []


def test_stamp_duty_skipped_when_flag_n():
    p = risk.plan(snap(), Config(), "N")
    assert p["stamp_gbp"] == 0.0
    assert p["breakeven_pct"] == pytest.approx(0.0)


def test_ptm_levy_above_threshold():
    cfg = Config(bankroll_gbp=200_000)
    p = risk.plan(snap(close_gbp=100.0, atr_gbp=5.0), cfg, "Y")
    assert p["shares"] == 200            # 2000 budget / 10 rps
    assert p["value_gbp"] == pytest.approx(20_000)
    assert p["ptm_gbp"] == pytest.approx(1.0)


def test_concentration_warning_over_20_pct():
    cfg = Config(bankroll_gbp=1000)
    p = risk.plan(snap(close_gbp=5.0, atr_gbp=0.05), cfg, "Y")
    assert p["pct_bankroll"] > 20
    assert p["warnings"] and "bankroll" in p["warnings"][0]


def test_zero_atr_rejected():
    p = risk.plan(snap(atr_gbp=0.0), Config(), "Y")
    assert not p["ok"] and "ATR" in p["why"]


def test_stop_below_zero_rejected():
    p = risk.plan(snap(close_gbp=1.0, atr_gbp=0.6), Config(), "Y")
    assert not p["ok"]


def test_risk_per_share_bigger_than_budget_rejected():
    cfg = Config(bankroll_gbp=1000, risk_pct=1.0)   # budget 10
    p = risk.plan(snap(close_gbp=100.0, atr_gbp=10.0), cfg, "Y")  # rps 20
    assert not p["ok"] and "budget" in p["why"]


def test_non_sterling_rejected():
    p = risk.plan(base_snap(close_gbp=None, atr_gbp=None), Config(), "Y")
    assert not p["ok"] and "sterling" in p["why"].lower()
