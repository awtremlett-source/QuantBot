"""The wall, sixth direction: nothing in qb2 can reach real money or leak a key.

Three dangers, each with a test rather than a promise:

* **the real-money account.** Its hostname must not appear anywhere in qb2 or its
  tests. Not in a constant, not in a comment, not commented out "for later". A
  string that does not exist cannot be typed into a request by mistake.
* **an order.** The order endpoints are documented in docs/t212/FACTS.md and
  deliberately not implemented. qb2's own code must contain no path to them, and
  the one function that touches the network refuses any method but GET.
* **a leaked credential.** Nothing in the repo may carry the contents of .env,
  and no file may set one of the secret names to a real-looking value.

The hostnames and names being searched for are written out in THIS file, which is
why this file is not inside the trees it scans -- the same arrangement as
tests/wall/test_forbidden_paths.py.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
QB2 = REPO_ROOT / "qb2"
QB2_TESTS = REPO_ROOT / "tests" / "qb2"

# The real-money environment. Forbidden everywhere in qb2 until PLAN_V3 S14.
LIVE_HOST = "live.trading212.com"
DEMO_HOST = "demo.trading212.com"

# Order endpoints, documented in FACTS.md and deliberately unimplemented.
ORDER_PATHS = ("orders/market", "orders/limit", "orders/stop", "orders/stop_limit")

# Secret NAMES (never values) that must never be set to a real-looking value.
SECRET_NAMES = ("T212_API_KEY", "T212_API_SECRET", "TELEGRAM_BOT_TOKEN",
                "SMTP_PASS")

# The recorder's run logs hold raw stdout from an unattended job. They are
# gitignored, so nothing stops a printed key from sitting on the disk unnoticed --
# which makes them exactly the place a leak would hide. Scanned like source.
LOGS = REPO_ROOT / "logs"

SCANNED = (QB2, QB2_TESTS, LOGS)


def files_under(*roots: Path) -> list[Path]:
    found: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        found += [p for p in sorted(root.rglob("*"))
                  if p.is_file() and "__pycache__" not in p.parts]
    return found


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


# ------------------------------------------------- the real-money account ----

def test_the_live_hostname_appears_nowhere_in_qb2() -> None:
    offenders = [_relative(p) for p in files_under(*SCANNED)
                 if LIVE_HOST in p.read_text(encoding="utf-8", errors="replace")]
    assert offenders == [], (
        f"the real-money hostname appears in {offenders} -- it must not exist in "
        f"qb2 until PLAN_V3 S14, so it cannot be reached by accident")


def test_the_client_is_pinned_to_the_practice_host() -> None:
    source = (QB2 / "execution" / "t212_client.py").read_text(encoding="utf-8")
    assert DEMO_HOST in source
    assert source.count("https://demo.") >= 1


def test_scanner_goes_red_on_a_planted_live_url() -> None:
    """Birth certificate: the same scan, a deliberate violation, red."""
    planted = f'BASE = "https://{LIVE_HOST}/api/v0"'
    assert LIVE_HOST in planted          # the scan's own condition, stated plainly
    museum = REPO_ROOT / "tests" / "museum" / "wall_violations" / "qb2_live_url.py.txt"
    assert museum.is_file(), "the planted live-URL fixture is missing"
    assert LIVE_HOST in museum.read_text(encoding="utf-8")


# ------------------------------------------------------------- no ordering ----

def test_qb2_code_contains_no_path_to_an_order_endpoint() -> None:
    """The test files may name them -- they prove refusal. The code may not."""
    offenders: list[str] = []
    for path in files_under(QB2):
        body = path.read_text(encoding="utf-8", errors="replace")
        for fragment in ORDER_PATHS:
            if fragment in body:
                offenders.append(f"{_relative(path)}: {fragment}")
    assert offenders == [], f"qb2 code can reach an order endpoint: {offenders}"


def test_the_only_http_method_in_qb2_is_get() -> None:
    """Scan the string constants: no verb that changes anything may appear."""
    changing = {"POST", "PUT", "PATCH", "DELETE"}
    offenders: list[str] = []
    for path in sorted(QB2.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and node.value.strip().upper() in changing):
                offenders.append(f"{_relative(path)}: {node.value!r}")
    assert offenders == [], f"a request-changing HTTP verb exists in qb2: {offenders}"


def test_the_read_only_refusal_is_proven_by_a_test() -> None:
    """The refusal must be exercised, not merely written."""
    body = (QB2_TESTS / "test_t212_client.py").read_text(encoding="utf-8")
    assert "ReadOnlyViolation" in body
    assert "POST" in body, "no test plants a non-GET request"


# ------------------------------------------------------------ no key leaks ----

def test_no_file_sets_a_secret_name_to_a_real_looking_value() -> None:
    """`NAME=` with something after it, anywhere we wrote."""
    pattern = re.compile(
        r"(" + "|".join(SECRET_NAMES) + r")\s*=\s*['\"]?([A-Za-z0-9_\-]{8,})")
    offenders: list[str] = []
    for path in files_under(*SCANNED):
        for match in pattern.finditer(path.read_text(encoding="utf-8",
                                                     errors="replace")):
            value = match.group(2)
            if value.startswith(("key-not-real", "secret-not-real", "abc", "def")):
                continue                     # obvious test placeholders
            offenders.append(f"{_relative(path)}: {match.group(1)}=<redacted>")
    assert offenders == [], f"a secret-shaped value was written down: {offenders}"


@pytest.mark.skipif(not (REPO_ROOT / ".env").is_file(),
                    reason="no .env on this machine")
def test_no_value_from_dot_env_appears_anywhere_we_wrote() -> None:
    """The real test of a leak: does the actual secret appear in our files?"""
    secrets: list[str] = []
    for raw in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("#") or "=" not in line:
            continue
        _, _, value = line.partition("=")
        value = value.strip().strip("'\"")
        if len(value) >= 8:                  # ignore blanks and trivia
            secrets.append(value)
    if not secrets:
        pytest.skip(".env has no filled-in values yet")
    offenders: list[str] = []
    for path in files_under(*SCANNED):
        body = path.read_text(encoding="utf-8", errors="replace")
        offenders += [_relative(path) for secret in secrets if secret in body]
    assert offenders == [], f"a real secret from .env appears in {set(offenders)}"


def test_dot_env_is_gitignored_and_its_template_is_not() -> None:
    patterns = [line.strip() for line
                in (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()]
    assert ".env" in patterns
    assert "!.env.example" in patterns


# ------------------------------------- the default test run stays offline ----

def test_the_practice_account_test_is_off_unless_keys_exist() -> None:
    """A network test that runs by default is a test that fails on a train."""
    body = (QB2_TESTS / "test_t212_client.py").read_text(encoding="utf-8")
    assert "skipif" in body
    assert "t212.available()" in body, (
        "the live smoke test must be gated on credentials existing")
    assert "this is not a failure" in body, (
        "a missing key must be reported as a skip with its reason, never as a pass")


def test_nothing_in_qb2_calls_the_network_at_import_time() -> None:
    """Importing a module must never open a socket."""
    offenders: list[str] = []
    for path in sorted(QB2.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:               # module level only
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                offenders.append(f"{_relative(path)}: call at import time")
    assert offenders == [], f"module-level calls found: {offenders}"


# ------------------------------------------- QT-07: the sender stays disarmed ---

def test_nothing_in_qb2_arms_the_order_sender() -> None:
    """S2b builds the refusals; S10 builds the sending.

    ``ARMED`` must be defined False and never assigned True anywhere in qb2. A
    test may monkeypatch it -- that is a test reaching in deliberately -- but no
    line of qb2 may flip it, so there is no path from a signal to a real order.
    """
    offenders: list[str] = []
    for path in sorted(QB2.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                continue
            targets = (node.targets if isinstance(node, ast.Assign)
                       else [node.target])
            for target in targets:
                named = (isinstance(target, ast.Name) and target.id == "ARMED")
                attributed = (isinstance(target, ast.Attribute)
                              and target.attr == "ARMED")
                if not (named or attributed):
                    continue
                value = getattr(node, "value", None)
                if isinstance(value, ast.Constant) and value.value is False:
                    continue                      # the definition itself
                offenders.append(f"{_relative(path)}:{node.lineno}")
    assert offenders == [], f"qb2 contains a path that arms the sender: {offenders}"


def test_the_sender_declares_itself_disarmed() -> None:
    source = (QB2 / "execution" / "sender.py").read_text(encoding="utf-8")
    assert "ARMED = False" in source
    assert "NotImplementedError" in source, (
        "even armed, the placing function must refuse to exist until S10")
