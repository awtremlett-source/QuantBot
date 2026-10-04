"""The wall, sixth direction: nothing in qb2 can reach real money or leak a key.

Three dangers, each with a test rather than a promise:

* **the real-money account.** Its hostname must not appear anywhere in qb2 or its
  tests. Not in a constant, not in a comment, not commented out "for later". A
  string that does not exist cannot be typed into a request by mistake.
* **an order.** The order endpoints are documented in docs/t212/FACTS.md and
  deliberately not implemented -- with ONE exception since QT-12: the P20 anchor
  buyer, qb2/execution/anchors.py, may place a practice MARKET BUY (operator's
  words, 2026-10-04: "P20 anchors bought by the program, practice only, fenced").
  That file alone may name the market-order path and the verb POST; no other qb2
  file may, it may name no other order path, and the bot cannot import it.
* **a leaked credential.** Nothing in the repo may carry the contents of .env,
  and no file may set one of the secret names to a real-looking value.

The hostnames and names being searched for are written out in THIS file, which is
why this file is not inside the trees it scans -- the same arrangement as
tests/wall/test_forbidden_paths.py.
"""

from __future__ import annotations

import ast
import os
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

# QT-12: the one fenced exception. Exactly one file, exactly one order path.
ORDER_DOORWAY = "qb2/execution/anchors.py"
DOORWAY_FRAGMENT = "orders/market"
DOORWAY_VERB = "POST"

# The order key's names (F2). Only the doorway may read them.
ORDER_KEY_NAMES = ("T212_ORDER_KEY", "T212_ORDER_SECRET")

# Secret NAMES (never values) that must never be set to a real-looking value.
SECRET_NAMES = ("T212_API_KEY", "T212_API_SECRET", "TELEGRAM_BOT_TOKEN",
                "SMTP_PASS") + ORDER_KEY_NAMES

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

def order_path_offenders(files: list[Path], root: Path = REPO_ROOT) -> list[str]:
    """Every order-path fragment in code, except the doorway's ONE path."""
    offenders: list[str] = []
    for path in files:
        name = path.relative_to(root).as_posix()
        body = path.read_text(encoding="utf-8", errors="replace")
        for fragment in ORDER_PATHS:
            if fragment in body and not (name == ORDER_DOORWAY
                                         and fragment == DOORWAY_FRAGMENT):
                offenders.append(f"{name}: {fragment}")
    return offenders


def changing_verb_offenders(files: list[Path], root: Path = REPO_ROOT) -> list[str]:
    """String constants naming a verb that changes something; the doorway may
    say POST and nothing else."""
    changing = {"POST", "PUT", "PATCH", "DELETE"}
    offenders: list[str] = []
    for path in files:
        if path.suffix != ".py":
            continue
        name = path.relative_to(root).as_posix()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and node.value.strip().upper() in changing):
                if name == ORDER_DOORWAY and node.value == DOORWAY_VERB:
                    continue
                offenders.append(f"{name}: {node.value!r}")
    return offenders


def test_qb2_code_contains_no_path_to_an_order_endpoint() -> None:
    """The test files may name them -- they prove refusal. The code may not,
    except the anchor doorway, and only its market-order path."""
    offenders = order_path_offenders(files_under(QB2))
    assert offenders == [], f"qb2 code can reach an order endpoint: {offenders}"


def test_the_only_http_method_in_qb2_is_get() -> None:
    """Scan the string constants: no verb that changes anything may appear,
    except POST inside the anchor doorway."""
    offenders = changing_verb_offenders(files_under(QB2))
    assert offenders == [], f"a request-changing HTTP verb exists in qb2: {offenders}"


def test_the_doorway_exemption_is_one_file_and_it_exists() -> None:
    """An exemption naming a file that is gone would quietly cover its successor."""
    assert (REPO_ROOT / ORDER_DOORWAY).is_file()
    body = (REPO_ROOT / ORDER_DOORWAY).read_text(encoding="utf-8")
    assert DOORWAY_FRAGMENT in body
    assert DEMO_HOST in body, "the doorway must be pinned to the practice host"


def test_scanners_go_red_on_a_planted_second_doorway(tmp_path: Path) -> None:
    """Birth certificate: a second order path, anywhere else in qb2, is caught."""
    planted = tmp_path / "qb2" / "signals" / "sneaky.py"
    planted.parent.mkdir(parents=True)
    planted.write_text('PATH = "/equity/orders/market"\nVERB = "POST"\n',
                       encoding="utf-8")
    assert order_path_offenders([planted], tmp_path) == [
        "qb2/signals/sneaky.py: orders/market"]
    assert changing_verb_offenders([planted], tmp_path) == [
        "qb2/signals/sneaky.py: 'POST'"]


def test_scanners_go_red_when_the_doorway_grows_another_order_type(
        tmp_path: Path) -> None:
    """The doorway's exemption is one path and one verb, not a blank cheque."""
    planted = tmp_path / ORDER_DOORWAY
    planted.parent.mkdir(parents=True)
    planted.write_text('A = "/equity/orders/market"\nB = "/equity/orders/limit"\n'
                       'C = "POST"\nD = "DELETE"\n', encoding="utf-8")
    assert order_path_offenders([planted], tmp_path) == [
        f"{ORDER_DOORWAY}: orders/limit"]
    assert changing_verb_offenders([planted], tmp_path) == [
        f"{ORDER_DOORWAY}: 'DELETE'"]


# --------------------------- QT-12: the order key and the doorway are fenced ---

CODE_SUFFIXES = frozenset({".py", ".bat", ".cmd", ".ps1", ".toml", ".cfg",
                           ".ini", ".json", ".yml", ".yaml"})
NOT_CODE = frozenset({".git", ".venv", ".venv-qb2", ".venv-ui", "archive",
                      "data", "logs", "tests", "docs", "reports", "__pycache__",
                      ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def order_key_offenders(root: Path = REPO_ROOT) -> list[str]:
    """Every code file naming the order key, except the doorway (F2).

    Walks with the excluded folders pruned BEFORE descending: the venvs and the
    data store hold tens of thousands of files that are not code.
    """
    offenders: list[str] = []
    for folder, subfolders, filenames in os.walk(root):
        subfolders[:] = sorted(d for d in subfolders if d not in NOT_CODE)
        for filename in sorted(filenames):
            path = Path(folder) / filename
            if path.suffix not in CODE_SUFFIXES and filename != ".env.example":
                continue
            relative = path.relative_to(root).as_posix()
            body = path.read_text(encoding="utf-8", errors="replace")
            if (any(name in body for name in ORDER_KEY_NAMES)
                    and relative != ORDER_DOORWAY):
                offenders.append(relative)
    return offenders


def test_only_the_doorway_names_the_order_key() -> None:
    """The recorder and everything else keep the read-only key (F2)."""
    assert order_key_offenders() == []
    body = (REPO_ROOT / ORDER_DOORWAY).read_text(encoding="utf-8")
    assert all(name in body for name in ORDER_KEY_NAMES)


def test_order_key_scan_goes_red_on_a_planted_reader(tmp_path: Path) -> None:
    planted = tmp_path / "qb2" / "ingest" / "recorder_two.py"
    planted.parent.mkdir(parents=True)
    planted.write_text('KEY = "T212_ORDER_KEY"\n', encoding="utf-8")
    assert order_key_offenders(tmp_path) == ["qb2/ingest/recorder_two.py"]


def doorway_importers(root: Path = REPO_ROOT) -> list[str]:
    """Any qb2 module that imports the doorway, by statement or by string."""
    offenders: list[str] = []
    for path in sorted((root / "qb2").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        name = path.relative_to(root).as_posix()
        if name == ORDER_DOORWAY:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            hit = False
            if isinstance(node, ast.ImportFrom):
                hit = (node.module == "qb2.execution.anchors"
                       or any(alias.name == "anchors" for alias in node.names))
            elif isinstance(node, ast.Import):
                hit = any(alias.name == "qb2.execution.anchors"
                          for alias in node.names)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                hit = "qb2.execution.anchors" in node.value
            if hit:
                offenders.append(f"{name}:{getattr(node, 'lineno', '?')}")
    return offenders


def test_nothing_in_qb2_imports_the_doorway() -> None:
    """F10: the bot cannot reach the one module that can place an order."""
    assert doorway_importers() == []


def test_doorway_import_scan_goes_red_on_a_planted_import(tmp_path: Path) -> None:
    (tmp_path / "qb2" / "model").mkdir(parents=True)
    (tmp_path / "qb2" / "model" / "combine.py").write_text(
        "from qb2.execution import anchors\n", encoding="utf-8")
    (tmp_path / "qb2" / "sizing").mkdir(parents=True)
    (tmp_path / "qb2" / "sizing" / "lazy.py").write_text(
        'import importlib\nm = importlib.import_module("qb2.execution.anchors")\n',
        encoding="utf-8")
    assert doorway_importers(tmp_path) == ["qb2/model/combine.py:1",
                                           "qb2/sizing/lazy.py:2"]


def test_the_doorway_never_touches_armed_or_the_bots_sender() -> None:
    """F10: buying an anchor must not be able to read, set or depend on ARMED."""
    tree = ast.parse((REPO_ROOT / ORDER_DOORWAY).read_text(encoding="utf-8"))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    imported = {alias.name for n in ast.walk(tree)
                if isinstance(n, (ast.Import, ast.ImportFrom)) for alias in n.names}
    modules = {n.module for n in ast.walk(tree)
               if isinstance(n, ast.ImportFrom) and n.module}
    assert "ARMED" not in names | attrs | imported
    assert "sender" not in imported and "qb2.execution.sender" not in modules


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
