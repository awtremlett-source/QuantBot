"""P22's second prices, gathered once per recorder run while London is shut (QT-30). Read-only.

Two sources for the two funds whose closes drive a stop, appended to
data/qb2/price_check/observations.jsonl with the moment each was fetched (rows carry their knowable
time); qb2/advisor/price_check.py is the only reader and decides which read counts for which session.
* Trading 212's ``currentPrice``, GET only, read key only -- it prices only what we hold.
* CNBC's daily bars, the free backup (independent of Yahoo; proven 68 of 68 sessions to the penny on
  2026-11-09). Its currency is read from CNBC's own quote and every price is stored in pounds.
Nothing here may stop or fail the recorder: every error is said in the run log and skipped.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from qb2.data import universe
from qb2.execution import xcheck
from qb2.ingest import recorder
from qb2.ingest.xcheck_shadow import broker_prices

REPO_ROOT = Path(__file__).resolve().parents[2]
FILE = REPO_ROOT / "data" / "qb2" / "price_check" / "observations.jsonl"
NAMES = (("VWRL.L", "VWRLl_EQ", "VWRL-GB"), ("VWRP.L", "VWRPl_EQ", "VWRP-GB"))
DAYS_BACK = 14                         # enough to catch up after the PC has been off
TIMEOUT_SECONDS = 20.0
AGENT = "QuantBot-price-check"         # a plain name: no contact details are sent
BARS = "https://ts-api.cnbc.com/harmony/app/bars/{symbol}/1D/{start}/{end}/unadjusted/EST5EDT.json"
QUOTE = ("https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?symbols={symbol}"
         "&requestMethod=itv&noform=1&partnerId=2&fund=1&exthrs=1&output=json")
SOURCE = "CNBC"

Say = Callable[[str], None]
Read = Callable[[], Sequence[Mapping[str, Any]]]
Fetch = Callable[[str], Any]


def get_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:      # noqa: S310 - https, fixed hosts
        return json.load(response)


def quote_currency(payload: Mapping[str, Any], symbol: str) -> str:
    rows = payload["FormattedQuoteResult"]["FormattedQuote"]
    return next(str(q["currencyCode"]) for q in rows if q.get("symbol") == symbol)


def closes_of(payload: Mapping[str, Any]) -> dict[date, float]:
    return {datetime.strptime(str(b["tradeTime"])[:8], "%Y%m%d").date(): float(b["close"])
            for b in payload["barData"]["priceBars"]}


def _append(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.writelines(json.dumps(r, sort_keys=True) + "\n" for r in rows)


def _known(path: Path) -> set[tuple[str, str, float]]:
    """The backup closes already on file. A half-written line is skipped; the file is only added to."""
    out = set()
    for line in path.read_text(encoding="utf-8").splitlines() if path.is_file() else []:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("kind") == "backup":
            out.add((str(row["ticker"]), str(row["session"]), float(row["close"])))
    return out


def t212_rows(read: Read, stamp: str) -> list[dict[str, Any]]:
    """Stored in pounds, from the currency Trading 212 states; a price it cannot convert is left out."""
    held, out = broker_prices(read()), []
    for ticker, t212, _ in NAMES:
        price, currency = held.get(t212, (None, ""))
        pounds = xcheck.to_quote(price, currency, "GBP")
        if pounds is not None:
            out.append({"kind": "t212", "ticker": ticker, "t212": t212, "price": pounds, "currency": "GBP",
                        "raw_price": price, "raw_currency": currency, "fetched_at": stamp})
    return out


def backup_rows(now: datetime, fetch: Fetch, known: set[tuple[str, str, float]], stamp: str) -> list[dict[str, Any]]:
    """New or corrected closes only; a price that cannot be put in pounds is left out."""
    span = {"start": f"{now - timedelta(days=DAYS_BACK):%Y%m%d}000000", "end": f"{now + timedelta(days=1):%Y%m%d}000000"}
    out = []
    for ticker, _, symbol in NAMES:
        currency = quote_currency(fetch(QUOTE.format(symbol=symbol)), symbol)
        for day, raw in sorted(closes_of(fetch(BARS.format(symbol=symbol, **span))).items()):
            pounds = xcheck.to_quote(raw, currency, "GBP")
            if pounds is not None and (ticker, day.isoformat(), pounds) not in known:
                out.append({"kind": "backup", "ticker": ticker, "session": day.isoformat(), "close": pounds,
                            "currency": "GBP", "source": SOURCE, "fetched_at": stamp})
    return out


def gather(now: datetime, read: Read, say: Say, *, fetch: Fetch = get_json, path: Path | None = None) -> None:
    """Both sources, each on its own: one failing never stops the other or the recorder."""
    if recorder.market_is_open(universe.LONDON, now):
        say("  Price check: London is open, no close to read")
        return
    target, stamp = path or FILE, now.astimezone(timezone.utc).isoformat(timespec="seconds")
    sources: tuple[tuple[str, Callable[[], list[dict[str, Any]]]], ...] = (
        ("Trading 212", lambda: t212_rows(read, stamp)),
        ("backup feed", lambda: backup_rows(now, fetch, _known(target), stamp)))
    for name, rows_of in sources:
        try:
            rows = rows_of()
            _append(target, rows)
            say(f"  Price check: {name}: {len(rows)} new prices saved")
        except Exception as exc:              # noqa: BLE001 - said, never fatal
            say(f"  Price check: {name} failed ({type(exc).__name__}: {exc}) -- skipped")
