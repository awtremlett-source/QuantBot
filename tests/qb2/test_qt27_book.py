"""QT-27 D2: batch 2's book -- the trade rule, the stop, the target, the graded window, the register."""

from __future__ import annotations

import copy
from dataclasses import replace
from datetime import date

import numpy as np
import pandas as pd
import pytest

from qb2.research import cm_book, cm_run, fills, preregister, walk_forward
from qb2.research.names import NameData
from tests.qb2 import qt27_synth as synth

DAY = date(2024, 3, 6)


def _preds(rows: list[tuple[str, str, float]], day: date = DAY) -> pd.DataFrame:
    return pd.DataFrame([{"symbol": s, "market": m, "day": day, "prediction": p} for s, m, p in rows])


def test_a_bet_qualifies_only_above_twice_its_own_cost() -> None:
    cost = {"A.L": 0.002, "B.L": 0.002, "C.L": 0.007}
    chosen = cm_book.choose(_preds([("A.L", "LSE", 0.004), ("B.L", "LSE", 0.0041), ("C.L", "LSE", 0.0139)]),
                            cost, groups={})
    assert chosen == {("B.L", DAY)}


def test_the_top_three_by_prediction_minus_cost_ties_by_bet_name() -> None:
    cost = {s: 0.002 for s in "ABCDE"}
    rows = [("A", "LSE", 0.010), ("B", "LSE", 0.020), ("C", "LSE", 0.010), ("D", "LSE", 0.030), ("E", "LSE", 0.009)]
    assert cm_book.choose(_preds(rows), cost, groups={}) == {("D", DAY), ("B", DAY), ("A", DAY)}


def test_a_bet_group_is_one_bet_its_lines_averaged_and_all_bought() -> None:
    cost = {"GOOG": 0.004, "GOOGL": 0.004, "AAPL": 0.004}
    groups = {"GOOG": "GOOGLE", "GOOGL": "GOOGLE"}
    weak = _preds([("GOOG", "US", 0.012), ("GOOGL", "US", 0.002), ("AAPL", "US", 0.009)])
    assert cm_book.choose(weak, cost, groups=groups) == {("AAPL", DAY)}            # mean 0.007 < 0.008
    strong = _preds([("GOOG", "US", 0.012), ("GOOGL", "US", 0.006), ("AAPL", "US", 0.009)])
    assert cm_book.choose(strong, cost, groups=groups) == {("AAPL", DAY), ("GOOG", DAY), ("GOOGL", DAY)}


def test_each_market_is_ranked_on_its_own_at_its_own_bar_1() -> None:
    cost = {s: 0.001 for s in ["L1", "L2", "L3", "L4", "U1", "U2", "U3", "U4"]}
    rows = [(f"L{i}", "LSE", 0.01 * i) for i in range(1, 5)] + [(f"U{i}", "US", 0.001 * (i + 2)) for i in range(1, 5)]
    chosen = cm_book.choose(_preds(rows), cost, groups={})
    assert chosen == {(s, DAY) for s in ["L2", "L3", "L4", "U2", "U3", "U4"]}


def _crafted(may_enter_at_bar1: bool = True) -> tuple[NameData, int, date]:
    """25 flat sessions (ATR = 1.0 exactly), then a day that jumps to 110, eases to 106 (above the
    raised stop, below where a lowered one would sit) and falls to 103."""
    frame = synth.bars("LSE", "2024-01-02", 26, seed=0)
    frame[["open", "close"]], frame["high"], frame["low"], frame["volume"] = 100.0, 100.5, 99.5, 1000.0
    days = frame.index.date
    day = days[-1]
    s0 = int(np.flatnonzero(days == day)[0])
    f = s0 + 2
    frame.iloc[f, :4] = [100.0, 110.5, 99.5, 110.0]
    frame.iloc[f + 1, :4] = [110.0, 110.0, 105.5, 106.0]
    frame.iloc[f + 2, :4] = [106.0, 106.0, 102.5, 103.0]
    frame.iloc[f + 3:, :4] = [103.0, 103.5, 102.5, 103.0]
    may = np.ones(len(frame), dtype=bool)
    may[s0] = may_enter_at_bar1
    return synth.name("X.L", "LSE", frame, 0, may_enter=may), s0, day


def test_the_stop_is_raised_never_lowered_and_crossed_on_a_close() -> None:
    name, s0, day = _crafted()
    w = cm_book.maker("CM-L-LON", {("X.L", day)})(name).weights(name.bars).to_numpy()
    f = s0 + 2
    assert w[s0] == 1.0 and w[f] == 1.0          # 110: level raised to 110 - 3 x ATR (about 104.9)
    assert w[f + 1] == 1.0                       # 106: above it (a lowered stop would drop to about 100.3)
    assert w[f + 2] == 0.0                       # 103 <= the raised level: stopped (a lowered one would not be)
    held = fills.positions(name.plan, w)
    assert held[f] == 1.0 and held[f + 3] == 1.0 and held[f + 4] == 0.0   # sold two bars after the stop's close


def test_p15_refusal_buys_nothing_that_day_and_nothing_replaces_it() -> None:
    name, s0, day = _crafted(may_enter_at_bar1=False)
    w = cm_book.maker("CM-L-LON", {("X.L", day)})(name).weights(name.bars).to_numpy()
    assert not fills.positions(name.plan, w)[s0:].any()


def test_the_target_is_batch_1s_own_trade_arithmetic_and_ignores_p15() -> None:
    name, s0, day = _crafted(may_enter_at_bar1=False)
    out = cm_book.targets("CM-L-LON", name, {day})
    opens = name.bars["open"].to_numpy()
    assert out == {day: pytest.approx(opens[s0 + 6] / opens[s0 + 2] - 1)}    # fill bar 3, sold at bar 7's open
    k = np.arange(len(name.bars)) - s0
    up = np.where(k >= 0, 100.0 + k, 100.0)                                  # rising all day: never stopped
    rising = replace(name, bars=name.bars.assign(open=up, close=up, high=up + 0.5, low=up - 0.5))
    e = s0 + 8                                                               # London E = the 16:00 bar
    assert cm_book.targets("CM-L-LON", rising, {day})[day] == pytest.approx(up[e] / up[s0 + 2] - 1)


def test_entry_possible_comes_from_the_calendar() -> None:
    assert cm_book.entry_possible(DAY, "LSE") and cm_book.entry_possible(DAY, "US")
    assert cm_book.entry_possible(date(2024, 12, 24), "LSE")                 # half day: 12:30 close
    assert cm_book.entry_possible(date(2024, 11, 29), "US")                  # half day: 13:00 close


def test_the_graded_window_starts_on_the_first_out_of_sample_bar() -> None:
    name = synth.london_arm(1, sessions=200)[0]
    first = date(2024, 6, 3)
    cut = cm_book.graded(name, first)
    train, test = walk_forward.default_sizes("1h", "LSE")
    windows = walk_forward.folds(len(cut.bars), train, test)
    assert cut.bars.index[windows[0].test_lo].date() == first
    assert cut.bars.index[windows[0].test_lo - 1].date() < first
    start = len(name.bars) - len(cut.bars)
    assert name.plan.may_enter is not None
    rebuilt = fills.schedule(cut.bars.index, "1h", "LSE", may_enter=name.plan.may_enter[start:])
    for field in ("n", "fills", "usable", "session_first", "forced_flat", "may_enter"):
        assert np.array_equal(getattr(cut.plan, field), getattr(rebuilt, field)), field
    short = cm_book.graded(name, date(2023, 12, 1))                           # too little before: unchanged
    assert short is name


def test_unregistered_ids_and_drills_are_refused_as_trials() -> None:
    assert cm_run.require_trial("CM-L-US").id == "CM-L-US"
    with pytest.raises(preregister.NotRegistered):
        cm_run.require_trial("CM-Q-US")
    with pytest.raises(preregister.NotRegistered):
        cm_run.require_trial("KN-CM-NULL")


def test_an_entry_unlike_what_the_code_implements_is_refused() -> None:
    entry = preregister.entries()["CM-G-US"]
    assert cm_run.check_entry(entry) == "gbt" and cm_run.check_entry(preregister.entries()["CM-L-MIX"]) == "ridge"
    for path, value in ((("model_settings", "HistGradientBoostingRegressor", "max_iter"), 300),
                        (("walk_forward", "refit_every_sessions"), 10), (("top",), 4), (("stop_k",), 2.0)):
        bad = copy.deepcopy(entry)
        node = bad["parameters"]
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
        with pytest.raises(ValueError):
            cm_run.check_entry(bad)
    short = copy.deepcopy(entry)
    short["parameters"]["features"] = short["parameters"]["features"][:16]
    with pytest.raises(ValueError):
        cm_run.check_entry(short)
