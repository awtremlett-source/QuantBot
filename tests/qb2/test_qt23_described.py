"""QT-23 E: ADV-0 described -- the default's back-test form, and the same rule as the live job.

Offline: hand-made price paths on real London sessions. The live job and the back-test must agree
bar for bar up to and including an exit; after it they part on purpose -- brakes are live only
(the S6 rule), so the back-test re-buys on the signal while the live re-buy waits behind the brake.
Each test was seen RED against a planted mutant (docs/reports/QT-23_E_redfirst.py.txt).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from qb2.advisor import scorecard, state
from qb2.research import adv0_describe as adv0
from qb2.research import advisor_book
from tests.qb2.test_qt23_advisor import DAYS, _run, at

D: list[date] = list(pd.DatetimeIndex(advisor_book.sessions("LSE", date(2025, 3, 3), date(2025, 5, 30))).date)
CALM = np.zeros(len(D), dtype=bool)


def test_the_first_buy_fills_after_the_first_weeks_last_session() -> None:
    p = adv0.path(D, np.full(len(D), 100.0), np.full(len(D), 100.0), CALM, D[0])
    assert p.fills == [(5, "BUY")]                                       # Fri 7 Mar decides, Mon 10 fills
    assert D[4].weekday() == 4 and p.held[:5].sum() == 0 and p.held[5:].all()


def test_the_stop_crosses_sells_at_the_next_open_and_rebuys_ten_percent_off_the_low() -> None:
    c = np.full(len(D), 100.0)
    c[6:] = 120.0
    c[8], c[9], c[10], c[11] = 101.0, 99.0, 95.0, 104.5                  # 120 x 0.85 = 102: crossed at 8
    p = adv0.path(D, c.copy(), c, CALM, D[0])
    assert p.fired == 1 and p.fills == [(5, "BUY"), (9, "SELL"), (12, "BUY")]   # 104.5 >= 95 x 1.10
    assert p.held[8] == 1.0 and p.held[9:12].sum() == 0 and p.held[12] == 1.0


def test_jumpy_markets_tighten_the_stop_to_ten_percent() -> None:
    c = np.full(len(D), 100.0)
    c[7] = 89.5                                                          # -10.5%: held at 15%, out at 10%
    calm = adv0.path(D, c.copy(), c, CALM, D[0])
    loud = adv0.path(D, c.copy(), c, np.ones(len(D), dtype=bool), D[0])
    assert calm.fired == 0 and loud.fired == 1


def test_unsettled_is_vix_above_30_before_the_day_or_none_within_five_days() -> None:
    days = [date(2025, 3, 10), date(2025, 3, 11), date(2025, 3, 20)]
    vix_days = np.array(["2025-03-07", "2025-03-10"], dtype="datetime64[D]")
    assert adv0.unsettled(days, vix_days, np.array([15.0, 35.0])).tolist() == [False, True, True]
    assert adv0.unsettled(days[2:], vix_days, np.array([15.0, 15.0])).tolist() == [True]   # calm, but
    assert adv0.unsettled(days, vix_days[:0], np.array([])).all()       # 10 days old = missing; none: too


def test_a_close_exactly_ten_percent_off_the_low_is_a_rebuy_signal() -> None:
    assert 95.0 * 1.10 > 104.5                                          # floating point, not the rule
    assert adv0.rebuy_signal(104.50, 95.00) and not adv0.rebuy_signal(104.49, 95.00)


def test_the_live_job_and_the_back_test_agree_until_the_brake_parts_them(tmp_path: Path) -> None:
    """Day by day, as the job runs: a crossing found on a catch-up is issued when it is found, so
    its as-if sale is the open after THAT -- when he could have acted (the page says so)."""
    closes = [100.0, 100.0, 120.0, 101.0, 99.0, 95.0, 104.6, 105.0]
    _run(tmp_path, closes[:1], DAYS[0], at(DAYS[0], 19), first=True)     # live: BUY fills at day 1
    for k in range(1, 8):
        _run(tmp_path, closes[:k + 1], DAYS[k], at(DAYS[k], 19))
    rows = state.rows(state.Paths.under(tmp_path).log("suggestions"))
    live = scorecard.held_path(DAYS[:8], scorecard.as_if(rows, DAYS[:8]))
    c = np.array(closes)
    back = adv0.path(DAYS[:8], c.copy(), c, np.zeros(8, dtype=bool), DAYS[0], first_fill=1)
    assert live[:6].tolist() == back.held[:6].tolist() == [0, 1, 1, 1, 0, 0]   # the same exit
    assert back.fills[-1] == (7, "BUY")                                  # the signal on day 6: 104.6
    rebuy = [r for r in rows if r["kind"] == "re-buy"]
    assert rebuy[0]["session"] == str(DAYS[6]) and not rebuy[0]["allowed"]      # live: the brake
    assert live[6:].sum() == 0
