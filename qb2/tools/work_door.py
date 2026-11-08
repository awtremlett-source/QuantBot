"""The doors for qb2/tools/work_items.py: add, close and load, the commit hook, the command line.

qb2/tools/hooks/commit-msg calls ``commit-msg`` here. A commit must name an open item in the ledger
it is committing, touch only the files that item names, and leave a declared seam's old path out of
the index. The ledger must have only grown since HEAD, and each row entering it is judged as ``add``
and ``close`` would judge it. tests/qb2/test_work_items.py re-reads every commit, so --no-verify is
seen afterwards. Everything is read from what is being committed, not from the working folder.
A real merge, and a revert naming a commit in this history, land without paperwork; nothing checks
that a revert truly undoes that commit. Standard library only: this runs on every commit.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from qb2.tools import work_items as wi

ID_NAMED = re.compile(r"\b[A-Z]{2,}-\d+[A-Za-z]?\b")
REVERT = re.compile(r'^(?:Revert|Reapply) ".*This reverts commit ([0-9a-f]{7,40})', re.DOTALL)
ALWAYS_ALLOWED = (wi.LEDGER_NAME, wi.STATE)


@dataclass(frozen=True, slots=True)
class Landing:
    """One commit about to land, as git has it staged."""

    message: str
    head_ledger: str
    staged_ledger: str
    staged_files: tuple[str, ...]
    head: wi.Tree
    index: wi.Tree
    in_history: Callable[[str], bool]
    is_merge: bool


def _append(item: wi.WorkItem, ledger: Path) -> None:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8", newline="\n") as out:
        out.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")


def load(ledger: Path, world: wi.World) -> list[wi.WorkItem]:
    """Every item as it stands, or Refused: the read door."""
    return wi.checked(ledger.read_text(encoding="utf-8") if ledger.is_file() else "", world)


def add(item: wi.WorkItem, ledger: Path, world: wi.World) -> None:
    """The write door for a new item."""
    items = load(ledger, world)
    if item.id in {x.id for x in items}:
        raise wi.Refused(f"{item.id} is already in the ledger")
    tree = wi.tree_of(world)
    said = wi.entry_refusals(item, world, tree) + wi.attempts([*items, item], tree)
    if item.status != wi.OPEN:
        said.append(f"{item.id}: a new item is open")
    if sum(x.status == wi.OPEN for x in items) >= wi.MAX_OPEN:
        said.append(f"{wi.MAX_OPEN} items are already open; land one first")
    if said:
        raise wi.Refused("\n".join(said))
    _append(item, ledger)


def close(item_id: str, ledger: Path, world: wi.World) -> None:
    """The write door for finishing: the check exists and any old path is gone."""
    found = [x for x in load(ledger, world) if x.id == item_id and x.status == wi.OPEN]
    if not found:
        raise wi.Refused(f"no open item called {item_id}")
    done = replace(found[0], status=wi.DONE)
    if said := wi.done_refusals(done, wi.tree_of(world)):
        raise wi.Refused("\n".join(said))
    _append(done, ledger)


def is_revert(message: str, in_history: Callable[[str], bool]) -> bool:
    """git's own revert message, naming a commit that exists. A revert must not wait for paperwork."""
    found = REVERT.match(message)
    return found is not None and in_history(found.group(1))


def outside(staged: Sequence[str], named: Sequence[str]) -> list[str]:
    allowed = [*named, *ALWAYS_ALLOWED]
    return [path for path in staged
            if not any(path == a or (a.endswith("/") and path.startswith(a)) for a in allowed)]


def commit_refusals(landing: Landing, world: wi.World) -> list[str]:
    """Why this commit may not land."""
    words = "\n".join(x for x in landing.message.splitlines() if not x.startswith("#"))
    if landing.is_merge or is_revert(words, landing.in_history):
        return []
    head, work = (t.replace("\r\n", "\n") for t in (landing.head_ledger, landing.staged_ledger))
    if not work.startswith(head):
        return ["the work ledger is append-only: a row already committed was changed"]
    try:
        items = wi.checked(work, world)
    except wi.Refused as why:
        return [str(why)]
    said: list[str] = []
    new = wi.parse(work[len(head):])
    for row in new:
        said += (wi.entry_refusals(row, world, landing.head) if row.status == wi.OPEN
                 else wi.done_refusals(row, landing.index))
    entering = {r.id for r in new}
    said += wi.attempts([replace(x, status=wi.OPEN) if x.id in entering else x for x in items],
                        wi.tree_of(world))
    was_open = {x.id for x in wi.current(wi.parse(head)) if x.status == wi.OPEN}
    named = set(ID_NAMED.findall(words))
    landing_on = [x for x in items if x.id in named and (x.status == wi.OPEN or x.id in was_open)]
    if not landing_on:
        return [*said, "this commit names no open work item. Add one with "
                "`python -m qb2.tools.work_door add item.json` and name its id in the message"]
    for item in landing_on:
        said += [f"{item.id}: {spec} is still staged: a seam change deletes the path it replaces"
                 for spec in item.deletes if wi.present(landing.index, spec)]
    if stray := outside(landing.staged_files, [f for x in landing_on for f in x.files]):
        said.append(f"these files are not named by {sorted(x.id for x in landing_on)}: {stray}")
    return said


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=wi.REPO_ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def _git(*args: str) -> str:
    found = _run(*args)
    found.check_returncode()
    return found.stdout


def _tree(prefix: str) -> wi.Tree:
    """A git tree as a reader: prefix "HEAD:" for the last commit, ":" for the index."""
    def read(name: str) -> str | None:
        found = _run("show", f"{prefix}{name}")
        if found.returncode == 0:
            return found.stdout
        return "" if prefix == ":" and _run("ls-files", "--", name).stdout.strip() else None
    return read


def _staged_world(index: wi.Tree) -> wi.World:
    """The phase as it is being committed. No Phase line opens nothing; a revert still lands."""
    try:
        wanted = wi.phase_requirements(index(wi.STATE) or "")
    except wi.Refused:
        wanted = frozenset()
    return wi.World(wi.REPO_ROOT, wanted, index)


def _commit_msg(message_file: Path) -> list[str]:
    head, index = _tree("HEAD:"), _tree(":")
    staged = tuple(_git("diff", "--cached", "--name-only", "--no-renames").split("\n"))
    landing = Landing(message_file.read_text(encoding="utf-8"), head(wi.LEDGER_NAME) or "",
                      index(wi.LEDGER_NAME) or "", tuple(x for x in staged if x), head, index,
                      lambda sha: _run("merge-base", "--is-ancestor", sha, "HEAD").returncode == 0,
                      _run("rev-parse", "-q", "--verify", "MERGE_HEAD").returncode == 0)
    return commit_refusals(landing, _staged_world(index))


def _list(world: wi.World) -> None:
    items = load(wi.LEDGER, world)
    for item in (x for x in items if x.status == wi.OPEN):
        print(f"{item.id}  {item.requirement[:60]}  {item.behaviour}")
    print(f"{sum(x.status == wi.OPEN for x in items)} open of {wi.MAX_OPEN}; "
          f"exceptions so far: {len(wi.exceptions(items))}")
    for item in wi.exceptions(items):
        print(f"  {item.id}: {item.requirement}")


def main(argv: Sequence[str]) -> int:
    command, rest = argv[0], argv[1:]
    try:
        if command == "add":
            raw = json.loads(Path(rest[0]).read_text(encoding="utf-8"))
            add(wi.WorkItem(**{**raw, "files": tuple(raw["files"]),
                               "deletes": tuple(raw.get("deletes", ()))}),
                wi.LEDGER, wi.current_world(wi.REPO_ROOT))
        elif command == "close":
            close(rest[0], wi.LEDGER, wi.current_world(wi.REPO_ROOT))
        elif command == "list":
            _list(wi.current_world(wi.REPO_ROOT))
        elif command == "commit-msg":
            said = _commit_msg(Path(rest[0]))
            if said:
                raise wi.Refused("\n".join(said))
        else:
            raise wi.Refused(f"no command called {command!r}: add, close, list, commit-msg")
    except wi.Refused as why:
        print(f"REFUSED: {why}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
