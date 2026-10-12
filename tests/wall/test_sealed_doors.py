"""The wall, sealed direction (QT-17 A1): research and tools read bars only through the door.

**How QT-16 got past the seal.** The seal lived in one function,
qb2/research/holdout.py ``research_bars``, but nothing said that function was the
only way in. qb2/research/stop_description.py called the daily loader
(``qb2.ingest.daily.load``) itself and so read the sealed daily year; pounds.py,
total_return.py (the benchmark) and qb2/tools/first_light.py read bars the same way.
The one scan that existed (test_s3d_dividends_and_return.py) looked only for
``read_parquet`` in files that name the bar tree, so a call to a LOADER passed it.

**The rule now.** Every module under qb2/research and qb2/tools reads bars through
holdout.py: ``research_bars`` (the unsealed part) or ``bars_through`` with the
single final run's pass. Calling a raw bar loader anywhere else -- ``daily.load``,
``daily.close_on``, ``access.bars``, or ``read_parquet`` -- is RED, whether it is
called as an attribute or imported by name. The planted fixture
tests/museum/wall_violations/research_reads_sealed_bars.py.txt proves the scanner
sees each form.

Not bars, so not scanned for: dividends, earnings and the universe files (their
own tables). brake_replay.py reads index series kept OUTSIDE the store
(data/research/brake_replay, SHA-256 manifest), with ``read_csv``: not the store's
bars, and reported as such in QT-17.

Read by ast, never imported: this file runs under v1's interpreter too.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCANNED = (REPO_ROOT / "qb2" / "research", REPO_ROOT / "qb2" / "tools")
DOORS = frozenset({REPO_ROOT / "qb2" / "research" / "holdout.py"})
MUSEUM = REPO_ROOT / "tests" / "museum" / "wall_violations"

RAW_CALLS = frozenset({("daily", "load"), ("daily", "close_on"), ("access", "bars")})
RAW_IMPORTS = {"qb2.ingest.daily": frozenset({"load", "close_on"}),
               "qb2.data.access": frozenset({"bars"})}


def raw_bar_reads(paths: Iterable[Path]) -> list[str]:
    """Every raw bar read in these files, as ``name:line what``."""
    found: list[str] = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in RAW_IMPORTS:
                for alias in node.names:
                    if alias.name in RAW_IMPORTS[node.module]:
                        found.append(f"{path.name}:{node.lineno} imports "
                                     f"{node.module}.{alias.name}")
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute):
                owner = func.value.id if isinstance(func.value, ast.Name) else ""
                if (owner, func.attr) in RAW_CALLS or func.attr == "read_parquet":
                    found.append(f"{path.name}:{node.lineno} calls "
                                 f"{owner + '.' if owner else ''}{func.attr}")
    return found


def scanned_modules() -> list[Path]:
    return sorted(p for folder in SCANNED for p in folder.rglob("*.py")
                  if "__pycache__" not in p.parts and p not in DOORS)


def test_research_and_tools_read_bars_only_through_the_door() -> None:
    offenders = raw_bar_reads(scanned_modules())
    assert offenders == [], (
        "these read bars around the holdout seal -- use holdout.research_bars, or "
        f"holdout.bars_through with the final run's pass: {offenders}")


def test_the_planted_reader_trips_the_wall() -> None:
    found = raw_bar_reads([MUSEUM / "research_reads_sealed_bars.py.txt"])
    joined = " | ".join(found)
    for form in ("calls daily.load", "imports qb2.ingest.daily.close_on",
                 "calls access.bars", "imports qb2.data.access.bars", "calls pd.read_parquet"):
        assert form in joined, f"the scanner missed {form!r}: {found}"


def test_the_door_itself_is_the_only_exemption() -> None:
    assert {p.name for p in DOORS} == {"holdout.py"}
    door = (REPO_ROOT / "qb2" / "research" / "holdout.py").read_text(encoding="utf-8")
    assert "def research_bars" in door and "def bars_through" in door
