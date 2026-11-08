"""The work-item front door: gates 1-3 of the operator's directive of 2026-11-08.

A work item is one piece of work, written down before it starts. Three refusals live here:

1. An item with no requirement, measured evidence, premortem or verifying check is refused.
2. The third item on one behaviour, or on one check, is refused without its own design note.
   The count comes from the ledger. It counts items, not failures: nothing records a failure.
3. A design-seam change must name what it deletes, and cannot close while that path survives.

These are the rules; the doors that apply them are in qb2/tools/work_door.py. Every read re-checks
every open row and the queue, so a hand-edited ledger is refused too. An old closed row is not
re-judged: a revert can legitimately bring a path back, and that must not jam every later commit.
What code cannot judge is the quality of the words: that is read by people.

Standard library only: the commit hook runs this on every commit. Nothing here can trade.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
LEDGER_NAME = "docs/work/items.jsonl"
LEDGER = REPO_ROOT / LEDGER_NAME
STATE = "STATE.md"

MAX_OPEN = 5                     # STARTING FIGURE: the queue stays short
MIN_WORDS = 5                    # a premortem of "tbd" is not a premortem
MIN_NOTE_WORDS = 20              # a design note says why the earlier attempts failed
THIRD_ATTEMPT = 3
OPEN, DONE = "open", "done"
EXCEPTION = "EXCEPTION:"
SEAMS = frozenset({"none", "prices", "exits", "stops", "sizing", "simulator", "scoreboard"})
NEEDED = ("id", "behaviour", "requirement", "assumption", "evidence", "evidence_source",
          "premortem", "check")
ID_SHAPE = re.compile(r"^[A-Z]{2,}-\d+[A-Za-z]?$")
CHECK_SHAPE = re.compile(r"^tests/[\w./-]+\.py::\w+$")

# A tree answers: the text of this path (empty for a folder), or None if it is not there.
Tree = Callable[[str], str | None]


class Refused(RuntimeError):
    """Work the gate will not accept. The message says why, in plain words."""


@dataclass(frozen=True, slots=True)
class WorkItem:
    id: str
    behaviour: str                   # one slug per behaviour: attempts are counted on it
    requirement: str                 # an open stage (S6), or "EXCEPTION: <why>"
    files: tuple[str, ...]           # the exact files; an entry ending in / covers a folder
    assumption: str                  # what the fix rests on
    evidence: str                    # a measured figure that tests the assumption
    evidence_source: str             # the repo file the figure came from
    premortem: str
    check: str                       # tests/...py::test_name, the verifying check
    seam: str = "none"               # one of SEAMS, always said out loud
    deletes: tuple[str, ...] = ()    # what a seam change removes: path or path::name
    design_note: str = ""            # needed from the third attempt on one behaviour
    status: str = OPEN


@dataclass(frozen=True, slots=True)
class World:
    """What the gates look at, injected so the tests run on a temporary folder."""

    root: Path
    requirements: frozenset[str]


def phase_requirements(state_text: str) -> frozenset[str]:
    """The stages STATE.md's Phase line calls OPEN. No Phase line refuses everything."""
    line = next((x for x in state_text.splitlines() if x.startswith("Phase:")), None)
    if line is None:
        raise Refused("STATE.md has no Phase: line, so no requirement can be named")
    return frozenset(re.findall(r"\b(S\d+) OPEN\b", line))


def current_world(root: Path | None = None) -> World:
    base = root or REPO_ROOT
    return World(base, phase_requirements((base / STATE).read_text(encoding="utf-8")))


def disk(root: Path) -> Tree:
    def read(name: str) -> str | None:
        path = root / name
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace")
        return "" if path.exists() else None
    return read


def present(tree: Tree, spec: str) -> bool:
    """Is this path, or this name as a whole word inside it, in the tree?"""
    name, _, symbol = spec.partition("::")
    text = tree(name)
    return text is not None and (not symbol
                                 or re.search(rf"\b{re.escape(symbol)}\b", text) is not None)


def _defined(tree: Tree, spec: str) -> bool:
    """Is this check a real test function, not a word in a comment?"""
    name, _, symbol = spec.partition("::")
    return re.search(rf"^\s*def\s+{re.escape(symbol)}\b", tree(name) or "", re.MULTILINE) is not None


def _shape(item: WorkItem) -> list[str]:
    said = [f"{item.id}: no {name}" for name in NEEDED if not getattr(item, name).strip()]
    for name in ("assumption", "premortem", "evidence"):
        if getattr(item, name).strip() and len(getattr(item, name).split()) < MIN_WORDS:
            said.append(f"{item.id}: {name} is a token answer: at least {MIN_WORDS} words")
    if not ID_SHAPE.match(item.id):
        said.append(f"{item.id!r}: an id looks like WI-0001 or QT-30")
    if not item.files or not all(x.strip() for x in item.files):
        said.append(f"{item.id}: no files named")
    if item.evidence.strip() and not re.search(r"\d", item.evidence):
        said.append(f"{item.id}: evidence holds no measured figure")
    if item.check.strip() and not CHECK_SHAPE.match(item.check):
        said.append(f"{item.id}: check must be tests/...py::test_name, not {item.check!r}")
    if item.seam not in SEAMS:
        said.append(f"{item.id}: no seam called {item.seam!r}: {sorted(SEAMS)}")
    if item.seam != "none" and not item.deletes:
        said.append(f"{item.id}: a {item.seam} seam change names nothing to delete")
    if item.status not in (OPEN, DONE):
        said.append(f"{item.id}: no status called {item.status!r}")
    return said


def _when_open(item: WorkItem, world: World) -> list[str]:
    said = []
    if item.requirement.startswith(EXCEPTION):
        if len(item.requirement[len(EXCEPTION):].split()) < MIN_WORDS:
            said.append(f"{item.id}: an EXCEPTION must say why in at least {MIN_WORDS} words")
    elif item.requirement.strip() and item.requirement not in world.requirements:
        said.append(f"{item.id}: {item.requirement!r} is not open in the current phase "
                    f"({sorted(world.requirements)})")
    if item.evidence_source.strip() and not disk(world.root)(item.evidence_source):
        said.append(f"{item.id}: evidence_source {item.evidence_source!r} is not a file with content")
    return said


def entry_refusals(item: WorkItem, world: World, tree: Tree) -> list[str]:
    """Why this item may not enter the ledger. ``tree`` is where its old paths must be today."""
    return [*_shape(item), *_when_open(item, world),
            *(f"{item.id}: says it will delete {spec}, which does not exist"
              for spec in item.deletes if not present(tree, spec))]


def done_refusals(item: WorkItem, tree: Tree) -> list[str]:
    """Why this item may not close: an old path survives, or its check is not a real test."""
    said = [f"{item.id}: still has {spec}: a seam change deletes the path it replaces"
            for spec in item.deletes if present(tree, spec)]
    if not _defined(tree, item.check):
        said.append(f"{item.id}: its check {item.check} is not a test function in that file")
    return said


def attempts(items: Sequence[WorkItem], tree: Tree) -> list[str]:
    """From the third item on one behaviour or one check, each needs its own real note."""
    count: Counter[str] = Counter()
    used: set[str] = set()
    said = []
    for item in items:
        count[item.behaviour] += 1
        count[item.check] += 1
        attempt = max(count[item.behaviour], count[item.check])
        if attempt < THIRD_ATTEMPT:
            continue
        note, text = item.design_note, tree(item.design_note) if item.design_note else None
        if not (note.endswith(".md") and note not in used and text is not None
                and item.behaviour in text and len(text.split()) >= MIN_NOTE_WORDS):
            said.append(f"{item.id}: attempt {attempt} on {item.behaviour!r} needs its own design "
                        f"note (.md, {MIN_NOTE_WORDS}+ words) saying why the earlier attempts failed")
        used.add(note)
    return said


def parse(text: str) -> list[WorkItem]:
    rows = []
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            raw: dict[str, Any] = json.loads(line)
            row = WorkItem(**{**raw, "files": tuple(raw["files"]), "seam": raw["seam"],
                              "deletes": tuple(raw["deletes"])})
            if not all(isinstance(v, str) for k, v in asdict(row).items()
                       if k not in ("files", "deletes")):
                raise ValueError("every field but files and deletes is text")
        except (ValueError, TypeError, KeyError) as why:
            raise Refused(f"ledger line {n} is not a work item: {why}") from why
        rows.append(row)
    return rows


def current(rows: Sequence[WorkItem]) -> list[WorkItem]:
    """One entry per id, oldest first. An item starts open; a later row may only close it."""
    now: dict[str, WorkItem] = {}
    for row in rows:
        was = now.get(row.id)
        if was is None and row.status != OPEN:
            raise Refused(f"{row.id}: an item starts open; its first row says {row.status!r}")
        if was is not None:
            if replace(row, status=was.status) != was:
                raise Refused(f"{row.id}: a later row may change only the status")
            if (was.status, row.status) != (OPEN, DONE):
                raise Refused(f"{row.id}: an item closes once, from open")
        now[row.id] = row
    return list(now.values())


def checked(text: str, world: World) -> list[WorkItem]:
    items = current(parse(text))
    said = [x for item in items for x in _shape(item)]
    said += [x for item in items if item.status == OPEN for x in _when_open(item, world)]
    said += attempts(items, disk(world.root))
    opened = sum(x.status == OPEN for x in items)
    if opened > MAX_OPEN:
        said.append(f"{opened} items are open; the limit is {MAX_OPEN}")
    if said:
        raise Refused("\n".join(said))
    return items


def exceptions(items: Sequence[WorkItem]) -> list[WorkItem]:
    """Urgent work outside the phase: named and counted."""
    return [x for x in items if x.requirement.startswith(EXCEPTION)]
