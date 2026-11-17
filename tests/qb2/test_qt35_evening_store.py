"""QT-35 A: the evening "Daily store" line is judged strictly only after a real new-day top-up. Offline.

From 17:00 UK London has closed but New York has not, so the target session is still yesterday. Retrying the
"short" names (CSH2.L, SMEA.L) made the line judge strictly and want London's same-day close: RED from 17:00
to 20:00 for no reason (QT-33/QT-34 PROPOSE 2). A truly missing VWRL/VWRP close stays BEHIND, RED and held.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from tests.qb2.test_qt32_behind import FRI_6, MON_9, TUE_0700, Feed, blank, marker, run, to_friday

TUE_1700 = datetime(2026, 11, 10, 17, 0, tzinfo=timezone.utc)      # London shut, New York open


def test_short_name_retries_alone_do_not_turn_the_evening_line_red(tmp_path: Path) -> None:
    to_friday(tmp_path)
    assert "· OK" in run(tmp_path, TUE_0700, Feed(MON_9, blank(MON_9, ["BP.L"])))
    feed = Feed(MON_9, blank(MON_9, ["BP.L"]))
    line = run(tmp_path, TUE_1700, feed)
    assert feed.calls == ["BP.L"]                                   # the short name retried, nothing else
    assert "· OK" in line and "· RED" not in line, line


def test_a_missing_vwrl_close_is_still_red_and_held_in_the_evening(tmp_path: Path) -> None:
    to_friday(tmp_path)
    run(tmp_path, TUE_0700, Feed(MON_9, blank(MON_9)))
    line = run(tmp_path, TUE_1700, Feed(MON_9, blank(MON_9)))
    assert "· RED" in line and "BEHIND" in line and "VWRL.L 2026-11-09" in line
    assert marker(tmp_path)["fetched_through"] == FRI_6.isoformat()   # the stop path stays held
