"""Where the advisor keeps its record (QT-23 C): append-only JSON lines, the state is their replay.

data/qb2/advisor/
* arm.json          -- the arm date (Part F). Nothing is scored before it; unarmed, the scheduled
                       jobs do nothing but say so.
* suggestions.jsonl -- every suggestion issued, checked (engine.issue is its only writer).
* days.jsonl        -- one line per processed session: the as-if record, reconciled daily.
* shadows.jsonl     -- S-01..S-06, one line per processed session from the arm date.
* runs.jsonl        -- each job run: the daily step, the weekly review, catch-ups, MISSED.
The ADVISOR's stop is its record in data/qb2/stops.jsonl; its brake, its lines in brakes.jsonl.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from qb2.execution.safety import Blocked

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class Paths:
    """Every file the advisor reads or writes; tests hand in a tmp root."""
    root: Path
    stops: Path
    brakes: Path
    page: Path

    @classmethod
    def default(cls) -> Paths:
        data = REPO_ROOT / "data" / "qb2"
        return cls(data / "advisor", data / "stops.jsonl", data / "brakes.jsonl",
                   REPO_ROOT / "logs" / "advisor" / "advisor.md")

    @classmethod
    def under(cls, tmp: Path) -> Paths:
        return cls(tmp / "advisor", tmp / "stops.jsonl", tmp / "brakes.jsonl", tmp / "advisor.md")

    @property
    def arm(self) -> Path:
        return self.root / "arm.json"

    def log(self, name: str) -> Path:
        return self.root / f"{name}.jsonl"


def append(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def rows(path: Path) -> list[dict[str, Any]]:
    """A log's lines; an unreadable line is refused, never skipped (no guessing)."""
    out = []
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    for n, line in enumerate(text.splitlines(), 1):
        try:
            out.append(dict(json.loads(line)))
        except json.JSONDecodeError as exc:
            raise Blocked(f"{path.name} line {n} is unreadable -- refusing to guess") from exc
    return out


def arm_date(paths: Paths) -> date | None:
    if not paths.arm.is_file():
        return None
    return date.fromisoformat(str(json.loads(paths.arm.read_text(encoding="utf-8"))["arm_date"]))


def arm(paths: Paths, day: date, now: datetime, box: str) -> date:
    """Arm the record from ``day``. Once only: a second arm would move the start of the test."""
    if (was := arm_date(paths)) is not None:
        raise Blocked(f"already armed on {was}: the arm date never moves")
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.arm.write_text(json.dumps({"arm_date": day.isoformat(), "box": box,
                                     "at": now.astimezone(timezone.utc).isoformat(timespec="seconds")},
                                    indent=1) + "\n", encoding="utf-8")
    return day
