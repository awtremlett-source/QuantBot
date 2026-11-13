"""QT-33 C: when London's closes really arrive -- a measurement only (PLAN_V3 S9, note 2026-11-13).

Operator, 2026-11-13 07:42 (verbatim): "Update this for Today (Friday) i ran out of useage. its currently
07:42" -- no GO given. Three mornings running Yahoo sent London's newest session with no close at 07:04
UTC; by 08:05 the row had vanished; by 10:05 it had its close (QT-33 A2, from the manifest). Every
recorder run now appends one line to data/clean/arrival.jsonl saying, per market and stop-driving name,
whether the newest finished session is present, blank, refused, absent or not fetched. Offline: QT-32's
stub feed on the real exchange calendars, the real ingest, tmp stores.
"""

from __future__ import annotations

import ast
import json
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from qb2.data import arrival, daily_step
from tests.qb2.test_qt32_behind import (LONDON, MON_9, TUE_0700, TUE_0800, TUE_0900, Feed, blank, marker,
                                        run, to_friday)

REPO = Path(__file__).resolve().parents[2]


class Gone(Feed):
    """Yahoo at 08:05: the session's row not sent at all for the names in ``gone``."""

    def __init__(self, last: date, gone: Iterable[tuple[str, date]]) -> None:
        super().__init__(last)
        self.gone = set(gone)

    def __call__(self, symbol: str) -> pd.DataFrame:
        frame = super().__call__(symbol)
        return frame[[(symbol, d) not in self.gone for d in pd.DatetimeIndex(frame.index).date]]


def lines(tmp: Path) -> list[dict[str, Any]]:
    path = tmp / "clean" / arrival.LOG
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


def test_each_run_logs_whether_the_newest_close_is_present_blank_or_absent(tmp_path: Path) -> None:
    """The work item's check: Thursday 12 Nov as Yahoo really served it, on Monday 9's dates."""
    to_friday(tmp_path)
    before = len(lines(tmp_path))                                    # the Saturday top-up's own line
    run(tmp_path, TUE_0700, Feed(MON_9, blank(MON_9)))               # 07:04: sent with no close
    run(tmp_path, TUE_0800, Gone(MON_9, blank(MON_9)))               # 08:05: not sent at all
    run(tmp_path, TUE_0900, Feed(MON_9))                             # 10:05: arrived
    quiet = Feed(MON_9)
    run(tmp_path, TUE_0900 + timedelta(hours=1), quiet)              # nothing missing: nothing fetched
    seven, eight, nine, ten = lines(tmp_path)[before:]
    assert quiet.calls == [] and len(lines(tmp_path)) == before + 4  # one line a run, appended
    assert [x["at"] for x in (seven, eight, nine, ten)] == [
        "2026-11-10T07:00:00+00:00", "2026-11-10T08:00:00+00:00", "2026-11-10T09:00:00+00:00",
        "2026-11-10T10:00:00+00:00"]
    for name in ("LSE", "VWRL.L", "VWRP.L"):
        assert [x[name]["session"] for x in (seven, eight, nine, ten)] == ["2026-11-09"] * 4
        assert [x[name]["state"] for x in (seven, eight, nine, ten)] == ["blank", "absent", "present", "present"]
    assert seven["LSE"]["names"] == {"blank": 3} and eight["LSE"]["names"] == {"absent": 3}
    assert "names" not in nine["LSE"]                                # counted only while not present
    assert all(x["US"] == {"session": "2026-11-09", "state": "present"} for x in (seven, eight, nine, ten))
    assert seven["fetched"] > 3 and eight["fetched"] == len(LONDON) and ten["fetched"] == 0


def test_the_watch_never_changes_what_the_fetch_returns() -> None:
    watch = arrival.Watch()
    frame = Feed(MON_9)("VWRL.L")
    assert watch.wrap(lambda s: frame)("VWRL.L") is frame            # the very object, untouched
    assert watch.sent["VWRL.L"]["2026-11-09"] is False and len(watch.sent["VWRL.L"]) == arrival.TAIL
    odd = pd.DataFrame({"close": [1.0]}, index=["not a date"])
    assert watch.wrap(lambda s: odd)("ODD") is odd                   # unreadable: noted as trouble only
    assert watch.trouble and watch.trouble[0].startswith("ODD:")

    def broken(symbol: str) -> pd.DataFrame:
        raise ConnectionError("the feed is down")
    with pytest.raises(ConnectionError):                             # still the ingest's to name as lost
        watch.wrap(broken)("VWRP.L")


def test_a_failed_arrival_write_is_said_and_the_top_up_is_unchanged(tmp_path: Path) -> None:
    to_friday(tmp_path)
    twin = tmp_path / "twin"
    to_friday(twin)
    (tmp_path / "clean" / arrival.LOG).unlink()
    (tmp_path / "clean" / arrival.LOG).mkdir()                       # the log cannot be written
    line = run(tmp_path, TUE_0700, Feed(MON_9, blank(MON_9)))
    good = run(twin, TUE_0700, Feed(MON_9, blank(MON_9)))
    assert "arrival log not written" in line and "arrival log" not in good
    assert line.startswith(good) and "· RED" in line                 # the top-up's own words, unchanged
    mine, theirs = marker(tmp_path), marker(twin)
    assert {k: v for k, v in mine.items() if k != "retry_s"} == {k: v for k, v in theirs.items() if k != "retry_s"}


def test_the_states_for_a_refused_and_an_unfetched_session() -> None:
    markets = {"VWRL.L": "LSE", "VWRP.L": "LSE", "AAPL": "US"}
    watch = arrival.Watch(sent={"VWRL.L": {"2026-11-09": False}})   # sent WITH a close, yet not stored
    got = arrival.states(MON_9, {"LSE": "2026-11-06", "US": "2026-11-09"}, {"VWRP.L": {date(2026, 11, 6)}},
                         markets, watch)
    assert got["VWRL.L"] == {"session": "2026-11-09", "state": "refused"}
    assert got["VWRP.L"] == {"session": "2026-11-09", "state": "not fetched"}
    assert got["LSE"] == {"session": "2026-11-09", "state": "refused", "names": {"refused": 1}}
    assert got["US"] == {"session": "2026-11-09", "state": "present"}


def test_nothing_but_people_reads_the_arrival_log() -> None:
    """Premortem: a rule must never start reading the log as a price feed. Only the daily step imports
    the module that writes it, and no other qb2 code names the file."""
    importers, naming = [], []
    for path in (REPO / "qb2").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        name = path.relative_to(REPO).as_posix()
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.ImportFrom) and any(a.name == "arrival" for a in node.names):
                importers.append(name)
            if isinstance(node, ast.Import) and any(a.name.endswith(".arrival") for a in node.names):
                importers.append(name)
        if "arrival.jsonl" in text and name != "qb2/data/arrival.py":
            naming.append(name)
    assert importers == ["qb2/data/daily_step.py"] and naming == []


def test_the_marker_the_log_reads_is_the_daily_steps_own(tmp_path: Path) -> None:
    to_friday(tmp_path)
    assert (tmp_path / "clean" / daily_step.MARKER).is_file()
    assert lines(tmp_path)[-1]["LSE"] == {"session": "2026-11-06", "state": "present"}
    assert datetime.fromisoformat(lines(tmp_path)[-1]["at"]).tzinfo is not None
