import pytest

from manual.scout import journal
from manual.scout.config import Config
from manual.scout.ladder import ladder_line, ladder_state
from manual.scout.playbook import with_money_split
from manual.scout import risk
from tests.manual.conftest import base_snap


def _open(store, value=2000.0):
    journal.open_trade(store, ticker="X.L", name="X", entry_px=value / 100,
                       stop_px=value / 100 * 0.9, shares=100, risk_gbp=1.0,
                       open_costs_gbp=0.0, setup_type="Manual",
                       thesis="t", checklist={})


def test_slots_halve(tmp_store):
    cfg = Config()                              # 10k bankroll
    st = ladder_state(tmp_store, cfg)
    assert st["next_slot"] == 1 and st["next_cap"] == pytest.approx(5000)
    _open(tmp_store, 2000)
    st = ladder_state(tmp_store, cfg)
    assert st["next_slot"] == 2 and st["next_cap"] == pytest.approx(2500)
    assert st["deployed"] == pytest.approx(2000)
    assert st["reserve"] == pytest.approx(8000)
    _open(tmp_store, 1000)
    assert ladder_state(tmp_store, cfg)["next_cap"] == pytest.approx(1250)


def test_ladder_line_wording(tmp_store):
    line = ladder_line(ladder_state(tmp_store, Config()))
    assert "position #1" in line and "\u00a35,000" in line and "50%" in line


def test_ladder_full_after_many_positions(tmp_store):
    for _ in range(7):                          # slot 8 -> 0.39% of 10k < 100
        _open(tmp_store, 100)
    st = ladder_state(tmp_store, Config())
    assert st["full"]
    assert "full" in ladder_line(st)


def test_plan_capped_by_ladder():
    cfg = Config()
    snap = base_snap(close_gbp=5.0, atr_gbp=0.5)   # risk size: 100sh = £500
    p = risk.plan(snap, cfg, "Y", max_value_gbp=250.0)
    assert p["ok"] and p["shares"] == 50
    assert any("money ladder" in w for w in p["warnings"])
    p2 = risk.plan(snap, cfg, "Y", max_value_gbp=5000.0)
    assert p2["shares"] == 100 and not p2["warnings"]


def test_plan_rejected_when_slot_below_one_share():
    p = risk.plan(base_snap(close_gbp=50.0, atr_gbp=0.5), Config(), "Y",
                  max_value_gbp=25.0)
    assert not p["ok"] and "ladder" in p["why"]


def test_money_split_step_inserted():
    rec = {"tradeable": True, "steps": [("Enter", "buy"), ("Exit", "sell")]}
    ladder = {"full": False, "next_slot": 2, "next_fraction": 0.25,
              "next_cap": 2500.0}
    plan = {"ok": True, "value_gbp": 500.0, "warnings": []}
    out = with_money_split(rec, ladder, plan)
    labels = [l for l, _t in out["steps"]]
    assert labels == ["Enter", "Money split", "Exit"]
    assert "position #2" in out["steps"][1][1]
    assert "fits comfortably" in out["steps"][1][1]
