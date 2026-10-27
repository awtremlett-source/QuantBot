"""QT-26 C: a London session the store lacks, with a later one present, is named -- never a silent gap.

The risk (QT-25 PROPOSE 2): had VWRL's Fri 23 Oct close stayed broken, Monday 26 Oct's 20:00 run
would have processed Monday and passed over Friday: the RED cleared, and nothing said that Friday's
close was never checked against the stop. Now the advisor still checks the stop on the newest sane
close, writes a SKIPPED row for the passed-over session in the as-if record, and names it by date
as UNCHECKED on every run and on the page while no sane close for it is stored. A close that comes
after a later session was processed is too late to use (a processed day is never re-done): the page
says so, final. Offline: a tmp store with the real VWRL figures (tests/museum) and tmp advisor files.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from qb2.advisor import daily, scorecard, state
from qb2.guard import stops
from tests.qb2.test_qt23_advisor import store
from tests.qb2.test_qt24_first_fill import THU_RUN, _armed

UTC = timezone.utc
SANE = json.loads((Path(__file__).resolve().parents[1] / "museum" / "vwrl_2026-10-23_refetch.json")
                  .read_text(encoding="utf-8"))["sane"]
FRI_RUN = datetime(2026, 10, 23, 17, 10, 32, tzinfo=UTC)
MON_RUN = datetime(2026, 10, 26, 20, 26, 55, tzinfo=UTC)          # the real 20:00 run's advisor
TUE_0800, TUE_RUN = datetime(2026, 10, 27, 8, 0, tzinfo=UTC), datetime(2026, 10, 27, 20, 30, tzinfo=UTC)
THU_2130 = datetime(2026, 10, 22, 20, 30, tzinfo=UTC)               # Thursday final everywhere (BST)
TUE = {"2026-10-27": [137.6, 138.0, 137.2, 137.8, 1]}            # invented: only its presence matters
UNCHECKED_23 = ("UNCHECKED: Fri 23 Oct (2026-10-23) has no sane VWRL close -- the as-if record skips that "
                "session, and the stop was checked only against later closes. Look at VWRL's close that "
                "day yourself.")
HOLDING_26 = ("holding VWRL as if bought (stop £117.91); VWRL closed £137.57 on 2026-10-26; as-if pot "
              "£6,945.11 (-0.78%) at 1x costs, £6,931.22 at 2x; brake OK")


def _clean(tmp: Path, days: list[str], through: str, close_26: float | None = None,
           close_22: float | None = None) -> Path:
    rows = {**SANE, **TUE}
    closes = [rows[d][3] for d in days]
    for day, close in (("2026-10-26", close_26), ("2026-10-22", close_22)):
        if close is not None and day in days:
            closes[days.index(day)] = close
    return store(tmp, [date.fromisoformat(d) for d in days], [rows[d][0] for d in days], closes,
                 through=date.fromisoformat(through))


def _to_friday(tmp: Path, close_22: float | None = None) -> state.Paths:
    """Armed 20 Oct, filled at Wed 21 Oct's open, Thursday processed, Friday's review: as live."""
    paths = _armed(tmp)
    week = ["2026-10-19", "2026-10-20", "2026-10-21"]
    daily.run(THU_RUN, paths, clean_root=_clean(tmp, week, "2026-10-21"), shadows=False)
    daily.run(FRI_RUN, paths, clean_root=_clean(tmp, [*week, "2026-10-22"], "2026-10-22", close_22=close_22),
              shadows=False)
    return paths


def _days(paths: state.Paths) -> list[tuple[str, bool]]:
    return [(str(r["session"]), bool(r.get("skipped"))) for r in state.rows(paths.log("days"))]


WITHOUT_FRIDAY = ["2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-26"]
BEFORE = [("2026-10-20", False), ("2026-10-21", False), ("2026-10-22", False)]


def test_a_run_with_no_skipped_session_reads_exactly_as_before(tmp_path: Path) -> None:
    """GUARD (green on the old code): Monday's real 20:26 run, Friday's close sane -- its lines
    replayed word for word and to the penny."""
    paths = _to_friday(tmp_path)
    lines = daily.run(MON_RUN, paths, shadows=False,
                      clean_root=_clean(tmp_path, [*WITHOUT_FRIDAY[:4], "2026-10-23", "2026-10-26"], "2026-10-26"))
    assert lines == ["woke after 2 sessions: stops checked, 0 to act on (logged)", HOLDING_26, "reconciled: OK"]
    assert _days(paths) == [*BEFORE, ("2026-10-23", False), ("2026-10-26", False)]


def test_the_stop_is_still_checked_against_the_newest_sane_close(tmp_path: Path) -> None:
    """GUARD (a): Friday missing, Monday's close at or below the stop -> URGENT-EXIT from Monday."""
    paths = _to_friday(tmp_path)
    daily.run(MON_RUN, paths, clean_root=_clean(tmp_path, WITHOUT_FRIDAY, "2026-10-26", close_26=117.0),
              shadows=False)
    urgent = [r for r in state.rows(paths.log("suggestions")) if r.get("kind") == "urgent-exit"]
    assert [(r["action"], r["session"]) for r in urgent] == [(scorecard.SELL, "2026-10-26")]


def test_a_passed_over_session_is_a_skipped_row_named_unchecked_on_every_run(tmp_path: Path) -> None:
    """(b) + (c): Monday processed, Friday a SKIPPED row, and the UNCHECKED line by date on the run's
    lines and the page -- again on the next run while Friday's close is still missing."""
    paths = _to_friday(tmp_path)
    clean = _clean(tmp_path, WITHOUT_FRIDAY, "2026-10-26")
    lines = daily.run(MON_RUN, paths, clean_root=clean, shadows=False)
    assert lines == [UNCHECKED_23, HOLDING_26, "reconciled: OK"]
    assert _days(paths) == [*BEFORE, ("2026-10-23", True), ("2026-10-26", False)]
    skipped = state.rows(paths.log("days"))[3]
    assert skipped["close"] is None and skipped["held"] is True
    assert daily.advisor_stop(stops.Ledger(paths.stops)) is not None
    page = paths.page.read_text(encoding="utf-8")
    assert f"- {UNCHECKED_23}" in page.split("## This week's suggestion")[0]
    assert "| 2026-10-23 | skipped | no sane close | — | — |" in page
    again = daily.run(TUE_0800, paths, clean_root=clean, shadows=False)
    assert again == [UNCHECKED_23, HOLDING_26, "reconciled: OK"]
    assert _days(paths) == [*BEFORE, ("2026-10-23", True), ("2026-10-26", False)]


def test_a_close_that_comes_too_late_is_final_and_never_processed_out_of_order(tmp_path: Path) -> None:
    """Friday's sane close arrives on Tuesday, after Monday was processed without it: no row is
    re-done or added for Friday, the record still reconciles, and the page says it is final."""
    paths = _to_friday(tmp_path)
    daily.run(MON_RUN, paths, clean_root=_clean(tmp_path, WITHOUT_FRIDAY, "2026-10-26"), shadows=False)
    late = [*WITHOUT_FRIDAY[:4], "2026-10-23", "2026-10-26", "2026-10-27"]
    lines = daily.run(TUE_RUN, paths, clean_root=_clean(tmp_path, sorted(late), "2026-10-27"), shadows=False)
    assert _days(paths) == [*BEFORE, ("2026-10-23", True), ("2026-10-26", False), ("2026-10-27", False)]
    assert lines[0] == ("SKIPPED for good: Fri 23 Oct (2026-10-23)'s VWRL close came after a later session "
                        "was processed (£137.00, above the stop of £117.91 then) -- the as-if record keeps "
                        "it skipped; nothing recorded changes.")
    assert not any(x.startswith("UNCHECKED") for x in lines) and lines[-1] == "reconciled: OK"


def test_a_late_close_never_moves_a_fill_already_recorded(tmp_path: Path) -> None:
    """Thursday processed on Thursday evening, its close at the stop: the URGENT-EXIT's as-if SELL
    fills at the next open there is -- Monday's, Friday being missing. Friday's bar arriving on
    Tuesday must not move that fill back to Friday's open: the recorded Monday would not reconcile."""
    paths = _armed(tmp_path)
    week = ["2026-10-19", "2026-10-20", "2026-10-21"]
    daily.run(THU_RUN, paths, clean_root=_clean(tmp_path, week, "2026-10-21"), shadows=False)
    thursday = [*week, "2026-10-22"]
    daily.run(THU_2130, paths, clean_root=_clean(tmp_path, thursday, "2026-10-22", close_22=117.0), shadows=False)
    assert [r["kind"] for r in state.rows(paths.log("suggestions"))][-1] == "urgent-exit"
    daily.run(MON_RUN, paths, clean_root=_clean(tmp_path, [*thursday, "2026-10-26"], "2026-10-26", close_22=117.0),
              shadows=False)
    assert (state.rows(paths.log("days"))[-1]["session"], state.rows(paths.log("days"))[-1]["held"]) == (
        "2026-10-26", False)                                                      # sold at Monday's open
    late = [*thursday, "2026-10-23", "2026-10-26", "2026-10-27"]
    lines = daily.run(TUE_RUN, paths, clean_root=_clean(tmp_path, late, "2026-10-27", close_22=117.0),
                      shadows=False)
    assert not any(x.startswith("RED") for x in lines) and lines[-1] == "reconciled: OK"
