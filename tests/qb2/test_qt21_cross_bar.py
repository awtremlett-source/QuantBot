"""QT-21 A: the daily front door's cross-bar check, fail-first on COPIES of the real files.

tests/qb2/fixtures/qt21/<symbol>.csv hold excerpts of the real daily files (unsealed rows
only, as stored: pounds; CSV because *.parquet is git-ignored), each fed through
daily.ingest by an injected fetch -- offline. The old
door let every break below into the series (docs/reports/QT-21_redfirst_a.txt); the new
one quarantines it, keeps it in the ledger, and never lets a re-fetch bring it back.
Real moves (VRT 2022, the Brexit vote, March 2020) must pass untouched.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from qb2.data import cross_bar, daily_step, front_door
from qb2.ingest import daily

FIXTURES = Path(__file__).parent / "fixtures" / "qt21"
NOW = datetime(2026, 10, 17, 1, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 10, 20, 22, 0, tzinfo=timezone.utc)
KIND = {"SMEA.L": "ETF", "FWRG.L": "ETF", "EDV.L": "STOCK", "IITU.L": "ETF", "PCT.L": "STOCK",
        "VRT": "STOCK", "AV.L": "STOCK", "EXPN.L": "STOCK"}


def real(symbol: str) -> pd.DataFrame:
    frame = pd.read_csv(FIXTURES / f"{symbol}.csv", index_col="date")
    zone = "America/New_York" if symbol == "VRT" else "Europe/London"
    frame.index = pd.to_datetime(frame.index, utc=True).tz_convert(zone).as_unit("ms")
    return frame


def entry(symbol: str) -> dict[str, str]:            # fixtures are already in pounds
    return {"yfinance": symbol, "quote_currency": "USD" if symbol == "VRT" else "GBP",
            "kind": KIND[symbol], "exchange": "NYSE" if symbol == "VRT" else "London Stock Exchange"}


def stored(tmp: Path, symbol: str, frame: pd.DataFrame | None = None,
           now: datetime = NOW) -> pd.DataFrame:
    got = frame if frame is not None else real(symbol)
    daily.ingest([entry(symbol)], fetch=lambda s: got.copy(), clean_root=tmp,
                 include_fx=False, now=now)
    out = daily.load(symbol, tmp)
    assert out is not None
    return out


def days(frame: pd.DataFrame) -> np.ndarray:
    return np.asarray(pd.DatetimeIndex(frame.index).date)


def ledger(tmp: Path, symbol: str) -> pd.DataFrame:
    path = cross_bar.ledger_path(symbol, tmp)
    assert path.is_file(), f"no quarantine ledger for {symbol}"
    return pd.read_parquet(path)


def test_smea_unit_break_quarantines_everything_from_2023_11_27(tmp_path: Path) -> None:
    kept = stored(tmp_path, "SMEA.L")
    assert days(kept).max() == date(2023, 11, 24)                 # the x114.6 open is gone
    held = ledger(tmp_path, "SMEA.L")
    assert days(held).min() == date(2023, 11, 27) and set(held["reason"]) == {"unit_break"}
    assert set(held["found"]) == {"2026-10-17"}
    assert len(kept) + len(held) == len(real("SMEA.L"))           # kept + quarantined = in


def test_fwrg_first_seven_rows_quarantined(tmp_path: Path) -> None:
    kept = stored(tmp_path, "FWRG.L")
    assert days(kept).min() == date(2023, 7, 11)
    assert len(ledger(tmp_path, "FWRG.L")) == 7


def test_edv_rows_before_its_london_listing_quarantined(tmp_path: Path) -> None:
    kept = stored(tmp_path, "EDV.L")
    assert days(kept).min() == date(2021, 6, 14)
    held = ledger(tmp_path, "EDV.L")
    assert len(held) == 848 and set(held["reason"]) == {"filler"}


def test_iitu_launch_rows_quarantined(tmp_path: Path) -> None:
    kept = stored(tmp_path, "IITU.L")
    assert days(kept).min() == date(2016, 2, 15)                  # its first trade
    assert {date(2015, 11, 20), date(2015, 11, 23)} <= set(days(ledger(tmp_path, "IITU.L")))


def test_three_breaks_keep_the_line_with_the_most_rows(tmp_path: Path) -> None:
    kept = stored(tmp_path, "PCT.L")                              # x0.1, x9.97, x0.101
    assert days(kept).min() == date(2013, 1, 2)
    assert days(ledger(tmp_path, "PCT.L")).max() == date(2012, 12, 31)


def test_real_moves_pass_untouched(tmp_path: Path) -> None:
    for symbol, day, ratio in (("VRT", date(2022, 2, 23), 0.62),       # the list's largest
                               ("AV.L", date(2016, 6, 24), 0.65),       # the Brexit vote
                               ("EXPN.L", date(2020, 3, 9), 0.70)):     # March 2020
        kept = stored(tmp_path, symbol)
        assert len(kept) == len(real(symbol)), symbol
        t = list(days(kept)).index(day)
        assert abs(kept["open"].iloc[t] / kept["close"].iloc[t - 1] - ratio) < 0.01
        assert not cross_bar.ledger_path(symbol, tmp_path).exists()


def test_the_nightly_refetch_cannot_bring_a_quarantined_row_back(tmp_path: Path) -> None:
    stored(tmp_path, "SMEA.L")
    first = ledger(tmp_path, "SMEA.L")
    again = real("SMEA.L")                                        # a "repaired" provider:
    late = days(again) >= date(2023, 11, 27)                      # the euro rows now in pounds
    for column in ("open", "high", "low", "close"):
        again.loc[late, column] = again.loc[late, column] / 114.6
    kept = stored(tmp_path, "SMEA.L", again, LATER)
    assert days(kept).max() == date(2023, 11, 24)                 # still out: sticky
    pd.testing.assert_frame_equal(ledger(tmp_path, "SMEA.L"), first)   # found date kept


def test_the_after_hours_step_runs_the_check(tmp_path: Path) -> None:
    clean = tmp_path / "clean"
    daily_step.run_if_due(NOW, clean_root=clean, fetch=lambda s: real("EDV.L") if s != daily.FX_PAIR
                          else real("VRT"), entries=[entry("EDV.L")], digest_dir=tmp_path / "d")
    kept = daily.load("EDV.L", clean)
    assert kept is not None and days(kept).min() == date(2021, 6, 14)


def test_requarantine_cleans_the_store_and_reconciles(tmp_path: Path) -> None:
    for symbol in ("SMEA.L", "EDV.L", "VRT"):                     # the store as it was
        front_door._write_parquet_atomically(real(symbol), daily.daily_path(symbol, tmp_path))
    out = daily.requarantine([entry(s) for s in ("SMEA.L", "EDV.L", "VRT")],
                             clean_root=tmp_path, now=NOW, include_fx=False)
    assert out.quarantined == 66 + 848
    for symbol in ("SMEA.L", "EDV.L", "VRT"):
        kept = daily.load(symbol, tmp_path)
        assert kept is not None
        held = cross_bar.load_ledger(symbol, tmp_path)
        assert len(kept) + (0 if held is None else len(held)) == len(real(symbol))
    lines = [json.loads(x) for x in front_door.manifest_path(tmp_path).read_text(
        encoding="utf-8").splitlines()]
    assert {(r["symbol"], r["reason"]) for r in lines if r["event"] == "quarantine"} == \
        {("SMEA.L", "unit_break"), ("EDV.L", "filler")}


def _bars(close: list[float], volume: list[float] | None = None) -> pd.DataFrame:
    index = pd.bdate_range("2024-01-01", periods=len(close), tz="Europe/London")
    c = np.asarray(close, dtype=float)
    return pd.DataFrame({"open": c, "high": c, "low": c, "close": c,
                         "volume": volume if volume is not None else [1e4] * len(c)}, index=index)


def test_one_glitch_bar_mid_series_costs_only_itself() -> None:
    frame = _bars([10.0] * 30 + [1000.0] + [10.2] * 30)
    assert list(np.flatnonzero(cross_bar.unit_break_rows(frame))) == [30]


def test_a_tie_keeps_the_latest_unit() -> None:
    frame = _bars([1.0] * 10 + [100.0] * 10)
    assert list(np.flatnonzero(cross_bar.unit_break_rows(frame))) == list(range(10))


def test_a_young_share_keeps_every_row_until_it_has_traded_a_month() -> None:
    frame = _bars([5.0] * 15, [0.0] * 3 + [1e4] * 12)
    assert not cross_bar.filler_rows(frame, "STOCK").any()        # no 20-session run yet
    assert list(np.flatnonzero(cross_bar.filler_rows(frame, "ETF"))) == [0, 1, 2]


def test_rates_and_indices_have_no_filler_rule() -> None:
    frame = _bars([1.3] * 30, [0.0] * 30)
    assert not cross_bar.filler_rows(frame, "").any()
    assert not cross_bar.found(frame, "RATE").astype(bool).any()
