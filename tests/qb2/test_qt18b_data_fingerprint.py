"""QT-18 B2: the two data fingerprints -- blind to the recorder's new days, not to a changed bar."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from qb2.data import data_fingerprint as fp
from qb2.research import holdout, p15_history, p19_run


def _bars(days: list[str]) -> pd.DataFrame:
    index = pd.DatetimeIndex([pd.Timestamp(f"{d} {h}:30", tz="America/New_York")
                              for d in days for h in (9, 10, 11)])
    close = 100.0 + index.dayofyear.to_numpy() * 0.01 + index.hour.to_numpy() * 0.001
    return pd.DataFrame({"open": close, "high": close, "low": close, "close": close,
                         "volume": 1.0}, index=index)


def _store(root: Path, symbol: str, frame: pd.DataFrame) -> None:
    folder = root / "bars" / "1h" / symbol
    folder.mkdir(parents=True, exist_ok=True)
    for month, part in frame.groupby(frame.index.strftime("%Y-%m")):
        part.to_parquet(folder / f"{month}.parquet")


def _earnings(root: Path, knowable: list[str]) -> None:
    (root / "earnings").mkdir(exist_ok=True)
    pd.DataFrame({"symbol": "AAPL", "earnings_date": "2026-10-29",
                  "knowable_time": knowable}).to_parquet(root / "earnings" / "AAPL.parquet")


DAYS = ["2026-07-09", "2026-07-10", "2026-07-13", "2026-07-14", "2026-10-08", "2026-10-09"]


def _both(root: Path) -> tuple[str, str]:
    return (fp.trial_data(["AAPL"], ["AAPL"], root), fp.holdout_data(["AAPL"], root))


def _setup(root: Path) -> None:
    _store(root, "AAPL", _bars(DAYS))
    _store(root, "GBPUSD=X", _bars(DAYS))
    _earnings(root, ["2026-10-02T17:50:45+00:00"])


def test_the_recorders_new_days_change_neither_fingerprint(tmp_path: Path) -> None:
    _setup(tmp_path)
    before = _both(tmp_path)
    _store(tmp_path, "AAPL", _bars(DAYS + ["2026-10-12", "2026-10-16"]))
    _store(tmp_path, "GBPUSD=X", _bars(DAYS + ["2026-10-16"]))
    _earnings(tmp_path, ["2026-10-02T17:50:45+00:00", "2026-10-19T18:00:00+00:00"])
    assert _both(tmp_path) == before


def test_a_changed_trial_bar_changes_a_and_not_b(tmp_path: Path) -> None:
    _setup(tmp_path)
    a, b = _both(tmp_path)
    frame = _bars(DAYS)
    frame.iloc[1, frame.columns.get_loc("close")] *= 1.0001      # 9 July, unsealed
    _store(tmp_path, "AAPL", frame)
    assert _both(tmp_path)[0] != a and _both(tmp_path)[1] == b


def test_a_changed_holdout_bar_changes_b_and_not_a(tmp_path: Path) -> None:
    _setup(tmp_path)
    a, b = _both(tmp_path)
    frame = _bars(DAYS)
    frame.iloc[-1, frame.columns.get_loc("open")] *= 0.9999      # 9 October, sealed
    _store(tmp_path, "GBPUSD=X", frame)
    assert _both(tmp_path) == (a, _both(tmp_path)[1]) and _both(tmp_path)[1] != b


def test_a_changed_earnings_row_before_the_cutoff_changes_a(tmp_path: Path) -> None:
    _setup(tmp_path)
    a, _ = _both(tmp_path)
    _earnings(tmp_path, ["2026-10-02T17:50:46+00:00"])
    assert _both(tmp_path)[0] != a


def test_the_fingerprint_dates_are_the_seal_and_the_cutoff() -> None:
    assert fp.SEALED_FROM == holdout.SEALED_FROM["1h"]
    assert fp.HOLDOUT_END == p19_run.HOLDOUT_END
    assert fp.EARNINGS_CUTOFF == p15_history.CUTOFF
