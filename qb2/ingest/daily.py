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
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from qb2.data.front_door import (CLEAN, PENCE, PENCE_PER_POUND, WriterLock,
                                 _append_manifest, _write_parquet_atomically,
                                 impossible_rows)

DAILY_DIR = CLEAN / "daily"
FX_PAIR = "GBPUSD=X"
# Three years covers the intraday history many times over and keeps one file per
# name small. STARTING FIGURE, tested first.
HISTORY = "3y"
COLUMNS = ("open", "high", "low", "close", "volume")


@dataclass(slots=True)
class DailyOutcome:
    """What one ingest run did, countable afterwards."""

    attempted: list[str] = field(default_factory=list)
    saved: dict[str, int] = field(default_factory=dict)
    lost: dict[str, str] = field(default_factory=dict)
    quarantined: int = 0

    def unaccounted(self) -> list[str]:
        seen = set(self.saved) | set(self.lost)
        return [name for name in self.attempted if name not in seen]


def fetch_daily(symbol: str, period: str = HISTORY) -> pd.DataFrame | None:
    """The real provider. Injected in tests so the default run stays offline."""
    import warnings

    import yfinance as yf

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        frame = yf.Ticker(symbol).history(period=period, interval="1d",
                                          auto_adjust=False)
    if frame is None or frame.empty:
        return None
    frame = frame.rename(columns=str.lower)
    wanted = [c for c in COLUMNS if c in frame.columns]
    frame = frame[wanted].dropna(how="all")
    return None if frame.empty else frame


def to_pounds(frame: pd.DataFrame, currency: str) -> tuple[pd.DataFrame, bool]:
    """Pence to pounds, exactly once -- the same rule the bars follow."""
    if currency not in PENCE:
        return frame, False
    converted = frame.copy()
    for column in ("open", "high", "low", "close"):
        if column in converted.columns:
            converted[column] = converted[column] / PENCE_PER_POUND
    return converted, True


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

    wanted: list[tuple[str, str]] = [
        (str(e["yfinance"]), str(e.get("quote_currency") or "USD")) for e in entries]
    if include_fx:
        wanted.append((FX_PAIR, "RATE"))

    with WriterLock((clean_root or CLEAN) / "daily.lock"):
        for symbol, currency in wanted:
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
            frame.index.name = "date"

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


def report(outcome: DailyOutcome) -> str:
    lines = [f"DAILY BARS: {len(outcome.saved)} saved of {len(outcome.attempted)} "
             f"attempted, {outcome.quarantined} row(s) quarantined"]
    if outcome.lost:
        lines.append(f"  {len(outcome.lost)} with nothing, named not guessed:")
        for symbol, why in list(outcome.lost.items())[:12]:
            lines.append(f"    {symbol:<10} {why}")
    missing = outcome.unaccounted()
    if missing:
        lines.append(f"  !! {len(missing)} attempted and unaccounted for: {missing}")
    return "\n".join(lines)
