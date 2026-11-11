"""QT-32: the daily step never calls a day done while a close is missing (PLAN_V3 S9, note 2026-11-11).

Operator, 2026-11-10 18:08 (verbatim): "QT-32, no GO" -- the box fixes the blank-price bug only.
On Tue 10 Nov 2026 Yahoo served Monday's London closes blank; the store rightly refused them, and the daily
step still wrote fetched_through 2026-11-09, so nothing retried until Wednesday and the 08:00 line read
"fresh to 2026-11-06 · OK" (QT-31 A2). Now a market or a stop-driving name (VWRL.L, VWRP.L) behind its last
finished session is BEHIND: named in the marker, retried every run, RED, and fetched_through -- the
advisor's and the bot pot's one door -- is held before it. Offline: a stub feed on the real exchange
calendars, the real ingest, tmp stores and tmp advisor files.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import exchange_calendars as xcals  # type: ignore[import-untyped]
import pandas as pd
import pytest

from qb2.advisor import bot_pot, daily, live, price_check, scorecard, state
from qb2.data import daily_step
from qb2.execution.safety import ADVISOR, Blocked
from qb2.guard import brakes
from qb2.ingest import daily as ingest

UTC = timezone.utc
LON = {"quote_currency": "GBP", "exchange": "London Stock Exchange", "kind": "ETF"}
NAMES = [{"yfinance": "VWRL.L", **LON}, {"yfinance": "VWRP.L", **LON}, {"yfinance": "BP.L", **LON},
         {"yfinance": "AAPL", "quote_currency": "USD", "exchange": "NASDAQ", "kind": "Stock"},
         {"yfinance": "^VIX", "quote_currency": "USD", "exchange": "Cboe (New York clock)"}]
LONDON = ("VWRL.L", "VWRP.L", "BP.L")
FRI_6, MON_9, TUE_10 = date(2026, 11, 6), date(2026, 11, 9), date(2026, 11, 10)
SAT_31_OCT, SAT_7 = datetime(2026, 10, 31, 12, 0, tzinfo=UTC), datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
TUE_0700, TUE_0800, TUE_0900 = (datetime(2026, 11, 10, h, 0, tzinfo=UTC) for h in (7, 8, 9))
WED_0700, WED_0800 = (datetime(2026, 11, 11, h, 0, tzinfo=UTC) for h in (7, 8))
REAL_10_NOV_MARKER = {"fetched_through": "2026-11-09", "at": "2026-11-10T07:03:59+00:00", "fetched": 223,
                      "lost": [], "refused": {}, "kept": {"GBPUSD=X": ["2026-11-09"]}, "corrected": {},
                      "newest": {"US": "2026-11-09", "LSE": "2026-11-06"}}   # data/clean/daily_step.json


class Feed:
    """Yahoo as the daily step sees it: each name's sessions on its own exchange from 1 Oct to ``last``;
    a blank close (NaN, as on 10 Nov) on each (name, day) in ``blank``. Open 100, close 100, except
    ``closes``. Every call is counted."""

    def __init__(self, last: date, blank: Iterable[tuple[str, date]] = (),
                 closes: dict[tuple[str, date], float] | None = None) -> None:
        self.last, self.blank, self.closes = last, set(blank), closes or {}
        self.calls: list[str] = []

    def __call__(self, symbol: str) -> pd.DataFrame:
        self.calls.append(symbol)
        london = symbol.endswith(".L") or symbol == ingest.FX_PAIR
        cal = xcals.get_calendar("XLON" if london else "XNYS")
        days = list(cal.sessions_in_range(pd.Timestamp("2026-08-03"), pd.Timestamp(self.last)).date)
        base = {ingest.FX_PAIR: 1.30, "^VIX": 15.0}.get(symbol, 100.0)
        close = [float("nan") if (symbol, d) in self.blank else self.closes.get((symbol, d), base) for d in days]
        opens = [base] * len(days)                                       # a blank CLOSE, as Yahoo served it
        tz = "Europe/London" if london else "America/New_York"
        index = pd.DatetimeIndex([pd.Timestamp(d).tz_localize(tz) for d in days])
        return pd.DataFrame({"open": opens, "high": [max(o, c) for o, c in zip(opens, close)],
                             "low": [min(o, c) for o, c in zip(opens, close)], "close": close,
                             "volume": 1e6}, index=index)


def run(tmp: Path, now: datetime, feed: Feed) -> str:
    return daily_step.run_if_due(now, clean_root=tmp / "clean", fetch=feed, entries=NAMES,
                                 digest_dir=tmp / "digest")


def marker(tmp: Path) -> dict[str, Any]:
    return dict(json.loads((tmp / "clean" / daily_step.MARKER).read_text(encoding="utf-8")))


def blank(day: date, names: Iterable[str] = LONDON) -> list[tuple[str, date]]:
    return [(n, day) for n in names]


def to_friday(tmp: Path) -> None:
    """The store complete through Fri 6 Nov, as on the morning of Tue 10 Nov before the 07:00 run."""
    run(tmp, SAT_7, Feed(FRI_6))
    assert marker(tmp)["fetched_through"] == "2026-11-06"


# ------------------------------------------------------------------------- C1 a, b, c: the marker, the line


def test_a_blank_london_close_is_red_and_retried_until_it_arrives(tmp_path: Path) -> None:
    to_friday(tmp_path)
    line = run(tmp_path, TUE_0700, Feed(MON_9, blank(MON_9)))
    seen = marker(tmp_path)
    assert set(seen["behind"]) == {"LSE", "VWRL.L", "VWRP.L"}             # a market, and each stop name
    assert {e["session"] for e in seen["behind"].values()} == {"2026-11-09"}
    assert all(e["since"] == "2026-11-10T07:00:00+00:00" for e in seen["behind"].values())
    assert seen["fetched_through"] == "2026-11-06" and seen["topped_up"] == "2026-11-09"
    assert "· RED" in line and "BEHIND" in line and "VWRL.L 2026-11-09" in line
    still = Feed(MON_9, blank(MON_9))
    eight = run(tmp_path, TUE_0800, still)                               # not strict: the QT-31 08:00 case
    assert sorted(still.calls) == sorted(LONDON)                         # the behind names only, once each
    assert "· RED" in eight and "BEHIND" in eight and "· OK" not in eight
    assert marker(tmp_path)["behind"]["LSE"]["since"] == "2026-11-10T07:00:00+00:00"   # first seen, kept
    arrived = Feed(MON_9)
    nine = run(tmp_path, TUE_0900, arrived)
    assert sorted(arrived.calls) == sorted(LONDON)
    assert nine.startswith("Daily store: fresh to 2026-11-09 · OK"), nine
    assert marker(tmp_path)["behind"] == {} and marker(tmp_path)["fetched_through"] == "2026-11-09"
    quiet = Feed(MON_9)
    assert run(tmp_path, TUE_0900 + timedelta(hours=1), quiet).startswith("Daily store: fresh to 2026-11-09 · OK")
    assert quiet.calls == []                                             # arrived: nothing retried again


def test_the_retry_takes_the_behind_names_once_a_run_and_says_how_long(tmp_path: Path) -> None:
    to_friday(tmp_path)
    run(tmp_path, TUE_0700, Feed(MON_9, blank(MON_9)))
    for hour in (8, 9, 10):
        feed = Feed(MON_9, blank(MON_9))
        line = run(tmp_path, datetime(2026, 11, 10, hour, tzinfo=UTC), feed)
        assert sorted(feed.calls) == sorted(LONDON)                      # never the US names, never twice
        assert "retried 3 names in " in line
        assert marker(tmp_path)["retry_s"] >= 0.0


# ------------------------------------------------------------------- C2 1, 2: calendars, not weekdays


class Split(Feed):
    """London and New York each to their own last session (a holiday on one side only)."""

    def __init__(self, lon: date, us: date) -> None:
        super().__init__(max(lon, us))
        self.lon, self.us = lon, us

    def __call__(self, symbol: str) -> pd.DataFrame:
        self.last = self.lon if symbol.endswith(".L") or symbol == ingest.FX_PAIR else self.us
        return super().__call__(symbol)


@pytest.mark.parametrize(("before", "last", "after", "now"), [
    (datetime(2026, 12, 24, 21, 30, tzinfo=UTC), date(2026, 12, 24), date(2026, 12, 29),
     datetime(2026, 12, 30, 7, 0, tzinfo=UTC)),                   # 25 Dec (both shut), 28 Dec (London only)
    (datetime(2026, 8, 28, 21, 30, tzinfo=UTC), date(2026, 8, 28), date(2026, 9, 1),
     datetime(2026, 9, 2, 7, 0, tzinfo=UTC))])                      # Mon 31 Aug: a UK bank holiday
def test_a_london_holiday_is_never_read_as_missing(tmp_path: Path, before: datetime, last: date, after: date,
                                                    now: datetime) -> None:
    assert run(tmp_path, before, Feed(last)).startswith(f"Daily store: fresh to {last} · OK")
    line = run(tmp_path, now, Feed(after))                         # the top-up's window spans the holiday
    assert line.startswith(f"Daily store: fresh to {after} · OK"), line
    assert marker(tmp_path)["behind"] == {} and marker(tmp_path)["short"] == {}
    assert marker(tmp_path)["fetched_through"] == after.isoformat()


def test_a_us_only_holiday_leaves_london_and_vix_green(tmp_path: Path) -> None:
    """Thanksgiving, Thu 26 Nov 2026: New York shut, London open -- the morning after, and the weekend."""
    run(tmp_path, datetime(2026, 11, 25, 21, 30, tzinfo=UTC), Feed(date(2026, 11, 25)))
    line = run(tmp_path, datetime(2026, 11, 27, 7, 0, tzinfo=UTC), Split(date(2026, 11, 26), date(2026, 11, 25)))
    assert line.startswith("Daily store: fresh to 2026-11-25 · OK"), line
    assert "^VIX" not in line and marker(tmp_path)["fetched_through"] == "2026-11-26"
    off = tmp_path / "off"                                          # the PC off from Wed night to Saturday
    run(off, datetime(2026, 11, 25, 21, 30, tzinfo=UTC), Feed(date(2026, 11, 25)))
    line = run(off, datetime(2026, 11, 28, 12, 0, tzinfo=UTC), Feed(date(2026, 11, 27)))      # spans Thu 26
    assert line.startswith("Daily store: fresh to 2026-11-27 · OK"), line
    assert marker(off)["behind"] == {} and marker(off)["short"] == {}


# --------------------------------------------------------- C2 9: a minor name, and a whole market


def test_a_minor_name_blank_is_named_but_does_not_hold_the_stops(tmp_path: Path) -> None:
    to_friday(tmp_path)
    line = run(tmp_path, TUE_0700, Feed(MON_9, blank(MON_9, ["BP.L"])))
    seen = marker(tmp_path)
    assert seen["behind"] == {} and seen["fetched_through"] == "2026-11-09"     # the stops go on
    assert seen["short"]["BP.L"]["session"] == "2026-11-09"
    assert "· OK" in line and "BP.L 2026-11-09" in line
    later = run(tmp_path, WED_0700, Feed(TUE_10, blank(MON_9, ["BP.L"])))   # Tuesday came, Monday never
    assert "· OK" in later and "BP.L 2026-11-09" in later                  # still named, still not held
    assert marker(tmp_path)["fetched_through"] == "2026-11-10"
    feed = Feed(TUE_10)
    assert "BP.L" not in run(tmp_path, WED_0800, feed) and feed.calls == ["BP.L"]


def test_a_whole_us_blank_is_behind_and_holds_the_stop_path(tmp_path: Path) -> None:
    to_friday(tmp_path)
    line = run(tmp_path, TUE_0700, Feed(MON_9, blank(MON_9, ["AAPL", "^VIX"])))
    seen = marker(tmp_path)
    assert set(seen["behind"]) == {"US"} and seen["fetched_through"] == "2026-11-06"
    assert "· RED" in line and "US 2026-11-09" in line


# ------------------------------------------------------------------------- C1 f: never delivered


def test_a_close_that_never_arrives_stays_red_and_is_named_a_gap(tmp_path: Path) -> None:
    to_friday(tmp_path)
    run(tmp_path, TUE_0700, Feed(MON_9, blank(MON_9)))
    line = run(tmp_path, WED_0700, Feed(TUE_10, blank(MON_9)))            # Tuesday came, Monday never
    seen = marker(tmp_path)
    assert seen["fetched_through"] == "2026-11-06" and seen["topped_up"] == "2026-11-10"
    assert seen["behind"]["VWRL.L"] == {"session": "2026-11-09", "since": "2026-11-10T07:00:00+00:00",
                                        "later": "2026-11-10"}
    assert "· RED" in line and "gap: VWRL.L 2026-11-09 never delivered" in line
    assert "gap: VWRP.L 2026-11-09 never delivered" in line
    stored = ingest.load("VWRL.L", tmp_path / "clean")
    assert stored is not None and MON_9 not in set(pd.DatetimeIndex(stored.index).date)   # never filled


# --------------------------------------------------------------- C2 10, 6, 7, 8: the edges


def test_a_pre_qt32_marker_is_read_correctly_on_first_deploy(tmp_path: Path) -> None:
    """The real 10 Nov 07:03 marker (fetched_through Monday, London's Monday absent): the first run of the
    new code, at 08:00 with no top-up due, still finds London behind and retries it at once."""
    to_friday(tmp_path)
    run(tmp_path, TUE_0700, Feed(MON_9, blank(MON_9)))                   # the store as on 10 Nov: US Monday in
    (tmp_path / "clean" / daily_step.MARKER).write_text(json.dumps(REAL_10_NOV_MARKER), encoding="utf-8")
    assert live.final_through(tmp_path / "clean") == MON_9               # the old meaning, read as before
    feed = Feed(MON_9, blank(MON_9))
    line = run(tmp_path, TUE_0800, feed)
    assert sorted(feed.calls) == sorted(LONDON)
    assert "· RED" in line and marker(tmp_path)["fetched_through"] == "2026-11-06"
    assert live.final_through(tmp_path / "clean") == FRI_6


def test_a_crash_mid_write_leaves_the_marker_readable_and_the_next_run_retries(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    to_friday(tmp_path)
    run(tmp_path, TUE_0700, Feed(MON_9, blank(MON_9)))
    before = marker(tmp_path)
    real = Path.write_text

    def torn(self: Path, data: str, *a: Any, **k: Any) -> int:          # the power goes mid-write
        if self.name.startswith(daily_step.MARKER):
            real(self, data[: len(data) // 2], *a, **k)
            raise OSError("planted: power lost mid-write")
        return real(self, data, *a, **k)
    monkeypatch.setattr(Path, "write_text", torn)
    line = run(tmp_path, TUE_0800, Feed(MON_9))
    monkeypatch.undo()
    assert "RED" in line and marker(tmp_path) == before                  # readable, and as it was
    retry = Feed(MON_9)
    assert run(tmp_path, TUE_0900, retry).startswith("Daily store: fresh to 2026-11-09 · OK")
    assert sorted(retry.calls) == sorted(LONDON)


def test_a_late_close_the_provider_later_corrects_is_still_named(tmp_path: Path) -> None:
    to_friday(tmp_path)
    run(tmp_path, TUE_0700, Feed(MON_9, blank(MON_9)))
    run(tmp_path, TUE_0800, Feed(MON_9))                                 # arrives at 100.00
    line = run(tmp_path, WED_0700, Feed(TUE_10, closes={("VWRL.L", MON_9): 101.0}))
    assert "VWRL.L 2026-11-09 100.00 → 101.00" in line                   # the QT-26 path, unchanged


def test_the_advisor_never_reads_a_held_back_session_and_qt24_still_stops(tmp_path: Path) -> None:
    to_friday(tmp_path)
    run(tmp_path, TUE_0700, Feed(MON_9, blank(MON_9, ["VWRP.L", "BP.L"])))   # VWRL's Monday is stored...
    clean = tmp_path / "clean"
    assert live.final_through(clean, TUE_0800) == FRI_6                  # ...but VWRP's is not: held
    assert list(live.days_of(live.bars("VWRL.L", "LSE", FRI_6, clean_root=clean).index, "LSE"))[-1] == FRI_6
    (clean / daily_step.MARKER).write_text(json.dumps({**marker(tmp_path), "fetched_through": "2026-11-10"}),
                                           encoding="utf-8")
    with pytest.raises(Blocked, match="STOP"):
        live.final_through(clean, datetime(2026, 11, 10, 12, 0, tzinfo=UTC))   # London still trading


# ------------------------------------- C1 e: the advisor, the bot pot and P22, each session exactly once


def armed(tmp: Path) -> state.Paths:
    """Store through Fri 30 Oct; the advisor armed then, its first review a BUY (filled Mon 2 Nov's open);
    the bot pot armed from Mon 2 Nov. Then the store through Fri 6, both processed: both hold, stops 85."""
    run(tmp, SAT_31_OCT, Feed(date(2026, 10, 30)))
    paths = state.Paths.under(tmp)
    state.arm(paths, date(2026, 10, 30), SAT_31_OCT, "test")
    brakes.Brakes(paths.brakes).update(ADVISOR, scorecard.POT_GBP, at=SAT_31_OCT)
    jobs(tmp, SAT_31_OCT, first=True)
    run(tmp, SAT_7, Feed(FRI_6))
    jobs(tmp, SAT_7)
    return paths


def jobs(tmp: Path, now: datetime, first: bool = False) -> None:
    paths, clean = state.Paths.under(tmp), tmp / "clean"
    daily.run(now, paths, clean_root=clean, first_review=first, shadows=False)
    bot_pot.run(now, bot_pot.beside(paths), paths, clean_root=clean)


def sessions(paths: state.Paths) -> list[tuple[str, bool]]:
    return [(str(r["session"]), bool(r.get("skipped"))) for r in state.rows(paths.log("days"))]


CRASH = {(n, MON_9): 80.0 for n in ("VWRL.L", "VWRP.L")}                 # at or below both stops (85)
VWRP_CRASH = {("VWRP.L", MON_9): 80.0}                                   # the bot pot's own stop only


def test_monday_arrives_later_and_is_processed_once_with_its_stop_hit(tmp_path: Path) -> None:
    paths = armed(tmp_path)
    pot, done = bot_pot.beside(paths), sessions(paths)
    assert done[-1] == ("2026-11-06", False) and sessions(pot)[-1] == ("2026-11-06", False)
    run(tmp_path, TUE_0700, Feed(MON_9, blank(MON_9)))
    jobs(tmp_path, TUE_0700)
    assert sessions(paths) == done                                       # held: nothing processed
    for now in (TUE_0800, TUE_0900):                                     # arrives at 08:00; 09:00 again
        run(tmp_path, now, Feed(MON_9, closes=CRASH))
        jobs(tmp_path, now)
    assert sessions(paths) == [*done, ("2026-11-09", False)]             # once
    assert sessions(pot)[-1] == ("2026-11-09", False) and sessions(pot).count(("2026-11-09", False)) == 1
    exits = [r for r in state.rows(paths.log("suggestions")) if r.get("kind") == "urgent-exit"]
    assert len(exits) == 1 and "£80.00 on 2026-11-09" in str(exits[0]["reason"])    # never suppressed
    sells = [r for r in state.rows(pot.log("signals")) if r["action"] == "SELL"]
    assert [r["session"] for r in sells] == ["2026-11-09"]               # out with ADV-0, that session
    journal = [(r["ticker"], r["session"]) for r in state.rows(price_check.journal(paths))]
    assert journal.count(("VWRL.L", "2026-11-09")) == 1 and journal.count(("VWRP.L", "2026-11-09")) == 1


def test_monday_arriving_after_tuesday_is_processed_first_and_never_skipped(tmp_path: Path) -> None:
    paths = armed(tmp_path)
    pot, done = bot_pot.beside(paths), sessions(paths)
    run(tmp_path, TUE_0700, Feed(MON_9, blank(MON_9)))
    jobs(tmp_path, TUE_0700)
    run(tmp_path, WED_0700, Feed(TUE_10, blank(MON_9)))                  # Tuesday first, Monday still blank
    jobs(tmp_path, WED_0700)
    assert sessions(paths) == done and sessions(pot)[-1] == ("2026-11-06", False)   # no SKIPPED Monday
    run(tmp_path, WED_0800, Feed(TUE_10, closes=VWRP_CRASH))             # Monday arrives
    jobs(tmp_path, WED_0800)
    assert sessions(paths) == [*done, ("2026-11-09", False), ("2026-11-10", False)]   # Monday first
    assert sessions(pot)[-2:] == [("2026-11-09", False), ("2026-11-10", False)]
    sells = [(r["kind"], r["session"]) for r in state.rows(pot.log("signals")) if r["action"] == "SELL"]
    assert sells == [("stop", "2026-11-09")]                             # its own stop, on Monday's close


# ------------------------------------------------------------------- Part E: the status page's pointer


def test_the_status_page_points_at_the_report_that_explains_the_anchor(tmp_path: Path) -> None:
    """Not yet anchored, the page names the newest report that explains why: QT-32's (CSH2's split)."""
    lines = price_check.page_lines(state.Paths.under(tmp_path), "VWRL.L")
    assert lines[-1] == "VWRL anchor: not set up — see the QT-32 report"
    report = Path(__file__).resolve().parents[2] / "docs" / "reports" / "QT-32.md"
    assert "CSH2" in report.read_text(encoding="utf-8") and "VWRL" in report.read_text(encoding="utf-8")
