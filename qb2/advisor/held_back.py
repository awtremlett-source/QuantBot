"""Why the advisor's stop is unchecked, in the RED's own words (QT-33 F; PLAN_V3 S9, note 2026-11-13).

**Why.** Since QT-32 the daily top-up holds the advisor and the bot pot back while a stop-driving close
or a whole market's session is missing (qb2/data/behind.py: BEHIND, named in the marker). On Wed 11 and
Thu 12 Nov 2026 the top-up ran on time and held VWRL's close back until about 10:05 UTC, yet a RED that
fired then would have said "the daily top-up is overdue": the wrong cause (QT-32 PROPOSE 19).

**The rule.** When VWRL's newest final close is the session the store calls final (``have == through``),
the cause is read from the daily step's marker: every key it holds back, with its session -- "held back:
VWRL.L 2026-11-11 not delivered yet; retrying each run", or for one a later session has overtaken,
"gap: ... never delivered". With nothing held back, the top-up really is overdue and says so, as before.
When VWRL's own bars stop short of the final session, its close is missing, as before. Words only:
nothing here moves a stop, a brake or the time a RED fires.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from qb2.data import daily_step
from qb2.data.front_door import CLEAN

OVERDUE, MISSING = "the daily top-up is overdue", "VWRL's daily close is missing"


def held(seen: dict[str, Any]) -> str:
    """The marker's held-back keys in words; "" when it holds nothing back. Pure."""
    entries = dict(seen.get("behind") or {})
    late = [f"{k} {e['session']}" for k, e in entries.items() if not e.get("later")]
    gone = [f"{k} {e['session']}" for k, e in entries.items() if e.get("later")]
    said = ([f"held back: {', '.join(late)} not delivered yet"] if late else []) + \
        ([f"gap: {', '.join(gone)} never delivered"] if gone else [])
    return "; ".join(said) + "; retrying each run" if said else ""


def cause(have: date, through: date, clean_root: Path | None = None) -> str:
    """The RED's cause: a held-back close, an overdue top-up, or VWRL's own close missing."""
    if have != through:
        return MISSING
    path = (clean_root or CLEAN) / daily_step.MARKER
    seen = dict(json.loads(path.read_text(encoding="utf-8"))) if path.is_file() else {}
    return held(seen) or OVERDUE
