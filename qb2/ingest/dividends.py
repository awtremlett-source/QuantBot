"""What each holding actually paid out, in the same unit as its price.

P3 judges return "in pounds terms including the effect of currency moves and
dividends". A strategy scored on price alone is scored on the wrong number: a
share that pays 4% a year and goes nowhere is not a flat holding.

**The trap this file is mostly about is units.** Trading 212 and yfinance quote
most London shares in PENCE, and they quote those shares' dividends in pence too.
The clean store keeps prices in POUNDS. Convert the price and forget the dividend
and BP's 6.2p payout sits next to a GBP 5.58 share: an apparent 112% yield, every
quarter, for every London payer. Convert both and it is 1.1%. So the conversion
happens at the boundary, once, and the result is checked against the price it was
paid out of before it is allowed into the store.

**The second trap is counting them twice.** yfinance offers an "Adj Close" that
already has dividends reinvested. Adding this table to that column counts every
payout twice and quietly inflates every back-test. Nothing here uses Adj Close,
and :mod:`qb2.research.total_return` refuses it outright.

**The third is knowing too early.** A dividend row fetched today must not let a
back-test act on a payout that had not gone ex yet. Historical rows are knowable no
earlier than the ex-date's opening bell; rows still in the future are knowable only
from the moment we fetched them.

Nothing is guessed. A payment that fails the yield check is marked SUSPECT and
kept; an ETF with no payouts is only called accumulating when the evidence says so.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from qb2.data.front_door import (CLEAN, PENCE, PENCE_PER_POUND, WriterLock,
                                 _append_manifest, _write_parquet_atomically)
from qb2.ingest import daily
from qb2.ingest.recorder import EXCHANGE_TZ, REGULAR_HOURS

DIVIDEND_DIR = CLEAN / "dividends"

# A single payment worth more than this much of the share price is not a normal
# dividend. STARTING FIGURE, tested first: ordinary quarterly yields sit near
# 0.3-2%, so 15% leaves room for a big annual or special payout while still
# catching a pence-for-pounds error, which shows up around 100x.
MAX_SENSIBLE_YIELD = 0.15
# Words a fund uses when it reinvests rather than pays out.
ACCUMULATING_WORDS = ("(acc)", " acc ", "accumulating", "accumulation")


@dataclass(frozen=True, slots=True)
class Coverage:
    """One name's dividend history, and why if there is none."""

    symbol: str
    sleeve: str
    kind: str
    rows: int
    suspect: int
    status: str                  # OK | ACC: N/A | UNKNOWN | NONE | MISSING
    reason: str = ""


@dataclass(slots=True)
class Outcome:
    coverage: list[Coverage] = field(default_factory=list)
    suspect_rows: int = 0

    def by_status(self, status: str) -> list[Coverage]:
        return [c for c in self.coverage if c.status == status]


def fetch_dividends(symbol: str) -> pd.Series | None:
    """The real provider. Injected in tests so the default run stays offline."""
    import warnings

    import yfinance as yf

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        series = yf.Ticker(symbol).dividends
    if series is None or len(series) == 0:
        return None
    return series


def market_open_utc(day: pd.Timestamp, market: str) -> datetime:
    """The opening bell on the ex-date, in UTC. When a payout becomes knowable."""
    zone = EXCHANGE_TZ.get(market, "America/New_York")
    opens = REGULAR_HOURS.get(market, REGULAR_HOURS["US"])[0]
    stamp = pd.Timestamp(day)
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert(None)
    local = pd.Timestamp(
        datetime.combine(stamp.date(), opens)).tz_localize(zone)
    converted: datetime = local.tz_convert("UTC").to_pydatetime()
    return converted


def to_rows(symbol: str, market: str, currency: str, series: pd.Series,
            fetched_at: datetime, *, clean_root: Path | None = None,
            now: datetime | None = None) -> pd.DataFrame:
    """One row per payment, converted, checked, and stamped with what we knew.

    The amount is converted with exactly the same rule the price was, because the
    yield check below only means anything if both sides are in one unit.
    """
    moment = now or fetched_at
    pence = currency in PENCE
    records: list[dict[str, object]] = []

    for when, raw_amount in series.items():
        ex_date = pd.Timestamp(when)
        amount = float(raw_amount) / (PENCE_PER_POUND if pence else 1.0)
        close = daily.close_on(symbol, ex_date, clean_root)
        yield_ = (amount / close) if (close and close > 0) else None

        if yield_ is None:
            verdict, why = "UNCHECKED", "no close on or near the ex-date to check against"
        elif yield_ <= 0:
            verdict, why = "SUSPECT", f"amount is not positive ({amount})"
        elif yield_ > MAX_SENSIBLE_YIELD:
            verdict = "SUSPECT"
            why = (f"one payment worth {yield_:.1%} of the share price -- either a "
                   "special dividend or a units error; kept for a human to decide")
        else:
            verdict, why = "OK", ""

        in_future = ex_date.tz_localize(None) > pd.Timestamp(moment).tz_localize(None) \
            if ex_date.tzinfo is None else ex_date > pd.Timestamp(moment)
        knowable = (fetched_at if in_future
                    else market_open_utc(ex_date, market))

        records.append({
            "symbol": symbol,
            "ex_date": str(pd.Timestamp(when).date()),
            "amount": amount,
            "currency": "GBP" if pence else currency,
            "quote_currency": currency,
            "pence_to_pounds": pence,
            "close_on_ex_date": close,
            "yield_of_price": yield_,
            "verdict": verdict,
            "why": why,
            "when": "announced" if in_future else "past",
            "knowable_time": knowable.isoformat(),
            "source": "yfinance.Ticker.dividends",
            # The data contract (CLAUDE.md, scar #22): yfinance's prices AND its
            # dividends arrive already split-adjusted. Re-adjusting would divide a
            # payout that was never doubled.
            "split_adjusted_by_provider": True,
        })
    return pd.DataFrame.from_records(records)


def looks_accumulating(name: str) -> bool:
    lowered = f" {name.lower()} "
    return any(word in lowered for word in ACCUMULATING_WORDS)


def collect(entries: Sequence[Mapping[str, object]], *,
            fetch: object = None, clean_root: Path | None = None,
            now: datetime | None = None) -> Outcome:
    """Fetch, check and store dividends for every entry."""
    getter = fetch or fetch_dividends
    moment = now or datetime.now(timezone.utc)
    outcome = Outcome()
    target = (clean_root or CLEAN) / "dividends"
    target.mkdir(parents=True, exist_ok=True)

    with WriterLock((clean_root or CLEAN) / "dividends.lock"):
        for entry in entries:
            symbol = str(entry["yfinance"])
            sleeve = str(entry.get("sleeve", "?"))
            kind = str(entry.get("kind") or "STOCK")
            name = str(entry.get("name") or "")
            currency = str(entry.get("quote_currency") or "USD")
            market = "LSE" if symbol.endswith(".L") else "US"

            try:
                series = getter(symbol)                   # type: ignore[operator]
            except Exception as exc:                      # noqa: BLE001
                outcome.coverage.append(Coverage(
                    symbol, sleeve, kind, 0, 0, "MISSING",
                    f"{type(exc).__name__}: {exc}"))
                continue

            if series is None or len(series) == 0:
                # Evidence, not assumption: no payouts in the whole history AND the
                # fund's own name says it accumulates. One without the other is
                # UNKNOWN, and UNKNOWN gets listed rather than quietly counted.
                if kind == "ETF" and looks_accumulating(name):
                    outcome.coverage.append(Coverage(
                        symbol, sleeve, kind, 0, 0, "ACC: N/A",
                        "no distributions in the full history and the fund name "
                        "says it accumulates"))
                elif kind == "ETF":
                    outcome.coverage.append(Coverage(
                        symbol, sleeve, kind, 0, 0, "UNKNOWN",
                        "no distributions found, but the name does not say it "
                        "accumulates -- not counted either way"))
                else:
                    outcome.coverage.append(Coverage(
                        symbol, sleeve, kind, 0, 0, "NONE",
                        "this company has never paid a dividend"))
                continue

            rows = to_rows(symbol, market, currency, series, moment,
                           clean_root=clean_root, now=moment)
            suspect = int((rows["verdict"] == "SUSPECT").sum())
            outcome.suspect_rows += suspect

            _write_parquet_atomically(rows, target / f"{symbol}.parquet")
            _append_manifest({
                "event": "dividends",
                "at": moment.isoformat(timespec="seconds"),
                "symbol": symbol,
                "rows": int(len(rows)),
                "suspect": suspect,
                "quote_currency": currency,
                "pence_to_pounds": currency in PENCE,
            }, clean_root)
            outcome.coverage.append(
                Coverage(symbol, sleeve, kind, len(rows), suspect, "OK"))
    return outcome


def load(symbol: str, clean_root: Path | None = None) -> pd.DataFrame | None:
    path = (clean_root or CLEAN) / "dividends" / f"{symbol}.parquet"
    return pd.read_parquet(path) if path.is_file() else None


def knowable_at(frame: pd.DataFrame, moment: datetime) -> pd.DataFrame:
    """Only the payouts we could honestly have known about at ``moment``."""
    knowable = pd.to_datetime(frame["knowable_time"], utc=True)
    cutoff = pd.Timestamp(moment)
    cutoff = (cutoff.tz_localize("UTC") if cutoff.tzinfo is None
              else cutoff.tz_convert("UTC"))
    return frame[knowable <= cutoff]


def report(outcome: Outcome) -> str:
    lines = ["DIVIDENDS"]
    sleeves = sorted({c.sleeve for c in outcome.coverage})
    for sleeve in sleeves:
        rows = [c for c in outcome.coverage if c.sleeve == sleeve]
        ok = [c for c in rows if c.status == "OK"]
        acc = [c for c in rows if c.status == "ACC: N/A"]
        none = [c for c in rows if c.status == "NONE"]
        unknown = [c for c in rows if c.status == "UNKNOWN"]
        missing = [c for c in rows if c.status == "MISSING"]
        expected = len(rows) - len(acc)
        share = f"{len(ok) + len(none)}/{expected}" if expected else "0/0"
        lines.append(
            f"  {sleeve:<10} {share} resolved ({len(ok)} paying, {len(none)} never "
            f"paid){', ' + str(len(acc)) + ' accumulating ETFs N/A' if acc else ''}"
            f"{', ' + str(len(unknown)) + ' UNKNOWN' if unknown else ''}"
            f"{', ' + str(len(missing)) + ' MISSING' if missing else ''}")
    for status in ("UNKNOWN", "MISSING"):
        named = outcome.by_status(status)
        if named:
            lines.append(f"  {status}, listed rather than guessed:")
            for c in named:
                lines.append(f"    {c.symbol:<10} {c.reason}")
    lines.append(f"  {outcome.suspect_rows} SUSPECT payment(s) kept and flagged")
    return "\n".join(lines)
