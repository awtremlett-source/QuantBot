"""The wall, fifth direction: qb2 and v1 stay strangers.

v1 is producing a live forward paper record and is FROZEN. That record is only
worth something because nothing has been changed underneath it. So:

* **qb2 may not import a v1 engine package.** If it did, v1's behaviour would
  start depending on v2's development, and the baseline v2 is measured against
  would stop being independent of v2. qb2 has its own `data/`, `research/`,
  `execution/` and `tools/` subpackages, so this is a real hazard rather than a
  theoretical one: a bare `from research import ...` inside qb2 resolves to
  V1's research package, because the repo root is on the path. Inside qb2, use
  `qb2.research` or a relative import.
* **v1 may not import qb2** -- enforced next door in
  test_engine_never_imports_manual.py, which owns the list of things the engine
  is not allowed to import.
* **The fingerprint must not swallow qb2.** v1's fingerprint is the proof that
  v1 has not moved; if qb2's folders were inside it, every day of v2's work
  would break it and the proof would be abandoned as noise.
* **The environments stay separate.** v1's `.venv` must never gain qb2's UI
  toolkit, whatever gets installed where.

Both directions are checked by reading the source (ast), never by importing it:
these tests have to run under v1's interpreter, which cannot import PySide6.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tools.engine_fingerprint import ENGINE_DIRS

REPO_ROOT = Path(__file__).resolve().parents[2]
QB2 = REPO_ROOT / "qb2"
MUSEUM = REPO_ROOT / "tests" / "museum" / "wall_violations"

# v1's engine packages, by their importable top-level name.
V1_PACKAGES = frozenset({
    "data_store", "execution", "ingest", "monitors", "reconcile", "research",
    "risk", "strategies", "tools",
})

QB2_ENV = REPO_ROOT / ".venv-qb2"
V1_ENV = REPO_ROOT / ".venv"
UI_ONLY = frozenset({"pyside6", "pyside6-essentials", "pyside6-addons",
                     "shiboken6"})


def python_files(root: Path) -> list[Path]:
    return [p for p in sorted(root.rglob("*.py"))
            if "__pycache__" not in p.parts]


def v1_imports(files: list[Path]) -> list[str]:
    """Absolute imports of a v1 engine package. Relative imports are fine."""
    found: list[str] = []
    for path in files:
        name = (path.relative_to(REPO_ROOT).as_posix()
                if path.is_relative_to(REPO_ROOT) else path.name)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"),
                                       filename=str(path))):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in V1_PACKAGES:
                        found.append(f"{name}: imports {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                # level > 0 is a relative import: it cannot leave qb2.
                if node.level:
                    continue
                root = (node.module or "").split(".")[0]
                if root in V1_PACKAGES:
                    found.append(f"{name}: imports from {node.module}")
    return found


def installed_distributions(venv: Path) -> set[str]:
    found: set[str] = set()
    for pattern in ("Lib/site-packages", "lib/site-packages",
                    "lib/python*/site-packages"):
        for site in venv.glob(pattern):
            for info in site.glob("*.dist-info"):
                found.add(info.name.split("-")[0].lower().replace("_", "-"))
    return found


# ------------------------------------------------- qb2 never reaches into v1 ---

def test_the_skeleton_exists_and_is_importable_by_shape() -> None:
    """Fails loudly if the package is half-created, so later tests mean something."""
    assert (QB2 / "__init__.py").is_file(), "qb2 is not a package"
    expected = {"data", "research", "signals", "model", "sizing", "execution",
                "ui", "tools"}
    for name in sorted(expected):
        assert (QB2 / name / "__init__.py").is_file(), f"qb2/{name} missing"


def test_qb2_never_imports_a_v1_engine_package() -> None:
    files = python_files(QB2)
    assert files, "no qb2 files scanned -- the scan is broken"
    assert v1_imports(files) == []


def test_scanner_goes_red_on_a_planted_reach_back_into_v1() -> None:
    """Birth certificate: the same scanner, a deliberate violation, red."""
    planted = MUSEUM / "qb2_imports_v1.py.txt"
    found = v1_imports([planted])
    assert found, "the planted file should have tripped the scanner"
    assert any("data_store" in line for line in found)
    assert any("research" in line for line in found)


# ----------------------------------------- the fingerprint stays v1's alone ---

def test_the_v1_fingerprint_does_not_cover_qb2() -> None:
    """v1's proof-of-not-moving must not be broken by v2's ordinary work."""
    assert "qb2" not in ENGINE_DIRS
    assert not any(folder.startswith("qb2") for folder in ENGINE_DIRS)
    # and it still covers all of v1
    assert V1_PACKAGES == set(ENGINE_DIRS)


# ------------------------------------------- three environments, no leakage ---

@pytest.mark.skipif(not V1_ENV.is_dir(), reason="no .venv on this machine")
def test_v1_env_still_has_no_ui_toolkit() -> None:
    installed = installed_distributions(V1_ENV)
    assert installed, "read no distributions from .venv -- the scan is broken"
    assert sorted(installed & UI_ONLY) == []


@pytest.mark.skipif(not QB2_ENV.is_dir(), reason="no .venv-qb2 on this machine")
def test_qb2_env_holds_the_engine_libraries_and_the_ui_together() -> None:
    """The single-environment claim, checked against what is really installed."""
    installed = installed_distributions(QB2_ENV)
    assert "pyside6" in installed
    assert "pandas" in installed
    assert "yfinance" in installed


def test_qb2_requirements_are_fully_pinned() -> None:
    loose = []
    for raw in (REPO_ROOT / "requirements-qb2.txt").read_text(
            encoding="utf-8").splitlines():
        line = raw.split("#")[0].strip()
        if line and "==" not in line:
            loose.append(line)
    assert loose == [], f"unpinned qb2 requirements: {loose}"


def test_the_qb2_environment_is_gitignored_by_repo_policy() -> None:
    """Not merely by the .gitignore that venv writes inside itself.

    A venv writes its own `.gitignore` containing `*`. That protects the repo
    only for as long as that file survives; the policy belongs in the repo.
    """
    patterns = [line.strip() for line
                in (REPO_ROOT / ".gitignore").read_text(
                    encoding="utf-8").splitlines()]
    assert ".venv-qb2/" in patterns
    for expected in (".venv/", ".venv-ui/"):
        assert expected in patterns, f"{expected} vanished from .gitignore"
