"""QT-22: advisor batch 2 = batch 1's six with the P10 stop widened to a big-fall stop
(15% below the highest price since the fill, 10% when unsettled -- S5's crash-test figures)."""

from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from qb2.research import (advisor_book, advisor_drills, advisor_results, advisor_run, preregister,
                          rank_null)
from tests.qb2.test_qt19b_advisor import DAYS, S, _book, _flat, _month_end, _ranked
from tests.qb2.test_qt19b_run import FakeResult, _fake

BIG = replace(S, stop_fall=0.15, stop_fall_unsettled=0.10)
CALM, LOUD = pd.Series(15.0, index=DAYS), pd.Series(35.0, index=DAYS)
NAMES = [f"N{j}" for j in range(10)]
STOP_KEYS = {"stop_k", "stop_k_unsettled", "atr_period"}
FALL_KEYS = {"stop", "stop_fall", "stop_fall_unsettled"}
PAIRS = [(f"A-0{j}", f"A2-0{j}") for j in range(1, 7)] + [
    (f"KN-A-{d}-1d", f"KN-A2-{d}-1d") for d in ("RANDOM", "GAP", "PLANT-v2")]


# ---------------------------------------------------------------- the register

def test_batch_two_is_batch_one_but_the_stop_and_the_count() -> None:
    reg = preregister.entries()
    for old, new in PAIRS:
        a, b = reg[old], reg[new]
        preregister.require(new)                                     # committed, unchanged
        same = set(a) - {"id", "name", "date", "source", "exit_rule", "book", "parameters", "judged"}
        assert {k: a[k] for k in same} == {k: b[k] for k in same}
        pa, pb = a["parameters"], b["parameters"]
        assert {k: v for k, v in pa.items() if k not in STOP_KEYS} == \
               {k: v for k, v in pb.items() if k not in FALL_KEYS}
        assert (pb["stop"], pb["stop_fall"], pb["stop_fall_unsettled"]) == ("big-fall", 0.15, 0.10)
        assert "brake_replay_2026-10.md" in b["book"] and "GO on QT-22" in b["book"]
        if "judged" in a:
            assert b["judged"] == a["judged"].replace("N = 48 (42 + these 6)", "N = 54 (48 + these 6)")


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(preregister.REPO_ROOT), *args], capture_output=True,
                          text=True, check=True).stdout.strip()


def test_batch_two_was_registered_alone_before_the_stop_code() -> None:
    registered = _git("log", "--format=%H", "--reverse", '-S"A2-01"', "--",
                      preregister.REGISTER_REL).split()[0]
    assert _git("show", "--name-only", "--format=", registered) == preregister.REGISTER_REL
    for commit in _git("log", "--format=%H", "-Sstop_fall", "--",
                       "qb2/research/advisor_book.py").split():   # empty until it is committed
        assert commit != registered
        assert subprocess.run(["git", "-C", str(preregister.REPO_ROOT), "merge-base",
                               "--is-ancestor", registered, commit]).returncode == 0


def test_settings_read_the_stop_the_entry_registered() -> None:
    reg = preregister.entries()
    two = advisor_book.Settings.of(reg["A2-01"]["parameters"], 252, False)
    one = advisor_book.Settings.of(reg["A-01"]["parameters"], 252, False)
    assert (two.stop_fall, two.stop_fall_unsettled) == (0.15, 0.10)
    assert (one.stop_fall, one.stop_k, one.stop_k_unsettled) == (None, 3.0, 2.0)
    both = {**reg["A2-01"]["parameters"], "stop_k": 3.0}
    with pytest.raises(ValueError, match="one stop"):
        advisor_book.Settings.of(both, 252, False)
    neither = {k: v for k, v in reg["A-01"]["parameters"].items() if k != "stop_k"}
    with pytest.raises(ValueError, match="one stop"):
        advisor_book.Settings.of(neither, 252, False)


def test_the_luck_bar_books_carry_the_same_stop() -> None:
    nulls = rank_null.Nulls(preregister.entries()["A2-03"], [], vix=None, cuts=[])
    assert (nulls.settings.stop_fall, nulls.settings.stop_fall_unsettled) == (0.15, 0.10)


# ---------------------------------------------------------------- the stop in the book

def _dip(fall: float) -> tuple[np.ndarray, int]:
    close, jan = _flat(), _month_end(2015, 1)
    close[jan + 5] = close[jan + 4] * (1 - fall)                    # one close, then back
    return close, jan + 5


def test_big_fall_stop_holds_a_fourteen_percent_dip_and_sells_sixteen() -> None:
    close, t = _dip(0.14)
    held, _ = _book(_ranked(NAMES), {"N0": close}, s=BIG, vix=CALM)
    assert held.decisions["N0"][t] == 1.0                           # 3 x ATR would have sold it
    close, t = _dip(0.16)
    sold, _ = _book(_ranked(NAMES), {"N0": close}, s=BIG, vix=CALM)
    assert sold.decisions["N0"][t] == 0.0 and sold.stops[0] == ("N0", t)


def test_unsettled_tightens_the_big_fall_stop_to_ten_percent() -> None:
    close, t = _dip(0.12)
    calm, _ = _book(_ranked(NAMES), {"N0": close}, s=BIG, vix=CALM)
    loud, _ = _book(_ranked(NAMES), {"N0": close}, s=BIG, vix=LOUD)
    assert calm.decisions["N0"][t] == 1.0 and loud.decisions["N0"][t] == 0.0


def test_the_level_trails_the_peak_and_is_never_lowered() -> None:
    close, jan = _flat(), _month_end(2015, 1)
    peak = close[jan + 1] * 1.2
    close[jan + 2:jan + 6] = peak
    close[jan + 6] = peak * 0.88                                    # -12% from the peak: held
    close[jan + 7:jan + 9] = peak * 0.92
    close[jan + 9] = peak * 0.84                                    # -16% from the peak, -9% from 0.92
    book, _ = _book(_ranked(NAMES), {"N0": close}, s=BIG, vix=CALM)
    assert book.decisions["N0"][jan + 8] == 1.0 and book.decisions["N0"][jan + 9] == 0.0


def test_the_one_percent_ceiling_uses_the_fifteen_percent_distance() -> None:
    rng = np.random.default_rng(5)
    wild = 100 * np.cumprod(1 + rng.normal(0, 0.25, len(DAYS)))      # ATR huge: irrelevant here
    book, _ = _book(_ranked(NAMES), {"N0": wild}, s=BIG, vix=CALM)
    cap = 0.01 / 0.7 / 0.15                                         # k = 2: the slot 0.5 is capped
    w = book.weights["N0"].iloc[30:].to_numpy()
    assert w == pytest.approx(np.full(len(w), cap)) and book.capped["N0"][30:].all()


# ---------------------------------------------------------------- the runner and the drills

def test_batch_two_runs_its_own_six_at_n_fifty_four(monkeypatch: pytest.MonkeyPatch,
                                                     tmp_path: Path) -> None:
    prefix, n, _ = advisor_run.BATCHES[2]
    assert [e["id"] for e in advisor_run.trials(prefix=prefix)] == [b for _, b in PAIRS[:6]]
    assert [e["id"] for e in advisor_run.trials()] == [a for a, _ in PAIRS[:6]]   # batch 1 as was
    assert (n, advisor_run.BATCHES[1][1]) == (54, 48)
    assert advisor_run.where(1) == (advisor_run.RUN_DIR, advisor_run.PAGE)
    assert advisor_run.where(2)[0].name == "A_batch2_runs" and advisor_run.where(2)[0].parent == \
        advisor_run.RUN_DIR.parent
    _fake(monkeypatch, tmp_path, [{"a": "A", "b": "B"}])
    seen: list[tuple[str, int]] = []

    def score(token: Any, *a: Any, **kw: Any) -> Any:
        seen.append((token.id, kw["n_trials"]))
        return FakeResult("FAIL")
    monkeypatch.setattr(advisor_run, "score", score)
    advisor_run.run(run_dir=tmp_path, say=lambda s: None, batch=2)
    assert seen == [("A-01", 54), ("A-02", 54)]                    # the fake's two entries, N 54


def test_the_page_loads_batch_two_results_and_skips_holdout_files(tmp_path: Path) -> None:
    for cid in ("A2-01", "A2-02", "A-01"):
        (tmp_path / f"{cid}.json").write_text(json.dumps({"id": cid}), encoding="utf-8")
    (tmp_path / "A2-01.holdout.json").write_text("{}", encoding="utf-8")
    got = advisor_results.load(tmp_path, ["A2-01", "A2-02"])
    assert [r["id"] for r in got] == ["A2-01", "A2-02"]


def test_batch_two_drills_are_the_three_new_entries_gated_the_same_way() -> None:
    honest, red = advisor_drills.DRILLS[2]
    assert [(g, d, s) for g, d, s in honest] == [
        ("gate1", "KN-A2-RANDOM-1d", 1.0), ("gate1", "KN-A2-GAP-1d", 1.0),
        ("gate2", "KN-A2-PLANT-v2-1d", 1.0), ("gate2", "KN-A2-PLANT-v2-1d", 2.0)]
    assert [(d, b, w) for _, d, _, b, w in red] == [
        ("KN-A2-GAP-1d", "same_bar_fill", "PASS"), ("KN-A2-PLANT-v2-1d", "no_slot_weights", "FAIL")]
    assert advisor_drills.DRILLS[1] == (advisor_drills.HONEST, advisor_drills.RED_FIRST)
