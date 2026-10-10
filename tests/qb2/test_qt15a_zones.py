"""QT-15 A2: every clean file is stamped on its exchange's own clock. Offline.

QT-14 found US day files stamped Europe/London (right instants, wrong label). The
cause: the hourly recorder asks yfinance for US and London names in ONE batched
request, and the shared index comes back labelled London; the front door copied
the label through. Fixed at the door, re-cleaned through it, and the census goes
RED on a wrong-zone file. Each test was seen RED on the QT-14 code first.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from qb2.data import census, front_door

US_SESSION = pd.date_range("2026-10-08 13:30", periods=78, freq="5min", tz="UTC")


def _bars(index: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0,
                         "volume": 10}, index=index)


def _raw(tmp: Path, symbol: str, zone: str) -> Path:
    folder = tmp / "raw" / "intraday" / "5m" / symbol
    folder.mkdir(parents=True)
    path = folder / "2026-10-08.parquet"
    _bars(US_SESSION.tz_convert(zone)).to_parquet(path)
    return path


def _clean(tmp: Path, symbol: str = "WDC") -> pd.DataFrame:
    return pd.read_parquet(front_door.clean_path("5m", symbol, "2026-10-08", tmp / "clean"))


def test_a_us_file_labelled_london_comes_out_on_new_york_time(tmp_path: Path) -> None:
    _raw(tmp_path, "WDC", "Europe/London")
    front_door.ingest(intervals=("5m",), clean_root=tmp_path / "clean",
                      raw_root=tmp_path / "raw" / "intraday")
    out = _clean(tmp_path)
    assert str(out.index.tz) == "America/New_York"
    assert (out.index == US_SESSION).all()                  # same instants, right label


def test_an_old_wrong_label_is_re_cleaned_through_the_door(tmp_path: Path) -> None:
    raw = _raw(tmp_path, "WDC", "Europe/London")
    kw = dict(intervals=("5m",), clean_root=tmp_path / "clean",
              raw_root=tmp_path / "raw" / "intraday")
    front_door.ingest(**kw)                                 # type: ignore[arg-type]
    target = front_door.clean_path("5m", "WDC", "2026-10-08", tmp_path / "clean")
    stale = _clean(tmp_path)
    stale.index = stale.index.tz_convert("Europe/London")   # the store as QT-14 left it
    stale.to_parquet(target)
    again = front_door.ingest(**kw)                         # type: ignore[arg-type]
    assert again.files_skipped_unchanged == 1               # unchanged raw: no work...
    source = raw.relative_to(tmp_path / "raw").as_posix()
    redone = front_door.ingest(redo=[source], **kw)         # type: ignore[arg-type]
    assert redone.files_written == 1                        # ...until re-cleaned
    assert str(_clean(tmp_path).index.tz) == "America/New_York"
    assert raw.is_file()                                    # raw never edited


def _store(tmp: Path, zone: str) -> Path:
    root = tmp / "clean"
    path = front_door.clean_path("5m", "AAPL", "2026-10-08", root)
    path.parent.mkdir(parents=True)
    _bars(US_SESSION.tz_convert(zone)).to_parquet(path)
    return root


def test_the_census_goes_red_on_a_wrong_zone_clean_file(tmp_path: Path) -> None:
    entries = [{"yfinance": "AAPL", "sleeve": "us_liquid"}]
    good = census.take("5m", today=date(2026, 10, 9), entries=entries,
                       clean_root=_store(tmp_path / "a", "America/New_York"))
    assert good.verdict == "GREEN"
    bad = census.take("5m", today=date(2026, 10, 9), entries=entries,
                      clean_root=_store(tmp_path / "b", "Europe/London"))
    assert bad.verdict == "RED"
    assert "not stamped America/New_York" in "; ".join(bad.names[0].reasons)
