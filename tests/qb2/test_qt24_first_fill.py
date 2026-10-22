"""QT-24 A: the advisor's first live fill, replayed to the penny -- and no fill from a bar taken
before its session. Offline: a tmp clean store with the real VWRL figures and tmp advisor files.

A daily bar is LABELLED with its date at midnight UK, so its stamp alone says nothing about when
it became knowable; what does is the run's own clock. A run reads a session's bar only once that
session has closed by the run's clock (daily.run): before 08:00 UK on Wed 21 Oct no bar can carry
Wednesday's open, and before 16:30 UK none can carry its close.
* test_a_run_before_the_open_never_fills_from_a_pre_open_bar: the store as the top-up really
  writes it at 07:00 UK (through Tuesday) -- GUARDS existing behaviour (green on the old code).
* test_a_store_claiming_a_session_not_yet_closed_is_refused: RED on the old code, which filled at
  the pre-open row's price (docs/reports/QT-24_redfirst_fill.txt).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from qb2.advisor import daily, scorecard, state
from qb2.execution.safety import ADVISOR, Blocked
from qb2.guard import brakes, stops
from tests.qb2.test_qt23_advisor import store

UTC = timezone.utc
MON, TUE, WED = date(2026, 10, 19), date(2026, 10, 20), date(2026, 10, 21)
OPEN_WED = 138.3800048828125                          # the stored figures, float for float
CLOSES = {MON: 139.02000427246094, TUE: 138.22000122070312, WED: 138.72000122070312}
ARMED = datetime(2026, 10, 20, 20, 39, 40, tzinfo=UTC)
WED_0700_UK, WED_1300_UK = datetime(2026, 10, 21, 6, 0, tzinfo=UTC), datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
WED_RUN, THU_RUN = datetime(2026, 10, 21, 17, 21, 58, tzinfo=UTC), datetime(2026, 10, 22, 17, 14, 30, tzinfo=UTC)


def _store(tmp: Path, wednesday_open: float, wednesday_close: float, through: date) -> Path:
    days = [MON, TUE, WED]
    return store(tmp, days, [138.82000732421875, 138.11000061035156, wednesday_open],
                 [CLOSES[MON], CLOSES[TUE], wednesday_close], through=through)


def _armed(tmp: Path) -> state.Paths:
    """Armed as on 20 Oct: the first review, from Monday's close, BUY (allowed)."""
    paths = state.Paths.under(tmp)
    state.arm(paths, TUE, ARMED, "test")
    brakes.Brakes(paths.brakes).update(ADVISOR, scorecard.POT_GBP, at=ARMED)
    daily.run(ARMED, paths, clean_root=_store(tmp, OPEN_WED, CLOSES[WED], MON), first_review=True,
              shadows=False)
    assert [(r["action"], r["allowed"], r["session"]) for r in state.rows(paths.log("suggestions"))] == [
        ("BUY", True, "2026-10-19")]
    return paths


def test_the_live_first_fill_reproduces_to_the_penny(tmp_path: Path) -> None:
    """Wed 18:21 UK: the store final through Tuesday -> day 0, in cash. Thu 18:14 UK: through
    Wednesday -> the BUY fills at Wednesday's open, 138.38; the stop opens at 138.38 x 0.85 and is
    raised at Wednesday's close (138.72 x 0.85 = 117.912); the day line, by hand: 7000 x 138.72 /
    138.38 x 0.999 x 0.999 = 7003.17 at 1x, and x 0.998 x 0.998 = 6989.16 at 2x."""
    paths = _armed(tmp_path)
    daily.run(WED_RUN, paths, clean_root=_store(tmp_path, OPEN_WED, CLOSES[WED], TUE), shadows=False)
    assert daily.advisor_stop(stops.Ledger(paths.stops)) is None
    lines = daily.run(THU_RUN, paths, clean_root=_store(tmp_path, OPEN_WED, CLOSES[WED], WED), shadows=False)
    held = daily.advisor_stop(stops.Ledger(paths.stops))
    assert held is not None and held.entry == OPEN_WED and held.opened_at == "2026-10-21T07:00:00+00:00"
    assert [c.level for c in held.history] == pytest.approx([117.62300415039062, 117.91200103759766], abs=1e-9)
    days = state.rows(paths.log("days"))
    assert [(d["session"], d["held"], d["value_1x"], d["value_2x"], d["pct_1x"], d["pct_2x"]) for d in days] == [
        ("2026-10-20", False, 7000.0, 7000.0, 0.0, 0.0), ("2026-10-21", True, 7003.17, 6989.16, 0.0453, -0.1549)]
    assert "reconciled: OK" in lines


def test_a_run_before_the_open_never_fills_from_a_pre_open_bar(tmp_path: Path) -> None:
    """07:00 UK Wed, a provider row for Wednesday already in the file (Tuesday's close as its
    'open'), the marker through Tuesday as the top-up writes it: no fill, no stop, no Wednesday."""
    paths = _armed(tmp_path)
    daily.run(WED_0700_UK, paths, clean_root=_store(tmp_path, CLOSES[TUE], CLOSES[TUE], TUE), shadows=False)
    assert daily.advisor_stop(stops.Ledger(paths.stops)) is None
    assert [d["session"] for d in state.rows(paths.log("days"))] == ["2026-10-20"]


@pytest.mark.parametrize("now", [WED_0700_UK, WED_1300_UK], ids=["before the open", "mid-session"])
def test_a_store_claiming_a_session_not_yet_closed_is_refused(tmp_path: Path, now: datetime) -> None:
    paths = _armed(tmp_path)
    with pytest.raises(Blocked, match="calls 2026-10-21 final, but London's 2026-10-21 session closes "
                                      "2026-10-21 15:30 UTC.*taken before its session ended"):
        daily.run(now, paths, clean_root=_store(tmp_path, CLOSES[TUE], CLOSES[TUE], WED), shadows=False)
    assert daily.advisor_stop(stops.Ledger(paths.stops)) is None          # nothing filled, nothing written
    assert state.rows(paths.log("days")) == []
