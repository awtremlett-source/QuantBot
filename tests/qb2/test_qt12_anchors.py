"""QT-12: the P20 anchor buyer, fence by fence.

The first order path that ever runs, so every fence has a test here, and every
test was watched fail before the fence existed (the session log records it).
OFFLINE throughout: the broker is a fake that records what it was asked, and the
order transport is a fake that never opens a socket. Fields in the fakes come
from Trading 212's own schema pages (docs/t212/FACTS.md rows g, t, w, x).
"""

from __future__ import annotations

import ast
import base64
import inspect
import json
import re
import urllib.request
from collections.abc import Callable, Mapping
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from qb2.execution import anchors, costs, safety
from qb2.execution.anchor_ledger import (ACCEPTED, FILLED, INTENT, NOT_PLACED,
                                         OUTCOME, RECONCILED, UNRESOLVED,
                                         AnchorLedger, LedgerCorrupt)
from qb2.execution.anchors import (NATIVE, SKIP, WAIT, WOULD_BUY,
                                   AnchorOrderClient, AnchorRefused,
                                   BrokerReader, Identity, Inputs,
                                   LiveServerRefused, OrderKeyMissing, Quote,
                                   Quotes, UniverseTampered, Unresolved)
from qb2.execution.t212_client import (DEMO_BASE_URL, Credentials, Response,
                                       Throttle)

REPO_ROOT = Path(__file__).resolve().parents[2]
UTC = timezone.utc
FAKE = Credentials(key="key-not-real-order", secret="secret-not-real-order")

# Monday, inside both regular sessions: 15:45 London (BST), 10:45 New York (EDT).
MON_OVERLAP = datetime(2026, 10, 5, 14, 45, tzinfo=UTC)
SUNDAY = datetime(2026, 10, 4, 18, 0, tzinfo=UTC)

MU = Identity("MU", "Micron Technology", "us_liquid", "US", "NASDAQ",
              "MU_US_EQ", "US5951121038", "USD", "STOCK", False, 53)
AZN = Identity("AZN.L", "AstraZeneca", "uk_share", "LSE", "London Stock Exchange",
               "AZNl_EQ", "GB0009895292", "GBX", "STOCK", False, 55)
VUAG = Identity("VUAG.L", "Vanguard S&P 500 (Acc)", "uk_etf", "LSE",
                "London Stock Exchange", "VUAGl_EQ", "IE00BFMXXD54", "GBP", "ETF",
                False, 55)
IDENTITIES: list[Identity | Unresolved] = [MU, AZN, VUAG]


def quotes_on(day: date, **override: Quotes) -> dict[str, Quotes]:
    """Friday's real closes (clean store) and last raw bars, dated ``day``."""
    base = {
        "MU": Quotes(Quote(1074.89, "USD", "clean daily close", day),
                     Quote(1076.0, NATIVE, "raw 1m bar", day)),
        "AZN.L": Quotes(Quote(118.7, "GBP", "clean daily close", day),
                        Quote(11848.0, NATIVE, "raw 1m bar", day)),
        "VUAG.L": Quotes(Quote(111.8, "GBP", "clean daily close", day),
                         Quote(112.84, NATIVE, "raw 1m bar", day)),
    }
    base.update(override)
    return base


def fx_on(day: date) -> Quote:
    return Quote(1.324, "RATE", "clean daily close", day)


FRIDAY = date(2026, 10, 2)


def calendar(around: date, *, skip_lse: date | None = None) -> list[dict[str, Any]]:
    """A broker calendar shaped like GET /equity/metadata/exchanges, built with
    a real timezone database for the week around ``around``."""
    ny, ldn = ZoneInfo("America/New_York"), ZoneInfo("Europe/London")

    def utc(day: date, hour: int, minute: int, zone: ZoneInfo) -> str:
        local = datetime(day.year, day.month, day.day, hour, minute, tzinfo=zone)
        return local.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    us, lse = [], []
    for offset in range(-4, 5):
        day = around + timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        us += [{"date": utc(day, 4, 0, ny), "type": "PRE_MARKET_OPEN"},
               {"date": utc(day, 9, 30, ny), "type": "OPEN"},
               {"date": utc(day, 16, 0, ny), "type": "AFTER_HOURS_OPEN"},
               {"date": utc(day, 20, 0, ny), "type": "OVERNIGHT_OPEN"}]
        if day != skip_lse:
            lse += [{"date": utc(day, 8, 0, ldn), "type": "OPEN"},
                    {"date": utc(day, 16, 30, ldn), "type": "CLOSE"}]
    return [{"id": 1, "name": "NASDAQ",
             "workingSchedules": [{"id": 53, "timeEvents": us}]},
            {"id": 2, "name": "London Stock Exchange",
             "workingSchedules": [{"id": 55, "timeEvents": lse}]}]


def frozen_throttle() -> Throttle:
    clock = {"now": 1_000.0}

    def sleeper(seconds: float) -> None:
        clock["now"] += seconds

    return Throttle(monotonic=lambda: clock["now"], sleeper=sleeper)


class FakeReader:
    """GETs only, answered from fixtures; counts every call."""

    def __init__(self, *, positions: list[dict[str, Any]] | None = None,
                 pending: list[dict[str, Any]] | None = None,
                 exchanges: list[dict[str, Any]] | None = None,
                 history: Mapping[str, list[dict[str, Any]]] | None = None,
                 positions_seq: list[list[dict[str, Any]]] | None = None) -> None:
        self._positions = positions or []
        self._positions_seq = positions_seq
        self._pending = pending or []
        self._exchanges = exchanges if exchanges is not None else calendar(
            MON_OVERLAP.date())
        self._history = dict(history or {})
        self.calls: list[str] = []

    def positions(self) -> list[dict[str, Any]]:
        self.calls.append("positions")
        if self._positions_seq:
            return self._positions_seq.pop(0) if len(self._positions_seq) > 1 \
                else self._positions_seq[0]
        return self._positions

    def pending_orders(self) -> list[dict[str, Any]]:
        self.calls.append("pending")
        return self._pending

    def exchanges(self) -> list[dict[str, Any]]:
        self.calls.append("exchanges")
        return self._exchanges

    def history_orders(self, ticker: str) -> list[dict[str, Any]]:
        self.calls.append(f"history:{ticker}")
        return self._history.get(ticker, [])


def position(ticker: str, quantity: float, price: float = 100.0) -> dict[str, Any]:
    """Shaped like GET /equity/positions: the ticker lives in ``instrument``."""
    return {"instrument": {"ticker": ticker, "currency": "USD", "isin": "X",
                           "name": ticker},
            "quantity": quantity, "currentPrice": price,
            "averagePricePaid": price, "createdAt": "2026-10-05T14:00:00Z"}


class OrderWire:
    """The fake order transport: answers GET account and POST market order,
    records everything, never opens a socket."""

    def __init__(self, *, currency: str = "GBP",
                 on_post: Callable[[int, bytes], Response] | None = None) -> None:
        self.calls: list[tuple[str, str, dict[str, str], bytes | None]] = []
        self.currency = currency
        self.on_post = on_post
        self.posts = 0

    def __call__(self, method: str, url: str, headers: Mapping[str, str],
                 body: bytes | None) -> Response:
        self.calls.append((method, url, dict(headers), body))
        if method == "GET":
            return Response(200, {}, json.dumps(
                {"currency": self.currency, "id": 1, "totalValue": 10000}).encode())
        self.posts += 1
        if self.on_post is not None:
            return self.on_post(self.posts, body or b"")
        return Response(200, {}, json.dumps(
            {"id": 1000 + self.posts, "status": "NEW", "type": "MARKET",
             "side": "BUY"}).encode())

    def posted(self) -> list[dict[str, Any]]:
        return [json.loads(body or b"{}") for m, _, _, body in self.calls
                if m == "POST"]


def live(tmp_path: Path, *, reader: FakeReader | None = None,
         wire: OrderWire | None = None, now: datetime = MON_OVERLAP,
         identities: list[Identity | Unresolved] | None = None,
         quotes: dict[str, Quotes] | None = None,
         ledger: AnchorLedger | None = None) -> tuple[anchors.LiveReport,
                                                       FakeReader, OrderWire,
                                                       AnchorLedger]:
    reader = reader or FakeReader(exchanges=calendar(now.date()))
    wire = wire or OrderWire()
    book = ledger or AnchorLedger(tmp_path / "anchors" / "ledger.jsonl")
    report = anchors.run_live(
        inputs=Inputs(identities or list(IDENTITIES),
                      quotes or quotes_on(now.date() - timedelta(days=1)),
                      fx_on(now.date() - timedelta(days=1))),
        reader=reader,
        orderer=AnchorOrderClient(FAKE, transport=wire, throttle=frozen_throttle()),
        ledger=book, now_fn=lambda: now, root=tmp_path, sleep=lambda s: None)
    return report, reader, wire, book


def plan(tmp_path: Path, *, now: datetime = MON_OVERLAP,
         identities: list[Identity | Unresolved] | None = None,
         quotes: dict[str, Quotes] | None = None,
         positions: list[dict[str, Any]] | None = None,
         pending: list[dict[str, Any]] | None = None,
         ledger: AnchorLedger | None = None,
         schedules: Any = "default",
         killswitch_on: bool = False) -> anchors.Plan:
    return anchors.build_plan(
        identities=identities or list(IDENTITIES),
        quotes=quotes or quotes_on(now.date() - timedelta(days=1)),
        fx=fx_on(now.date() - timedelta(days=1)),
        positions=positions if positions is not None else [],
        pending=pending if pending is not None else [],
        ledger=ledger or AnchorLedger(tmp_path / "ledger.jsonl"), now=now,
        schedules=(anchors.parse_schedules(calendar(now.date()))
                   if schedules == "default" else schedules),
        killswitch_on=killswitch_on)


def decisions(p: anchors.Plan) -> dict[str, str]:
    return {r.yfinance: r.decision for r in p.rows}


def planted_live_url() -> str:
    """The real-money URL, read from the museum so this file never contains it
    (tests/wall scans tests/qb2 for the hostname)."""
    museum = REPO_ROOT / "tests" / "museum" / "wall_violations" / "qb2_live_url.py.txt"
    match = re.search(r'LIVE_BASE_URL = "([^"]+)"', museum.read_text(encoding="utf-8"))
    assert match is not None
    return match.group(1)


# ==================================================================== F1 ===

def test_f1_the_host_is_the_hard_coded_practice_url() -> None:
    """FACTS row b1. One constant, the same as the read-only client's."""
    assert anchors.DEMO_BASE_URL == "https://demo.trading212.com/api/v0"
    assert anchors.DEMO_BASE_URL == DEMO_BASE_URL


def test_f1_a_planted_live_url_is_refused_before_any_network_call(
        monkeypatch: pytest.MonkeyPatch) -> None:
    live_url = planted_live_url()
    wire = OrderWire()
    with pytest.raises(LiveServerRefused):
        AnchorOrderClient(FAKE, transport=wire, base_url=live_url)
    with pytest.raises(LiveServerRefused):
        anchors.assert_demo_url(live_url + anchors.MARKET_ORDER_PATH)

    def no_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("a network opener was built for a refused host")

    monkeypatch.setattr(urllib.request, "build_opener", no_network)
    with pytest.raises(LiveServerRefused):
        anchors.order_transport("POST", live_url + anchors.MARKET_ORDER_PATH,
                                {}, b"{}")
    assert wire.calls == []


@pytest.mark.parametrize("url", [
    "https://demo.trading212.com.evil.example/api/v0/equity/account/summary",
    "http://demo.trading212.com/api/v0/equity/account/summary",
    "https://user:pw@demo.trading212.com/api/v0/equity/account/summary",
    "https://demo.trading212.com:8443/api/v0/equity/account/summary",
    "https://demo.trading212.com/api/v1/equity/account/summary",
])
def test_f1_lookalike_hosts_are_refused(url: str) -> None:
    with pytest.raises(LiveServerRefused):
        anchors.assert_demo_url(url)


def test_f1_the_refusal_never_echoes_the_bad_host() -> None:
    """A message that printed the live host would carry it into a log."""
    with pytest.raises(LiveServerRefused) as caught:
        anchors.assert_demo_url(planted_live_url() + "/equity/account/summary")
    assert "live." not in str(caught.value)


def test_f1_an_env_override_is_refused(tmp_path: Path) -> None:
    empty = tmp_path / "empty.env"
    empty.write_text("", encoding="utf-8")
    for environ in ({"T212_ENV": "live"},
                    {"T212_BASE_URL": planted_live_url()},
                    {"T212_HOST": "https://example.org/api/v0"}):
        with pytest.raises(LiveServerRefused) as caught:
            anchors.refuse_host_overrides(environ, empty)
        name = next(iter(environ))
        assert name in str(caught.value)
        assert environ[name] not in str(caught.value), "the value must not print"
    env_file = tmp_path / ".env"
    env_file.write_text(f"T212_BASE_URL={planted_live_url()}\n", encoding="utf-8")
    with pytest.raises(LiveServerRefused):
        anchors.refuse_host_overrides({}, env_file)
    anchors.refuse_host_overrides({"T212_ENV": "demo",
                                   "T212_API_KEY": "key-not-real"}, empty)


def test_f1_main_refuses_an_override_before_reading_anything(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("T212_ENV", "live")

    def must_not_run(**kwargs: object) -> Inputs:
        raise AssertionError("inputs were loaded after a refused override")

    monkeypatch.setattr(anchors, "load_inputs", must_not_run)
    assert anchors.main(["--live"]) == 2
    assert "T212_ENV" in capsys.readouterr().out


# ==================================================================== F2 ===

def test_f2_live_needs_the_order_key_and_never_falls_back(tmp_path: Path) -> None:
    empty = tmp_path / ".env"
    empty.write_text("T212_API_KEY=key-not-real\nT212_API_SECRET=secret-not-real\n",
                     encoding="utf-8")
    with pytest.raises(OrderKeyMissing) as caught:
        anchors.order_credentials({}, empty)
    assert "T212_ORDER_KEY" in str(caught.value)
    assert "key-not-real" not in str(caught.value)


def test_f2_the_order_key_comes_from_its_own_names(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("T212_ORDER_KEY=key-not-real-o\n"
                        "T212_ORDER_SECRET=secret-not-real-o\n"
                        "T212_API_KEY=key-not-real-r\n", encoding="utf-8")
    credentials = anchors.order_credentials({}, env_file)
    assert credentials.key == "key-not-real-o"


def test_f2_the_order_key_must_not_be_the_read_only_key(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("T212_ORDER_KEY=key-not-real-same\n"
                        "T212_ORDER_SECRET=secret-not-real-o\n"
                        "T212_API_KEY=key-not-real-same\n", encoding="utf-8")
    with pytest.raises(OrderKeyMissing, match="read-only key must stay read-only"):
        anchors.order_credentials({}, env_file)


def test_f2_live_without_the_order_key_sends_nothing(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    for name in ("T212_ORDER_KEY", "T212_ORDER_SECRET", "T212_ENV"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(anchors, "read_env_file", lambda path=None: {})
    monkeypatch.setattr(anchors, "load_inputs",
                        lambda **kw: Inputs(list(IDENTITIES), {}, None))
    assert anchors.main(["--live"]) == 2
    assert "T212_ORDER_KEY" in capsys.readouterr().out


def test_f2_the_read_only_client_still_uses_the_read_only_names() -> None:
    from qb2.execution import t212_client
    assert t212_client.KEY_VARIABLE == "T212_API_KEY"
    assert t212_client.SECRET_VARIABLE == "T212_API_SECRET"


# ==================================================================== F3 ===

def test_f3_there_is_no_sell_function_anywhere_in_the_module() -> None:
    tree = ast.parse(inspect.getsource(anchors))
    functions = [n.name for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    assert not [f for f in functions if "sell" in f.lower()]
    assert not [n for n in dir(AnchorOrderClient) if "sell" in n.lower()]
    assert '"SELL"' not in inspect.getsource(anchors)


@pytest.mark.parametrize("quantity", [Decimal("-0.0013"), Decimal("0"),
                                      Decimal("NaN"), Decimal("Infinity")])
def test_f3_a_planted_non_positive_quantity_raises_and_sends_nothing(
        quantity: Decimal) -> None:
    wire = OrderWire()
    client = AnchorOrderClient(FAKE, transport=wire, throttle=frozen_throttle())
    with pytest.raises(AnchorRefused, match="buy only"):
        client.buy("MU_US_EQ", quantity, 1.0)
    assert wire.calls == []


def test_f3_a_float_quantity_is_refused_too() -> None:
    client = AnchorOrderClient(FAKE, transport=OrderWire(), throttle=frozen_throttle())
    with pytest.raises(AnchorRefused):
        client.buy("MU_US_EQ", -0.5, 1.0)          # type: ignore[arg-type]


def test_f3_the_body_is_a_positive_buy_with_extended_hours_off() -> None:
    wire = OrderWire()
    client = AnchorOrderClient(FAKE, transport=wire, throttle=frozen_throttle())
    outcome = client.buy("MU_US_EQ", Decimal("0.0013"), 1.06)
    assert outcome.status == ACCEPTED and outcome.order_id == 1001
    method, url, headers, body = wire.calls[0]
    assert method == "POST"
    assert url == DEMO_BASE_URL + "/equity/orders/market"
    payload = json.loads(body or b"")
    assert payload == {"ticker": "MU_US_EQ", "quantity": 0.0013,
                       "extendedHours": False}
    assert b"-" not in (body or b"").split(b'"quantity": ')[1][:3]


# ==================================================================== F4 ===

def test_f4_the_universe_hash_is_pinned_and_the_file_matches_it() -> None:
    assert anchors.sha256_lf(anchors.UNIVERSE_FILE) == anchors.UNIVERSE_SHA256
    entries = anchors.load_universe()
    assert len(entries) == 50
    assert {e["sleeve"] for e in entries} == {"us_liquid", "uk_etf", "uk_share"}


def test_f4_a_tampered_universe_is_refused(tmp_path: Path) -> None:
    text = anchors.UNIVERSE_FILE.read_text(encoding="utf-8")
    planted = tmp_path / "bot-universe-v1-2026-10-01.json"
    planted.write_text(text.replace('"MU_US_EQ"', '"MU1_US_EQ"', 1), encoding="utf-8")
    with pytest.raises(UniverseTampered, match="agreed"):
        anchors.load_universe(planted)


def test_f4_a_windows_checkout_hashes_like_gits_copy(tmp_path: Path) -> None:
    lf, crlf = tmp_path / "lf.json", tmp_path / "crlf.json"
    lf.write_bytes(b'{\n "a": 1\n}\n')
    crlf.write_bytes(b'{\r\n "a": 1\r\n}\r\n')
    assert anchors.sha256_lf(lf) == anchors.sha256_lf(crlf)


NWG_US = {"ticker": "NWG_US_EQ", "type": "STOCK", "workingScheduleId": 56,
          "isin": "US6390572070", "currencyCode": "USD", "name": "NatWest",
          "shortName": "NWG", "maxOpenQuantity": 211357.0, "extendedHours": True,
          "addedOn": "2020-10-06T18:50:56.000+03:00"}
NWG_LONDON = {"ticker": "RBSl_EQ", "type": "STOCK", "workingScheduleId": 55,
              "isin": "GB00BM8PJY71", "currencyCode": "GBX", "name": "NatWest",
              "shortName": "NWG", "maxOpenQuantity": 744180.0,
              "extendedHours": False, "addedOn": "2018-07-12T07:10:09.000+03:00"}
NAMES = {55: "London Stock Exchange", 56: "NYSE"}


def nwg_entry(**override: str) -> dict[str, Any]:
    entry = {"yfinance": "NWG.L", "name": "NatWest", "sleeve": "uk_share",
             "exchange": "London Stock Exchange", "t212_ticker": "RBSl_EQ",
             "isin": "GB00BM8PJY71", "quote_currency": "GBX"}
    entry.update(override)
    return entry


def test_f4_the_nwg_trap_resolves_to_the_london_line() -> None:
    """FACTS row q: NWG_US_EQ is NatWest's New York ADR. Letters would pick it."""
    [found] = anchors.resolve_identities([nwg_entry()], [NWG_US, NWG_LONDON], NAMES)
    assert isinstance(found, Identity)
    assert (found.t212_ticker, found.isin, found.currency, found.market) == (
        "RBSl_EQ", "GB00BM8PJY71", "GBX", "LSE")
    assert found.schedule_id == 55


def test_f4_a_file_that_names_the_adr_is_refused() -> None:
    [found] = anchors.resolve_identities([nwg_entry(t212_ticker="NWG_US_EQ")],
                                         [NWG_US, NWG_LONDON], NAMES)
    assert isinstance(found, Unresolved)
    assert "RBSl_EQ" in found.reason


def test_f4_a_wrong_isin_is_refused() -> None:
    [found] = anchors.resolve_identities([nwg_entry(isin="US6390572070")],
                                         [NWG_US, NWG_LONDON], NAMES)
    assert isinstance(found, Unresolved) and "ISIN" in found.reason


def test_f4_an_unresolved_name_is_skipped_never_bought(tmp_path: Path) -> None:
    bad = Unresolved("NWG.L", "NatWest", "uk_share", "London Stock Exchange",
                     "ISIN disagrees")
    p = plan(tmp_path, identities=[bad, MU])
    assert decisions(p) == {"NWG.L": SKIP, "MU": WOULD_BUY}


@pytest.mark.skipif(not anchors.INSTRUMENTS_FILE.is_file(),
                    reason="the saved instrument list is local data, not in git")
def test_f4_all_50_agreed_names_resolve_against_the_verified_list() -> None:
    instruments, names = anchors.load_verified_lists()
    found = anchors.resolve_identities(anchors.load_universe(), instruments, names)
    unresolved = [f for f in found if isinstance(f, Unresolved)]
    assert unresolved == []
    tickers = {f.t212_ticker for f in found if isinstance(f, Identity)}
    assert len(tickers) == 50 and "FB_US_EQ" in tickers


@pytest.mark.skipif(not anchors.INSTRUMENTS_FILE.is_file(),
                    reason="the saved instrument list is local data, not in git")
def test_f4_a_changed_instrument_list_is_refused(tmp_path: Path) -> None:
    copy = tmp_path / "instruments.json"
    copy.write_bytes(anchors.INSTRUMENTS_FILE.read_bytes() + b" ")
    with pytest.raises(UniverseTampered):
        anchors.load_verified_lists(copy, anchors.EXCHANGES_FILE)


# ==================================================================== F5 ===

def test_f5_the_caps_are_the_agreed_figures() -> None:
    """PLAN_V3 P20 addendum. Changing one of these needs the operator's GO."""
    assert anchors.TARGET_GBP == 1.00
    assert anchors.MAX_ORDER_GBP == 3.00
    assert anchors.LIFETIME_CAP_GBP == 100.00
    assert anchors.MAX_ORDERS_PER_DAY == 50


def test_f5_a_name_too_dear_for_three_pounds_is_skipped(tmp_path: Path) -> None:
    day = MON_OVERLAP.date() - timedelta(days=1)
    dear = Quotes(Quote(40_000.0, "GBP", "clean daily close", day),
                  Quote(4_000_000.0, NATIVE, "raw 1m bar", day))
    p = plan(tmp_path, quotes=quotes_on(day, **{"AZN.L": dear}))
    row = next(r for r in p.rows if r.yfinance == "AZN.L")
    assert row.decision == SKIP and row.reason.startswith("over GBP 3 cap")


def _settled_intent(book: AnchorLedger, ticker: str, est: float, at: datetime,
                    status: str, n: int) -> None:
    intent_id = f"anchor-test-{n}"
    book.append({"kind": INTENT, "intent_id": intent_id, "at_utc": at.isoformat(),
                 "ticker": ticker, "quantity": "0.01", "est_gbp": est})
    book.append({"kind": OUTCOME, "intent_id": intent_id, "status": ACCEPTED,
                 "order_id": 5000 + n, "at_utc": at.isoformat()})
    book.append({"kind": RECONCILED, "intent_id": intent_id, "status": status,
                 "filled_quantity": 0.01 if status == FILLED else 0.0,
                 "at_utc": at.isoformat()})


def test_f5_the_lifetime_cap_counts_top_ups_and_stops_buying(tmp_path: Path) -> None:
    book = AnchorLedger(tmp_path / "ledger.jsonl")
    for n in range(33):                                  # 33 x 3.00 = 99.00
        _settled_intent(book, f"X{n}_US_EQ", 3.00, MON_OVERLAP - timedelta(days=3),
                        FILLED, n)
    assert book.committed_gbp() == pytest.approx(99.0)
    p = plan(tmp_path, ledger=book)
    assert {r.decision for r in p.rows} == {SKIP}
    assert all(r.reason.startswith("lifetime cap") for r in p.rows)


def test_f5_settled_empty_orders_do_not_use_up_the_lifetime_cap(tmp_path: Path) -> None:
    book = AnchorLedger(tmp_path / "ledger.jsonl")
    for n in range(40):
        _settled_intent(book, f"X{n}_US_EQ", 3.00, MON_OVERLAP - timedelta(days=3),
                        NOT_PLACED, n)
    assert book.committed_gbp() == 0.0


def test_f5_fifty_orders_a_day_is_the_limit(tmp_path: Path) -> None:
    book = AnchorLedger(tmp_path / "ledger.jsonl")
    for n in range(50):
        _settled_intent(book, f"X{n}_US_EQ", 1.0, MON_OVERLAP - timedelta(hours=1),
                        NOT_PLACED, n)
    p = plan(tmp_path, ledger=book)
    assert all(r.reason.startswith("daily limit") for r in p.rows)


def test_f5_the_order_client_itself_refuses_more_than_three_pounds() -> None:
    wire = OrderWire()
    client = AnchorOrderClient(FAKE, transport=wire, throttle=frozen_throttle())
    with pytest.raises(AnchorRefused, match="may not exceed"):
        client.buy("MU_US_EQ", Decimal("0.01"), 3.01)
    assert wire.calls == []


# ==================================================================== F6 ===

def test_f6_one_conversion_rule_per_unit() -> None:
    assert anchors.to_gbp(118.7, "GBP", None) == 118.7
    assert anchors.to_gbp(11848.0, "GBX", None) == pytest.approx(118.48)
    assert anchors.to_gbp(11848.0, "GBp", None) == pytest.approx(118.48)
    assert anchors.to_gbp(1076.0, "USD", 1.324) == pytest.approx(812.6888, rel=1e-6)
    with pytest.raises(anchors.UnitUnknown):
        anchors.to_gbp(10.0, "EUR", 1.3)
    with pytest.raises(anchors.UnitUnknown):
        anchors.to_gbp(10.0, "USD", None)


def test_f6_clean_store_pounds_are_never_divided_again(tmp_path: Path) -> None:
    """Scar #22: the clean store is already in pounds for London."""
    row = next(r for r in plan(tmp_path).rows if r.yfinance == "AZN.L")
    assert row.price_gbp == pytest.approx(118.7)
    assert row.quantity == Decimal("0.0085")             # 1/118.7 -> 0.0084 -> lifted
    assert row.est_gbp is not None and 1.0 < row.est_gbp < 1.05


def test_f6_a_planted_double_divided_price_cannot_buy_100x(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The failure: pounds divided by 100 again -> a quantity 100x too big."""
    day = MON_OVERLAP.date() - timedelta(days=1)
    planted = Quotes(Quote(1.187, "GBP", "clean daily close", day),
                     Quote(11848.0, NATIVE, "raw 1m bar", day))
    row = next(r for r in plan(tmp_path, quotes=quotes_on(day, **{"AZN.L": planted})).rows
               if r.yfinance == "AZN.L")
    assert row.decision == SKIP and row.reason.startswith("prices disagree")
    # Second layer: even with the agreement check switched off, the GBP 3 cap is
    # judged on the LARGER price, so the 100x quantity is still refused.
    monkeypatch.setattr(anchors, "PRICE_AGREEMENT", 1e9)
    row = next(r for r in plan(tmp_path, quotes=quotes_on(day, **{"AZN.L": planted})).rows
               if r.yfinance == "AZN.L")
    assert row.decision == SKIP and row.reason.startswith("over GBP 3 cap")


def test_f6_dollars_go_through_the_stored_rate_and_the_fx_fee(tmp_path: Path) -> None:
    row = next(r for r in plan(tmp_path).rows if r.yfinance == "MU")
    assert row.price_gbp == pytest.approx(1074.89 / 1.324)
    assert row.quantity == Decimal("0.0013")
    consideration = 0.0013 * (1076.0 / 1.324)            # the LARGER of the two
    fees = 0.0015 + 3e-4 + 2e-4                          # FX fee, spread, slippage
    assert row.est_gbp == pytest.approx(consideration * (1 + fees))


def test_f6_quantity_rounds_down_then_lifts_only_to_the_minimum() -> None:
    etf = costs.Instrument("T", "GBP", "LSE", "ETF")
    exact = anchors.size_anchor(0.5, 0.5, etf)
    assert exact.quantity == Decimal("2.0000") and exact.note == ""
    third = anchors.size_anchor(3.0, 3.0, etf)          # 1/3 -> 0.3333 (down)
    assert third.quantity == Decimal("0.3334")           # lifted to >= GBP 1
    assert "minimum" in third.note
    assert third.quantity.as_tuple().exponent == -anchors.ASSUMED_QUANTITY_DECIMALS


def test_f6_a_price_with_no_second_source_is_skipped(tmp_path: Path) -> None:
    day = MON_OVERLAP.date() - timedelta(days=1)
    lonely = Quotes(Quote(118.7, "GBP", "clean daily close", day), None)
    row = next(r for r in plan(tmp_path, quotes=quotes_on(day, **{"AZN.L": lonely})).rows
               if r.yfinance == "AZN.L")
    assert row.decision == SKIP and row.reason.startswith("no price")


def test_f6_a_stale_price_is_skipped(tmp_path: Path) -> None:
    old = MON_OVERLAP.date() - timedelta(days=9)
    p = plan(tmp_path, quotes=quotes_on(old))
    assert all(r.decision == SKIP for r in p.rows)


def test_f6_the_store_readers_take_the_unit_from_the_data(tmp_path: Path) -> None:
    import pandas as pd

    index = pd.DatetimeIndex([pd.Timestamp("2026-10-02", tz="Europe/London")])
    (tmp_path / "clean" / "daily").mkdir(parents=True)
    pd.DataFrame({"close": [118.7], "currency": ["GBP"]}, index=index).to_parquet(
        tmp_path / "clean" / "daily" / "AZN.L.parquet")
    (tmp_path / "raw" / "intraday" / "1m" / "AZN.L").mkdir(parents=True)
    bars = pd.DatetimeIndex([pd.Timestamp("2026-10-02 16:29", tz="Europe/London")])
    pd.DataFrame({"close": [11848.0]}, index=bars).to_parquet(
        tmp_path / "raw" / "intraday" / "1m" / "AZN.L" / "2026-10-02.parquet")
    clean = anchors.clean_close("AZN.L", tmp_path / "clean")
    raw = anchors.raw_last("AZN.L", tmp_path / "raw")
    assert clean == Quote(118.7, "GBP", "clean daily close", date(2026, 10, 2))
    assert raw == Quote(11848.0, NATIVE, "raw 1m bar", date(2026, 10, 2))
    assert anchors.clean_close("NOPE", tmp_path / "clean") is None
    assert anchors.raw_last("NOPE", tmp_path / "raw") is None


# ==================================================================== F7 ===

def test_f7_both_markets_buy_inside_the_overlap(tmp_path: Path) -> None:
    assert decisions(plan(tmp_path)) == {"MU": WOULD_BUY, "AZN.L": WOULD_BUY,
                                         "VUAG.L": WOULD_BUY}


def test_f7_a_weekend_waits_and_never_buys(tmp_path: Path) -> None:
    p = plan(tmp_path, now=SUNDAY)
    assert set(decisions(p).values()) == {WAIT}


def test_f7_the_week_the_clocks_disagree(tmp_path: Path) -> None:
    """2026-10-26: the UK is on GMT, New York still on EDT -- a 4-hour gap.
    At 13:45 UTC New York is 09:45 (open). A fixed +5h would say 08:45 (shut)."""
    gap_week = datetime(2026, 10, 26, 13, 45, tzinfo=UTC)
    assert decisions(plan(tmp_path, now=gap_week)) == {
        "MU": WOULD_BUY, "AZN.L": WOULD_BUY, "VUAG.L": WOULD_BUY}
    just_opened = datetime(2026, 10, 26, 13, 35, tzinfo=UTC)
    assert decisions(plan(tmp_path, now=just_opened))["MU"] == WAIT
    a_week_later = datetime(2026, 11, 2, 13, 45, tzinfo=UTC)   # both on winter time
    assert decisions(plan(tmp_path, now=a_week_later))["MU"] == WAIT


def test_f7_london_shuts_before_its_close(tmp_path: Path) -> None:
    late = datetime(2026, 10, 5, 15, 20, tzinfo=UTC)          # 16:20 BST
    d = decisions(plan(tmp_path, now=late))
    assert d["AZN.L"] == WAIT and d["MU"] == WOULD_BUY


def test_f7_the_brokers_holiday_overrides_the_clock(tmp_path: Path) -> None:
    """A weekday, in hours by the clock -- but the broker lists no London open."""
    holiday = MON_OVERLAP.date()
    schedules = anchors.parse_schedules(calendar(holiday, skip_lse=holiday))
    p = plan(tmp_path, schedules=schedules)
    row = next(r for r in p.rows if r.yfinance == "AZN.L")
    assert row.decision == WAIT and "CLOSE" in row.reason
    assert decisions(p)["MU"] == WOULD_BUY


def test_f7_no_calendar_is_treated_as_shut(tmp_path: Path) -> None:
    assert set(decisions(plan(tmp_path, schedules=None)).values()) == {WAIT}


def test_f7_live_sends_nothing_into_a_shut_market(tmp_path: Path) -> None:
    report, _, wire, _ = live(tmp_path, now=SUNDAY)
    assert wire.posted() == []
    assert report.accepted == []


# ==================================================================== F8 ===

def test_f8_held_and_pending_names_are_skipped(tmp_path: Path) -> None:
    p = plan(tmp_path, positions=[position("MU_US_EQ", 12.5711224)],
             pending=[{"ticker": "AZNl_EQ", "id": 9, "status": "NEW"}])
    d = decisions(p)
    assert d == {"MU": SKIP, "AZN.L": SKIP, "VUAG.L": WOULD_BUY}
    mu = next(r for r in p.rows if r.yfinance == "MU")
    assert mu.fractional == "yes (held fractionally)"


def test_f8_live_re_reads_the_broker_before_each_order(tmp_path: Path) -> None:
    """Held by the time we get there (the operator bought it by hand) -> skip."""
    reader = FakeReader(positions_seq=[[], [position("MU_US_EQ", 1.0)]])
    report, reader, wire, _ = live(tmp_path, reader=reader)
    assert "MU_US_EQ" not in {p["ticker"] for p in wire.posted()}
    assert {p["ticker"] for p in wire.posted()} == {"AZNl_EQ", "VUAGl_EQ"}
    assert reader.calls.count("pending") >= 1 + len(wire.posted())


def test_f8_the_intent_is_on_disk_before_the_order_leaves(tmp_path: Path) -> None:
    ledger_path = tmp_path / "anchors" / "ledger.jsonl"
    seen: list[list[dict[str, Any]]] = []

    def on_post(n: int, body: bytes) -> Response:
        lines = [json.loads(x) for x in ledger_path.read_text().splitlines()]
        seen.append(lines)
        return Response(200, {}, json.dumps({"id": n, "status": "NEW"}).encode())

    live(tmp_path, wire=OrderWire(on_post=on_post))
    for lines, ticker in zip(seen, ("MU_US_EQ", "AZNl_EQ", "VUAGl_EQ")):
        assert lines[-1]["kind"] == INTENT and lines[-1]["ticker"] == ticker


def test_f8_an_unknown_outcome_halts_and_is_never_resent(tmp_path: Path) -> None:
    def timeout(n: int, body: bytes) -> Response:
        raise TimeoutError("no reply")

    report, _, wire, book = live(tmp_path, wire=OrderWire(on_post=timeout))
    assert wire.posts == 1, "the run must halt at the first unknown outcome"
    assert "halted" in report.halted.lower() or "unknown" in report.halted
    [state] = book.states().values()
    assert state.state == UNRESOLVED and state.ticker == "MU_US_EQ"

    # A restart one minute later: nothing settles it yet, so nothing is sent.
    report2, _, wire2, _ = live(tmp_path, now=MON_OVERLAP + timedelta(minutes=1),
                                ledger=book)
    assert wire2.posted() == [] and "no confirmed outcome" in report2.halted

    # Eleven minutes on, with no trace in history or pending: settled NOT_PLACED.
    report3, _, wire3, _ = live(tmp_path, now=MON_OVERLAP + timedelta(minutes=11),
                                ledger=book)
    assert any("NOT_PLACED" in line for line in report3.lines)
    assert next(s for s in book.states().values()
                if s.intent_id == state.intent_id).state == NOT_PLACED


def test_f8_a_lost_reply_found_in_history_is_settled_not_resent(tmp_path: Path) -> None:
    def lost(n: int, body: bytes) -> Response:
        return Response(500, {}, b"upstream")

    _, _, _, book = live(tmp_path, wire=OrderWire(on_post=lost))
    [state] = book.states().values()
    history = {"MU_US_EQ": [{
        "order": {"id": 77, "ticker": "MU_US_EQ", "side": "BUY", "status": "FILLED",
                  "initiatedFrom": "API", "quantity": state.quantity,
                  "filledQuantity": state.quantity,
                  "createdAt": (MON_OVERLAP + timedelta(seconds=2)).isoformat()},
        "fill": {"quantity": state.quantity, "price": 1076.0,
                 "walletImpact": {"currency": "GBP", "netValue": -1.06}}}]}
    reader = FakeReader(positions=[position("MU_US_EQ", state.quantity)],
                        history=history)
    _, _, wire, _ = live(tmp_path, reader=reader, ledger=book,
                         now=MON_OVERLAP + timedelta(minutes=1))
    settled = book.states()[state.intent_id]
    assert settled.state == FILLED and settled.order_id == 77
    assert "MU_US_EQ" not in {p["ticker"] for p in wire.posted()}


def test_f8_a_crash_between_intent_and_outcome_blocks_that_name(tmp_path: Path) -> None:
    book = AnchorLedger(tmp_path / "anchors" / "ledger.jsonl")
    book.append({"kind": INTENT, "intent_id": "anchor-crash", "ticker": "AZNl_EQ",
                 "at_utc": MON_OVERLAP.isoformat(), "quantity": "0.0085",
                 "est_gbp": 1.02})
    p = plan(tmp_path, ledger=book)
    row = next(r for r in p.rows if r.yfinance == "AZN.L")
    assert row.decision == SKIP and row.reason.startswith("unresolved order")


def test_f8_a_corrupt_ledger_refuses_rather_than_guessing(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    path.write_text('{"kind": "INTENT", "intent_id": "a"\n', encoding="utf-8")
    with pytest.raises(LedgerCorrupt):
        plan(tmp_path, ledger=AnchorLedger(path))


# ==================================================================== F9 ===

def test_f9_the_killswitch_stops_every_anchor_buy(tmp_path: Path) -> None:
    safety.arm_killswitch("drill", root=tmp_path)
    report, reader, wire, _ = live(tmp_path)
    assert wire.calls == [] and "killswitch" in report.halted
    p = anchors.run_dry(inputs=Inputs(list(IDENTITIES), quotes_on(FRIDAY),
                                      fx_on(FRIDAY)),
                        reader=FakeReader(), ledger=AnchorLedger(tmp_path / "l.jsonl"),
                        now=MON_OVERLAP, root=tmp_path)
    assert all(r.reason.startswith("killswitch") for r in p.rows)


def test_f9_a_killswitch_set_mid_run_stops_the_next_order(tmp_path: Path) -> None:
    def arm_then_accept(n: int, body: bytes) -> Response:
        safety.arm_killswitch("set mid-run", root=tmp_path)
        return Response(200, {}, json.dumps({"id": n, "status": "NEW"}).encode())

    report, _, wire, _ = live(tmp_path, wire=OrderWire(on_post=arm_then_accept))
    assert wire.posts == 1 and "killswitch" in report.halted


# =================================================================== F10 ===

def test_f10_flatten_leaves_the_anchor_alone(tmp_path: Path) -> None:
    """P20: the bot's view of a position is the position minus the anchor."""
    book = AnchorLedger(tmp_path / "ledger.jsonl")
    _settled_intent(book, "MU_US_EQ", 1.06, MON_OVERLAP, FILLED, 1)
    anchors_held = book.anchor_quantities()
    assert anchors_held == {"MU_US_EQ": 0.01}
    broker = {"MU_US_EQ": 5.01, "AZNl_EQ": 0.0085}
    assert safety.bot_view(broker, anchors_held) == pytest.approx(
        {"MU_US_EQ": 5.0, "AZNl_EQ": 0.0085})
    # A bot record that wrongly absorbed the anchor still cannot sell it.
    sells = safety.flatten_bot([safety.Holding("MU_US_EQ", 5.01, safety.BOT)],
                               "close", broker_quantities=broker,
                               anchor_quantities=anchors_held)
    assert len(sells) == 1 and sells[0].ticker == "MU_US_EQ"
    assert sells[0].quantity == pytest.approx(5.0)
    # An anchor with no bot holding is never sold at all.
    assert safety.flatten_bot([], "close", broker_quantities=broker,
                              anchor_quantities=anchors_held) == []


def test_f10_an_unconfirmed_anchor_is_protected_as_if_it_filled(tmp_path: Path) -> None:
    book = AnchorLedger(tmp_path / "ledger.jsonl")
    book.append({"kind": INTENT, "intent_id": "a1", "ticker": "AZNl_EQ",
                 "at_utc": MON_OVERLAP.isoformat(), "quantity": "0.0085",
                 "est_gbp": 1.02})
    assert book.anchor_quantities() == {"AZNl_EQ": 0.0085}


def test_f10_without_broker_figures_flatten_behaves_as_before() -> None:
    sells = safety.flatten_bot([safety.Holding("MU_US_EQ", 2.0, safety.BOT),
                                safety.Holding("AZNl_EQ", 1.0, safety.ADVISOR)], "x")
    assert [(s.ticker, s.quantity) for s in sells] == [("MU_US_EQ", 2.0)]


# =================================================================== F11 ===

def test_f11_the_dry_run_client_has_no_order_method_at_all() -> None:
    public = [n for n in dir(BrokerReader) if not n.startswith("_")]
    assert set(public) == {"positions", "pending_orders", "exchanges",
                           "history_orders"}
    source = inspect.getsource(BrokerReader)
    assert "POST" not in source and "transport" not in source


def test_f11_the_dry_run_builds_no_order_client_and_writes_no_ledger(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Forbidden:
        def __init__(self, *a: object, **k: object) -> None:
            raise AssertionError("the dry run built an order client")

    monkeypatch.setattr(anchors, "AnchorOrderClient", Forbidden)
    book = AnchorLedger(tmp_path / "anchors" / "ledger.jsonl")
    p = anchors.run_dry(inputs=Inputs(list(IDENTITIES), quotes_on(FRIDAY),
                                      fx_on(FRIDAY)),
                        reader=FakeReader(), ledger=book, now=MON_OVERLAP,
                        root=tmp_path)
    assert {r.decision for r in p.rows} == {WOULD_BUY}
    assert not book.path.exists()


def test_f11_main_is_a_dry_run_even_with_the_order_key_present(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    class Forbidden:
        def __init__(self, *a: object, **k: object) -> None:
            raise AssertionError("an order client was built without --live")

    monkeypatch.setenv("T212_ORDER_KEY", "key-not-real-o")
    monkeypatch.setenv("T212_ORDER_SECRET", "secret-not-real-o")
    monkeypatch.delenv("T212_ENV", raising=False)
    monkeypatch.setattr(anchors, "read_env_file", lambda path=None: {})
    monkeypatch.setattr(anchors, "AnchorOrderClient", Forbidden)
    monkeypatch.setattr(anchors, "BrokerReader", lambda: FakeReader())
    monkeypatch.setattr(anchors, "REPORT_DIR", tmp_path / "reports")
    monkeypatch.setattr(anchors, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(anchors, "load_inputs", lambda **kw: Inputs(
        list(IDENTITIES), quotes_on(FRIDAY), fx_on(FRIDAY)))
    assert anchors.main([]) == 0
    out = capsys.readouterr().out
    assert "nothing was sent" in out
    assert "UNKNOWN: minimum order" in out


# =================================================================== F12 ===

def test_f12_no_secret_reaches_any_output(tmp_path: Path,
                                          capsys: pytest.CaptureFixture[str]) -> None:
    report, _, wire, book = live(tmp_path)
    assert len(wire.posted()) == 3
    header = "Basic " + base64.b64encode(b"key-not-real-order:secret-not-real-order").decode()
    assert wire.calls[0][2]["Authorization"] == header      # the wire does carry it
    texts = ["\n".join(report.lines), book.path.read_text(encoding="utf-8"),
             capsys.readouterr().out, anchors.render(report.plan)
             if report.plan else ""]
    for text in texts:
        for secret in (FAKE.key, FAKE.secret, header, header.split()[1]):
            assert secret not in text
    assert "hidden" in repr(FAKE)


def test_f12_a_failed_account_check_names_no_secret() -> None:
    def deny(method: str, url: str, headers: Mapping[str, str],
             body: bytes | None) -> Response:
        return Response(401, {}, b"Bad API key")

    client = AnchorOrderClient(FAKE, transport=deny, throttle=frozen_throttle())
    with pytest.raises(AnchorRefused) as caught:
        client.account_summary()
    message = str(caught.value)
    assert "401" in message
    # The auth header is the key and secret in base64 -- a leak in disguise.
    encoded = base64.b64encode(f"{FAKE.key}:{FAKE.secret}".encode()).decode()
    for secret in (FAKE.key, FAKE.secret, encoded, "Basic "):
        assert secret not in message


# ============================================================ live: misc ===

def test_live_refuses_an_account_that_is_not_in_pounds(tmp_path: Path) -> None:
    with pytest.raises(AnchorRefused, match="not GBP"):
        live(tmp_path, wire=OrderWire(currency="EUR"))


def test_live_happy_path_buys_each_absent_anchor_once(tmp_path: Path) -> None:
    report, _, wire, book = live(tmp_path)
    assert [p["ticker"] for p in wire.posted()] == ["MU_US_EQ", "AZNl_EQ", "VUAGl_EQ"]
    assert {s.state for s in book.states().values()} == {ACCEPTED}
    # A second run straight after: every name is blocking until reconciled.
    _, _, wire2, _ = live(tmp_path, ledger=book)
    assert wire2.posted() == []


def test_render_lists_totals_and_unknowns(tmp_path: Path) -> None:
    text = anchors.render(plan(tmp_path, now=SUNDAY))
    assert "names to buy: 3 (0 now, 3 when their market opens)" in text
    assert "lifetime cap" in text
    assert text.count("UNKNOWN:") == len(anchors.UNKNOWN_FACTS)


def test_live_halts_cleanly_when_the_broker_cannot_be_read(tmp_path: Path) -> None:
    from qb2.execution.t212_client import BrokerError

    class Unreadable(FakeReader):
        def exchanges(self) -> list[dict[str, Any]]:
            raise BrokerError("exchanges: practice API replied 503 (0 bytes)")

    report, _, wire, _ = live(tmp_path, reader=Unreadable())
    assert wire.posted() == [] and "could not read the broker" in report.halted


def test_an_account_check_with_no_reply_is_a_refusal_not_a_crash() -> None:
    def silent(method: str, url: str, headers: Mapping[str, str],
               body: bytes | None) -> Response:
        raise anchors.OrderTransportError("no reply (TimeoutError)")

    client = AnchorOrderClient(FAKE, transport=silent, throttle=frozen_throttle())
    with pytest.raises(AnchorRefused, match="no reply"):
        client.account_summary()
