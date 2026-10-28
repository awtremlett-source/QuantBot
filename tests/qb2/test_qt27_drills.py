"""QT-27 E: the drills plant, shuffle and judge exactly as registered (KN-CM-NULL/EDGE/BELOW)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from qb2.model import features
from qb2.research import cm_book, cm_drills, verdict
from qb2.signals import s6_rules
from tests.qb2 import qt27_synth as synth


def test_the_plant_moves_prices_from_the_fill_bar_on_planted_sessions_only() -> None:
    name = synth.london_arm(1, sessions=40)[0]
    out = cm_drills.plant(name, 0.05)
    a, b = name.bars, out.bars
    spans = s6_rules.sessions(pd.DatetimeIndex(a.index), "LSE")
    planted = [s for s in spans if cm_drills.fp(name.bet, s[2]) > 0]
    assert 0 < len(planted) < len(spans)
    for s0, s1, day in spans:
        f = s0 + 2
        if cm_drills.fp(name.bet, day) > 0:
            assert b["open"].iloc[f] == a["open"].iloc[f]                         # the entry price stays
            assert np.allclose(b["close"].iloc[f:s1], a["close"].iloc[f:s1] * 1.05)
            assert np.allclose(b["open"].iloc[f + 1:s1], a["open"].iloc[f + 1:s1] * 1.05)
            assert b.iloc[s0:f].equals(a.iloc[s0:f])
        else:
            assert b.iloc[s0:s1].equals(a.iloc[s0:s1])
    assert (b["high"] >= b[["open", "close"]].max(axis=1)).all() and (b["low"] <= b[["open", "close"]].min(axis=1)).all()


def test_on_a_path_the_stop_never_touches_the_target_gains_exactly_x() -> None:
    name = synth.london_arm(1, sessions=40)[0]
    k = np.arange(len(name.bars), dtype=float)
    up = 100.0 * 1.0005 ** k                                                       # rises every bar
    rising = replace(name, bars=name.bars.assign(open=up, close=up * 1.0002, high=up * 1.001, low=up * 0.999))
    days = {d for _, _, d in s6_rules.sessions(pd.DatetimeIndex(name.bars.index), "LSE")}
    before = cm_book.targets("KN-CM-EDGE", rising, days)
    after = cm_book.targets("KN-CM-EDGE", cm_drills.plant(rising, 0.03), days)
    assert set(before) == set(after) and before
    for d, t in before.items():
        want = (1 + t) * 1.03 - 1 if cm_drills.fp(name.bet, d) > 0 else t
        assert after[d] == pytest.approx(want, rel=1e-12, abs=1e-12)


def test_the_null_shuffle_moves_features_within_a_session_and_keeps_each_names_outcome() -> None:
    rng = np.random.default_rng(1)
    rows = pd.DataFrame({"symbol": list("abcdef") * 2, "day": [pd.Timestamp("2024-03-06").date()] * 6
                         + [pd.Timestamp("2024-03-07").date()] * 6, "target": rng.normal(size=12)})
    for f in features.FEATURES:
        rows[f] = rng.normal(size=12)
    out = cm_drills.shuffle(rows)
    assert out[["symbol", "day", "target"]].equals(rows[["symbol", "day", "target"]])
    cols = list(features.FEATURES)
    for day in set(rows["day"]):
        x, y = rows[rows["day"] == day][cols].to_numpy(), out[out["day"] == day][cols].to_numpy()
        assert sorted(map(tuple, x)) == sorted(map(tuple, y)) and not np.array_equal(x, y)
    assert out.equals(cm_drills.shuffle(rows))                                     # seeded: the same every run


def test_both_lines_of_a_bet_share_their_planted_feature() -> None:
    a, b = synth.london_arm(2, sessions=30)
    b = replace(b, bet=a.bet)
    rows = pd.DataFrame({"symbol": [a.symbol, b.symbol], "day": [pd.Timestamp("2024-01-10").date()] * 2})
    out = cm_drills.with_fp([a, b])(rows)
    assert out[cm_drills.FP].iloc[0] == out[cm_drills.FP].iloc[1]
    assert cm_drills.columns("KN-CM-EDGE")[-1] == cm_drills.FP and cm_drills.FP not in cm_drills.columns("KN-CM-NULL")


def _result(outcome: str, p: float | None, mean: float) -> SimpleNamespace:
    marked = pd.Series([mean] * 40, index=pd.date_range("2024-06-03", periods=40, freq="h", tz="UTC"))
    return SimpleNamespace(observed=SimpleNamespace(marked=marked, trades=40),
                           verdict=verdict.Verdict(outcome), p_value=p, deflated={}, benchmark=None,
                           start=None, end=None)


def test_the_gates_are_the_registered_ones() -> None:
    def green(drill: str, outcome: str, p: float | None, mean: float) -> bool:
        return bool(cm_drills.figures(drill, "ridge", 1.0, _result(outcome, p, mean), {})["green"])  # type: ignore[arg-type]
    assert green("KN-CM-NULL", verdict.FAIL, 0.40, 0.001) and green("KN-CM-NULL", verdict.INSUFFICIENT, None, 0.0)
    assert not green("KN-CM-NULL", verdict.FAIL, 0.03, -0.001)                     # luck passed: red
    assert not green("KN-CM-NULL", verdict.PASS, 0.01, 0.001)
    assert green("KN-CM-EDGE", verdict.PASS, 0.005, 0.001) and not green("KN-CM-EDGE", verdict.FAIL, 0.005, 0.001)
    assert green("KN-CM-BELOW", verdict.FAIL, 0.01, -0.0001) and green("KN-CM-BELOW", verdict.INSUFFICIENT, None, 0.001)
    assert not green("KN-CM-BELOW", verdict.FAIL, 0.01, 0.0001)                    # made money: costs did not reject it


def test_the_page_names_each_gate_and_each_red_first(tmp_path: Path) -> None:
    run = {"drill": "KN-CM-NULL", "model": "gbt", "stress": 1.0, "verdict": "FAIL", "failed": ["luck"],
           "p": 0.4, "trades": 120, "mean_per_bar": -0.0001, "net": -0.05, "vwrp": 0.4, "green": True}
    edge = {**run, "drill": "KN-CM-EDGE", "verdict": "FAIL", "failed": ["benchmark"], "green": False}
    leak = {**run, "verdict": "FAIL", "failed": ["benchmark"], "p": 0.005, "mean_per_bar": 0.0002, "red": True}
    text = (tmp_path / "page.md")
    cm_drills.write_page({"honest": [run, edge], "red_first": {"fold_boundary_leaked": [leak]},
                          "seen": {"fold_boundary_leaked": True}}, target=text)
    page = text.read_text(encoding="utf-8")
    assert "Gate 1 GREEN · Gate 2 RED" in page and "fold_boundary_leaked: **RED** ✓" in page
    assert "Seen: fold_boundary_leaked YES" in page
