"""QT-33 E and F: SMEA.L accepted in writing; the advisor's RED names a held-back close (PLAN_V3 S9,
note 2026-11-13).

Operator, 2026-11-13 07:42 (verbatim): "Update this for Today (Friday) i ran out of useage. its currently
07:42" -- no GO given. E: SMEA.L's store ends 24 Nov 2023 (QT-20's unit break, quarantined for good); it
stays on the advisor list and in the line, marked accepted. F: on Wed 11 and Thu 12 Nov the top-up ran on
time and held VWRL's close back until about 10:05 UTC; a RED then would have blamed "the daily top-up is
overdue". Offline: QT-32's stub feed on the real calendars, the real ingest and the real advisor.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from qb2.advisor import daily, held_back, state
from qb2.data import behind, daily_step
from tests.qb2.test_qt32_behind import MON_9, TUE_0700, Feed, armed, blank, run

TUE_1030 = datetime(2026, 11, 10, 10, 30, tzinfo=timezone.utc)      # past Monday's due time, 10:00 UK


def advisor(tmp: Path, now: datetime) -> list[str]:
    return daily.run(now, state.Paths.under(tmp), clean_root=tmp / "clean", shadows=False)


def test_the_red_names_the_close_the_top_up_held_back(tmp_path: Path) -> None:
    """Case 1: the top-up ran at 07:00 and 10:30 and held Monday back: the RED says so, by name."""
    armed(tmp_path)
    run(tmp_path, TUE_0700, Feed(MON_9, blank(MON_9)))
    run(tmp_path, TUE_1030, Feed(MON_9, blank(MON_9)))
    red = [x for x in advisor(tmp_path, TUE_1030) if x.startswith("RED")]
    assert red == ["RED: held back: LSE 2026-11-09, VWRL.L 2026-11-09, VWRP.L 2026-11-09 not delivered yet; "
                   "retrying each run (due Tue 10 Nov 10:00 UK): the stop has been unchecked since 2026-11-06"]


def test_the_red_still_says_overdue_when_the_top_up_never_ran(tmp_path: Path) -> None:
    """Case 2: no top-up since Saturday (the PC off): the top-up really is overdue, and it says so."""
    armed(tmp_path)
    red = [x for x in advisor(tmp_path, TUE_1030) if x.startswith("RED")]
    assert red == ["RED: the daily top-up is overdue (due Tue 10 Nov 10:00 UK): the stop has been unchecked "
                   "since 2026-11-06"]


def test_a_gap_and_vwrls_own_missing_close_keep_their_words(tmp_path: Path) -> None:
    seen = {"behind": {"VWRL.L": {"session": "2026-11-09", "since": "x", "later": "2026-11-10"},
                       "US": {"session": "2026-11-10", "since": "x", "later": None}}}
    assert held_back.held(seen) == ("held back: US 2026-11-10 not delivered yet; gap: VWRL.L 2026-11-09 never "
                                    "delivered; retrying each run")
    assert held_back.held({"behind": {}}) == held_back.held({}) == ""
    (tmp_path / daily_step.MARKER).write_text(json.dumps(seen), encoding="utf-8")
    fri, mon = date(2026, 11, 6), MON_9
    assert held_back.cause(fri, mon, tmp_path) == held_back.MISSING          # VWRL's own bars stop short
    assert held_back.cause(fri, fri, tmp_path).startswith("held back: US")
    assert held_back.cause(fri, fri, tmp_path / "none") == held_back.OVERDUE  # no marker: as before


def test_smea_is_named_in_the_line_and_marked_accepted_only_for_its_known_hole() -> None:
    seen = {"short": {"CSH2.L": {"session": "2026-10-26"}, "SMEA.L": {"session": "2023-11-27"}},
            "retried": 2, "retry_s": 1.9}
    _, tail = behind.words(seen)
    assert "CSH2.L 2026-10-26, SMEA.L 2023-11-27 (accepted)" in tail and tail.count("(accepted)") == 1
    _, fresh = behind.words({"short": {"SMEA.L": {"session": "2026-11-12"}}})
    assert "SMEA.L 2026-11-12" in fresh and "accepted" not in fresh        # a NEW hole is never accepted
