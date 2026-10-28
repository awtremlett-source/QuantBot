"""QT-28 C: drills v2 judge by the firewall's own verdict (register 787d4a27: KN-CM-*-v2); v1 unchanged."""

from __future__ import annotations

from typing import Any

import pytest

from qb2.execution import costs
from qb2.research import cm_drills, preregister, simulate, verdict
from tests.qb2 import qt27_synth as synth
from tests.qb2.test_qt27_drills import _result

INS, FAIL, PASS = verdict.INSUFFICIENT, verdict.FAIL, verdict.PASS
# QT-27 E1's twelve honest runs as recorded (docs/research/known_null_2026-10-28_QT27_cm.json):
# drill, model, stress, verdict, luck p, net mean per bar, v1's gate
QT27 = [("KN-CM-NULL", "ridge", 1.0, INS, None, 1.33e-07, True), ("KN-CM-NULL", "ridge", 2.0, INS, None, -9.5e-09, True),
        ("KN-CM-NULL", "gbt", 1.0, INS, 0.0199, -1.67e-06, False), ("KN-CM-NULL", "gbt", 2.0, INS, 0.0050, -4.6e-06, False),
        ("KN-CM-EDGE", "ridge", 1.0, PASS, 0.0050, 1.97e-04, True), ("KN-CM-EDGE", "ridge", 2.0, PASS, 0.0050, 1.54e-04, True),
        ("KN-CM-EDGE", "gbt", 1.0, PASS, 0.0050, 2.34e-04, True), ("KN-CM-EDGE", "gbt", 2.0, PASS, 0.0050, 1.85e-04, True),
        ("KN-CM-BELOW", "ridge", 1.0, FAIL, 0.0199, 1.55e-06, False), ("KN-CM-BELOW", "ridge", 2.0, FAIL, 0.0100, 4.4e-08, False),
        ("KN-CM-BELOW", "gbt", 1.0, INS, 0.0398, -2.14e-06, True), ("KN-CM-BELOW", "gbt", 2.0, INS, 0.0149, -7.64e-06, True)]


def _fig(drill: str, model: str, stress: float, outcome: str, p: float | None, mean: float) -> dict[str, Any]:
    return cm_drills.figures(drill, model, stress, _result(outcome, p, mean), {})  # type: ignore[arg-type]


def _four(drill: str, outcome: str, p: float | None, mean: float) -> list[dict[str, Any]]:
    return [_fig(drill, m, s, outcome, p, mean) for m in ("ridge", "gbt") for s in (1.0, 2.0)]


def test_qt27s_null_gbt_case_v1_words_red_the_firewall_and_v2_green() -> None:
    # INSUFFICIENT, luck p 0.020 on a LOSING book (net -0.80%): not PASS, and not Gate 1 (it lost money)
    v1 = _fig("KN-CM-NULL", "gbt", 1.0, INS, 0.0199, -1.67e-06)
    v2 = _fig("KN-CM-NULL-v2", "gbt", 1.0, INS, 0.0199, -1.67e-06)
    assert (v1["green"], v2["green"], v2["luck_and_positive"]) == (False, True, False)


def test_v1_still_returns_qt27s_verdicts_and_v2_greens_the_same_twelve() -> None:
    one = [_fig(d, m, s, o, p, x) for d, m, s, o, p, x, _ in QT27]
    assert [r["green"] for r in one] == [g for *_, g in QT27]
    assert cm_drills.gates(one, cm_drills.DRILLS) == {"KN-CM-NULL": False, "KN-CM-EDGE": True, "KN-CM-BELOW": False}
    two = [_fig(d + "-v2", m, s, o, p, x) for d, m, s, o, p, x, _ in QT27]
    assert cm_drills.gates(two, cm_drills.DRILLS_V2) == dict.fromkeys(cm_drills.DRILLS_V2, True)


def test_each_v2_gate_is_the_verdict_alone_over_all_four_runs() -> None:
    edge, gate = _four("KN-CM-EDGE-v2", PASS, 0.005, 1e-4), cm_drills.gates
    assert gate(edge, ["KN-CM-EDGE-v2"]) == {"KN-CM-EDGE-v2": True}
    assert gate(edge[:3] + [_fig("KN-CM-EDGE-v2", "gbt", 2.0, FAIL, 0.005, 1e-4)], ["KN-CM-EDGE-v2"]) == {"KN-CM-EDGE-v2": False}
    assert gate([r for r in edge if r["stress"] == 1.0], ["KN-CM-EDGE-v2"]) == {"KN-CM-EDGE-v2": False}  # 2x missing
    for drill in ("KN-CM-NULL-v2", "KN-CM-BELOW-v2"):
        lucky = _four(drill, FAIL, 0.01, 1e-5)                 # Gate 1 cleared, still rejected: not PASS
        assert gate(lucky, [drill]) == {drill: True}
        assert gate(lucky[:3] + [_fig(drill, "gbt", 2.0, PASS, 0.01, 1e-5)], [drill]) == {drill: False}
        assert gate(lucky[1:], [drill]) == {drill: False}      # a missing run is never GREEN


def test_a_red_first_is_seen_only_through_the_firewalls_gate_1() -> None:
    leak = [_fig("KN-CM-NULL-v2", "ridge", 1.0, INS, None, 1.09e-06), _fig("KN-CM-NULL-v2", "gbt", 1.0, FAIL, 0.005, 1.41e-05)]
    free = [_fig("KN-CM-BELOW-v2", "ridge", 1.0, FAIL, 0.0995, 1.93e-05), _fig("KN-CM-BELOW-v2", "gbt", 1.0, FAIL, 0.159, 1.82e-05)]
    assert cm_drills.seen({"fold_boundary_leaked": leak, "costs_off": free}) == \
        {"fold_boundary_leaked": True, "costs_off": False}    # QT-27 E3, as seen then
    loser = [_fig("KN-CM-NULL-v2", "gbt", 1.0, FAIL, 0.005, -1e-05)]
    ridge_only = [_fig("KN-CM-NULL-v2", "ridge", 1.0, FAIL, 0.005, 1e-05), loser[0]]
    one_model = [free[1], _fig("KN-CM-BELOW-v2", "ridge", 1.0, FAIL, 0.01, 2e-05)]
    assert cm_drills.seen({"fold_boundary_leaked": loser, "costs_off": one_model}) == \
        {"fold_boundary_leaked": False, "costs_off": True}    # a losing book never clears Gate 1
    assert cm_drills.seen({"fold_boundary_leaked": ridge_only, "costs_off": []})["fold_boundary_leaked"] is False


def test_proven_needs_every_v2_gate_green_and_both_red_firsts_seen() -> None:
    honest = [_fig(d + "-v2", m, s, o, p, x) for d, m, s, o, p, x, _ in QT27]
    both = {"fold_boundary_leaked": True, "costs_off": True}
    assert cm_drills.proven({"honest": honest, "seen": both})
    assert not cm_drills.proven({"honest": honest, "seen": {**both, "costs_off": False}})
    assert not cm_drills.proven({"honest": honest, "seen": {"fold_boundary_leaked": True}})
    assert not cm_drills.proven({"honest": honest[:-1], "seen": both})


def test_below_v2_is_sized_by_the_registered_k_below_the_1x_round_trip() -> None:
    p = preregister.entries()["KN-CM-BELOW-v2"]["parameters"]
    assert p["k"] == 0.9 and p["k_ladder"] == [0.7, 0.8, 0.9] and p["k"] < 1
    for name in synth.london_arm(2, sessions=5):
        trip = costs.round_trip(name.instrument, simulate.STAKE_GBP).fraction
        assert cm_drills.SIZE["KN-CM-BELOW-v2"](name) == pytest.approx(p["k"] * trip, rel=1e-12)
        assert cm_drills.SIZE["KN-CM-BELOW"](name) == pytest.approx(0.5 * trip, rel=1e-12)          # v1 unchanged
        assert cm_drills.SIZE["KN-CM-EDGE-v2"](name) == cm_drills.SIZE["KN-CM-EDGE"](name)


def test_the_front_door_refuses_a_v2_entry_the_code_does_not_implement() -> None:
    reg = preregister.entries()
    for drill in cm_drills.DRILLS_V2:
        cm_drills.check_entry(reg[drill])
    wrong = {**reg["KN-CM-BELOW-v2"], "parameters": {**reg["KN-CM-BELOW-v2"]["parameters"], "k": 0.5}}
    with pytest.raises(ValueError, match="KN-CM-BELOW-v2"):
        cm_drills.check_entry(wrong)
    one_stress = {**reg["KN-CM-NULL-v2"], "parameters": {**reg["KN-CM-NULL-v2"]["parameters"], "stresses": [1.0]}}
    with pytest.raises(ValueError, match="KN-CM-NULL-v2"):
        cm_drills.check_entry(one_stress)


def test_v2_entries_change_only_the_gate_words_and_belows_size() -> None:
    reg = preregister.entries()
    for drill in cm_drills.DRILLS:
        one, two = reg[drill], reg[drill + "-v2"]
        assert (two["kind"], two["rule"]) == ("drill", one["rule"]) and two["gate"] != one["gate"]
        assert all(two[k] == one[k] for k in ("bar_size", "universe", "exit_rule", "side", "holdout"))
        p1, p2 = dict(one["parameters"]), dict(two["parameters"])
        if drill == "KN-CM-BELOW":
            p1.pop("x"), p2.pop("x"), p2.pop("k"), p2.pop("k_ladder")
        assert p1 == p2 and "AFTER v1's drill results were seen" in two["note"] and "STOP rule" in two["note"]
