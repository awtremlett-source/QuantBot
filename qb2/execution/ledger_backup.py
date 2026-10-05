"""Keep the anchor ledger alive across a lost laptop or a machine move (F13).

The ledger (``data/anchors/ledger.jsonl``) is the only memory of which orders the
anchor buyer sent, and it lives in gitignored ``data/``. Two jobs, both about
trusting the ledger:

* ``backup`` -- a dated, hash-verified copy after every live run, to the operator's
  off-laptop folder (QUANTBOT_BACKUP_DIR, the same one v1's journal backup uses),
  else ``data/backups/`` with a LOCAL-ONLY warning. Copies are never pruned: data
  is never deleted. v1's tools/backup.py is frozen, so this is not a variant of it.
* ``refusal`` / ``unrecorded`` -- why --live must not trust the ledger: missing,
  empty or unreadable; or STALE, i.e. the broker holds an API order no ledger
  intent matches -- what a restored backup looks like. Hand orders (WEB, IOS) are
  the operator's, not anchors, and are ignored. Only the newest page of history
  (50 orders) is checked: a stale copy lacks the NEWEST orders, which are there.

Nothing here can place an order or write the ledger; a refusal changes nothing.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from qb2.execution.anchor_ledger import LEDGER_PATH, REPO_ROOT, AnchorLedger, IntentState

ENV_DEST = "QUANTBOT_BACKUP_DIR"
LOCAL_DEST = REPO_ROOT / "data" / "backups"
REBUILD = "rebuilding it needs the operator's GO, from broker order history"

Matcher = Callable[[Mapping[str, Any], IntentState], bool]


def refusal(book: AnchorLedger) -> str:
    """Missing, empty or unreadable: --live refuses before touching the broker."""
    why = book.unusable()
    return f"anchor ledger {why} -- --live refuses; {REBUILD}" if why else ""


def unrecorded(book: AnchorLedger, history: Sequence[Mapping[str, Any]],
               matches: Matcher) -> str:
    """Stale: API orders in the broker's history that no ledger intent matches."""
    states = list(book.states().values())
    missing = [f"{o.get('ticker')} order {o.get('id')} ({o.get('createdAt')})"
               for o in (item.get("order") for item in history)
               if isinstance(o, dict) and o.get("initiatedFrom", "API") == "API"
               and not any(matches(o, s) for s in states)]
    if not missing:
        return ""
    return (f"anchor ledger is stale: the broker holds {len(missing)} API order(s) "
            f"it lacks: {'; '.join(missing)} -- changed nothing; {REBUILD}")


def backup(path: Path = LEDGER_PATH, dest: Path | None = None,
           now: datetime | None = None, environ: Mapping[str, str] = os.environ,
           local_dest: Path = LOCAL_DEST) -> str:
    """Copy, verify by hash, report. A missing ledger is reported, never created."""
    if not path.is_file():
        return f"ledger backup: no ledger at {path.name} -- nothing copied"
    chosen = environ.get(ENV_DEST, "").strip()
    target_root = dest or (Path(chosen) if chosen else local_dest)
    stamp = (now or datetime.now().astimezone()).strftime("%Y%m%dT%H%M%S%z")
    target = target_root / "anchors" / f"ledger-{stamp}.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    if _sha256(target) != _sha256(path):
        target.replace(target.with_suffix(".unverified"))       # quarantined
        raise OSError(f"ledger backup to {target} did not verify")
    local = dest is None and not chosen
    return (f"ledger backup verified: {target}"
            + (f" -- WARNING: LOCAL-ONLY, set {ENV_DEST}" if local else ""))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":       # DEPLOY step 1: python -m qb2.execution.ledger_backup
    print(backup())
