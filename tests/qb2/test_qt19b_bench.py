"""QT-19 B2: the four bench extensions the monthly advisor book needs, each fail-first.

1. **Slot weights** (bet_groups.combine ``weights``; firewall NameData.weight): the
   advisor holds the top 20% of the list, each slot 1/k of the pot. Averaged over
   every name, the old combine left ~80% of the pot in cash against a fully invested
   VWRP.
2. **Dividend income** (simulate ``income``; backtest; matched null): a name held
   through an ex-date's open earns the payout (P3). Same-day trades never were.
3. **D3 before VWRP existed** (benchmark.over): VWRL with dividends added back,
   chained at VWRP's first close -- benchmark.py's named fallback.
4. **Daily fingerprints** (data_fingerprint): the bars a daily run reads, by content.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qb2.data import data_fingerprint
from qb2.research import benchmark, bet_groups, simulate, total_return

UTC = "UTC"


def _idx(n: int, start: str = "2024-01-02") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="D", tz=UTC)


def test_slot_weights_sum_the_held_slots_instead_of_averaging_every_name() -> None:
    idx = _idx(3)
    r = {"A": pd.Series([0.01, 0.02, 0.0], idx), "B": pd.Series([0.0] * 3, idx),
         "C": pd.Series([0.0] * 3, idx), "D": pd.Series([0.0] * 3, idx)}
    old = bet_groups.combine(r, {})
    assert old.iloc[0] == pytest.approx(0.0025)                     # 3/4 of the pot in cash
    w = {s: pd.Series(1.0, idx) for s in r}                          # one slot: A holds all of it
    new = bet_groups.combine(r, {}, weights=w)
    assert list(new) == pytest.approx([0.01, 0.02, 0.0])
    half = bet_groups.combine(r, {}, weights={"A": pd.Series(0.5, idx)})
    assert half.iloc[1] == pytest.approx(0.01)                       # unweighted names: cash


def test_income_is_credited_only_when_held_through_the_ex_date_open() -> None:
    opens = np.array([10.0, 9.8, 9.8, 9.8])
    closes = np.array([10.0, 9.8, 9.8, 9.8])
    income = np.array([0.0, 0.02, 0.0, 0.0])                        # 0.20 paid, ex on bar 1
    legs = simulate.LegFractions(1e-9, 1e-9)
    held = simulate.run(opens, closes, np.array([1.0, 1.0, 1.0, 0.0]), legs, income=income)
    assert np.prod(1 + held.gross) == pytest.approx(1.0)            # price drop repaid
    bought_on_ex = simulate.run(opens, closes, np.array([0.0, 1.0, 1.0, 0.0]), legs,
                                income=income)
    assert bought_on_ex.gross[1] == pytest.approx(0.0)              # bought at the ex open
    none = simulate.run(opens, closes, np.array([1.0, 1.0, 1.0, 0.0]), legs)
    assert np.prod(1 + none.gross) == pytest.approx(0.98)


def test_backtest_and_matched_null_carry_the_income() -> None:
    from qb2.research import backtest, matched_null
    assert "income" in backtest.BacktestResult.__dataclass_fields__
    assert "g.full.income" in Path(matched_null.__file__).read_text(encoding="utf-8")


def _bench_bars(start: str, closes: list[float]) -> pd.DataFrame:
    idx = pd.date_range(start, periods=len(closes), freq="B", tz="Europe/London")
    return pd.DataFrame({"open": closes, "high": closes, "low": closes, "close": closes,
                         "currency": "GBP"}, index=idx)


def test_d3_before_vwrp_existed_is_vwrl_with_dividends_chained_at_vwrp_first_close(
        monkeypatch: pytest.MonkeyPatch) -> None:
    vwrl = _bench_bars("2014-01-01", [10.0] * 10 + [11.0] * 30)      # +10% price
    vwrp = _bench_bars("2014-01-15", [50.0] * 5 + [55.0] * 20)       # first close 2014-01-15
    seen: list[str] = []

    def held(symbol: str, start: object, end: object, **kw: object) -> object:
        seen.append(symbol)
        frame = vwrl if symbol == benchmark.D3_FALLBACK else vwrp
        days = pd.Series(frame.index.date, index=frame.index)
        a = frame[(days <= pd.Timestamp(str(start)).date()).to_numpy()]["close"].iloc[-1]
        b = frame[(days <= pd.Timestamp(str(end)).date()).to_numpy()]["close"].iloc[-1]
        bonus = 0.5 if symbol == benchmark.D3_FALLBACK else 0.0       # dividends added back
        return type("H", (), {"total_return_gross": (b + bonus) / a - 1.0})()

    monkeypatch.setattr(total_return, "holding_return", held)
    monkeypatch.setattr(benchmark, "_first_close", lambda symbol, **kw: vwrp.index[0].date())
    out = benchmark.over(date(2014, 1, 3), date(2014, 2, 14), chosen=(benchmark.D3, "VWRP"))
    assert seen == [benchmark.D3_FALLBACK, benchmark.D3]
    assert out.total_return == pytest.approx((11.5 / 10.0) * (55.0 / 50.0) - 1.0)
    assert "VWRL" in out.why
    later = benchmark.over(date(2014, 1, 20), date(2014, 2, 14), chosen=(benchmark.D3, "VWRP"))
    assert later.total_return == pytest.approx(55.0 / 50.0 - 1.0)   # VWRP alone once it exists


def test_daily_fingerprint_reads_content_and_ignores_appended_days(tmp_path: Path) -> None:
    from qb2.ingest import daily
    folder = tmp_path / "daily"
    folder.mkdir()
    bars = _bench_bars("2025-10-01", [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
    bars["volume"] = 5.0
    bars.to_parquet(folder / "X.L.parquet")
    a = data_fingerprint.daily_digest(["X.L"], None, date(2025, 10, 6), tmp_path)
    more = pd.concat([bars, _bench_bars("2025-10-15", [9.0]).assign(volume=1.0)])
    more.to_parquet(folder / "X.L.parquet")
    assert data_fingerprint.daily_digest(["X.L"], None, date(2025, 10, 6), tmp_path) == a
    changed = more.copy()
    changed.iloc[2, changed.columns.get_loc("close")] = 3.5
    changed.to_parquet(folder / "X.L.parquet")
    assert data_fingerprint.daily_digest(["X.L"], None, date(2025, 10, 6), tmp_path) != a
    vol = more.copy()
    vol["volume"] = 9.0                                              # a column no rule reads
    vol.to_parquet(folder / "X.L.parquet")
    assert data_fingerprint.daily_digest(["X.L"], None, date(2025, 10, 6), tmp_path) == a
    assert daily.load("X.L", tmp_path) is not None
