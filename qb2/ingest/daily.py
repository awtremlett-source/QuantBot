"""Daily bars and the pound/dollar rate, through the same front door as everything else.

Two things need these, and neither can be honest without them.

**The dividend check.** A dividend only makes sense next to the price it was paid
out of: 6.2 against a share priced 557 is a normal quarter, 6.2 against a share
priced 5.57 is nonsense. The check needs the close on the ex-date, and the ex-date
can be years back -- far beyond the ~60 days of intraday history we hold.

**P3.** Return is judged "in pounds terms including the effect of currency moves and
dividends". A US holding that rose 5% while the dollar fell 6% lost money in
pounds, and saying otherwise reports a win that was never earned. That needs a
daily GBP/USD series, so the rate is ingested like any other series rather than
being a number someone types in.

The unit rule is the same one the bars follow and is the reason this module exists
rather than a quick download: London is quoted in pence about as often as in
pounds, and the clean store is always in POUNDS for London and dollars for the US.
Prices and dividends must be converted the same way or the yield check compares a
pence dividend with a pound price and condemns every London payer.

**Only a closed session gets in (QT-25 B).** A daily bar is labelled with its date, not
the moment it was taken: fetched before its session closed (a 09:25 New York pre-open
^VIX, a 13:10 New York share mid-session) it is a snapshot, not a close. Such a row is
refused, said in the manifest and the "Daily store:" line, and taken by the next top-up.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from qb2.data import cross_bar, universe
from qb2.data.front_door import (CLEAN, PENCE, WriterLock, _append_manifest,
                                 _write_parquet_atomically, impossible_rows, to_pounds)
from qb2.ingest.recorder import EXCHANGE_TZ

FX_PAIR = "GBPUSD=X"
# QT-19: from 2010-01-01, so the advisor's slow rules have their lookback and a
# walk-forward long enough to judge them. Every top-up re-fetches the whole span (one
# consistent split adjustment); a shorter routine fetch would cut the history back.
HISTORY_START = "2010-01-01"
COLUMNS = ("open", "high", "low", "close", "volume")
NOT_CLOSED = "its session had not closed on its exchange's clock when fetched (QT-25 B)"


@dataclass(slots=True)
class DailyOutcome:
    """What one ingest run did, countable afterwards."""

    attempted: list[str] = field(default_factory=list)
    saved: dict[str, int] = field(default_factory=dict)
    lost: dict[str, str] = field(default_factory=dict)
    refused: dict[str, list[str]] = field(default_factory=dict)    # symbol -> sessions not closed
    quarantined: int = 0


def fetch_daily(symbol: str, start: str = HISTORY_START) -> pd.DataFrame | None:
    """The real provider. Injected in tests so the default run stays offline."""
    import warnings

    import yfinance as yf

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        frame = yf.Ticker(symbol).history(start=start, interval="1d", auto_adjust=False)
    if frame is None or frame.empty:
        return None
    frame = frame.rename(columns=str.lower)
    wanted = [c for c in COLUMNS if c in frame.columns]
    frame = frame[wanted].dropna(how="all")
    return None if frame.empty else frame


def daily_path(symbol: str, clean_root: Path | None = None) -> Path:
    return (clean_root or CLEAN) / "daily" / f"{symbol}.parquet"


def load(symbol: str, clean_root: Path | None = None) -> pd.DataFrame | None:
    path = daily_path(symbol, clean_root)
    return pd.read_parquet(path) if path.is_file() else None


def close_on(symbol: str, day: object, clean_root: Path | None = None,
             within_days: int = 5) -> float | None:
    """The close on a date, or the nearest earlier trading day within a window.

    An ex-date can fall on a holiday or a day the share did not trade. Walking
    back a few days is honest; inventing a price is not, so beyond the window the
    answer is None and the caller must say so.
    """
    frame = load(symbol, clean_root)
    if frame is None or frame.empty:
        return None
    wanted = pd.Timestamp(day)
    if wanted.tzinfo is not None:
        wanted = wanted.tz_convert(None)
    index = pd.DatetimeIndex(frame.index)
    naive = index.tz_convert(None) if index.tz is not None else index
    earlier = naive[naive <= wanted]
    if len(earlier) == 0:
        return None
    nearest = earlier[-1]
    if (wanted - nearest).days > within_days:
        return None
    return float(frame["close"].to_numpy()[list(naive).index(nearest)])


def unclosed(frame: pd.DataFrame, market: str | None, now: datetime) -> pd.Series:
    """True on a row (dated on its exchange's clock) whose session had not closed at ``now``, the
    fetch: never a close. The pound/dollar rate has no exchange close, so no row of it is judged."""
    from qb2.data import clean_step                   # clean_step -> daily_step -> this module
    recent = (now - timedelta(days=7)).date()          # older sessions closed long before
    return pd.Series([market is not None and d >= recent and clean_step.closed(market, d, now) is False
                      for d in pd.DatetimeIndex(frame.index).date], index=frame.index, dtype=bool)


def ingest(entries: Sequence[Mapping[str, object]], *,
           fetch: object = None, clean_root: Path | None = None,
           include_fx: bool = True,
           now: datetime | None = None) -> DailyOutcome:
    """Fetch and store daily bars for every entry, plus the pound/dollar rate."""
    getter = fetch or fetch_daily
    moment = now or datetime.now(timezone.utc)
    outcome = DailyOutcome()
    target = (clean_root or CLEAN) / "daily"
    target.mkdir(parents=True, exist_ok=True)

    wanted = _wanted(entries, include_fx)
    with WriterLock((clean_root or CLEAN) / "daily.lock"):
        for symbol, currency, kind, market in wanted:
            outcome.attempted.append(symbol)
            try:
                frame = getter(symbol)                    # type: ignore[operator]
            except Exception as exc:                      # noqa: BLE001
                outcome.lost[symbol] = f"{type(exc).__name__}: {exc}"
                continue
            if frame is None or frame.empty:
                outcome.lost[symbol] = "provider returned nothing"
                continue

            bad = impossible_rows(frame) if set(COLUMNS) <= set(frame.columns) \
                else pd.Series(False, index=frame.index)
            if bool(bad.any()):
                # KEPT, not dropped. These are real and worth seeing: BP.L has a
                # day whose open sits above its own high, and the GBP/USD series
                # has days where the close exceeds the high by about 0.002% --
                # rounding inside the provider's own aggregation. Dropping them
                # silently would hide a genuine bad bar among harmless ones.
                quarantine = (clean_root or CLEAN) / "quarantine" / "daily"
                quarantine.mkdir(parents=True, exist_ok=True)
                _write_parquet_atomically(
                    frame[bad], quarantine / f"{symbol}-impossible.parquet")
                _append_manifest({
                    "event": "quarantine", "table": "daily", "symbol": symbol,
                    "at": moment.isoformat(timespec="seconds"),
                    "rows": int(bad.sum()), "reason": "ohlc_sanity",
                    "note": "kept here; excluded from the daily series",
                }, clean_root)
                outcome.quarantined += int(bad.sum())
                frame = frame[~bad]
            if frame.empty:
                outcome.lost[symbol] = "every row failed the sanity check"
                continue

            frame, converted = to_pounds(frame, currency)
            stored = "GBP" if currency in PENCE else currency
            frame = frame.copy()
            frame["currency"] = stored
            if market is not None and getattr(frame.index, "tz", None) is not None:
                # QT-24, as QT-15 A2 for the minute bars: the exchange's own clock, whatever
                # label the provider carries (^VIX arrives on Chicago's)
                frame.index = pd.DatetimeIndex(frame.index).tz_convert(EXCHANGE_TZ[market])
            frame.index.name = "date"
            if bool((early := unclosed(frame, market, moment).to_numpy()).any()):   # QT-25 B: said
                refused = outcome.refused[symbol] = [str(d) for d in pd.DatetimeIndex(frame.index[early]).date]
                _append_manifest({"event": "refused", "table": "daily", "symbol": symbol, "sessions": refused,
                                  "at": moment.isoformat(timespec="seconds"), "reason": NOT_CLOSED,
                                  "closes": [float(x) for x in frame["close"].to_numpy()[early]]}, clean_root)
                frame = frame[~early]
            frame, moved = cross_bar.apply(frame, symbol, kind, now=moment,   # QT-21: every write
                                           clean_root=clean_root)
            outcome.quarantined += moved
            if frame.empty:
                outcome.lost[symbol] = "every row is quarantined (cross_bar.py)"
                continue

            destination = daily_path(symbol, clean_root)
            _write_parquet_atomically(frame, destination)
            _append_manifest({
                "event": "daily",
                "at": moment.isoformat(timespec="seconds"),
                "symbol": symbol,
                "rows": int(len(frame)),
                "first": str(frame.index.min()),
                "last": str(frame.index.max()),
                "quote_currency": currency,
                "stored_currency": stored,
                "pence_to_pounds": converted,
            }, clean_root)
            outcome.saved[symbol] = int(len(frame))
    return outcome


def _wanted(entries: Sequence[Mapping[str, object]], include_fx: bool,
            ) -> list[tuple[str, str, str, str | None]]:
    """(symbol, quote currency, kind, market) per entry; the pound/dollar rate has no kind and no
    exchange, and keeps its own stamp (pounds.FX_CLOCK)."""
    out: list[tuple[str, str, str, str | None]] = [
        (str(e["yfinance"]), str(e.get("quote_currency") or "USD"), str(e.get("kind") or ""),
         universe.market_of(e)) for e in entries]
    return out + [(FX_PAIR, "RATE", "", None)] if include_fx else out


def requarantine(entries: Sequence[Mapping[str, object]], *, clean_root: Path | None = None,
                 include_fx: bool = True, now: datetime | None = None) -> DailyOutcome:
    """QT-21 A2: the cross-bar check run over the files ALREADY stored, through the same
    lock, ledger, atomic write and manifest as every top-up. No fetch; rows are moved, never
    changed: rows in = rows kept + rows quarantined."""
    moment = now or datetime.now(timezone.utc)
    outcome = DailyOutcome()
    with WriterLock((clean_root or CLEAN) / "daily.lock"):
        for symbol, _, kind, _ in _wanted(entries, include_fx):
            outcome.attempted.append(symbol)
            frame = load(symbol, clean_root)
            if frame is None or frame.empty:
                outcome.lost[symbol] = "nothing stored"
                continue
            kept, moved = cross_bar.apply(frame, symbol, kind, now=moment, clean_root=clean_root)
            outcome.quarantined += moved
            outcome.saved[symbol] = int(len(kept))
            if len(kept) != len(frame):
                _write_parquet_atomically(kept, daily_path(symbol, clean_root))
                _append_manifest({
                    "event": "daily", "at": moment.isoformat(timespec="seconds"),
                    "symbol": symbol, "rows": int(len(kept)), "first": str(kept.index.min()),
                    "last": str(kept.index.max()), "requarantine": int(len(frame) - len(kept)),
                    "note": "QT-21 cross-bar check over the stored file (no fetch)"}, clean_root)
    return outcome
