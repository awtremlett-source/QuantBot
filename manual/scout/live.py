"""Near-live quotes, done politely.

Yahoo's LSE feed is ~15 minutes delayed and rate-limited, so live mode
never touches the whole universe. It watches only what matters intraday:
open positions, the watchlist, and the three market gauges -- one batched
call every few minutes during London trading hours. Daily bars in the
cache remain the source of truth for all scoring; live prices overlay the
displays and the sell-alert checks.
"""
from __future__ import annotations

from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")
LSE_OPEN = dtime(8, 0)
LSE_CLOSE = dtime(16, 30)
GAUGES = ["^FTSE", "^FTMC", "^VIX"]
MAX_LIVE_TICKERS = 40


def is_market_open(now: datetime | None = None) -> bool:
    now = now or datetime.now(LONDON)
    if now.tzinfo is None:
        now = now.replace(tzinfo=LONDON)
    now = now.astimezone(LONDON)
    if now.weekday() >= 5:          # Sat/Sun (public holidays not modelled)
        return False
    return LSE_OPEN <= now.time() <= LSE_CLOSE


def tickers_of_interest(store, extra: list[str] | None = None) -> list[str]:
    """Open positions + watchlist + gauges (+ whatever is on screen),
    deduped, oldest-first, capped."""
    wanted: list[str] = list(extra or [])
    for tr in store.list_trades(open_only=True):
        if tr["ticker"] not in wanted:
            wanted.append(tr["ticker"])
    for t in store.watchlist():
        if t not in wanted:
            wanted.append(t)
    for t in GAUGES:
        if t not in wanted:
            wanted.append(t)
    return wanted[:MAX_LIVE_TICKERS]


class LiveQuoteProvider:
    """Interface: return {ticker: last_price_in_quote_units}."""

    def fetch_last(self, tickers: list[str]) -> dict[str, float]:
        raise NotImplementedError


class YFinanceLiveProvider(LiveQuoteProvider):
    def fetch_last(self, tickers):
        if not tickers:
            return {}
        import pandas as pd
        import yfinance as yf
        try:
            raw = yf.download(tickers=tickers, period="1d", interval="5m",
                              auto_adjust=True, group_by="ticker",
                              threads=True, progress=False)
        except Exception:
            return {}
        out: dict[str, float] = {}
        if raw is None or raw.empty:
            return out
        multi = isinstance(raw.columns, pd.MultiIndex)
        for t in tickers:
            try:
                sub = raw[t] if multi else raw
                series = sub["Close"].dropna()
                if not series.empty:
                    out[t] = float(series.iloc[-1])
            except (KeyError, TypeError):
                continue
        return out
