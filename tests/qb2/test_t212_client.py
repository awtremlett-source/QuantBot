"""The read-only broker doorway: it reads, it waits its turn, it cannot trade.

Every fixture below is shaped from the field lists in Trading 212's own schema
pages, recorded in docs/t212/FACTS.md rows g and i. No field is invented: if a
name appears here, it appears in their documentation.

These tests are OFFLINE. The one test that touches the practice account is
skipped unless real credentials exist, and it never places anything.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date
from pathlib import Path

import pytest

from qb2.execution import t212_client as t212
from qb2.execution.t212_client import (BrokerError, CredentialsMissing,
                                       Credentials, ReadOnlyViolation, Response,
                                       T212DemoClient, Throttle)

FAKE = Credentials(key="key-not-real", secret="secret-not-real")

# Fields from https://docs.trading212.com/api/positions/getpositions (row g).
POSITION = {
    "averagePricePaid": 191.12,
    "createdAt": "2026-09-01T09:31:04.000+03:00",
    "currentPrice": 214.5,
    "instrument": {"currency": "USD", "isin": "US0378331005",
                   "name": "Apple Inc", "ticker": "AAPL_US_EQ"},
    "quantity": 1.5,
    "quantityAvailableForTrading": 1.5,
    "quantityInPies": 0.0,
    "walletImpact": {"currency": "GBP", "currentValue": 250.0, "fxImpact": -1.2,
                     "totalCost": 240.0, "unrealizedProfitLoss": 10.0},
}

# Fields from https://docs.trading212.com/api/instruments/instruments (row i).
INSTRUMENT = {
    "addedOn": "2019-08-24T14:15:22Z",
    "currencyCode": "GBP",
    "extendedHours": False,
    "isin": "IE00B4L5Y983",
    "maxOpenQuantity": 100000.0,
    "name": "iShares Core MSCI World UCITS ETF",
    "shortName": "SWDA",
    "ticker": "SWDAl_EQ",
    "type": "ETF",
    "workingScheduleId": 43,
}


def recorded(payload: object, status: int = 200,
             headers: Mapping[str, str] | None = None) -> t212.Transport:
    """A transport that answers from a fixture and records what it was asked."""
    calls: list[tuple[str, str, Mapping[str, str]]] = []

    def transport(method: str, url: str,
                  request_headers: Mapping[str, str]) -> Response:
        calls.append((method, url, request_headers))
        if method != "GET":
            raise ReadOnlyViolation(f"read-only client refused {method}")
        return Response(status=status, headers=dict(headers or {}),
                        body=json.dumps(payload).encode("utf-8"))

    transport.calls = calls          # type: ignore[attr-defined]
    return transport


def frozen_throttle() -> Throttle:
    """A throttle whose clock and sleep are ours, so nothing really waits."""
    clock = {"now": 1_000.0}

    def monotonic() -> float:
        return clock["now"]

    def sleeper(seconds: float) -> None:
        clock["now"] += seconds

    return Throttle(monotonic=monotonic, sleeper=sleeper)


# --------------------------------------------------------- it cannot trade ---

def test_the_client_has_no_method_that_could_place_an_order() -> None:
    """The guarantee is structural: there is nothing to call."""
    forbidden = ("buy", "sell", "order", "place", "cancel", "amend", "modify",
                 "close", "trade")
    public = [name for name in dir(T212DemoClient) if not name.startswith("_")]
    offenders = [name for name in public
                 if any(word in name.lower() for word in forbidden)
                 and name != "pending_orders"]
    assert offenders == [], f"the read-only client grew a trading method: {offenders}"
    assert set(public) == {"account_summary", "positions", "pending_orders",
                           "instruments", "exchanges", "save_instruments_raw"}


def test_a_planted_non_get_is_refused_at_the_network_layer() -> None:
    """Failure mode: an order sent. The choke point must refuse it."""
    with pytest.raises(ReadOnlyViolation, match="read-only"):
        t212.urllib_transport("POST", f"{t212.DEMO_BASE_URL}/equity/orders/market",
                              {"Authorization": "Basic x"})
    for method in ("PUT", "DELETE", "PATCH", "HEAD"):
        with pytest.raises(ReadOnlyViolation):
            t212.urllib_transport(method, t212.DEMO_BASE_URL, {})


def test_the_client_refuses_a_non_practice_base_url() -> None:
    with pytest.raises(ReadOnlyViolation, match="practice"):
        T212DemoClient(credentials=FAKE, base_url="https://example.com/api/v0")


def test_it_only_ever_talks_to_the_practice_environment() -> None:
    assert t212.DEMO_BASE_URL.startswith("https://demo.trading212.com")
    transport = recorded([POSITION])
    T212DemoClient(credentials=FAKE, transport=transport,
                   throttle=frozen_throttle()).positions()
    method, url, _ = transport.calls[0]          # type: ignore[attr-defined]
    assert method == "GET"
    assert url.startswith("https://demo.trading212.com/api/v0")


# --------------------------------------------------------------- the reads ---

def test_positions_come_back_with_the_documented_fields() -> None:
    client = T212DemoClient(credentials=FAKE, transport=recorded([POSITION]),
                            throttle=frozen_throttle())
    rows = client.positions()
    assert len(rows) == 1
    assert rows[0]["instrument"]["ticker"] == "AAPL_US_EQ"
    # The only price the API will give us, and only because we hold it (row h).
    assert rows[0]["currentPrice"] == 214.5


def test_instruments_come_back_with_the_documented_fields() -> None:
    client = T212DemoClient(credentials=FAKE, transport=recorded([INSTRUMENT]),
                            throttle=frozen_throttle())
    rows = client.instruments()
    assert rows[0]["type"] == "ETF"
    assert rows[0]["currencyCode"] == "GBP"
    assert "isaEligible" not in rows[0], (
        "FACTS.md row i2: no ISA-eligibility field is documented, so nothing "
        "may start depending on one")


def test_account_summary_reads_an_object_not_a_list() -> None:
    client = T212DemoClient(credentials=FAKE,
                            transport=recorded({"cash": {"free": 10_000.0}}),
                            throttle=frozen_throttle())
    assert client.account_summary()["cash"]["free"] == 10_000.0


def test_a_broken_reply_is_reported_not_guessed_at() -> None:
    client = T212DemoClient(credentials=FAKE, transport=recorded({}, status=500),
                            throttle=frozen_throttle())
    with pytest.raises(BrokerError, match="500"):
        client.positions()


def test_a_list_endpoint_that_returns_an_object_is_an_error() -> None:
    client = T212DemoClient(credentials=FAKE, transport=recorded({"oops": 1}),
                            throttle=frozen_throttle())
    with pytest.raises(BrokerError, match="expected a list"):
        client.positions()


# ------------------------------------------------------------- the throttle ---

def test_two_calls_to_one_endpoint_wait_the_documented_period() -> None:
    throttle = frozen_throttle()
    client = T212DemoClient(credentials=FAKE, transport=recorded([POSITION]),
                            throttle=throttle)
    client.instruments()          # documented as 1 req / 50s
    client.instruments()
    assert throttle.waits, "the second call did not wait at all"
    reason, seconds = throttle.waits[0]
    assert "instruments" in reason
    assert seconds == pytest.approx(50.0)


def test_different_endpoints_do_not_block_each_other() -> None:
    throttle = frozen_throttle()
    client = T212DemoClient(credentials=FAKE, transport=recorded([POSITION]),
                            throttle=throttle)
    client.positions()
    client.pending_orders()
    assert throttle.waits == []


def test_a_rate_limited_reply_backs_off_and_retries_once() -> None:
    """Failure mode: the throttle blocks. It must wait, retry, and say so."""
    attempts = {"n": 0}

    def transport(method: str, url: str, headers: Mapping[str, str]) -> Response:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return Response(status=429, headers={"x-ratelimit-reset": "7"},
                            body=b"")
        return Response(status=200, headers={},
                        body=json.dumps([POSITION]).encode())

    throttle = frozen_throttle()
    client = T212DemoClient(credentials=FAKE, transport=transport,
                            throttle=throttle)
    rows = client.positions()
    assert len(rows) == 1, "the retry after backing off did not succeed"
    assert attempts["n"] == 2
    assert any("rate limited" in reason for reason, _ in throttle.waits)
    assert any(seconds == pytest.approx(7.0) for _, seconds in throttle.waits)


def test_a_rate_limit_with_no_usable_header_still_waits() -> None:
    """FACTS.md rows f8/f9 are UNVERIFIED, so absence must not crash us."""
    throttle = frozen_throttle()
    assert throttle._reset_wait({}) == t212.DEFAULT_BACKOFF_SECONDS
    assert throttle._reset_wait({"x-ratelimit-reset": "nonsense"}) == (
        t212.DEFAULT_BACKOFF_SECONDS)
    # A Unix timestamp is recognised and turned into a sane wait.
    import time as clock
    soon = throttle._reset_wait({"x-ratelimit-reset": str(int(clock.time()) + 9)})
    assert 0 < soon <= 300


def test_every_documented_endpoint_has_a_limit_from_the_facts_file() -> None:
    assert set(t212.ENDPOINTS) == {"account_summary", "positions",
                                   "pending_orders", "instruments", "exchanges"}
    expected = {"account_summary": 5.0, "positions": 1.0, "pending_orders": 5.0,
                "instruments": 50.0, "exchanges": 30.0}
    for name, endpoint in t212.ENDPOINTS.items():
        assert endpoint.seconds_between_calls == expected[name]


# ---------------------------------------------------------- the credentials ---

def test_the_auth_header_is_basic_base64_of_key_and_secret() -> None:
    """FACTS.md row a, checked 2026-09-27 against their quickstart."""
    import base64

    header = FAKE.basic_auth_header()
    assert header.startswith("Basic ")
    decoded = base64.b64decode(header.removeprefix("Basic ")).decode()
    assert decoded == "key-not-real:secret-not-real"


def test_credentials_never_appear_in_their_own_repr() -> None:
    assert "key-not-real" not in repr(FAKE)
    assert "secret-not-real" not in repr(FAKE)
    assert "hidden" in repr(FAKE)


def test_missing_credentials_say_which_names_to_set_and_no_more() -> None:
    with pytest.raises(CredentialsMissing) as raised:
        Credentials.from_environment(environ={}, env_file=Path("nowhere.env"))
    message = str(raised.value)
    assert "T212_API_KEY" in message and "T212_API_SECRET" in message
    assert "SETUP.md" in message


def test_credentials_are_read_from_a_dot_env_file(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("# comment\nT212_API_KEY=abc\nT212_API_SECRET=def\n",
                   encoding="utf-8")
    found = Credentials.from_environment(environ={}, env_file=env)
    assert found.key == "abc" and found.secret == "def"
    assert t212.available(environ={}, env_file=env) is True
    assert t212.available(environ={}, env_file=tmp_path / "absent.env") is False


# ------------------------------------------------------------- raw landing ---

def test_the_instrument_list_lands_raw_and_goes_no_further(tmp_path: Path) -> None:
    client = T212DemoClient(credentials=FAKE, transport=recorded([INSTRUMENT]),
                            throttle=frozen_throttle())
    written = client.save_instruments_raw(destination=tmp_path,
                                          today=date(2026, 9, 27))
    assert written.name == "instruments-2026-09-27.json"
    # RAW means untouched: what we saved is what they sent.
    assert json.loads(written.read_text(encoding="utf-8")) == [INSTRUMENT]


# --------------------------------------- the practice account, if keys exist ---

@pytest.mark.skipif(not t212.available(),
                    reason="no T212 practice credentials in .env -- "
                           "see docs/t212/SETUP.md (this is not a failure)")
def test_live_demo_smoke_read_only() -> None:
    """Reads the real practice account. Places nothing. Off unless keys exist.

    It asserts only what a smoke test should: the credentials work and the
    account can be read. It does NOT assume the key holds every read scope -- a
    key granted fewer permissions is SAFER, not broken, so a 403 on the metadata
    endpoints is reported as a scope finding rather than failed. What still fails
    here is what matters: bad credentials, or no connection at all.
    """
    client = T212DemoClient()

    summary = client.account_summary()        # this is the authentication test
    positions = client.positions()            # portfolio scope
    assert isinstance(summary, dict) and summary, "the account read came back empty"
    assert isinstance(positions, list)

    # These two are already proven granted by the reads above. Re-probing them
    # would only hit the rate limit and report 429, which is NOT a permission
    # problem -- confusing the two is how a working key looks broken.
    scopes: dict[str, str] = {"account_summary": "granted",
                              "positions": "granted"}
    for name in ("pending_orders", "instruments", "exchanges"):
        url = f"{t212.DEMO_BASE_URL}{t212.ENDPOINTS[name].path}"
        reply = client._transport("GET", url, client._headers())
        scopes[name] = ("granted" if reply.status == 200
                        else f"HTTP {reply.status}"
                        + (" (no scope)" if reply.status == 403 else ""))

    tickers = [row.get("instrument", {}).get("ticker") for row in positions]
    distinct = len(set(tickers))
    print(f"\nT212 practice smoke: connected: yes, {len(positions)} positions, "
          f"{distinct} distinct tickers")
    print("T212 practice smoke: rows per ticker = "
          + ("one each" if distinct == len(tickers) else "SOME REPEAT"))
    for name, state in scopes.items():
        print(f"T212 practice smoke: {name:16} {state}")

    # A key that cannot even READ orders certainly cannot place one. That is the
    # read-only evidence, gathered without ever probing an order endpoint.
    if scopes["pending_orders"] != "granted":
        print("T212 practice smoke: the orders scope is NOT granted, so this "
              "key cannot place an order")



# ------------------------------------------- nothing secret reaches a log ---

def test_no_credential_reaches_an_error_message_or_a_log(
        capsys: pytest.CaptureFixture[str]) -> None:
    """The exit-gate promise: a key cannot escape through a failure path.

    Every way this client can fail is exercised, and the key and secret are
    hunted for in the exception text AND in everything printed.
    """
    secret_values = (FAKE.key, FAKE.secret)

    def failing(method: str, url: str, headers: Mapping[str, str]) -> Response:
        return Response(status=401, headers={}, body=b"unauthorised")

    client = T212DemoClient(credentials=FAKE, transport=failing,
                            throttle=frozen_throttle())
    with pytest.raises(BrokerError) as raised:
        client.positions()
    assert not any(value in str(raised.value) for value in secret_values)

    # A rate-limit pause prints a line; it must name the endpoint, not the key.
    throttle = frozen_throttle()
    noisy = T212DemoClient(credentials=FAKE, transport=recorded([POSITION]),
                           throttle=throttle)
    noisy.instruments()
    noisy.instruments()
    printed = capsys.readouterr()
    everything = printed.out + printed.err
    assert "instruments" in everything
    assert not any(value in everything for value in secret_values)
    assert "Basic " not in everything, "an auth header was printed"
