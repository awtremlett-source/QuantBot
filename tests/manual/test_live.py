from datetime import datetime
from zoneinfo import ZoneInfo

from manual.scout.live import (GAUGES, LiveQuoteProvider, is_market_open,
                        tickers_of_interest)
from manual.scout import journal

LONDON = ZoneInfo("Europe/London")


def dt(day, hour, minute=0):
    # 2026-08-17 is a Monday
    return datetime(2026, 8, day, hour, minute, tzinfo=LONDON)


def test_market_hours():
    assert is_market_open(dt(17, 10))            # Monday 10:00
    assert is_market_open(dt(17, 8, 0))          # at the open
    assert is_market_open(dt(17, 16, 30))        # at the close
    assert not is_market_open(dt(17, 7, 59))
    assert not is_market_open(dt(17, 16, 31))
    assert not is_market_open(dt(22, 12))        # Saturday
    assert not is_market_open(dt(23, 12))        # Sunday


def test_tickers_of_interest_positions_watchlist_gauges(tmp_store):
    journal.open_trade(tmp_store, ticker="AAA.L", name="A", entry_px=1.0,
                       stop_px=0.9, shares=10, risk_gbp=1.0,
                       open_costs_gbp=0.0, setup_type="Manual",
                       thesis="t", checklist={})
    tmp_store.watch("BBB.L", True)
    tmp_store.watch("AAA.L", True)               # duplicate on purpose
    wanted = tickers_of_interest(tmp_store)
    assert wanted[:2] == ["AAA.L", "BBB.L"]
    assert all(g in wanted for g in GAUGES)
    assert len(wanted) == len(set(wanted))


class FakeLive(LiveQuoteProvider):
    def __init__(self, quotes):
        self.quotes = quotes
        self.calls = []

    def fetch_last(self, tickers):
        self.calls.append(list(tickers))
        return {t: self.quotes[t] for t in tickers if t in self.quotes}


def test_fake_live_roundtrip():
    fake = FakeLive({"AAA.L": 123.0})
    out = fake.fetch_last(["AAA.L", "MISSING.L"])
    assert out == {"AAA.L": 123.0}
