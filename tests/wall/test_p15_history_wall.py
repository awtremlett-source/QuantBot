"""The wall, history direction (QT-18 A1): the back-test's P15 history never reaches the live path.

qb2/research/p15_history.py treats a results date as known from the close of the
one before it -- a reading the operator allowed IN BACK-TESTS ONLY (GO,
2026-10-16). Live, the sender must see only what was really recorded, at its real
knowable_time. So nothing outside qb2/research may reach p15_history, directly or
through any chain of qb2 imports, and inside qb2/research only p15.py (and the
A2 measurement, p15_coverage.py) imports it.

The live roots are every qb2 module outside qb2/research (guard, the sender and
anchors, the recorder and ingest, data, tools, ui...) and manual/. Each import of
a qb2 module is followed, so a live module importing research.fills is followed
into fills's own imports. The planted fixture
tests/museum/wall_violations/live_imports_p15_history.py.txt proves the scanner
sees an import arriving through another module.

Read by ast, never imported: this file runs under v1's interpreter too.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
QB2 = REPO_ROOT / "qb2"
TARGET = "qb2.research.p15_history"
# QT-19: advisor_results counts the ADVISOR's P15 warnings on its back-test buys (research only)
ALLOWED_IMPORTERS = frozenset({"qb2.research.p15", "qb2.research.p15_coverage",
                               "qb2.research.advisor_results"})
MUSEUM = REPO_ROOT / "tests" / "museum" / "wall_violations"


def module_name(path: Path) -> str:
    parts = list(path.relative_to(REPO_ROOT).with_suffix("").parts)
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def known_modules() -> dict[str, Path]:
    return {module_name(p): p for p in QB2.rglob("*.py") if "__pycache__" not in p.parts}


def imports_of(path: Path, name: str, modules: dict[str, Path]) -> set[str]:
    """The qb2 modules ``path`` imports (``from qb2.x import y`` counts y if it is one)."""
    package = name if path.name == "__init__.py" else name.rpartition(".")[0]
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                up = package.split(".")[: len(package.split(".")) - (node.level - 1)]
                base = ".".join(up + ([base] if base else []))
            found.add(base)
            found |= {f"{base}.{a.name}" for a in node.names}
    return {m for m in found if m in modules}


def reaches(roots: Iterable[tuple[str, Path]], modules: dict[str, Path]) -> list[str]:
    """Every chain from a root to TARGET, as 'root -> ... -> target'."""
    found: list[str] = []
    for root, path in roots:
        seen, todo = {root}, [(root, path, [root])]
        while todo:
            name, file, chain = todo.pop()
            for dep in sorted(imports_of(file, name, modules)):
                if dep == TARGET:
                    found.append(" -> ".join(chain + [dep]))
                elif dep not in seen:
                    seen.add(dep)
                    todo.append((dep, modules[dep], chain + [dep]))
    return found


def live_roots(modules: dict[str, Path]) -> list[tuple[str, Path]]:
    roots = [(n, p) for n, p in modules.items() if not n.startswith("qb2.research")]
    roots += [(module_name(p), p) for p in (REPO_ROOT / "manual").rglob("*.py")
              if "__pycache__" not in p.parts]
    return sorted(roots)


def test_nothing_on_the_live_path_reaches_the_history_rule() -> None:
    modules = known_modules()
    assert TARGET in modules
    assert reaches(live_roots(modules), modules) == []


def test_inside_research_only_p15_and_its_measurement_import_the_history_rule() -> None:
    modules = known_modules()
    direct = sorted(n for n, p in modules.items() if TARGET in imports_of(p, n, modules))
    assert direct == sorted(ALLOWED_IMPORTERS)


def test_the_planted_live_import_is_caught() -> None:
    """A guard module importing a helper that imports p15_history: RED."""
    modules = known_modules()
    planted = MUSEUM / "live_imports_p15_history.py.txt"
    chains = reaches([("qb2.guard.planted", planted)], modules)
    assert chains and all(c.endswith(TARGET) for c in chains)
    assert any(" -> qb2.research.p15 -> " in c for c in chains)    # found through p15
