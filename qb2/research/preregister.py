"""Pre-registration: a candidate is written down, and committed, before it is scored.

PLAN_V3 S4: "pre-registration (the candidate written down before it is tested)".
The register is docs/research/preregistered.json, tracked by git, so the commit
date proves "written before tested".

Every scoring path in qb2/research takes a :class:`Registered` token, and the only
way to get one is :func:`require`, which refuses:

* a candidate that is not in the register at all;
* a candidate that is in the working copy but NOT in the committed register
  (registered-but-uncommitted -- the date would prove nothing);
* a candidate whose entry changed after it was committed.

Each entry holds: id, rule, bar size, universe, exit rule, fixed parameters,
holdout, and the date. Drills (known-null instruments) are registered too.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTER_REL = "docs/research/preregistered.json"
FIELDS = ("id", "kind", "rule", "bar_size", "universe", "exit_rule", "parameters",
          "holdout", "date")
KINDS = frozenset({"trial", "drill"})
BAR_SIZES = frozenset({"5m", "1d"})

Git = Callable[[Path, list[str]], str]


class NotRegistered(RuntimeError):
    """Refused: not written down and committed before scoring."""


_KEY = object()


@dataclass(frozen=True, slots=True)
class Registered:
    """Proof a candidate is in the committed register. Built only by :func:`require`."""

    entry: Mapping[str, Any]
    commit: str
    committed_at: str
    key: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.key is not _KEY:
            raise NotRegistered("a Registered token can only come from preregister.require()")

    @property
    def id(self) -> str:
        return str(self.entry["id"])

    @property
    def is_drill(self) -> bool:
        return bool(self.entry["kind"] == "drill")


def check(token: object) -> Registered:
    """Every scoring path's first line."""
    if not isinstance(token, Registered) or token.key is not _KEY:
        raise NotRegistered("scoring needs a token from preregister.require(); "
                            "an unregistered candidate cannot be scored")
    return token


def parse(text: str) -> dict[str, dict[str, Any]]:
    """The register's entries by id, each with every required field."""
    doc = json.loads(text)
    out: dict[str, dict[str, Any]] = {}
    for entry in doc.get("entries", []):
        missing = [f for f in FIELDS if f not in entry]
        if missing:
            raise NotRegistered(f"register entry {entry.get('id')!r} lacks {missing}")
        if entry["kind"] not in KINDS or entry["bar_size"] not in BAR_SIZES:
            raise NotRegistered(f"register entry {entry['id']!r}: bad kind or bar size")
        if entry["id"] in out:
            raise NotRegistered(f"register entry {entry['id']!r} appears twice")
        out[str(entry["id"])] = entry
    return out


def _git(root: Path, args: list[str]) -> str:
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          text=True, encoding="utf-8", check=False)
    if done.returncode != 0:
        raise NotRegistered(f"git {' '.join(args[:2])} failed: {done.stderr.strip()[:120]}")
    return done.stdout


def require(candidate_id: str, *, root: Path | None = None, rel: str = REGISTER_REL,
            git: Git = _git) -> Registered:
    """The token, or a refusal that says which of the three rules was broken."""
    base = root or REPO_ROOT
    path = base / rel
    working = parse(path.read_text(encoding="utf-8")) if path.is_file() else {}
    if candidate_id not in working:
        raise NotRegistered(f"{candidate_id!r} is not in {rel}: write it down, "
                            "commit it, then score it")
    try:
        committed = parse(git(base, ["show", f"HEAD:{rel}"]))
    except NotRegistered:
        committed = {}
    if candidate_id not in committed:
        raise NotRegistered(f"{candidate_id!r} is registered but NOT committed: the "
                            "commit date is the proof it was written before testing")
    if committed[candidate_id] != working[candidate_id]:
        raise NotRegistered(f"{candidate_id!r} changed after it was committed: a "
                            "changed candidate is a new candidate")
    stamp = git(base, ["log", "-1", "--format=%H %cI", "--", rel]).split()
    if len(stamp) != 2:
        raise NotRegistered(f"no commit found for {rel}")
    return Registered(entry=committed[candidate_id], commit=stamp[0],
                      committed_at=stamp[1], key=_KEY)


def entries(root: Path | None = None, rel: str = REGISTER_REL) -> dict[str, dict[str, Any]]:
    return parse(((root or REPO_ROOT) / rel).read_text(encoding="utf-8"))
