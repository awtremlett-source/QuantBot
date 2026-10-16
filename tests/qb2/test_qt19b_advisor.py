"""QT-19 B2: the six advisor values and the monthly book, on hand-made bars with known answers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
import pandas as pd
import pytest

from qb2.research import advisor_book, preregister
from qb2.research.strategy import LookAhead
from qb2.signals import a_rules, indicators


@dataclass(frozen=True)
class N:
    symbol: str
    market: str
    bars: pd.DataFrame
    bet: int


DAYS = pd.DatetimeIndex(advisor_book.sessions("US", date(2015, 1, 1), date(2016, 12, 31))
                        ).tz_localize("America/New_York")


def _bars(close: np.ndarray, high: np.ndarray | None = None, days: pd.DatetimeIndex = DAYS
          ) -> pd.DataFrame:
    close = np.asarray(close, dtype=float)                           # a 1% range: ATR ~ 1%
    top = close * 1.005 if high is None else np.maximum(high, close * 1.005)
    return pd.DataFrame({"open": close, "high": top, "low": close * 0.995,
                         "close": close, "volume": 1.0}, index=days[:len(close)])


def _flat(n: int = len(DAYS), price: float = 100.0) -> np.ndarray:
    return price * 1.0005 ** np.arange(n)                           # a gentle rise: no stop


def _entry(cid: str) -> dict[str, Any]:
    return dict(preregister.entries()[cid])


# ---------------------------------------------------------------- the six values

def test_each_registered_value_on_a_known_series() -> None:
    close = 100.0 + np.arange(400.0)
    high = close + 5.0
    bars = _bars(close, high)
    months = np.zeros(400)
    t = 300
    got = {cid: a_rules.of(_entry(cid)).values(bars, 0, months)[t]
           for cid in ("A-01", "A-02", "A-03", "A-04", "A-05", "A-06")}
    mom12 = close[t - 21] / close[t - 252] - 1
    vol = pd.Series(close).pct_change().iloc[t - 251:t + 1].std(ddof=1)
    assert got["A-01"] == pytest.approx(mom12) and got["A-06"] == pytest.approx(mom12)
    assert got["A-02"] == pytest.approx(close[t - 21] / close[t - 126] - 1)
    assert got["A-03"] == pytest.approx(mom12 / vol)
    assert got["A-04"] == pytest.approx(close[t] / bars["high"].to_numpy()[t - 251:t + 1].max())
    assert got["A-05"] == pytest.approx(vol)
    assert a_rules.of(_entry("A-05")).ascending and not a_rules.of(_entry("A-01")).ascending
    assert a_rules.of(_entry("A-06")).market_filter and not a_rules.of(_entry("A-01")).market_filter


def test_values_never_read_a_later_bar() -> None:
    rng = np.random.default_rng(1)
    close = 100 * np.cumprod(1 + rng.normal(0, 0.01, 400))
    full, cut = _bars(close, close * 1.01), _bars(close[:320], close[:320] * 1.01)
    for cid in ("A-01", "A-02", "A-03", "A-04", "A-05"):
        rule = a_rules.of(_entry(cid))
        a = rule.values(full, 0, np.zeros(400))[:320]
        b = rule.values(cut, 0, np.zeros(320))
        assert np.allclose(a, b, equal_nan=True), cid
        assert np.isnan(a[:rule.lookback - 1]).all()                # not enough bars: NaN


def test_rules_refuse_anything_not_registered() -> None:
    for change in ({"lookback": 200}, {"order": "lowest first"}, {"value": "close[t] / close[t-5]"}):
        bad = _entry("A-01")
        bad["parameters"] = {**bad["parameters"], **change}
        with pytest.raises(ValueError, match="not implemented exactly"):
            a_rules.of(bad)
    bad = _entry("A-06")
    bad["parameters"] = {**bad["parameters"], "filter": "VWRP above its 50-day average"}
    with pytest.raises(ValueError, match="filter"):
        a_rules.of(bad)


# ---------------------------------------------------------------- the book

S = advisor_book.Settings(lookback=5, ascending=False, top=0.2, buffer=0.3)


def _book(values: dict[str, np.ndarray], closes: dict[str, np.ndarray] | None = None,
          s: advisor_book.Settings = S, **kw: Any) -> tuple[advisor_book.Book, list[N]]:
    closes = closes or {}
    data = [N(sym, "US", _bars(closes.get(sym, _flat(len(v)))), i)
            for i, (sym, v) in enumerate(values.items())]
    return advisor_book.build(s, data, values, **kw), data


def _month_end(year: int, month: int) -> int:
    ends = advisor_book.last_sessions(advisor_book.sessions("US", date(2015, 1, 1),
                                                            date(2017, 1, 31)))
    return int(np.flatnonzero(DAYS.date == ends[year * 12 + month - 1])[0])


def _ranked(order: list[str], n: int = len(DAYS)) -> dict[str, np.ndarray]:
    """Ten names ranked in this order at every bar (first = best)."""
    return {sym: np.full(n, float(len(order) - r)) for r, sym in enumerate(order)}


def test_top_twenty_percent_bought_at_the_month_end_close_filled_next_open() -> None:
    names = [f"N{j}" for j in range(10)]
    book, data = _book(_ranked(names))
    jan = _month_end(2015, 1)
    held = {s for s in names if book.decisions[s][jan] == 1.0}
    assert held == {"N0", "N1"}                                      # k = round(0.2 x 10) = 2
    assert book.decisions["N0"][jan - 1] == 0.0                      # decided AT the close
    bars = data[0].bars
    atr = indicators.atr_wilder(bars, 14).to_numpy()[jan]
    cap = 0.01 / 0.7 / (3 * atr / bars["close"].to_numpy()[jan])          # the 1% rule
    assert book.weights["N0"].iloc[jan + 1] == pytest.approx(min(0.5, cap))   # 1/k, capped


def test_buffer_keeps_a_name_inside_the_top_thirty_percent() -> None:
    names = [f"N{j}" for j in range(10)]
    vals = _ranked(names)
    feb = _month_end(2015, 2)
    vals["N1"][feb:] = 7.5                                           # 3rd: out of top 2, in top 3
    vals["N0"][feb + 1:] = 0.5                                       # March: last -> sold
    book, _ = _book(vals)
    assert book.decisions["N1"][feb] == 1.0 and book.decisions["N2"][feb] == 0.0
    mar = _month_end(2015, 3)
    assert book.decisions["N0"][mar] == 0.0 and book.decisions["N2"][mar] == 1.0


def test_stop_sells_and_no_rebuy_at_the_same_close_then_back_next_month() -> None:
    names = [f"N{j}" for j in range(10)]
    close = _flat()
    feb = _month_end(2015, 2)
    close[feb] = 50.0                                                # crash on February's close
    vals = _ranked(names)
    vals["N2"][feb + 1:] = 0.1                    # March: the refill falls out, a slot frees
    book, _ = _book(vals, {"N0": close})
    assert book.decisions["N0"][feb] == 0.0 and book.stopped == 1
    assert book.decisions["N2"][feb] == 1.0                          # its slot refilled
    assert book.decisions["N0"][_month_end(2015, 3)] == 1.0          # back at the next decision


def test_unsettled_vix_tightens_the_stop_to_two_atr() -> None:
    names = [f"N{j}" for j in range(10)]
    close = _flat()
    jan = _month_end(2015, 1)
    atr = indicators.atr_wilder(_bars(close), 14).to_numpy()
    close[jan + 5] = close[jan + 4] - 2.5 * atr[jan + 4]             # 2.5 ATR down in one close
    calm, loud = pd.Series(15.0, index=DAYS), pd.Series(35.0, index=DAYS)
    a, _ = _book(_ranked(names), {"N0": close}, vix=calm)
    b, _ = _book(_ranked(names), {"N0": close}, vix=loud)
    assert a.decisions["N0"][jan + 5] == 1.0                        # 3 x ATR: still held
    assert b.decisions["N0"][jan + 5] == 0.0                        # 2 x ATR: sold


def test_p13_after_twelve_months_requalify_or_sell() -> None:
    names = [f"N{j}" for j in range(10)]
    vals = _ranked(names)
    jan16 = _month_end(2016, 1)
    vals["N1"][jan16 - 10:] = 7.5                                    # 3rd in Jan 2016: top 30%, not top 20%
    book, _ = _book(vals)
    assert book.decisions["N0"][jan16] == 1.0 and book.requalified >= 1   # re-justified, no trade
    assert book.decisions["N1"][jan16] == 0.0                        # 12 months: needs the top k


def test_market_filter_off_sells_everything_and_buys_nothing() -> None:
    names = [f"N{j}" for j in range(10)]
    mar = advisor_book.month_of(DAYS[_month_end(2015, 3)].date())
    on = {m: m != mar for m in range(24000, 24400)}
    book, _ = _book(_ranked(names), market_on=on)
    i = _month_end(2015, 3)
    assert all(book.decisions[s][i] == 0.0 for s in names)
    assert book.decisions["N0"][_month_end(2015, 4)] == 1.0 and book.filter_off_months == 1


def test_no_month_end_bar_sells_at_the_next_bar() -> None:
    names = [f"N{j}" for j in range(10)]
    vals = _ranked(names)
    data = [N(s, "US", _bars(_flat()), i) for i, s in enumerate(names)]
    feb = _month_end(2015, 2)
    gap = data[0].bars.drop(data[0].bars.index[feb])
    data[0] = N("N0", "US", gap, 0)
    vals["N0"] = np.delete(vals["N0"], feb)
    book = advisor_book.build(S, data, vals)
    assert book.decisions["N0"][feb - 1] == 1.0 and book.decisions["N0"][feb] == 0.0


def test_weights_cap_at_the_one_percent_rule() -> None:
    names = [f"N{j}" for j in range(10)]
    rng = np.random.default_rng(5)
    wild = 100 * np.cumprod(1 + rng.normal(0, 0.25, len(DAYS)))      # ATR huge vs price
    book, _ = _book(_ranked(names), {"N0": wild})
    w = book.weights["N0"].iloc[60:]
    assert (w < 0.5).all() and (w <= 0.01 / 0.7 / 0.3).any()


def test_causal_check_passes_honest_and_catches_a_peek() -> None:
    names = [f"N{j}" for j in range(10)]
    rng = np.random.default_rng(7)
    vals = {s: rng.random(len(DAYS)) for s in names}
    book, data = _book(vals)
    cuts = [date(2015, 6, 15), date(2016, 2, 15)]
    advisor_book.causal(lambda d: advisor_book.build(S, d, {n.symbol: vals[n.symbol][:len(n.bars)]
                                                            for n in d}), data, book, cuts)
    peek = {s: np.r_[v[15:], np.zeros(15)] for s, v in vals.items()}   # 15 bars ahead
    full = advisor_book.build(S, data, peek)

    def cut_peek(d: Sequence[Any]) -> advisor_book.Book:                   # recomputed on cut data
        return advisor_book.build(S, d, {n.symbol: np.r_[vals[n.symbol][15:len(n.bars)],
                                                         np.zeros(15)] for n in d})
    with pytest.raises(LookAhead):
        advisor_book.causal(cut_peek, data, full, cuts)


def test_a_two_line_bet_is_refused() -> None:
    data = [N("A", "US", _bars(_flat()), 0), N("B", "US", _bars(_flat()), 0)]
    with pytest.raises(ValueError, match="two lines"):
        advisor_book.build(S, data, {"A": _flat(), "B": _flat()})
