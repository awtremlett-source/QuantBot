"""QT-24 B: ^VIX rides the daily top-up, on New York's clock, and a lagging ^VIX is RED. Offline.

The bug: the store's ^VIX ended 16 Oct (one hand load in QT-19, taken at 09:25 New York time,
before the open) while VWRL ran on. Nothing asked for ^VIX again, and the US market's freshness
check read the bot's US shares, so it never went RED: the only sign was the advisor quietly
reading "unsettled". The fetcher is injected: no test here touches the network.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from qb2.advisor import live
from qb2.data import daily_step
from qb2.ingest import daily

THURSDAY_0700_UK = datetime(2026, 10, 22, 6, 0, tzinfo=timezone.utc)   # Wed 21 Oct finished
AAPL = {"yfinance": "AAPL", "quote_currency": "USD", "exchange": "NASDAQ"}
VWRL = {"yfinance": "VWRL.L", "quote_currency": "GBP", "exchange": "London Stock Exchange"}
ZONES = {"AAPL": "America/New_York", "VWRL.L": "Europe/London", "^VIX": "America/Chicago",
         daily.FX_PAIR: "Europe/London"}       # ^VIX: the provider's own Chicago label


def vix_entry() -> dict[str, object]:
    return next(e for e in daily_step.wanted() if e["yfinance"] == "^VIX")


class _Fetch:
    """Daily bars ending on each name's own last day, stamped as the provider stamps them."""

    def __init__(self, last: dict[str, str]) -> None:
        self.last, self.calls = last, list[str]()

    def __call__(self, symbol: str) -> pd.DataFrame:
        self.calls.append(symbol)
        index = pd.bdate_range(end=self.last.get(symbol, "2026-10-21"), periods=30,
                               tz=ZONES[symbol])
        return pd.DataFrame({"open": 16.0, "high": 17.0, "low": 15.0, "close": 16.5,
                             "volume": 0.0}, index=index)


def _top_up(tmp: Path, vix_last: str) -> str:
    return daily_step.run_if_due(THURSDAY_0700_UK, clean_root=tmp / "clean",
                                 fetch=_Fetch({"^VIX": vix_last}),
                                 entries=[AAPL, VWRL, vix_entry()], digest_dir=tmp / "digest")


def test_the_daily_top_up_asks_for_vix() -> None:
    names = [str(e["yfinance"]) for e in daily_step.wanted()]
    assert names.count("^VIX") == 1
    assert {"VWRL.L", "VWRP.L"} <= set(names)                 # beside the advisor's own names


def test_vix_is_stored_on_new_yorks_clock_and_the_advisor_can_read_it(tmp_path: Path) -> None:
    _top_up(tmp_path, "2026-10-21")
    stored = daily.load("^VIX", tmp_path / "clean")
    assert stored is not None and str(stored.index.tz) == "America/New_York"
    raw = _Fetch({"^VIX": "2026-10-21"})("^VIX")
    assert (stored.index == raw.index).all()                  # the same instants, relabelled only
    vix, when = live.vix_before(date(2026, 10, 22), date(2026, 10, 21), tmp_path / "clean")
    assert (vix, when) == (16.5, date(2026, 10, 21))          # read, not refused for its clock


def test_the_top_up_is_clean_when_vix_keeps_pace(tmp_path: Path) -> None:
    assert _top_up(tmp_path, "2026-10-21") == "Daily store: fresh to 2026-10-21 · OK"


def test_one_london_session_behind_is_allowed(tmp_path: Path) -> None:
    assert _top_up(tmp_path, "2026-10-20").endswith("· OK")   # e.g. a US-only holiday


def test_vix_more_than_one_session_behind_vwrl_is_red(tmp_path: Path) -> None:
    line = _top_up(tmp_path, "2026-10-16")                    # the real store's shape
    assert line == ("Daily store: fresh to 2026-10-21 · RED (^VIX ends 2026-10-16, "
                    "3 London sessions behind VWRL.L's 2026-10-21)")
    again = daily_step.status_line(THURSDAY_0700_UK, clean_root=tmp_path / "clean")
    assert again == line                                      # every later run says it too


def test_vix_missing_beside_vwrl_is_red(tmp_path: Path) -> None:
    daily_step.run_if_due(THURSDAY_0700_UK, clean_root=tmp_path / "clean", fetch=_Fetch({}),
                          entries=[AAPL, VWRL], digest_dir=tmp_path / "digest")
    line = daily_step.status_line(THURSDAY_0700_UK, clean_root=tmp_path / "clean")
    assert line.endswith("· RED (^VIX never fetched)")
