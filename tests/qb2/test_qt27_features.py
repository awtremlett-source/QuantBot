"""QT-27 D2: the 17 features are what the register says, and none reads the future.

The look-ahead test: for 50 random (name, day) pairs, every bar that ends after that day's
decision moment (bar 1's close) is deleted -- every name's, and ^VIX's -- and the arm is built
and predicted again. The row's features AND its prediction must be byte-identical. A planted
leak (a feature that is the target) must turn the same check RED.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from qb2.model import features
from qb2.research import cm_arm
from qb2.research.names import NameData
from qb2.signals import indicators
from tests.qb2 import qt27_synth as synth


def _arm(names: list[NameData], vix: pd.DataFrame) -> cm_arm.Arm:
    return cm_arm.assemble("CM-L-LON", names, vix, oos_from=date(2024, 2, 1))


def _mismatches(full: cm_arm.Arm, names: list[NameData], vix: pd.DataFrame,
                pairs: list[tuple[str, date]]) -> list[str]:
    preds, _ = cm_arm.predictions(full, "ridge")
    bad = []
    for symbol, day in pairs:
        row = full.rows[(full.rows["symbol"] == symbol) & (full.rows["day"] == day)].iloc[0]
        bar1 = next(d for d in names if d.symbol == symbol).bars.index[int(row["s0"])]
        moment = pd.Timestamp(bar1).tz_convert("UTC") + pd.Timedelta(hours=1)
        cut = _arm(synth.cut(names, moment), synth.cut([synth.name("^VIX", "US", vix, 0)], moment)[0].bars)
        again = cut.rows[(cut.rows["symbol"] == symbol) & (cut.rows["day"] == day)]
        cols = list(features.FEATURES)
        if again.empty or again[cols].to_numpy(float).tobytes() != row[cols].to_numpy(float).tobytes():
            bad.append(f"{symbol} {day}: features moved")
            continue
        p_cut, _ = cm_arm.predictions(cut, "ridge")
        if p_cut.loc[again.index[0]] != preds.loc[row.name]:
            bad.append(f"{symbol} {day}: prediction moved")
    return bad


World = tuple[list[NameData], pd.DataFrame, cm_arm.Arm, list[tuple[str, date]]]


@pytest.fixture(scope="module")
def world() -> World:
    names, vix = synth.london_arm(), synth.vix()
    full = _arm(names, vix)
    preds, _ = cm_arm.predictions(full, "ridge")
    oos = full.rows.loc[preds.dropna().index]
    pick = np.random.default_rng(7).choice(len(oos), size=50, replace=False)
    return names, vix, full, [(oos.iloc[i]["symbol"], oos.iloc[i]["day"]) for i in sorted(pick)]


def test_cutting_the_future_leaves_features_and_prediction_byte_identical(world: World) -> None:
    names, vix, full, pairs = world
    assert len(pairs) == 50
    assert _mismatches(full, names, vix, pairs) == []


def test_a_planted_leak_feature_equal_to_the_target_goes_red(world: World,
                                                             monkeypatch: pytest.MonkeyPatch) -> None:
    names, vix, _, pairs = world
    real = cm_arm.with_targets

    def leaky(rows: pd.DataFrame, data: list[NameData], cid: str) -> pd.DataFrame:
        out = real(rows, data, cid)
        return out.assign(F1=out["target"].fillna(0.0))   # the planted leak: a feature = the target
    monkeypatch.setattr(cm_arm, "with_targets", leaky)
    leaked = _arm(names, vix)
    assert _mismatches(leaked, names, vix, pairs[:10]) != []


def test_each_feature_is_the_registered_formula_on_one_row() -> None:
    frame = synth.bars("LSE", "2023-11-01", 60, seed=3)
    vix = synth.vix(sessions=80)
    rows = features.name_rows("SYN3.L", "LSE", frame, features.vix_closes(vix))
    r = rows.iloc[-1]
    days = pd.DatetimeIndex(frame.index).date
    closes = frame.groupby(days)["close"].last()
    first = frame[days == r["day"]].iloc[0]
    p = closes[closes.index < r["day"]]
    assert r["F1"] == first["close"] / first["open"] - 1
    assert r["F2"] == first["open"] / p.iloc[-1] - 1
    assert r["F3"] == p.iloc[-1] / p.iloc[-2] - 1
    assert r["F4"] == p.iloc[-1] / p.iloc[-6] - 1
    assert r["F5"] == p.iloc[-1] / p.iloc[-21] - 1
    assert r["F16"] == r["day"].weekday()
    assert r["F15"] == features.vix_before(r["day"], features.vix_closes(vix))
    s0 = int(r["s0"])
    atr = indicators.atr_wilder(frame, 14).to_numpy()
    assert r["F6"] == (first["high"] - first["low"]) / atr[s0 - 1]
    bar1 = frame[frame.index.hour == 8]["volume"]
    assert r["F7"] == first["volume"] / bar1[bar1.index.date < r["day"]].iloc[-20:].mean()
    for col, n in (("F8", 9), ("F9", 21), ("F10", 50)):
        assert r[col] == first["close"] / indicators.ema(frame["close"], n).iloc[s0] - 1
    lower, _, upper = indicators.keltner(frame)
    assert r["F11"] == (first["close"] - lower.iloc[s0]) / (upper.iloc[s0] - lower.iloc[s0])


def test_bar_1_must_start_at_the_open_and_vix_is_never_todays() -> None:
    frame = synth.bars("LSE", "2024-03-01", 40, seed=4)
    late = frame.drop(frame.index[(frame.index.date == date(2024, 3, 20)) & (frame.index.hour == 8)])
    rows = features.name_rows("X.L", "LSE", late, pd.Series(dtype=float))
    assert date(2024, 3, 20) not in set(rows["day"]) and date(2024, 3, 21) in set(rows["day"])
    closes = pd.Series({date(2024, 3, 27): 13.0, date(2024, 3, 28): 14.0, date(2024, 4, 1): 15.0})
    assert features.vix_before(date(2024, 3, 28), closes) == 13.0          # never the same date
    assert features.vix_before(date(2024, 4, 2), closes) == 15.0
    assert np.isnan(features.vix_before(date(2024, 4, 12), closes))          # more than 5 weekdays back


def test_turn_of_month_and_the_cross_section() -> None:
    flags = features.turn_of_month([date(2024, 3, 1), date(2024, 3, 6), date(2024, 3, 28)], "LSE")
    assert flags == {date(2024, 3, 1): 1, date(2024, 3, 6): 0, date(2024, 3, 28): 1}  # 29th: Good Friday
    rows = pd.DataFrame({"symbol": list("abcd"), "market": ["LSE"] * 3 + ["US"], "day": [date(2024, 3, 6)] * 4,
                         "F1": [0.01, -0.02, 0.01, 0.5], "F2": [0.0, 0.1, np.nan, 0.2]})
    out = features.cross_section(rows)
    assert out["F12"].tolist() == [2.5 / 3, 1 / 3, 2.5 / 3, 1.0]           # ties averaged; US apart
    assert out["F13"].tolist()[:2] == [0.5, 1.0] and np.isnan(out["F13"].iloc[2])
    assert out["F14"].iloc[0] == pytest.approx(0.0 / 3) and out["F14"].iloc[3] == 0.5
    kept, dropped = features.complete(out.assign(**{f: 0.0 for f in features.FEATURES if f not in out}))
    assert dropped == 1 and len(kept) == 3
