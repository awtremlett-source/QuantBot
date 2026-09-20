"""Data layer. Cache-first and Yahoo-polite.

Rules:
  * The UI always renders from the SQLite cache; network only on refresh.
  * Refresh is incremental (only bars newer than what's cached).
  * Batched downloads, pauses between chunks, exponential backoff on 429s.
  * At most one full refresh per calendar day unless forced.
  * A failed chunk is recorded as an issue and never poisons other chunks.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from .config import Config
from .store import Store

LONDON = ZoneInfo("Europe/London")
BACKOFF_S = (2, 8, 30)
COLMAP = {"Open": "open", "High": "high", "Low": "low",
          "Close": "close", "Volume": "volume"}


class ProviderError(Exception):
    pass


class DataProvider(ABC):
    """Interface so an alternative source (e.g. Stooq) can slot in later."""

    @abstractmethod
    def fetch_daily(self, tickers: list[str], start: str | None = None,
                    period: str | None = None) -> dict[str, pd.DataFrame]:
        """Return {ticker: DataFrame} with a datetime index and lowercase
        open/high/low/close/volume columns. Raise ProviderError on failure."""


class YFinanceProvider(DataProvider):
    def fetch_daily(self, tickers, start=None, period=None):
        import yfinance as yf  # local import keeps tests fully offline
        last_err: Exception | None = None
        for attempt, pause in enumerate((0,) + BACKOFF_S):
            if pause:
                time.sleep(pause)
            try:
                raw = yf.download(
                    tickers=tickers, start=start,
                    period=None if start else (period or "2y"),
                    interval="1d", auto_adjust=True, group_by="ticker",
                    threads=True, progress=False)
                return self._normalise(raw, tickers)
            except Exception as exc:  # yfinance raises many types; treat alike
                last_err = exc
        raise ProviderError(f"yfinance failed after retries: {last_err}")

    @staticmethod
    def _normalise(raw: pd.DataFrame, tickers: list[str]) -> dict[str, pd.DataFrame]:
        out: dict[str, pd.DataFrame] = {}
        if raw is None or raw.empty:
            return out
        multi = isinstance(raw.columns, pd.MultiIndex)
        for t in tickers:
            try:
                sub = raw[t] if multi else raw
            except KeyError:
                continue
            if sub is None or sub.empty:
                continue
            sub = sub.rename(columns=COLMAP)
            keep = [c for c in ("open", "high", "low", "close", "volume")
                    if c in sub.columns]
            sub = sub[keep].dropna(subset=["close"])
            if not sub.empty:
                out[t] = sub
        return out


class RefreshService:
    """Coordinates incremental cache refresh across the universe."""

    def __init__(self, store: Store, provider: DataProvider, cfg: Config):
        self.store = store
        self.provider = provider
        self.cfg = cfg

    def london_today(self) -> date:
        return datetime.now(LONDON).date()

    def already_refreshed_today(self) -> bool:
        return self.store.get_setting("last_refresh_date") == self.london_today().isoformat()

    def refresh(self, tickers: list[str], force: bool = False,
                progress_cb=None) -> list[str]:
        """Refresh the cache. Returns a list of human-readable issue strings."""
        issues: list[str] = []
        if self.already_refreshed_today() and not force:
            return ["Already refreshed today - use Force refresh to repeat."]

        new_tickers = [t for t in tickers if self.store.last_date(t) is None]
        existing = [t for t in tickers if t not in new_tickers]
        chunks: list[tuple[list[str], str | None, str | None]] = []
        for group, is_new in ((new_tickers, True), (existing, False)):
            for i in range(0, len(group), self.cfg.chunk_size):
                chunk = group[i:i + self.cfg.chunk_size]
                if is_new:
                    chunks.append((chunk, None, self.cfg.history_period))
                else:
                    earliest = min(self.store.last_date(t) for t in chunk)
                    start = (pd.Timestamp(earliest) + timedelta(days=1)).strftime("%Y-%m-%d")
                    chunks.append((chunk, start, None))

        total = len(chunks)
        for n, (chunk, start, period) in enumerate(chunks, start=1):
            if progress_cb:
                progress_cb(n, total, f"Fetching {len(chunk)} tickers "
                                      f"(chunk {n}/{total})")
            try:
                frames = self.provider.fetch_daily(chunk, start=start, period=period)
            except ProviderError as exc:
                issues.append(f"Chunk of {len(chunk)} tickers failed: {exc}")
                continue
            for t in chunk:
                df = frames.get(t)
                if df is None or df.empty:
                    if start is None:  # brand-new ticker returned nothing
                        issues.append(f"{t}: no data returned")
                    continue
                last = self.store.last_date(t)
                if last is not None:
                    df = df[df.index > pd.Timestamp(last)]
                self.store.upsert_prices(t, df)
            if n < total and self.cfg.chunk_pause_s:
                time.sleep(self.cfg.chunk_pause_s)

        self.store.set_setting("last_refresh_date", self.london_today().isoformat())
        self.store.set_setting("last_refresh_at",
                               datetime.now(LONDON).strftime("%Y-%m-%d %H:%M"))
        return issues
