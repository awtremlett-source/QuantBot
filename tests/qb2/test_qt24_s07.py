"""QT-24 D: S-07, the slow trend filter -- its book on a hand-worked year, and its shadow wiring.

S-07 (registered cd3e863, before any S-07 code): at each month-end close hold VWRL if the
close is above the mean of the last 10 month-end closes, else cash; changes fill at the next open.
Offline: real London sessions, made-up prices. The filter-inverted mutant turns the year RED
(docs/reports/QT-24_mutants.txt).
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from qb2.advisor import page, shadow
from qb2.execution import costs
from qb2.research import advisor_book, fills, preregister, s07_describe, trend_filter
from qb2.research.names import NameData

# Month by month, every bar of the month opens and closes at that month's price, so all the price
# moves happen at a month's first open (made up; 2018 warms the 10-month average).
PRICE = {(2018, m): 99.0 + m for m in range(1, 13)} | {
    (2019, 1): 112.0, (2019, 2): 113.0, (2019, 3): 100.0, (2019, 4): 95.0, (2019, 5): 98.0,
    (2019, 6): 104.0, (2019, 7): 115.0, (2019, 8): 116.0, (2019, 9): 117.0, (2019, 10): 118.0,
    (2019, 11): 119.0, (2019, 12): 120.0}
DAYS = [d for d in pd.DatetimeIndex(advisor_book.sessions("LSE", date(2018, 1, 1), date(2019, 12, 31))).date]
CLOSES = np.array([PRICE[(d.year, d.month)] for d in DAYS])
VWRL = costs.Instrument("VWRLl_EQ", "GBP", "LSE", "ETF", False)
START = date(2019, 1, 1)


def _vwrl() -> NameData:
    idx = pd.DatetimeIndex([pd.Timestamp(d).tz_localize("Europe/London") for d in DAYS])
    bars = pd.DataFrame({"open": CLOSES, "high": CLOSES, "low": CLOSES, "close": CLOSES, "volume": 1.0},
                        index=idx)
    return NameData("VWRL.L", "LSE", VWRL, bars, fills.schedule(bars.index, "1d", "LSE"), 0, None,
                    np.zeros(len(bars)))


def _entry() -> dict[str, object]:
    """S-07 as registered; its day 0 moved to the hand-worked year (the rule itself unchanged)."""
    entry = dict(preregister.require("S-07").entry)
    entry["parameters"] = {**entry["parameters"], "scored_from": START.isoformat()}
    return entry


def test_s07s_book_on_a_hand_worked_year_to_the_penny() -> None:
    """The first review, Fri 4 Jan 2019: December's 111 is above its average (102..111: 106.5) ->
    BUY at Mon 7 Jan's open, 112. March's month-end 100 is below its average (Jun 2018..Mar 2019:
    108.1) -> SELL at 1 Apr's open, 95: the one exit. April 95 (107.1), May 98 (106.3), June 104
    (106.0) stay below: cash. July's 115 is above (106.7) -> BUY at 1 Aug's open, 116: the one
    re-entry; held to 31 Dec's 120, marked as if sold. Four legs of 0.10% at 1x (0.20% at 2x):
    1x: 7000 x 95/112 x 120/116 x 0.999^4 = 6117.709 -> £6,117.71;
    2x: 7000 x 95/112 x 120/116 x 0.998^4 = 6093.251 -> £6,093.25."""
    month_end, week_end = trend_filter.calendar_ends(DAYS)
    book = trend_filter.fills(DAYS, month_end, week_end, trend_filter.above(CLOSES, month_end), START)
    assert [(DAYS[t], side) for t, side in book] == [
        (date(2019, 1, 7), "BUY"), (date(2019, 4, 1), "SELL"), (date(2019, 8, 1), "BUY")]
    by = shadow.score(_entry(), [_vwrl()], pd.Series(dtype=float), START, {})
    assert {s: round(float(v.iloc[-1]) * 7000, 2) for s, v in by.items()} == {1.0: 6117.71, 2.0: 6093.25}
    assert by[1.0].index[0].date() == date(2019, 1, 2)          # scored from its day 0 only (R8)


def test_the_description_runs_s07_through_adv0s_own_runner() -> None:
    sig = s07_describe.signal(_vwrl().bars)
    p = s07_describe.rule(DAYS, CLOSES.copy(), CLOSES, sig, START)
    assert [DAYS[t] for t, _ in p.fills] == [date(2019, 1, 7), date(2019, 4, 1), date(2019, 8, 1)]
    assert p.fired == 1 and int(p.held.sum()) == sum(1 for d in DAYS if date(2019, 1, 7) <= d < date(2019, 4, 1)
                                                   or d >= date(2019, 8, 1))


def test_s07_is_the_seventh_shadow_from_its_own_day_0_scoring_nothing() -> None:
    assert shadow.SHADOWS == tuple(f"S-0{j}" for j in range(1, 8))
    entry = preregister.require("S-07").entry
    assert shadow.start(entry, date(2026, 10, 20)) == date(2026, 10, 23)
    scored = {"S-01": {1.0: pd.Series([1.0], index=[pd.Timestamp("2026-10-22", tz="Europe/London")])},
              "S-07": {1.0: pd.Series(dtype=float)}}
    entries = {"S-01": preregister.require("S-01").entry, "S-07": entry}
    assert shadow.row(scored, entries, date(2026, 10, 20), date(2026, 10, 22)) == {"S-01": {"pct_1x": 0.0}}
    on_day_0 = shadow.row(scored, entries, date(2026, 10, 20), date(2026, 10, 23))
    assert on_day_0["S-07"] == {"pct_1x": 0.0}                    # day 0: in cash, nothing scored


def test_the_page_lists_s07_with_its_own_start() -> None:
    rows = [{"session": "2026-10-22", "rules": {"S-01": {"pct_1x": 0.0, "pct_2x": 0.0}}},
            {"session": "2026-10-23", "rules": {"S-01": {"pct_1x": 0.1, "pct_2x": 0.0},
                                                "S-07": {"pct_1x": 0.0, "pct_2x": 0.0}}}]
    text = page.build(pd.Timestamp("2026-10-26 08:00", tz="UTC").to_pydatetime(), arm=date(2026, 10, 20),
                      days=[], suggestions=[], runs=[], shadows=rows, status={})
    assert "| S-07 | 2026-10-23 | +0.00% | +0.00% |" in text and "| S-01 | 2026-10-22 |" in text


@pytest.mark.parametrize("closes, expect", [([100.0] * 10, 0.0), ([100.0] * 9 + [100.01], 1.0)])
def test_above_means_strictly_above_the_ten_month_average(closes: list[float], expect: float) -> None:
    up = trend_filter.above(np.array(closes), np.ones(10, dtype=bool))
    assert np.isnan(up[:9]).all() and up[9] == expect
