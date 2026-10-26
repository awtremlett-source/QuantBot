"""QT-25 B: the daily front door refuses a row whose session had not closed when it was fetched. Offline.

The cause (QT-24): the store held a 09:25 New York pre-open ^VIX snapshot as 16 Oct's "close". Every
top-up rewrites each file whole, so such a row lasted only until that name's next good fetch -- and
for good while that fetch kept failing, read as final once the marker passed its day. The door now
compares each row's session close, on its exchange's own clock, with the fetch time: a session
still trading (or not yet open) is refused, said in the manifest and the "Daily store:" line, and
fetched again by the next top-up once it has closed. The fetcher is injected: no network.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from qb2.advisor import daily as advisor_daily
from qb2.advisor import live, state
from qb2.data import daily_step
from qb2.guard import stops
from qb2.ingest import daily

UK = ZoneInfo("Europe/London")
VIX_HAND_LOAD = datetime(2026, 10, 16, 13, 25, 10, tzinfo=timezone.utc)   # QT-19: 09:25 New York
FRI_1410_UK = datetime(2026, 10, 23, 13, 10, tzinfo=timezone.utc)         # BST: London trading
FRI_1810_UK = datetime(2026, 10, 23, 17, 10, 32, tzinfo=timezone.utc)     # the real top-up: NY trading
MON_0611_UK = datetime(2026, 10, 26, 6, 11, 59, tzinfo=timezone.utc)      # GMT: Friday final everywhere
AAPL = {"yfinance": "AAPL", "quote_currency": "USD", "exchange": "NASDAQ"}
VWRL = {"yfinance": "VWRL.L", "quote_currency": "GBP", "exchange": "London Stock Exchange"}
ZONES = {"AAPL": "America/New_York", "VWRL.L": "Europe/London", "^VIX": "America/Chicago",
         daily.FX_PAIR: "Europe/London"}       # ^VIX: the provider's own Chicago label
SNAPSHOT, FINAL = 101.0, 102.0                 # the last row's close: mid-session, then the close


def vix_entry() -> dict[str, object]:
    return next(e for e in daily_step.wanted() if e["yfinance"] == "^VIX")


class _Fetch:
    """30 daily bars to ``end`` for every name, as the provider stamps them; the last bar's close is
    ``last`` (a snapshot or the real close), so the two can be told apart. ``fail``: nothing back."""

    def __init__(self, end: str, last: float, fail: tuple[str, ...] = ()) -> None:
        self.end, self.last, self.fail = end, last, fail

    def __call__(self, symbol: str) -> pd.DataFrame | None:
        if symbol in self.fail:
            return None
        index = pd.bdate_range(end=self.end, periods=30, tz=ZONES[symbol])
        close = [100.0] * 29 + [self.last]
        return pd.DataFrame({"open": 100.0, "high": 105.0, "low": 95.0, "close": close,
                             "volume": 1000.0}, index=index)


def _newest(symbol: str, root: Path) -> tuple[str, float]:
    frame = daily.load(symbol, root / "clean")
    assert frame is not None
    return str(pd.Timestamp(frame.index.max()).date()), float(frame["close"].iloc[-1])


def _refusals(root: Path) -> list[dict[str, object]]:
    lines = (root / "clean" / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
    return [row for row in map(json.loads, lines) if row.get("event") == "refused"]


def _top_up(root: Path, now: datetime, fetch: _Fetch) -> str:
    return daily_step.run_if_due(now, clean_root=root / "clean", fetch=fetch,
                                 entries=[AAPL, VWRL, vix_entry()], digest_dir=root / "digest")


# (a) refused at the door, and said -------------------------------------------------------------

def test_a_session_still_trading_is_refused_and_logged(tmp_path: Path) -> None:
    outcome = daily.ingest([AAPL, VWRL], fetch=_Fetch("2026-10-23", SNAPSHOT),
                           clean_root=tmp_path / "clean", include_fx=False, now=FRI_1810_UK)
    assert _newest("AAPL", tmp_path) == ("2026-10-22", 100.0)        # New York closes 21:00 UK (BST)
    assert _newest("VWRL.L", tmp_path) == ("2026-10-23", SNAPSHOT)   # London closed at 16:30 UK
    assert outcome.refused == {"AAPL": ["2026-10-23"]}
    assert [(r["symbol"], r["sessions"], r["closes"], r["at"]) for r in _refusals(tmp_path)] == [
        ("AAPL", ["2026-10-23"], [SNAPSHOT], "2026-10-23T17:10:32+00:00")]
    assert "not closed" in str(_refusals(tmp_path)[0]["reason"])


def test_the_pre_open_vix_snapshot_of_16_october_is_refused(tmp_path: Path) -> None:
    outcome = daily.ingest([vix_entry()], fetch=_Fetch("2026-10-16", SNAPSHOT),
                           clean_root=tmp_path / "clean", include_fx=False, now=VIX_HAND_LOAD)
    assert outcome.refused == {"^VIX": ["2026-10-16"]}
    assert _newest("^VIX", tmp_path) == ("2026-10-15", 100.0)


def test_the_daily_store_line_names_every_refusal(tmp_path: Path) -> None:
    line = _top_up(tmp_path, FRI_1810_UK, _Fetch("2026-10-23", SNAPSHOT))
    assert line == ("Daily store: fresh to 2026-10-22 · OK · 2 rows refused, their session not closed "
                    "when fetched (fetched again once it has): AAPL 2026-10-23, ^VIX 2026-10-23")


# (b) fetched again, and accepted once closed ---------------------------------------------------

def test_a_refused_row_is_fetched_again_and_accepted_once_its_session_has_closed(tmp_path: Path) -> None:
    _top_up(tmp_path, FRI_1810_UK, _Fetch("2026-10-23", SNAPSHOT))
    assert _newest("AAPL", tmp_path)[0] == "2026-10-22"
    line = _top_up(tmp_path, MON_0611_UK, _Fetch("2026-10-23", FINAL))
    assert _newest("AAPL", tmp_path) == ("2026-10-23", FINAL)          # the close, not the snapshot
    assert _newest("^VIX", tmp_path) == ("2026-10-23", FINAL)
    assert line == "Daily store: fresh to 2026-10-23 · OK"


# (c) behind, never current ---------------------------------------------------------------------

def test_a_name_whose_newest_row_was_refused_shows_behind_never_current(tmp_path: Path) -> None:
    _top_up(tmp_path, FRI_1410_UK, _Fetch("2026-10-23", SNAPSHOT))     # London mid-session
    line = _top_up(tmp_path, MON_0611_UK, _Fetch("2026-10-23", FINAL, fail=("VWRL.L",)))
    assert line == ("Daily store: fresh to 2026-10-22 · RED (LSE ends 2026-10-22, 2026-10-23 has "
                    "finished) · 1 not fetched, retrying: VWRL.L")
    through = live.final_through(tmp_path / "clean", MON_0611_UK)
    assert through is not None and str(through) == "2026-10-23"
    bars = live.bars("VWRL.L", "LSE", through, clean_root=tmp_path / "clean")
    assert (str(live.days_of(bars.index, "LSE")[-1]), float(bars["close"].iloc[-1])) == ("2026-10-22", 100.0)


def test_vwrl_behind_the_marker_leaves_the_stop_unchecked_and_says_so(tmp_path: Path) -> None:
    """Live, Mon 26 Oct 06:31 UK: the top-up marked Fri 23 Oct final, but the provider sent no 23 Oct
    row for VWRL.L -- and the advisor's line said nothing, as if its stop had been checked."""
    paths = state.Paths.under(tmp_path)
    index = pd.bdate_range(end="2026-10-22", periods=5, tz="Europe/London")
    bars = pd.DataFrame({"open": 137.0, "high": 138.0, "low": 136.0, "close": 137.06, "volume": 1.0},
                        index=index)
    lines = advisor_daily.today_line(MON_0611_UK, paths, stops.Ledger(paths.stops), bars,
                                     date(2026, 10, 23), [])
    assert lines[0] == ("UNCHECKED: the newest final close is from 2026-10-22 -- the stop was NOT "
                        "checked against 2026-10-23's close or any later price. Look at VWRL yourself "
                        "if markets moved.")
    later = advisor_daily.today_line(datetime(2026, 10, 26, 10, 30, tzinfo=UK), paths,
                                     stops.Ledger(paths.stops), bars, date(2026, 10, 23), [])
    assert later[1].startswith("RED:") and later[1].endswith("unchecked since 2026-10-22")


# (d) this week's clock gap: UK on GMT, New York still on summer time ---------------------------

def test_a_us_session_on_monday_26_october_is_closed_at_2030_uk_not_at_1930(tmp_path: Path) -> None:
    for hour, newest in ((20, "2026-10-26"), (19, "2026-10-23")):
        root = tmp_path / str(hour)
        daily.ingest([AAPL], fetch=_Fetch("2026-10-26", FINAL), clean_root=root / "clean",
                     include_fx=False, now=datetime(2026, 10, 26, hour, 30, tzinfo=UK))
        assert _newest("AAPL", root)[0] == newest, f"{hour}:30 UK"
