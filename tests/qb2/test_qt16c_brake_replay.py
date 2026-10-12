"""QT-16 C1: the brake replay's arithmetic, on hand-made paths. Offline."""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from qb2.research import brake_replay as br


def _path(start: str, values: list[float]) -> pd.Series:
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)))


def test_a_dip_that_regains_its_peak_first_is_a_false_alarm() -> None:
    eps = br.replay(_path("2015-03-02", [100, 105, 94, 100, 102, 106]))
    assert [(e.level, e.start, e.end, e.false_alarm) for e in eps] == \
        [("10%", date(2015, 3, 4), date(2015, 3, 5), True)]      # 100/105: within 5%
    assert eps[0].missed == pytest.approx(100 / 94 - 1)


def test_a_dip_that_falls_a_further_five_percent_first_is_not() -> None:
    eps = br.replay(_path("2016-03-01", [100, 89, 84, 90, 101]))
    assert [(e.level, e.false_alarm) for e in eps] == [("10%", False), ("15%", None)]
    assert all(e.end == date(2016, 3, 7) for e in eps)


def test_inside_a_crisis_window_it_counts_as_firing_not_as_an_alarm() -> None:
    eps = br.replay(_path("2020-02-20", [100, 95, 88, 80, 70, 75]))
    assert {e.level for e in eps} == {"10%", "15%"} and {e.window for e in eps} == {"2020"}
    assert all(e.false_alarm is None and e.end is None for e in eps)
    found = {"x": eps}
    assert br.on_in(eps, "15%", "2020") and not br.on_in(eps, "10%", "2008")
    assert br.required_misses(found) == ["10% never on in 2008",       # never cleared,
                                         "15% never on in 2008"]       # so on in 2022 too


def test_us_paths_are_put_in_pounds_by_date() -> None:
    usd = _path("2020-03-02", [100.0, 110.0])
    fx = _path("2020-03-02", [1.25, 1.10])
    gbp, dropped = br.in_pounds(usd, fx)
    assert list(gbp.round(4)) == [80.0, 100.0] and dropped == 0


def test_the_stored_paths_are_refused_if_a_file_changed(tmp_path: Path) -> None:
    def fake(symbol: str) -> pd.Series:
        return _path("2010-01-04", [1.0, 2.0, 3.0])
    manifest = br.store(fake, folder=tmp_path)
    assert set(manifest) == {*br.PATHS, br.FX}
    first = tmp_path / manifest["^GSPC"]["file"]
    assert hashlib.sha256(first.read_bytes()).hexdigest() == manifest["^GSPC"]["sha256"]
    paths, _ = br.load(tmp_path)
    assert list(paths["URTH"]) == [1.0, 2.0, 3.0]
    first.write_text("date,close\n2010-01-04,9\n", encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        br.load(tmp_path)


# ------------------------------------------------- C2: the stop description --

def test_the_stop_description_walks_a_trailing_three_atr_stop_by_hand() -> None:
    from qb2.research import stop_description as sd

    days = pd.bdate_range("2024-01-01", periods=120, tz="America/New_York")
    close = [100.0] * 120
    bars = pd.DataFrame({"open": close, "high": [101.0] * 120, "low": [99.0] * 120,
                         "close": close}, index=days)
    bars.loc[days[40], "low"] = 90.0                       # ATR = 2: stop at 94, hit
    out = sd.walk(bars, "X")
    first = out[0]                                         # entry at bar 14
    assert first.stopped and first.days == 26 and first.distance == pytest.approx(0.06, 0.05)
    assert first.after == pytest.approx(100.0 / first_level(bars) - 1.0, 0.02)
    summary = sd.summary(out)
    assert 0 < summary["stopped"] <= 1 and summary["entries"] == len(out)


def first_level(bars: pd.DataFrame) -> float:
    from qb2.signals.indicators import atr_wilder

    atr = atr_wilder(bars, 14)
    return float(max(bars["close"].iloc[k] - 3 * atr.iloc[k] for k in range(14, 40)))
