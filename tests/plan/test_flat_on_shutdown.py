"""QT-16 B7: S10 cannot be marked DONE until every flat-on-shutdown test exists.

docs/plan/FLAT_ON_SHUTDOWN.md (S5's design) names, for each trigger -- shutdown,
restart, sleep, power loss, unplanned stop -- the S10 test that must prove it. This
wall reads those names; the day PLAN_V3's S10 heading says DONE, every one must
exist as a real test function. Planted: S10 marked DONE with the tests absent is RED.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DESIGN = REPO_ROOT / "docs" / "plan" / "FLAT_ON_SHUTDOWN.md"
PLAN_V3 = REPO_ROOT / "docs" / "plan" / "PLAN_V3.md"
TRIGGERS = ("shutdown", "restart", "sleep", "power loss", "unplanned stop")
NAMED = re.compile(r"`(tests/[\w/]+\.py)::(test_\w+)`")


def required(design: str) -> list[tuple[str, str]]:
    return NAMED.findall(design)


def s10_done(plan: str) -> bool:
    heading = next((line for line in plan.splitlines() if line.startswith("### S10")), "")
    return "DONE" in heading


def missing(design: str, plan: str, root: Path) -> list[str]:
    if not s10_done(plan):
        return []
    gone = []
    for path, name in required(design):
        file = root / path
        if not (file.is_file() and f"def {name}(" in file.read_text(encoding="utf-8")):
            gone.append(f"{path}::{name}")
    return gone


def test_the_design_covers_every_trigger_with_a_named_s10_test() -> None:
    design = DESIGN.read_text(encoding="utf-8")
    rows = {line.split("|")[1].strip(): line for line in design.splitlines()
            if line.startswith("| ") and line.count("|") >= 4}
    for trigger in TRIGGERS:
        assert trigger in rows, f"no row for {trigger}"
        assert NAMED.search(rows[trigger]), f"{trigger} names no S10 test"
    assert "desktop" in design
    assert "bot holdings first" in rows["unplanned stop"].replace("**", "")


def test_s10_is_not_done_today_so_nothing_is_missing() -> None:
    assert missing(DESIGN.read_text(encoding="utf-8"), PLAN_V3.read_text(encoding="utf-8"),
                   REPO_ROOT) == []


def test_s10_marked_done_without_the_tests_is_red(tmp_path: Path) -> None:
    design = DESIGN.read_text(encoding="utf-8")
    plan = PLAN_V3.read_text(encoding="utf-8").replace(
        "### S10 — Demo execution", "### S10 — Demo execution — **DONE**", 1)
    assert s10_done(plan)
    assert len(missing(design, plan, tmp_path)) == len(required(design)) >= 5
    first, name = required(design)[0]
    (tmp_path / first).parent.mkdir(parents=True)
    (tmp_path / first).write_text(f"def {name}() -> None:\n    assert True\n")
    assert f"{first}::{name}" not in missing(design, plan, tmp_path)
