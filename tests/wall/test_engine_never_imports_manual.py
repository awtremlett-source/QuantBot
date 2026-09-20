"""The wall, direction 1: the ENGINE never imports the manual app.

The engine runs headless on a schedule and its forward paper record is only
worth something if nothing else can perturb it. An engine module that imported
manual/, PySide6 or tools_ui would drag a GUI toolkit into the 07:45 run --
and a missing display, a Qt upgrade or a broken UI dependency could then stop
a trading loop that has no business knowing the UI exists.

The scan is AST-based, not textual: a comment mentioning PySide6 is fine, an
`import` of it is not. Dynamic imports (importlib.import_module("manual"),
__import__("manual")) are caught too, so the ban cannot be routed around with
a string.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# The engine, confirmed against the repo (see tools/engine_fingerprint.py).
ENGINE_DIRS: tuple[str, ...] = (
    "data_store", "execution", "ingest", "monitors", "reconcile",
    "research", "risk", "strategies", "tools",
)

# Top-level module names the engine may never import.
FORBIDDEN_ROOTS = frozenset({"manual", "tools_ui", "PySide6", "shiboken6"})

MUSEUM = REPO_ROOT / "tests" / "museum" / "wall_violations"


def engine_python_files() -> list[Path]:
    files: list[Path] = []
    for folder in ENGINE_DIRS:
        for path in sorted((REPO_ROOT / folder).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            files.append(path)
    return files


def imported_roots(source: str, filename: str) -> set[str]:
    """Every top-level module name this source imports, by any route."""
    roots: set[str] = set()
    for node in ast.walk(ast.parse(source, filename=filename)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            # A relative import can never reach out of its own package.
            if not node.level and node.module:
                roots.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            called = ""
            if isinstance(node.func, ast.Attribute):
                called = node.func.attr
            elif isinstance(node.func, ast.Name):
                called = node.func.id
            if called in {"import_module", "__import__"} and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    roots.add(first.value.split(".")[0])
    return roots


def violations(files: list[Path]) -> list[str]:
    """Human-readable violation lines -- empty means the wall holds."""
    found: list[str] = []
    for path in files:
        source = path.read_text(encoding="utf-8")
        for root in sorted(imported_roots(source, str(path)) & FORBIDDEN_ROOTS):
            found.append(f"{path.relative_to(REPO_ROOT).as_posix()} imports {root}")
    return found


def test_engine_never_imports_manual() -> None:
    files = engine_python_files()
    assert len(files) > 20, f"only {len(files)} engine files scanned -- scan broken"
    assert violations(files) == []


def test_scanner_goes_red_on_a_planted_engine_import() -> None:
    """Birth certificate: the same scanner, a deliberate violation, red."""
    planted = MUSEUM / "engine_imports_manual.py.txt"
    found = violations([planted])
    assert "imports manual" in " ".join(found)
    assert "imports PySide6" in " ".join(found)


def test_scanner_catches_a_dynamic_import() -> None:
    """A string-routed import is still an import."""
    source = "import importlib\nm = importlib.import_module('manual.scout.store')\n"
    assert "manual" in imported_roots(source, "<dynamic>")
