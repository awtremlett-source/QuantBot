"""The P20 anchor buyer: about a pound of each bot name, on the PRACTICE account.

WHY. Trading 212 prices only what we hold (docs/t212/FACTS.md row h), and PLAN_V3
P20 cross-checks every price against the broker. So the practice account holds a
small "anchor" of each of the 50 bot names, and the broker then prices all 50.
Whole shares of all 50 cost GBP 14,032 -- more than the account -- so an anchor is
the smallest practical fractional amount, a target of about GBP 1.

WHAT THIS IS NOT. It is not the bot's sender (``sender.py`` stays disarmed and this
file never touches it), it is not imported by anything in qb2, and it cannot sell.
It is the only order path that exists before S10, so every fence below is held by
a test that was watched fail first:

F1  practice only -- the host is a constant; any other host, or any T212_* setting
    pointing elsewhere, is refused BEFORE a socket opens. No setting changes it.
F2  its own key -- orders use T212_ORDER_KEY / T212_ORDER_SECRET and nothing else
    in the repo may name them; reads keep using the read-only key.
F3  buy only -- there is no sell function; a quantity that is not positive raises.
F4  names only from the agreed 50-name file, whose bytes are pinned by hash, each
    resolved through the verified instrument list on ticker + ISIN + exchange.
F5  caps -- GBP 1 target, GBP 3 per order, GBP 100 lifetime, 50 orders a day. A cap
    is never raised without the operator's GO (PLAN_V3 P20 addendum).
F6  units -- sized in pounds from the clean daily close (its own unit column), and
    capped on the LARGER of that and a second, independently converted price, so a
    100x unit slip cannot buy 100x the money.
F7  open market only -- the broker's own calendar AND the exchange-local clock must
    both say "regular session"; extendedHours is always false; nothing is queued.
F8  no duplicates -- positions and pending orders are read fresh before each order;
    the intent is on disk before the order leaves; an unknown outcome blocks that
    name until the broker's order history settles it, and halts the run.
F9  the killswitch file stops every anchor buy, checked before each order.
F10 not a back door -- never reads or writes ARMED; flatten subtracts anchor
    quantities read from the ledger (qb2/execution/anchor_ledger.py).
F11 the dry run is the default and its client class has no order method at all.
F12 secrets -- names only, in every message, log and ledger line.

CLI:  python -m qb2.execution.anchors            (dry run, read-only key)
      python -m qb2.execution.anchors --live     (practice orders, order key)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from datetime import time as clock_time
from decimal import ROUND_DOWN, ROUND_UP, Decimal
from http.client import HTTPMessage
from pathlib import Path
from typing import IO, Any, Protocol
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from qb2.execution import costs, safety
from qb2.execution.anchor_ledger import (ACCEPTED, BLOCKING, FILLED, INTENT,
                                         NOT_FILLED, NOT_PLACED, OUTCOME,
                                         RECONCILED, UNRESOLVED, AnchorLedger,
                                         IntentState)
from qb2.execution.t212_client import (KEY_VARIABLE, BrokerError, Credentials,
                                       CredentialsMissing, Endpoint, Response,
                                       T212DemoClient, Throttle, read_env_file)
from qb2.ingest import verify_universe

REPO_ROOT = Path(__file__).resolve().parents[2]

# --- F1: the practice server, hard-coded. FACTS row b1. -----------------------
DEMO_HOST = "demo.trading212.com"
DEMO_BASE_URL = "https://demo.trading212.com/api/v0"
SETTING_PREFIX = "T212_"

# --- F2: the order key's names. Nothing else in the repo may name them. --------
ORDER_KEY_VARIABLE = "T212_ORDER_KEY"
ORDER_SECRET_VARIABLE = "T212_ORDER_SECRET"

# --- the only two calls the order client can make -----------------------------
_GET = "GET"
_POST = "POST"
MARKET_ORDER_PATH = "/equity/orders/market"      # FACTS row t, checked 2026-10-04
ACCOUNT_PATH = "/equity/account/summary"
_ALLOWED_CALLS = frozenset({(_GET, ACCOUNT_PATH), (_POST, MARKET_ORDER_PATH)})
ORDER_ENDPOINT = Endpoint(MARKET_ORDER_PATH, 1.5, "market order (50 req / 1m)")
ACCOUNT_ENDPOINT = Endpoint(ACCOUNT_PATH, 5.0, "account summary (1 req / 5s)")
ORDER_TIMEOUT_SECONDS = 20.0

# --- F5: the caps. Raising one needs the operator's GO (PLAN_V3 P20). ----------
TARGET_GBP = 1.00
MAX_ORDER_GBP = 3.00
LIFETIME_CAP_GBP = 100.00
MAX_ORDERS_PER_DAY = 50

# --- F6: what Trading 212 does not publish, so we ASSUME it, and say so. -------
# FACTS rows u and v: no minimum order and no quantity precision is documented,
# and the instrument list carries neither. Community reports: about GBP 1, and an
# error "invalid quantity precision 4". Both are assumptions until a fill proves
# them, and both are printed as UNKNOWN in every report.
ASSUMED_MIN_ORDER_GBP = 1.00
ASSUMED_QUANTITY_DECIMALS = 4
QUANTUM = Decimal(1).scaleb(-ASSUMED_QUANTITY_DECIMALS)
# Two prices for one name must agree this closely after conversion. A unit slip is
# a factor of 100; a day's move is a few percent. STARTING FIGURE.
PRICE_AGREEMENT = 0.25
MAX_PRICE_AGE_DAYS = 7

# --- F7: regular sessions, in each exchange's own clock. STARTING margins. -----
SESSIONS: Mapping[str, tuple[str, clock_time, clock_time]] = {
    "LSE": ("Europe/London", clock_time(8, 0), clock_time(16, 30)),
    "US": ("America/New_York", clock_time(9, 30), clock_time(16, 0)),
}
OPEN_MARGIN = timedelta(minutes=10)
CLOSE_MARGIN = timedelta(minutes=15)
MARKET_OF_EXCHANGE: Mapping[str, str] = {
    "NASDAQ": "US", "NYSE": "US", verify_universe.LONDON_MAIN: "LSE"}

# --- F4: the agreed universe and the verified instrument list, pinned. ---------
UNIVERSE_FILE = REPO_ROOT / "docs" / "universe" / "bot-universe-v1-2026-10-01.json"
# sha256 with line endings normalised to LF -- identical to the file as committed
# in 4d7a39f, where the operator's "GO on bot universe v1" was recorded.
UNIVERSE_SHA256 = (
    "b229811dedd54aef4a87e8bff9a8ee4fc61522d035ac29457d7f547fe2b26e44")
INSTRUMENTS_FILE = REPO_ROOT / "data" / "raw" / "t212" / "instruments-2026-10-01.json"
EXCHANGES_FILE = REPO_ROOT / "data" / "raw" / "t212" / "exchanges-2026-10-01.json"
# First 32 hex of the raw bytes, as data/raw/t212/manifest.jsonl recorded them.
INSTRUMENTS_SHA256_PREFIX = "e53d1757f3885de8034b0002ba23b92b"
EXCHANGES_SHA256_PREFIX = "bb628adbeb49a382e50db238bbb8a2c8"

CLEAN_ROOT = REPO_ROOT / "data" / "clean"
RAW_ROOT = REPO_ROOT / "data" / "raw"
REPORT_DIR = REPO_ROOT / "data" / "anchors"
FX_SYMBOL = "GBPUSD=X"

# How long an unheard order must be absent from every broker list before it is
# settled as never placed, and how long to let fills land before checking.
RECONCILE_AFTER = timedelta(minutes=10)
SETTLE_SECONDS = 10.0

WOULD_BUY = "BUY"
WAIT = "WAIT"
SKIP = "SKIP"

UNKNOWN_FACTS: tuple[str, ...] = (
    "minimum order value/quantity: NOT DOCUMENTED (FACTS row u) -- assumed "
    f"GBP {ASSUMED_MIN_ORDER_GBP:.2f}",
    "quantity precision per instrument: NOT DOCUMENTED (FACTS row v) -- assumed "
    f"{ASSUMED_QUANTITY_DECIMALS} decimal places",
    "which instruments allow fractional orders: no such field in the "
    "instrument list -- UNKNOWN until a fill",
)


class AnchorRefused(RuntimeError):
    """A fence said no. The message says which, in plain words, names only."""


class LiveServerRefused(AnchorRefused):
    """F1: something tried to point the anchor buyer away from practice."""


class OrderKeyMissing(AnchorRefused):
    """F2: live buying needs the order key, and it is not there."""


class UniverseTampered(AnchorRefused):
    """F4: the 50-name file is not the one the operator agreed."""


class UnitUnknown(AnchorRefused):
    """F6: a price whose unit we cannot name is not a price we can size on."""


# ================================================================== F1 ===

def assert_demo_url(url: str) -> None:
    """Refuse anything but the practice API. The bad host is never echoed --
    a refusal message that printed it would carry it into a log."""
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.hostname != DEMO_HOST
            or parts.port not in (None, 443) or parts.username or parts.password
            or not url.startswith(DEMO_BASE_URL + "/")):
        raise LiveServerRefused(
            "the anchor buyer talks to the practice server only; a request to "
            "another address was refused before any network call")


def refuse_host_overrides(environ: Mapping[str, str] | None = None,
                          env_file: Path | None = None) -> None:
    """A T212_* setting that points elsewhere is a reason to stop, not ignore.

    The buyer has no setting that changes its server. But a setting that TRIES
    to (T212_ENV=live, a URL in a T212_* variable) means someone expects it to,
    and running anyway would be a surprise in exactly the wrong direction.
    """
    merged: dict[str, str] = dict(read_env_file(env_file))
    merged.update({k: v for k, v in (environ if environ is not None
                                     else os.environ).items()
                   if k.startswith(SETTING_PREFIX)})
    offenders: list[str] = []
    for name, raw in merged.items():
        if not name.startswith(SETTING_PREFIX):
            continue
        value = raw.strip().strip("'\"").lower()
        if name == "T212_ENV" and value not in ("", "demo", "practice"):
            offenders.append(name)
        elif ("trading212" in value or "://" in value) and not (
                value == DEMO_BASE_URL.lower()
                or value.startswith(DEMO_BASE_URL.lower() + "/")):
            offenders.append(name)
    if offenders:
        raise LiveServerRefused(
            f"refusing to run: {', '.join(sorted(offenders))} points somewhere "
            "other than the practice server (values not shown). The anchor "
            "buyer cannot be redirected; real-money anchors are decided at S14")


# ================================================================== F2 ===

def order_credentials(environ: Mapping[str, str] | None = None,
                      env_file: Path | None = None) -> Credentials:
    """The order key, from its own two names and nowhere else."""
    source: dict[str, str] = dict(read_env_file(env_file))
    source.update({k: v for k, v in (environ if environ is not None
                                     else os.environ).items()
                   if k in (ORDER_KEY_VARIABLE, ORDER_SECRET_VARIABLE,
                            KEY_VARIABLE)})
    key = (source.get(ORDER_KEY_VARIABLE) or "").strip()
    secret = (source.get(ORDER_SECRET_VARIABLE) or "").strip()
    if not key or not secret:
        raise OrderKeyMissing(
            f"live anchor buying needs {ORDER_KEY_VARIABLE} and "
            f"{ORDER_SECRET_VARIABLE} in .env -- a PRACTICE key with Orders - "
            "Execute ticked (docs/t212/SETUP.md). Nothing was sent")
    if key == (source.get(KEY_VARIABLE) or "").strip():
        raise OrderKeyMissing(
            f"{ORDER_KEY_VARIABLE} is the same key as {KEY_VARIABLE}: the "
            "read-only key must stay read-only, so the order key has to be a "
            "separate key. Nothing was sent")
    return Credentials(key=key, secret=secret)


# ================================================================== F4 ===

@dataclass(frozen=True, slots=True)
class Identity:
    """One agreed name, resolved to exactly one Trading 212 instrument."""

    yfinance: str
    name: str
    sleeve: str
    market: str
    exchange: str
    t212_ticker: str
    isin: str
    currency: str               # Trading 212's own code: GBX, GBP or USD
    kind: str
    aim: bool
    schedule_id: int | None


@dataclass(frozen=True, slots=True)
class Unresolved:
    yfinance: str
    name: str
    sleeve: str
    exchange: str
    reason: str


def sha256_lf(path: Path) -> str:
    """Hash with CRLF folded to LF, so a Windows checkout hashes like git's copy."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load_universe(path: Path | None = None,
                  expected_sha256: str = UNIVERSE_SHA256) -> list[dict[str, Any]]:
    """The agreed 50, or a refusal. Never a list nobody agreed to."""
    target = path or UNIVERSE_FILE
    if sha256_lf(target) != expected_sha256:
        raise UniverseTampered(
            f"{target.name} is not the file agreed on 2026-10-02 (its hash "
            "changed) -- a changed list is a new decision, not an edit")
    doc = json.loads(target.read_text(encoding="utf-8"))
    entries = doc.get("entries")
    if (doc.get("list") != "bot" or doc.get("status") != "AGREED"
            or not isinstance(entries, list) or len(entries) != 50):
        raise UniverseTampered(f"{target.name} is not the agreed 50-name bot list")
    return [e for e in entries if isinstance(e, dict)]


def _check_prefix(path: Path, prefix: str) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if not digest.startswith(prefix):
        raise UniverseTampered(
            f"{path.name} does not match the hash recorded when it was saved")


def load_verified_lists(instruments_file: Path | None = None,
                        exchanges_file: Path | None = None,
                        ) -> tuple[list[dict[str, Any]], dict[int, str]]:
    """The saved instrument and exchange lists, checked against their manifest."""
    inst = instruments_file or INSTRUMENTS_FILE
    exch = exchanges_file or EXCHANGES_FILE
    _check_prefix(inst, INSTRUMENTS_SHA256_PREFIX)
    _check_prefix(exch, EXCHANGES_SHA256_PREFIX)
    rows = json.loads(inst.read_text(encoding="utf-8"))
    names: dict[int, str] = {}
    for exchange in json.loads(exch.read_text(encoding="utf-8")):
        if not isinstance(exchange, dict):
            continue
        for schedule in exchange.get("workingSchedules") or []:
            if isinstance(schedule, dict) and isinstance(schedule.get("id"), int):
                names[int(schedule["id"])] = str(exchange.get("name", "?"))
    return [r for r in rows if isinstance(r, dict)], names


def resolve_identities(entries: Sequence[Mapping[str, Any]],
                       instruments: Sequence[Mapping[str, Any]],
                       schedule_names: Mapping[int, str],
                       ) -> list[Identity | Unresolved]:
    """Look each name up; demand that ticker, ISIN AND exchange all agree.

    Letters alone are a trap: NWG_US_EQ is NatWest's New York ADR in dollars,
    while NatWest in London is RBSl_EQ (FACTS row q). The lookup runs by
    shortName on the RIGHT market, then the answer must match the pinned
    ticker and ISIN in the agreed file -- one disagreement and the name is out.
    """
    by_ticker = {str(r.get("ticker")): r for r in instruments}
    out: list[Identity | Unresolved] = []
    for entry in entries:
        yf = str(entry.get("yfinance", ""))
        name = str(entry.get("name", ""))
        sleeve = str(entry.get("sleeve", ""))
        exchange = str(entry.get("exchange", ""))

        def no(reason: str) -> Unresolved:
            return Unresolved(yf, name, sleeve, exchange, reason)

        market = MARKET_OF_EXCHANGE.get(exchange)
        if market is None:
            out.append(no(f"exchange {exchange!r} is not one anchors may use"))
            continue
        found = verify_universe.resolve(
            [(yf, market, str(entry.get("quote_currency", "")))],
            instruments=instruments, exchanges=schedule_names)[0]
        if not found.ok or not found.tradable or found.t212_ticker is None:
            out.append(no(f"not found on {market}: {found.reason}"))
            continue
        if found.t212_ticker != entry.get("t212_ticker"):
            out.append(no(f"resolves to {found.t212_ticker}, but the agreed file "
                          f"says {entry.get('t212_ticker')}"))
            continue
        if found.isin != entry.get("isin"):
            out.append(no(f"ISIN {found.isin} disagrees with the agreed "
                          f"{entry.get('isin')}"))
            continue
        if found.exchange != exchange:
            out.append(no(f"listed on {found.exchange}, agreed on {exchange}"))
            continue
        row = by_ticker.get(found.t212_ticker, {})
        schedule = row.get("workingScheduleId")
        out.append(Identity(
            yfinance=yf, name=name, sleeve=sleeve, market=market,
            exchange=exchange, t212_ticker=found.t212_ticker, isin=str(found.isin),
            currency=str(found.currency or ""), kind=str(found.kind or ""),
            aim=found.aim,
            schedule_id=(int(schedule) if isinstance(schedule, int)
                         and not isinstance(schedule, bool) else None)))
    return out


# ================================================================== F6 ===

@dataclass(frozen=True, slots=True)
class Quote:
    """One price with its unit and where it came from. ``unit`` is a currency
    code (GBP, GBX/GBp, USD) or NATIVE, meaning "as the exchange quotes it",
    which is converted with Trading 212's own currency code for the name."""

    price: float
    unit: str
    source: str
    as_of: date


NATIVE = "NATIVE"
PENCE_UNITS = frozenset({"GBX", "GBp"})


def to_gbp(price: float, unit: str, usd_per_gbp: float | None) -> float:
    """One conversion, in one place. Pence /100; dollars at the stored rate."""
    if not math.isfinite(price) or price <= 0:
        raise UnitUnknown(f"{price!r} is not a price")
    if unit == "GBP":
        return price
    if unit in PENCE_UNITS:
        return price / 100.0
    if unit == "USD":
        if usd_per_gbp is None or not math.isfinite(usd_per_gbp) or usd_per_gbp <= 0:
            raise UnitUnknown("a dollar price needs the stored GBP/USD rate")
        return price / usd_per_gbp
    raise UnitUnknown(f"no rule converts a price in {unit!r} to pounds")


def clean_close(symbol: str, clean_root: Path | None = None) -> Quote | None:
    """The latest daily close in the clean store, in the store's own unit.

    The store is in POUNDS for London (pence were divided once, at the front
    door) and dollars for the US, and every row says which in ``currency``.
    That column is read, never assumed -- dividing again is scar #22.
    """
    import pandas as pd

    path = (clean_root or CLEAN_ROOT) / "daily" / f"{symbol}.parquet"
    if not path.is_file():
        return None
    frame = pd.read_parquet(path)
    if frame.empty or "close" not in frame.columns or "currency" not in frame.columns:
        return None
    last = frame.iloc[-1]
    stamp = pd.Timestamp(frame.index[-1])
    return Quote(price=float(last["close"]), unit=str(last["currency"]),
                 source="clean daily close", as_of=stamp.date())


def raw_last(symbol: str, raw_root: Path | None = None) -> Quote | None:
    """The newest recorded intraday bar, in the units the provider served.

    This is the SECOND price, and its value is that it took a different road:
    raw, before the front door touched it, converted afterwards with Trading
    212's currency code rather than the provider's label.
    """
    import pandas as pd

    base = (raw_root or RAW_ROOT) / "intraday"
    for interval in ("1m", "5m"):
        folder = base / interval / symbol
        files = sorted(folder.glob("*.parquet")) if folder.is_dir() else []
        for path in reversed(files[-3:]):
            try:
                frame = pd.read_parquet(path)
            except (OSError, ValueError) as exc:
                print(f"anchors: skipped unreadable {interval} file for {symbol} "
                      f"({type(exc).__name__})")
                continue
            if frame.empty or "close" not in frame.columns:
                continue
            stamp = pd.Timestamp(frame.index[-1])
            return Quote(price=float(frame["close"].iloc[-1]), unit=NATIVE,
                         source=f"raw {interval} bar", as_of=stamp.date())
    return None


@dataclass(frozen=True, slots=True)
class Sizing:
    quantity: Decimal
    value_gbp: float            # quantity x the sizing price
    est_gbp: float              # all-in at the LARGER price, with costs
    note: str


def size_anchor(price_gbp: float, cap_price_gbp: float,
                instrument: costs.Instrument) -> Sizing:
    """Round DOWN to the assumed precision; lift to the assumed minimum.

    The estimate the GBP 3 cap is judged on uses the larger of the two prices
    plus the cost model's charges (FX fee, stamp duty, spread, slippage), so
    the cap errs towards refusing.
    """
    price = Decimal(repr(price_gbp))
    quantity = (Decimal(repr(TARGET_GBP)) / price).quantize(QUANTUM, ROUND_DOWN)
    note = ""
    minimum = Decimal(repr(ASSUMED_MIN_ORDER_GBP))
    if quantity * price < minimum:
        quantity = (minimum / price).quantize(QUANTUM, ROUND_UP)
        note = f"raised to the assumed GBP {ASSUMED_MIN_ORDER_GBP:.2f} minimum"
    consideration = float(quantity) * max(price_gbp, cap_price_gbp)
    est = consideration + costs.leg_cost(instrument, consideration, "BUY").total_gbp
    return Sizing(quantity=quantity, value_gbp=float(quantity) * price_gbp,
                  est_gbp=est, note=note)


# ================================================================== F7 ===

Schedules = Mapping[int, Sequence[tuple[datetime, str]]]


def parse_schedules(exchanges: Sequence[Mapping[str, Any]]) -> dict[int, list[tuple[datetime, str]]]:
    """Broker calendar: schedule id -> time-ordered (UTC moment, event type)."""
    out: dict[int, list[tuple[datetime, str]]] = {}
    for exchange in exchanges:
        for schedule in exchange.get("workingSchedules") or []:
            if not isinstance(schedule, dict) or not isinstance(schedule.get("id"), int):
                continue
            events: list[tuple[datetime, str]] = []
            for event in schedule.get("timeEvents") or []:
                if not isinstance(event, dict):
                    continue
                try:
                    moment = datetime.fromisoformat(
                        str(event.get("date", "")).replace("Z", "+00:00"))
                except ValueError:
                    continue
                if moment.tzinfo is None:
                    continue
                events.append((moment.astimezone(timezone.utc), str(event.get("type"))))
            out[int(schedule["id"])] = sorted(events)
    return out


def clock_says_open(market: str, now: datetime) -> tuple[bool, str]:
    """The exchange's own clock, from a real timezone database -- the UK and
    the US change clocks on different dates (2026-10-25 and 2026-11-01)."""
    zone_name, opens, closes = SESSIONS[market]
    zone = ZoneInfo(zone_name)
    local = now.astimezone(zone)
    if local.weekday() >= 5:
        return False, f"weekend on the {market} clock"
    start = datetime.combine(local.date(), opens, tzinfo=zone) + OPEN_MARGIN
    end = datetime.combine(local.date(), closes, tzinfo=zone) - CLOSE_MARGIN
    if not start <= local <= end:
        return False, (f"outside {opens:%H:%M}-{closes:%H:%M} {zone_name} "
                       f"(less the margins) at {local:%a %H:%M} local")
    return True, f"open, {local:%H:%M} {zone_name}"


def broker_says_open(events: Sequence[tuple[datetime, str]],
                     now: datetime) -> tuple[bool, str]:
    """The broker's calendar knows holidays and half-days; a clock does not."""
    past = [e for e in events if e[0] <= now]
    future = [e for e in events if e[0] > now]
    if not past or not future:
        return False, "the broker's calendar does not cover this moment"
    moment, kind = past[-1]
    if kind != "OPEN":
        return False, f"the broker's calendar says {kind} since {moment:%a %H:%M} UTC"
    if now - moment < OPEN_MARGIN:
        return False, "the session has only just opened"
    if future[0][0] - now < CLOSE_MARGIN:
        return False, "the session closes too soon"
    return True, "open by the broker's calendar"


def session_open(identity: Identity, now: datetime,
                 schedules: Schedules | None) -> tuple[bool, str]:
    """Both must say open. Either saying shut means shut -- never queue (P4)."""
    clock_ok, clock_note = clock_says_open(identity.market, now)
    if not clock_ok:
        return False, clock_note
    schedule_id = identity.schedule_id
    if schedules is None or schedule_id is None or schedule_id not in schedules:
        return False, "no broker calendar for this name, so not treated as open"
    broker_ok, broker_note = broker_says_open(schedules[schedule_id], now)
    if not broker_ok:
        return False, broker_note
    return True, clock_note


# ============================================================ planning ===

@dataclass(frozen=True, slots=True)
class Quotes:
    clean: Quote | None
    raw: Quote | None


@dataclass(frozen=True, slots=True)
class Row:
    yfinance: str
    name: str
    exchange: str
    t212_ticker: str
    unit_note: str
    price_gbp: float | None
    quantity: Decimal | None
    est_gbp: float | None
    fractional: str
    held: str
    decision: str
    reason: str
    market: str = ""
    identity: Identity | None = None


@dataclass(slots=True)
class Plan:
    rows: list[Row]
    now: datetime
    committed_before_gbp: float
    orders_today_before: int
    notes: list[str] = field(default_factory=list)

    def to_buy(self) -> list[Row]:
        return [r for r in self.rows if r.decision in (WOULD_BUY, WAIT)]

    def est_total_gbp(self) -> float:
        return sum(r.est_gbp or 0.0 for r in self.to_buy())


def position_ticker(row: Mapping[str, Any]) -> str:
    """Positions carry the ticker inside ``instrument``; orders at the top."""
    instrument = row.get("instrument")
    if isinstance(instrument, dict) and instrument.get("ticker"):
        return str(instrument["ticker"])
    return str(row.get("ticker", ""))


def held_quantities(positions: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for row in positions:
        quantity = row.get("quantity")
        if isinstance(quantity, (int, float)) and not isinstance(quantity, bool):
            out[position_ticker(row)] = out.get(position_ticker(row), 0.0) + float(quantity)
    return out


def _price_text(price: float) -> str:
    """Plain digits, never scientific notation: 11,848 pence must read as such."""
    if price >= 1000:
        return f"{price:,.0f}"
    if price >= 1:
        return f"{price:,.2f}"
    return f"{price:.4f}"


def _skip_reason_key(reason: str) -> str:
    return reason.split(":", 1)[0]


def build_plan(*, identities: Sequence[Identity | Unresolved],
               quotes: Mapping[str, Quotes],
               fx: Quote | None,
               positions: Sequence[Mapping[str, Any]] | None,
               pending: Sequence[Mapping[str, Any]] | None,
               ledger: AnchorLedger,
               now: datetime,
               schedules: Schedules | None,
               killswitch_on: bool) -> Plan:
    """Decide every name, cheapest and most certain refusal first. Pure: no
    network, no orders -- the dry run prints this; the live run re-checks each
    BUY against fresh broker reads before it sends anything."""
    states = ledger.states()
    blocking = {s.ticker for s in states.values() if s.state in BLOCKING}
    anchors_held = ledger.anchor_quantities()
    committed = ledger.committed_gbp()
    today = ledger.orders_on(now.astimezone(timezone.utc).date())
    plan = Plan(rows=[], now=now, committed_before_gbp=committed,
                orders_today_before=today)
    running_gbp = committed
    running_orders = today
    held = held_quantities(positions) if positions is not None else None
    pending_tickers = ({position_ticker(p) for p in pending}
                       if pending is not None else None)
    usd_per_gbp = fx.price if fx is not None else None
    if fx is not None and (now.date() - fx.as_of).days > MAX_PRICE_AGE_DAYS:
        usd_per_gbp = None
        plan.notes.append(f"GBP/USD rate is from {fx.as_of}, too old to use")

    for item in identities:
        if isinstance(item, Unresolved):
            plan.rows.append(Row(item.yfinance, item.name, item.exchange, "-",
                                 "-", None, None, None, "-", "-", SKIP,
                                 f"identity: {item.reason}"))
            continue
        ident = item
        ticker = ident.t212_ticker
        held_qty = held.get(ticker) if held is not None else None
        anchor_qty = anchors_held.get(ticker, 0.0)
        if held is None:
            held_note = "UNKNOWN (positions unreadable)"
        elif held_qty:
            held_note = f"yes {held_qty:g}"
            if anchor_qty and abs(held_qty - anchor_qty) > 1e-9:
                held_note += f" (anchor ledger says {anchor_qty:g}: FLAG)"
        else:
            held_note = "no"
        if pending_tickers is not None and ticker in pending_tickers:
            held_note += ", order pending"
        fractional = ("yes (held fractionally)"
                      if held_qty and held_qty != int(held_qty) else "UNKNOWN")

        def row(decision: str, reason: str, unit_note: str = "-",
                price: float | None = None, sizing: Sizing | None = None,
                ident: Identity = ident, held_note: str = held_note,
                fractional: str = fractional) -> Row:
            return Row(ident.yfinance, ident.name, ident.exchange,
                       ident.t212_ticker, unit_note, price,
                       sizing.quantity if sizing else None,
                       sizing.est_gbp if sizing else None, fractional,
                       held_note, decision, reason, ident.market, ident)

        if killswitch_on:
            plan.rows.append(row(SKIP, "killswitch: STOP_NEW_TRADES is present"))
            continue
        if ticker in blocking:
            plan.rows.append(row(SKIP, "unresolved order: an earlier anchor order "
                                       "has no confirmed outcome -- never resend"))
            continue
        if held is None or pending_tickers is None:
            plan.rows.append(row(SKIP, "no broker read: cannot confirm it is not "
                                       "already held or pending"))
            continue
        if held_qty:
            plan.rows.append(row(SKIP, "held: the broker already prices it"))
            continue
        if ticker in pending_tickers:
            plan.rows.append(row(SKIP, "pending: an order is already waiting"))
            continue

        pair = quotes.get(ident.yfinance, Quotes(None, None))
        if pair.clean is None or pair.raw is None:
            missing = "clean daily close" if pair.clean is None else "raw bar"
            plan.rows.append(row(SKIP, f"no price: {missing} missing -- two "
                                       "prices are needed to trust the units"))
            continue
        stale = [q.source for q in (pair.clean, pair.raw)
                 if (now.date() - q.as_of).days > MAX_PRICE_AGE_DAYS]
        if stale:
            plan.rows.append(row(SKIP, f"stale price: {', '.join(stale)} older "
                                       f"than {MAX_PRICE_AGE_DAYS} days"))
            continue
        try:
            sizing_gbp = to_gbp(pair.clean.price, pair.clean.unit, usd_per_gbp)
            check_gbp = to_gbp(pair.raw.price, ident.currency, usd_per_gbp)
        except UnitUnknown as exc:
            plan.rows.append(row(SKIP, f"unit unknown: {exc}"))
            continue
        unit_note = (f"clean {_price_text(pair.clean.price)} {pair.clean.unit}"
                     f" | raw {_price_text(pair.raw.price)} {ident.currency}")
        gap = abs(sizing_gbp / check_gbp - 1.0)
        if gap > PRICE_AGREEMENT:
            plan.rows.append(row(SKIP, f"prices disagree: GBP {sizing_gbp:,.4f} vs "
                                       f"GBP {check_gbp:,.4f} ({gap:.0%}) -- a "
                                       "units slip looks exactly like this",
                                 unit_note, sizing_gbp))
            continue
        instrument = costs.Instrument(ticker=ticker, currency=ident.currency,
                                      market=ident.market, kind=ident.kind,
                                      aim=ident.aim)
        sizing = size_anchor(sizing_gbp, check_gbp, instrument)
        if sizing.quantity <= 0:
            plan.rows.append(row(SKIP, "sizing: no positive quantity", unit_note,
                                 sizing_gbp))
            continue
        if sizing.est_gbp > MAX_ORDER_GBP:
            plan.rows.append(row(SKIP, f"over GBP 3 cap: est GBP "
                                       f"{sizing.est_gbp:,.2f} for "
                                       f"{sizing.quantity} at the larger price",
                                 unit_note, sizing_gbp, sizing))
            continue
        if running_gbp + sizing.est_gbp > LIFETIME_CAP_GBP:
            plan.rows.append(row(SKIP, f"lifetime cap: GBP {running_gbp:,.2f} "
                                       f"committed of GBP {LIFETIME_CAP_GBP:,.0f}",
                                 unit_note, sizing_gbp, sizing))
            continue
        if running_orders >= MAX_ORDERS_PER_DAY:
            plan.rows.append(row(SKIP, f"daily limit: {MAX_ORDERS_PER_DAY} orders "
                                       "today already", unit_note, sizing_gbp,
                                 sizing))
            continue
        running_gbp += sizing.est_gbp
        running_orders += 1
        open_now, why = session_open(ident, now, schedules)
        suffix = f"; {sizing.note}" if sizing.note else ""
        if open_now:
            plan.rows.append(row(WOULD_BUY, f"buy now ({why}){suffix}", unit_note,
                                 sizing_gbp, sizing))
        else:
            plan.rows.append(row(WAIT, f"market shut now ({why}) -- would buy in "
                                       f"session{suffix}", unit_note, sizing_gbp,
                                 sizing))
    return plan


# ======================================================== the clients ===

class BrokerReader:
    """F11: reads only. This class has no method that can place anything.

    The dry run uses nothing else, and the live run uses it for every read, so
    the order key is only ever used for the account check and the buy itself.
    """

    def __init__(self, client: T212DemoClient | None = None) -> None:
        self._client = client or T212DemoClient()

    def positions(self) -> list[dict[str, Any]]:
        return self._client.positions()

    def pending_orders(self) -> list[dict[str, Any]]:
        return self._client.pending_orders()

    def exchanges(self) -> list[dict[str, Any]]:
        return self._client.exchanges()

    def history_orders(self, ticker: str) -> list[dict[str, Any]]:
        return self._client.history_orders(ticker=ticker)


class Reader(Protocol):
    def positions(self) -> list[dict[str, Any]]: ...
    def pending_orders(self) -> list[dict[str, Any]]: ...
    def exchanges(self) -> list[dict[str, Any]]: ...
    def history_orders(self, ticker: str) -> list[dict[str, Any]]: ...


OrderTransport = Callable[[str, str, Mapping[str, str], bytes | None], Response]


class OrderTransportError(RuntimeError):
    """No reply we can read. The order may or may not exist."""


class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    """A redirect could carry an order somewhere else. Never follow one."""

    def redirect_request(self, req: urllib.request.Request, fp: IO[bytes],
                         code: int, msg: str, headers: HTTPMessage,
                         newurl: str) -> urllib.request.Request | None:
        return None


def order_transport(method: str, url: str, headers: Mapping[str, str],
                    body: bytes | None) -> Response:
    """The real network, for the two allowed calls only, practice host only."""
    assert_demo_url(url)
    path = urlsplit(url).path.removeprefix(urlsplit(DEMO_BASE_URL).path)
    if (method, path) not in _ALLOWED_CALLS:
        raise AnchorRefused(f"the anchor buyer may not make {method} {path}")
    request = urllib.request.Request(url, data=body, method=method)  # noqa: S310
    for name, value in headers.items():
        request.add_header(name, value)
    opener = urllib.request.build_opener(_RefuseRedirects)
    try:
        with opener.open(request, timeout=ORDER_TIMEOUT_SECONDS) as reply:
            return Response(status=reply.status,
                            headers={k.lower(): v for k, v in reply.headers.items()},
                            body=reply.read())
    except urllib.error.HTTPError as exc:
        return Response(status=exc.code,
                        headers={k.lower(): v for k, v in (exc.headers or {}).items()},
                        body=exc.read() if hasattr(exc, "read") else b"")
    except (urllib.error.URLError, OSError) as exc:
        raise OrderTransportError(f"no reply ({type(exc).__name__})") from None


@dataclass(frozen=True, slots=True)
class OrderOutcome:
    status: str                  # ACCEPTED or UNRESOLVED
    order_id: int | None
    http_status: int | None
    broker_status: str
    detail: str


class AnchorOrderClient:
    """F1/F2/F3: practice host, order key, buy only. Constructed ONLY by --live."""

    def __init__(self, credentials: Credentials,
                 transport: OrderTransport | None = None,
                 base_url: str = DEMO_BASE_URL,
                 throttle: Throttle | None = None) -> None:
        if base_url != DEMO_BASE_URL:
            raise LiveServerRefused(
                "the anchor order client is fixed to the practice server")
        self._credentials = credentials
        self._transport: OrderTransport = transport or order_transport
        self._throttle = throttle or Throttle()

    def _headers(self, with_body: bool) -> dict[str, str]:
        headers = {"Authorization": self._credentials.basic_auth_header(),
                   "Accept": "application/json"}
        if with_body:
            headers["Content-Type"] = "application/json"
        return headers

    def account_summary(self) -> dict[str, Any]:
        url = DEMO_BASE_URL + ACCOUNT_PATH
        assert_demo_url(url)
        self._throttle.before("anchor_account", ACCOUNT_ENDPOINT)
        try:
            response = self._transport(_GET, url, self._headers(False), None)
        except OrderTransportError as exc:
            raise AnchorRefused(f"the order key's account check got {exc}") from None
        if response.status != 200:
            raise AnchorRefused(
                f"the order key's account check failed: HTTP {response.status} "
                "(a 401 is a bad key, a 403 a missing Account data permission)")
        try:
            payload = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise AnchorRefused("the account check reply was not JSON") from None
        if not isinstance(payload, dict):
            raise AnchorRefused("the account check reply was not an object")
        return payload

    def buy(self, ticker: str, quantity: Decimal, est_gbp: float) -> OrderOutcome:
        """One market BUY. There is no sell -- and a non-positive quantity,
        which is how the API spells a sell (FACTS row t), raises here."""
        if (not isinstance(quantity, Decimal) or not quantity.is_finite()
                or quantity <= 0):
            raise AnchorRefused("buy only: the quantity must be a positive number")
        if not 0 < est_gbp <= MAX_ORDER_GBP:
            raise AnchorRefused(f"an anchor order may not exceed GBP "
                                f"{MAX_ORDER_GBP:.2f} (estimate GBP {est_gbp:,.2f})")
        text = format(quantity, "f")
        body = ('{"ticker": ' + json.dumps(ticker) + ', "quantity": ' + text
                + ', "extendedHours": false}').encode("utf-8")
        url = DEMO_BASE_URL + MARKET_ORDER_PATH
        assert_demo_url(url)
        self._throttle.before("anchor_order", ORDER_ENDPOINT)
        try:
            response = self._transport(_POST, url, self._headers(True), body)
        except AnchorRefused:
            raise
        except Exception as exc:  # noqa: BLE001 - any failure here is UNRESOLVED
            return OrderOutcome(UNRESOLVED, None, None, "",
                                f"no usable reply: {type(exc).__name__}")
        snippet = response.body[:200].decode("utf-8", errors="replace")
        if response.status != 200:
            return OrderOutcome(UNRESOLVED, None, response.status, "",
                                f"HTTP {response.status}: {snippet}")
        try:
            payload = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return OrderOutcome(UNRESOLVED, None, 200, "", "HTTP 200 but not JSON")
        order_id = payload.get("id") if isinstance(payload, dict) else None
        if not isinstance(order_id, int) or isinstance(order_id, bool):
            return OrderOutcome(UNRESOLVED, None, 200, "", "HTTP 200 with no order id")
        return OrderOutcome(ACCEPTED, order_id, 200, str(payload.get("status", "")),
                            "accepted")


# ======================================================= reconciliation ===

def _parse_moment(text: object) -> datetime | None:
    try:
        moment = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo is not None else None


def _matches(order: Mapping[str, Any], state: IntentState) -> bool:
    if state.order_id is not None:
        return order.get("id") == state.order_id
    created = _parse_moment(order.get("createdAt"))
    intended = _parse_moment(state.at_utc)
    quantity = order.get("quantity")
    return (str(order.get("ticker", "")) == state.ticker
            and order.get("side") == "BUY"
            and order.get("initiatedFrom", "API") == "API"
            and isinstance(quantity, (int, float))
            and abs(float(quantity) - state.quantity) < 1e-9
            and created is not None and intended is not None
            and created >= intended - timedelta(minutes=2))


def reconcile(ledger: AnchorLedger, reader: Reader, now: datetime) -> list[str]:
    """Settle every unheard or unconfirmed order from the BROKER'S record.

    Found in history: FILLED, or NOT_FILLED when rejected/cancelled with nothing
    filled. Still pending: left blocking. Found nowhere: NOT_PLACED, but only once
    RECONCILE_AFTER has passed -- an order seconds old may not be listed yet.
    """
    notes: list[str] = []
    open_states = ledger.blocking()
    if not open_states:
        return notes
    pending = reader.pending_orders()
    for state in open_states:
        if any(_matches(p, state) for p in pending):
            notes.append(f"{state.ticker}: still pending at the broker")
            continue
        history = reader.history_orders(state.ticker)
        found = [item for item in history
                 if isinstance(item.get("order"), dict)
                 and _matches(item["order"], state)]
        if found:
            order = found[0]["order"]
            fill = found[0].get("fill") if isinstance(found[0].get("fill"), dict) else {}
            filled = order.get("filledQuantity")
            filled_qty = float(filled) if isinstance(filled, (int, float)) else 0.0
            impact = fill.get("walletImpact") if isinstance(fill, dict) else None
            net = (impact.get("netValue") if isinstance(impact, dict) else None)
            status = FILLED if filled_qty > 0 else NOT_FILLED
            ledger.append({
                "kind": RECONCILED, "intent_id": state.intent_id,
                "at_utc": now.isoformat(), "status": status,
                "order_id": order.get("id"), "filled_quantity": filled_qty,
                "filled_gbp": abs(float(net)) if isinstance(net, (int, float)) else 0.0,
                "detail": f"broker order history: {order.get('status')}"})
            notes.append(f"{state.ticker}: settled {status} from order history")
            continue
        intended = _parse_moment(state.at_utc)
        if (state.order_id is None and intended is not None
                and now - intended >= RECONCILE_AFTER):
            ledger.append({
                "kind": RECONCILED, "intent_id": state.intent_id,
                "at_utc": now.isoformat(), "status": NOT_PLACED,
                "detail": "no trace in pending orders or order history"})
            notes.append(f"{state.ticker}: settled NOT_PLACED (no trace anywhere)")
        else:
            notes.append(f"{state.ticker}: STILL UNRESOLVED -- not resent")
    return notes


# ================================================================ inputs ===

@dataclass(slots=True)
class Inputs:
    identities: list[Identity | Unresolved]
    quotes: dict[str, Quotes]
    fx: Quote | None


def load_inputs(*, universe_path: Path | None = None,
                instruments_file: Path | None = None,
                exchanges_file: Path | None = None,
                clean_root: Path | None = None,
                raw_root: Path | None = None) -> Inputs:
    entries = load_universe(universe_path)
    instruments, names = load_verified_lists(instruments_file, exchanges_file)
    identities = resolve_identities(entries, instruments, names)
    quotes = {str(e["yfinance"]): Quotes(clean_close(str(e["yfinance"]), clean_root),
                                         raw_last(str(e["yfinance"]), raw_root))
              for e in entries}
    return Inputs(identities=identities, quotes=quotes,
                  fx=clean_close(FX_SYMBOL, clean_root))


def _read(what: str, call: Callable[[], list[dict[str, Any]]],
          notes: list[str]) -> list[dict[str, Any]] | None:
    try:
        return call()
    except (BrokerError, CredentialsMissing) as exc:
        notes.append(f"could not read {what}: {exc}")
        return None


# =============================================================== dry run ===

def run_dry(*, inputs: Inputs, reader: Reader, ledger: AnchorLedger | None = None,
            now: datetime | None = None, root: Path | None = None) -> Plan:
    """F11: reads, decides, prints. Constructs no order client and writes nothing
    to the ledger."""
    moment = now or datetime.now(timezone.utc)
    notes: list[str] = []
    positions = _read("positions", reader.positions, notes)
    pending = _read("pending orders", reader.pending_orders, notes)
    exchanges = _read("the broker's calendar", reader.exchanges, notes)
    plan = build_plan(identities=inputs.identities, quotes=inputs.quotes,
                      fx=inputs.fx, positions=positions, pending=pending,
                      ledger=ledger or AnchorLedger(), now=moment,
                      schedules=(parse_schedules(exchanges)
                                 if exchanges is not None else None),
                      killswitch_on=safety.killswitch_armed(root))
    plan.notes[:0] = notes
    return plan


# ============================================================== live run ===

@dataclass(slots=True)
class LiveReport:
    plan: Plan | None
    lines: list[str] = field(default_factory=list)
    accepted: list[str] = field(default_factory=list)
    halted: str = ""


def run_live(*, inputs: Inputs, reader: Reader, orderer: AnchorOrderClient,
             ledger: AnchorLedger | None = None,
             now_fn: Callable[[], datetime] | None = None,
             root: Path | None = None,
             sleep: Callable[[float], None] = time.sleep) -> LiveReport:
    """Practice orders, one at a time, every fence re-checked before each."""
    clock = now_fn or (lambda: datetime.now(timezone.utc))
    book = ledger or AnchorLedger()
    report = LiveReport(plan=None)
    say = report.lines.append

    if safety.killswitch_armed(root):
        report.halted = "killswitch: STOP_NEW_TRADES is present -- no anchor bought"
        say(report.halted)
        return report

    summary = orderer.account_summary()
    if summary.get("currency") != "GBP":
        raise AnchorRefused(
            f"the order key's account reports currency {summary.get('currency')!r}, "
            "not GBP -- refusing")
    say("order key: practice server, account currency GBP")

    try:
        for note in reconcile(book, reader, clock()):
            say(f"reconcile: {note}")
        still_open = book.blocking()
        if still_open:
            report.halted = (f"{len(still_open)} anchor order(s) still have no "
                             "confirmed outcome -- nothing is sent until they do")
            say(report.halted)
            return report
        schedules = parse_schedules(reader.exchanges())
        positions_now = reader.positions()
        pending_now = reader.pending_orders()
    except (BrokerError, CredentialsMissing) as exc:
        report.halted = f"could not read the broker before starting: {exc}"
        say(report.halted)
        return report
    plan = build_plan(identities=inputs.identities, quotes=inputs.quotes,
                      fx=inputs.fx, positions=positions_now,
                      pending=pending_now, ledger=book, now=clock(),
                      schedules=schedules, killswitch_on=False)
    report.plan = plan

    for row in plan.rows:
        if (row.decision != WOULD_BUY or row.identity is None
                or row.quantity is None or row.est_gbp is None):
            continue
        ticker = row.t212_ticker
        if safety.killswitch_armed(root):                          # F9
            report.halted = "killswitch appeared mid-run -- stopped"
            break
        moment = clock()
        open_now, why = session_open(row.identity, moment, schedules)  # F7
        if not open_now:
            say(f"{ticker}: skipped, {why}")
            continue
        if book.orders_on(moment.date()) >= MAX_ORDERS_PER_DAY:   # F5
            report.halted = "daily order limit reached"
            break
        if book.committed_gbp() + row.est_gbp > LIFETIME_CAP_GBP:
            say(f"{ticker}: skipped, lifetime cap")
            continue
        if ticker in book.blocking_tickers():                      # F8
            say(f"{ticker}: skipped, unresolved earlier order")
            continue
        try:
            positions = reader.positions()
            pending = reader.pending_orders()
        except (BrokerError, CredentialsMissing) as exc:
            report.halted = f"could not re-read the broker before {ticker}: {exc}"
            break
        if held_quantities(positions).get(ticker):
            say(f"{ticker}: skipped, already held")
            continue
        if ticker in {position_ticker(p) for p in pending}:
            say(f"{ticker}: skipped, an order is pending")
            continue

        intent_id = f"anchor-{moment:%Y%m%dT%H%M%S%f}-{ticker}"
        book.append({"kind": INTENT, "intent_id": intent_id,
                     "at_utc": moment.isoformat(), "ticker": ticker,
                     "yfinance": row.yfinance, "isin": row.identity.isin,
                     "quantity": format(row.quantity, "f"),
                     "est_gbp": round(row.est_gbp, 4),
                     "price_gbp": row.price_gbp, "mode": "live-practice"})
        try:
            outcome = orderer.buy(ticker, row.quantity, row.est_gbp)
        except AnchorRefused as exc:
            book.append({"kind": OUTCOME, "intent_id": intent_id,
                         "at_utc": clock().isoformat(), "status": UNRESOLVED,
                         "detail": f"refused before sending: {exc}"})
            report.halted = f"{ticker}: {exc}"
            break
        book.append({"kind": OUTCOME, "intent_id": intent_id,
                     "at_utc": clock().isoformat(), "status": outcome.status,
                     "order_id": outcome.order_id,
                     "http_status": outcome.http_status,
                     "broker_status": outcome.broker_status,
                     "detail": outcome.detail})
        if outcome.status != ACCEPTED:
            report.halted = (f"{ticker}: outcome unknown ({outcome.detail}) -- "
                             "run halted; reconciled on the next run, never resent")
            break
        report.accepted.append(ticker)
        say(f"{ticker}: accepted, order {outcome.order_id}, qty {row.quantity}")

    if report.halted:
        say(f"HALTED: {report.halted}")
    if report.accepted:
        sleep(SETTLE_SECONDS)
        held = held_quantities(reader.positions())
        landed = [t for t in report.accepted if held.get(t)]
        say(f"broker now holds {len(landed)} of the {len(report.accepted)} "
            "anchors accepted this run")
    return report


# ============================================================== reporting ===

def render(plan: Plan) -> str:
    head = (f"{'name':<8} {'exchange':<9} {'T212 ticker':<12} "
            f"{'price source / unit':<36} {'GBP price':>10} {'quantity':>9} "
            f"{'est GBP':>8} {'fractional?':<24} {'held?':<14} decision")
    lines = [f"ANCHOR PLAN {plan.now:%Y-%m-%d %H:%M} UTC  (practice account)", head,
             "-" * len(head)]
    for r in plan.rows:
        lines.append(
            f"{r.yfinance:<8} {r.exchange[:9]:<9} {r.t212_ticker:<12} "
            f"{r.unit_note[:36]:<36} "
            f"{(f'{r.price_gbp:,.4f}' if r.price_gbp else '-'):>10} "
            f"{(str(r.quantity) if r.quantity is not None else '-'):>9} "
            f"{(f'{r.est_gbp:,.2f}' if r.est_gbp is not None else '-'):>8} "
            f"{r.fractional:<24} {r.held[:14]:<14} {r.decision}: {r.reason}")
    to_buy = plan.to_buy()
    skips: dict[str, int] = {}
    for r in plan.rows:
        if r.decision == SKIP:
            key = _skip_reason_key(r.reason)
            skips[key] = skips.get(key, 0) + 1
    lines += [
        "",
        f"names to buy: {len(to_buy)} "
        f"({sum(r.decision == WOULD_BUY for r in plan.rows)} now, "
        f"{sum(r.decision == WAIT for r in plan.rows)} when their market opens)",
        f"est GBP total: {plan.est_total_gbp():,.2f}, plus GBP "
        f"{plan.committed_before_gbp:,.2f} already committed, against the GBP "
        f"{LIFETIME_CAP_GBP:,.0f} lifetime cap",
        "skips by reason: " + (", ".join(f"{k} {v}" for k, v in sorted(skips.items()))
                               or "none"),
    ]
    lines += [f"note: {n}" for n in plan.notes]
    lines += [f"UNKNOWN: {fact}" for fact in UNKNOWN_FACTS]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m qb2.execution.anchors",
        description="P20 anchors on the PRACTICE account. Dry run unless --live.")
    parser.add_argument("--live", action="store_true",
                        help="place practice orders (needs the order key)")
    args = parser.parse_args(argv)
    try:
        refuse_host_overrides()
        inputs = load_inputs()
        reader = BrokerReader()
        if not args.live:
            plan = run_dry(inputs=inputs, reader=reader)
            text = render(plan)
            REPORT_DIR.mkdir(parents=True, exist_ok=True)
            out = REPORT_DIR / f"dry-run-{plan.now:%Y-%m-%d}.txt"
            out.write_text(text + "\n", encoding="utf-8")
            print(text)
            print(f"\n(dry run: nothing was sent; saved to {out.relative_to(REPO_ROOT)})")
            return 0
        orderer = AnchorOrderClient(order_credentials())
        report = run_live(inputs=inputs, reader=reader, orderer=orderer)
        if report.plan is not None:
            print(render(report.plan))
        print("\n".join(report.lines))
        return 1 if report.halted else 0
    except AnchorRefused as exc:
        print(f"REFUSED: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
