"""QT-29 C: the US clock change (Sun 1 Nov 2026), replayed run by run before it happens. Offline.

Every scheduled recorder run from Thu 29 Oct 19:00 to Wed 4 Nov 08:00 UK (07:00-20:00 hourly, weekdays)
runs the real chain on a fixture store: the daily top-up through the door, then the advisor, then the bot
pot. The fixture provider answers like the real one: a session that has opened has a row, a snapshot until
its close -- and ^VIX's until Cboe settles it at 16:15 New York. This week New York closes at 20:00 UK;
from Mon 2 Nov at 21:00 UK, after the last trigger, so Monday is processed at Tuesday's 07:00 run.
Each session is processed ONCE, never before both markets have closed, never on an early ^VIX.
"""

from __future__ import annotations

import json
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import exchange_calendars as xcals  # type: ignore[import-untyped]
import pandas as pd

from qb2.advisor import bot_pot, daily, state
from qb2.data import daily_step
from qb2.guard import stops

UK, NY = ZoneInfo("Europe/London"), ZoneInfo("America/New_York")
CAL = {"LSE": xcals.get_calendar("XLON"), "US": xcals.get_calendar("XNYS")}
NAMES = [{"yfinance": "VWRL.L", "quote_currency": "GBP", "exchange": "London Stock Exchange"},
         {"yfinance": "VWRP.L", "quote_currency": "GBP", "exchange": "London Stock Exchange"},
         {"yfinance": "^VIX", "quote_currency": "USD", "exchange": "Cboe (New York clock)"}]


def price(symbol: str, day: date) -> float:
    return (18.0 if symbol == "^VIX" else 100.0) + (day - date(2026, 10, 1)).days * 0.1


class Provider:
    """Rows for every session opened by ``now``; a snapshot (+0.5) until the row is final."""

    def __init__(self) -> None:
        self.now = datetime(2026, 10, 29, 19, 0, tzinfo=UK)

    def __call__(self, symbol: str) -> pd.DataFrame:
        market = "US" if symbol == "^VIX" else "LSE"
        zone = {"^VIX": "America/Chicago", "GBPUSD=X": "Europe/London"}.get(symbol, "Europe/London")
        cal, rows = CAL["LSE" if symbol == "GBPUSD=X" else market], {}
        for s in cal.sessions_in_range("2026-10-01", "2026-11-04"):
            if cal.session_open(s) > pd.Timestamp(self.now):
                continue
            final = cal.session_close(s) + (pd.Timedelta(minutes=15) if symbol == "^VIX" else pd.Timedelta(0))
            close = price(symbol, s.date()) + (0.5 if pd.Timestamp(self.now) < final else 0.0)
            rows[pd.Timestamp(s.date()).tz_localize(zone)] = close
        if symbol == "GBPUSD=X":
            rows = {k: 1.3 for k in rows}
        close = pd.Series(rows, dtype=float)
        return pd.DataFrame({"open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 1.0})


def runs() -> list[datetime]:
    out = [datetime(2026, 10, 29, 19, 0, tzinfo=UK), datetime(2026, 10, 29, 20, 0, tzinfo=UK)]
    for day in (date(2026, 10, 30), date(2026, 11, 2), date(2026, 11, 3)):
        out += [datetime.combine(day, time(h), UK) for h in range(7, 21)]
    return out + [datetime(2026, 11, 4, 7, 0, tzinfo=UK), datetime(2026, 11, 4, 8, 0, tzinfo=UK)]


def test_each_session_is_processed_once_after_both_closes_on_a_final_vix(tmp_path: Path) -> None:
    clean, adv, provider = tmp_path / "clean", state.Paths.under(tmp_path), Provider()
    provider.now = datetime(2026, 10, 28, 20, 30, tzinfo=UK)                      # Wednesday's top-up
    daily_step.run_if_due(provider.now, clean_root=clean, fetch=provider, entries=NAMES, digest_dir=tmp_path)
    state.arm(adv, date(2026, 10, 29), provider.now, "test")
    state.append(adv.log("suggestions"), {"at": "2026-10-28T20:30:00+00:00", "action": "BUY", "allowed": True,
                                          "kind": "weekly", "ticker": "VWRL.L", "session": "2026-10-28",
                                          "close": 102.7, "stop": 87.3, "reason": "test", "refusals": [],
                                          "warnings": []})                      # ADV-0 holds from 29 Oct
    first: dict[str, dict[str, datetime]] = {"advisor": {}, "bot pot": {}}
    for now in runs():
        provider.now = now
        daily_step.run_if_due(now, clean_root=clean, fetch=provider, entries=NAMES, digest_dir=tmp_path)
        daily.run(now, adv, clean_root=clean, shadows=False)
        bot_pot.run(now, bot_pot.beside(adv), adv, clean_root=clean)
        for who, paths in (("advisor", adv), ("bot pot", bot_pot.beside(adv))):
            for row in state.rows(paths.log("days")):
                first[who].setdefault(row["session"], now)
    want = {"2026-10-29": datetime(2026, 10, 29, 20, 0, tzinfo=UK),   # this week: final at 20:00 UK
            "2026-10-30": datetime(2026, 10, 30, 20, 0, tzinfo=UK),
            "2026-11-02": datetime(2026, 11, 3, 7, 0, tzinfo=UK),     # from Mon: final at 21:00 UK, so 07:00
            "2026-11-03": datetime(2026, 11, 4, 7, 0, tzinfo=UK)}
    assert first["advisor"] == want and first["bot pot"] == want                # the bot pot armed from 29 Oct
    for paths in (adv, bot_pot.beside(adv)):
        rows = state.rows(paths.log("days"))
        assert [r["session"] for r in rows] == list(want)                       # once each, none skipped
        for r in rows:                                                          # the previous session's FINAL
            d = date.fromisoformat(str(r["session"]))
            before = CAL["US"].previous_session(pd.Timestamp(d)).date()
            assert r["vix_before"] == price("^VIX", before)
        for session, at in want.items():                                        # never half a day
            closes = [CAL[m].session_close(pd.Timestamp(session)) for m in CAL]
            assert pd.Timestamp(at) >= max(closes)
    stop = bot_pot.held_stop(stops.Ledger(bot_pot.beside(adv).stops))
    assert stop is not None and stop.opened_at.startswith("2026-10-30")          # filled at Friday's open
    events = [json.loads(x) for x in (clean / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    early = [e["sessions"] for e in events if e.get("event") == "refused" and e["symbol"] == "^VIX"]
    assert early == [["2026-10-29"], ["2026-10-30"]]     # the gap week's 20:00 runs only (the seed ran at 20:30)
