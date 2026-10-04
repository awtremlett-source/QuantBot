"""A READ-ONLY doorway to the Trading 212 practice account.

This client cannot trade. Not "does not" -- cannot: there is no method on it that
places, amends or cancels anything, and the one function that touches the network
refuses any HTTP method except GET. Both facts are held by tests in tests/wall/,
so widening this file turns the wall red.

It also only ever talks to the PRACTICE environment. The real-money base URL does
not appear anywhere in this package, which a wall test checks by scanning for it.

Everything it knows about the broker was read from Trading 212's own
documentation and written down, with sources and dates, in docs/t212/FACTS.md.
Three rows from there shape this file:

* **row d1/d2** -- there is no trailing-stop order type and no amend endpoint. So
  our stops are run by our own code (PLAN_V3 P10), and this client never needs to
  place one.
* **row f5/f6** -- rate limits are per ACCOUNT, not per key or per IP, and the
  limiter allows bursts. Two programs sharing one account share one budget, so
  the throttle here is deliberately conservative.
* **row h** -- the API cannot price an instrument we do not hold. ``currentPrice``
  arrives only inside a position. Nothing here pretends otherwise.

Credentials come from the environment (or the repo's .env) and are never logged,
never printed, and never included in an exception message.
"""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

# The PRACTICE environment, and nothing else. FACTS.md row b1.
DEMO_BASE_URL = "https://demo.trading212.com/api/v0"

# Environment variable NAMES (never values). These already exist in .env.example.
KEY_VARIABLE = "T212_API_KEY"
SECRET_VARIABLE = "T212_API_SECRET"

# How long to wait after a rate-limited reply when the broker tells us nothing.
DEFAULT_BACKOFF_SECONDS = 5.0
RATE_LIMITED = 429


class ReadOnlyViolation(RuntimeError):
    """Something tried to send a request that was not a GET."""


class CredentialsMissing(RuntimeError):
    """No API key and secret were found in the environment or .env."""


class BrokerError(RuntimeError):
    """The broker replied with something we cannot use. Never carries a key."""


@dataclass(frozen=True, slots=True)
class Endpoint:
    """One GET we are allowed to make, and how often FACTS.md says we may."""

    path: str
    seconds_between_calls: float
    description: str


# Every endpoint this project reads, with the documented limit from FACTS.md.
# The first five are 1 request per period, so the period IS the minimum spacing;
# order history is 20 per minute, so one every 3 seconds stays inside it.
ENDPOINTS: Mapping[str, Endpoint] = {
    "account_summary": Endpoint("/equity/account/summary", 5.0,
                                "cash and account value (1 req / 5s)"),
    "positions": Endpoint("/equity/positions", 1.0,
                          "open positions, the only source of a price (1 req / 1s)"),
    "pending_orders": Endpoint("/equity/orders", 5.0,
                               "pending orders (1 req / 5s)"),
    "instruments": Endpoint("/equity/metadata/instruments", 50.0,
                            "the tradable universe (1 req / 50s)"),
    "exchanges": Endpoint("/equity/metadata/exchanges", 30.0,
                          "trading hours (1 req / 30s)"),
    "history_orders": Endpoint("/equity/history/orders", 3.0,
                               "past orders, for reconciling (20 req / 1m)"),
}


@dataclass(frozen=True, slots=True)
class Response:
    """What a transport hands back. Deliberately dumb and easy to fake."""

    status: int
    headers: Mapping[str, str]
    body: bytes


# method, url, headers -> Response
Transport = Callable[[str, str, Mapping[str, str]], Response]


def read_env_file(path: Path | None = None) -> dict[str, str]:
    """Parse KEY=VALUE lines from the repo's .env. Values are never logged."""
    env_path = path if path is not None else REPO_ROOT / ".env"
    values: dict[str, str] = {}
    if not env_path.is_file():
        return values
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        values[name.strip()] = value.strip()
    return values


@dataclass(frozen=True, slots=True)
class Credentials:
    """An API key and secret. Its repr hides both, so a traceback cannot leak."""

    key: str
    secret: str

    def __repr__(self) -> str:      # pragma: no cover - trivial, but load-bearing
        return "Credentials(key='<hidden>', secret='<hidden>')"

    def basic_auth_header(self) -> str:
        """`Basic <base64 of key:secret>` -- FACTS.md row a, checked 2026-09-27."""
        raw = f"{self.key}:{self.secret}".encode()
        return "Basic " + base64.b64encode(raw).decode("ascii")

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None,
                         env_file: Path | None = None) -> Credentials:
        """Real environment first, then the repo's .env. Never a literal."""
        import os

        source: dict[str, str] = dict(read_env_file(env_file))
        source.update({k: v for k, v in (environ if environ is not None
                                         else os.environ).items()
                       if k in (KEY_VARIABLE, SECRET_VARIABLE)})
        key = (source.get(KEY_VARIABLE) or "").strip()
        secret = (source.get(SECRET_VARIABLE) or "").strip()
        if not key or not secret:
            raise CredentialsMissing(
                f"set {KEY_VARIABLE} and {SECRET_VARIABLE} in .env "
                f"(practice-account key -- see docs/t212/SETUP.md)")
        return cls(key=key, secret=secret)


def available(environ: Mapping[str, str] | None = None,
              env_file: Path | None = None) -> bool:
    """True when credentials exist. Used to keep the live smoke test off."""
    try:
        Credentials.from_environment(environ, env_file)
    except CredentialsMissing:
        return False
    return True


def urllib_transport(method: str, url: str,
                     headers: Mapping[str, str]) -> Response:
    """The real network. Refuses anything but GET before it opens a socket."""
    if method != "GET":
        raise ReadOnlyViolation(
            f"this client is read-only: {method} is not permitted (url path "
            f"{url.removeprefix(DEMO_BASE_URL)})")
    request = urllib.request.Request(url, method="GET")  # noqa: S310 - fixed https
    for name, value in headers.items():
        request.add_header(name, value)
    try:
        with urllib.request.urlopen(request, timeout=30) as reply:  # noqa: S310
            return Response(status=reply.status,
                            headers={k.lower(): v for k, v in reply.headers.items()},
                            body=reply.read())
    except urllib.error.HTTPError as exc:
        return Response(status=exc.code,
                        headers={k.lower(): v for k, v in (exc.headers or {}).items()},
                        body=exc.read() if hasattr(exc, "read") else b"")
    except urllib.error.URLError as exc:
        # Never let the original exception escape: it can carry the request.
        raise BrokerError(f"could not reach the practice API: {exc.reason}") from None


@dataclass
class Throttle:
    """Keeps us inside the documented limits, and obeys the broker over us.

    Two rules. Ours: wait at least the documented period between calls to the
    same endpoint. Theirs: if a reply carries ``x-ratelimit-reset`` or comes back
    rate-limited, wait as long as it says. Theirs always wins -- FACTS.md rows
    f5-f7, and limits are per ACCOUNT, so being early is not a private mistake.
    """

    monotonic: Callable[[], float] = time.monotonic
    sleeper: Callable[[float], None] = time.sleep
    _last_call: dict[str, float] = field(default_factory=dict)
    waits: list[tuple[str, float]] = field(default_factory=list)

    def before(self, name: str, endpoint: Endpoint) -> None:
        last = self._last_call.get(name)
        now = self.monotonic()
        if last is not None:
            due = last + endpoint.seconds_between_calls
            if now < due:
                self._pause(name, due - now)
        self._last_call[name] = self.monotonic()

    def after(self, name: str, response: Response) -> float:
        """Returns how long we were told to wait; 0.0 when nothing was said."""
        if response.status != RATE_LIMITED:
            return 0.0
        wait = self._reset_wait(response.headers)
        self._pause(f"{name} (rate limited)", wait)
        return wait

    def _reset_wait(self, headers: Mapping[str, str]) -> float:
        """Honour x-ratelimit-reset when present; fall back when it is not.

        The reset header is documented (row f7). Whether it is a Unix timestamp
        or a number of seconds is not something we should bet on, so both are
        accepted and anything unusable falls back to a fixed pause.
        """
        raw = headers.get("x-ratelimit-reset") or headers.get("retry-after")
        if raw is None:
            return DEFAULT_BACKOFF_SECONDS
        try:
            value = float(raw)
        except ValueError:
            return DEFAULT_BACKOFF_SECONDS
        if value > 10_000_000:            # looks like a Unix timestamp
            value -= time.time()
        return min(max(value, 0.0), 300.0) or DEFAULT_BACKOFF_SECONDS

    def _pause(self, reason: str, seconds: float) -> None:
        if seconds <= 0:
            return
        self.waits.append((reason, seconds))
        print(f"t212 throttle: waiting {seconds:.1f}s before {reason}")
        self.sleeper(seconds)


class T212DemoClient:
    """Reads the practice account. Has no method that can trade."""

    def __init__(self, credentials: Credentials | None = None,
                 transport: Transport | None = None,
                 throttle: Throttle | None = None,
                 base_url: str = DEMO_BASE_URL) -> None:
        if not base_url.startswith("https://demo."):
            raise ReadOnlyViolation(
                "this client may only talk to the practice environment")
        self._credentials = credentials
        self._transport: Transport = transport or urllib_transport
        self._throttle = throttle or Throttle()
        self._base_url = base_url

    # ----------------------------------------------------------- the reads ---

    def account_summary(self) -> dict[str, Any]:
        payload = self._read("account_summary")
        return payload if isinstance(payload, dict) else {}

    def positions(self) -> list[dict[str, Any]]:
        return self._read_list("positions")

    def pending_orders(self) -> list[dict[str, Any]]:
        """Needed before any future send: the order endpoints are not idempotent
        (FACTS.md row e), so S10 must look before it leaps."""
        return self._read_list("pending_orders")

    def instruments(self) -> list[dict[str, Any]]:
        return self._read_list("instruments")

    def exchanges(self) -> list[dict[str, Any]]:
        return self._read_list("exchanges")

    def history_orders(self, ticker: str | None = None,
                       limit: int = 50) -> list[dict[str, Any]]:
        """The first page of past orders, newest first, optionally for one ticker.

        Reconciliation reads this to settle an order whose outcome we never
        heard (FACTS row e: a resend could duplicate it). One page of 50 is
        enough for that: the order being looked for is minutes old.
        """
        query = urllib.parse.urlencode(
            {k: v for k, v in (("ticker", ticker), ("limit", min(limit, 50)))
             if v is not None})
        payload = self._read("history_orders", query)
        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            raise BrokerError("history_orders: expected an object with items")
        return [row for row in items if isinstance(row, dict)]

    # ------------------------------------------------------------ the wire ---

    def _headers(self) -> dict[str, str]:
        credentials = self._credentials or Credentials.from_environment()
        return {"Authorization": credentials.basic_auth_header(),
                "Accept": "application/json"}

    def _read(self, name: str, query: str = "") -> object:
        endpoint = ENDPOINTS[name]
        url = f"{self._base_url}{endpoint.path}" + (f"?{query}" if query else "")
        self._throttle.before(name, endpoint)
        response = self._transport("GET", url, self._headers())
        if self._throttle.after(name, response) > 0:
            self._throttle.before(name, endpoint)
            response = self._transport("GET", url, self._headers())
        if response.status != 200:
            raise BrokerError(
                f"{name}: practice API replied {response.status} "
                f"({len(response.body)} bytes)")
        try:
            return json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BrokerError(f"{name}: reply was not JSON ({exc})") from None

    def _read_list(self, name: str) -> list[dict[str, Any]]:
        payload = self._read(name)
        if not isinstance(payload, list):
            raise BrokerError(f"{name}: expected a list, got {type(payload).__name__}")
        return [row for row in payload if isinstance(row, dict)]

    # --------------------------------------------------------- raw landing ---

    def save_instruments_raw(self, destination: Path | None = None,
                             today: date | None = None) -> Path:
        """Drop the instrument list to data/raw/t212/ exactly as received.

        RAW means untouched. It does NOT enter the data store here: that happens
        through S3's front door, which is the only writer, so that every row in
        the store has passed the same checks.
        """
        folder = destination or (REPO_ROOT / "data" / "raw" / "t212")
        folder.mkdir(parents=True, exist_ok=True)
        stamp = (today or date.today()).isoformat()
        target = folder / f"instruments-{stamp}.json"
        target.write_text(json.dumps(self.instruments(), indent=1),
                          encoding="utf-8")
        return target
