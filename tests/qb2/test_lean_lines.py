"""Anti-sprawl enforcer: no qb2 module grows past 250 lines.

New modules stay at or under the limit. The files already over it on 2026-10-05
are pinned at that day's count: they may shrink, never grow. Splitting one is a
PROPOSE -> GO decision, so the pin moves down only by hand.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

LIMIT = 250
QB2 = Path(__file__).resolve().parents[2] / "qb2"

# path relative to qb2/ -> line count on 2026-10-05 (may shrink, never grow)
OVERSIZE_PINNED: dict[str, int] = {
    "data/census.py": 255,
    "ingest/dividends.py": 269,
    "tools/sample_delay.py": 274,
    "execution/anchor_ledger.py": 283,
    "tools/build_universe.py": 318,
    "ingest/verify_universe.py": 341,
    "execution/t212_client.py": 348,
    "tools/record_now.py": 384,
    "data/front_door.py": 470,
    "ingest/recorder.py": 820,
    "execution/anchors.py": 1424,          # QT-12 MARGIN folded the sizing branches
}


def line_counts(root: Path) -> dict[str, int]:
    """Every .py file under root -> its number of lines."""
    return {p.relative_to(root).as_posix(): len(p.read_text(encoding="utf-8").splitlines())
            for p in sorted(root.rglob("*.py"))}


def breaches(counts: Mapping[str, int], pinned: Mapping[str, int]) -> list[str]:
    """Files over their allowance: the pin if pinned, else LIMIT."""
    return [f"{name}: {n} lines > {pinned.get(name, LIMIT)}"
            for name, n in counts.items() if n > pinned.get(name, LIMIT)]


def test_no_qb2_module_exceeds_its_allowance() -> None:
    assert breaches(line_counts(QB2), OVERSIZE_PINNED) == []


def test_a_new_module_over_the_limit_is_caught(tmp_path: Path) -> None:
    (tmp_path / "fat.py").write_text("x = 1\n" * (LIMIT + 1), encoding="utf-8")
    (tmp_path / "lean.py").write_text("x = 1\n" * LIMIT, encoding="utf-8")
    assert breaches(line_counts(tmp_path), {}) == ["fat.py: 251 lines > 250"]


def test_a_pinned_file_may_shrink_but_never_grow() -> None:
    pinned = {"big.py": 400}
    assert breaches({"big.py": 399}, pinned) == []
    assert breaches({"big.py": 401}, pinned) == ["big.py: 401 lines > 400"]
