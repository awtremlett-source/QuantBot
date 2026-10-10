"""qb2's append-only trial log -- the honest tally behind Deflated Sharpe (S4).

PORTED, NOT IMPORTED, from v1's research/trial_log.py (SHA-256 of that file at
copy time, 2026-10-10: 597d02b36f221d89bd5a2851167c8a4c27a7a9c9d00d8c3bf0da23524cd435f9).
Adapted for qb2:

* its OWN file, data/qb2/trials.jsonl -- separate from v1's data/trials.jsonl, so
  neither count contaminates the other;
* every record names the pre-registered ``candidate_id`` and the commit that
  registered it, so "written before tested" can be checked line by line;
* ``kind="drill"`` marks a known-null drill: logged like any run, but never
  counted as a trial (a measuring instrument is not a lottery ticket).

Append-only by construction ("a" mode, one JSON object per line). A failure to
write is RE-RAISED (Scar #12): a silently lost trial would understate the count.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRIAL_LOG = REPO_ROOT / "data" / "qb2" / "trials.jsonl"

DRILL = "drill"
FIREWALL = "firewall"
BACKTEST = "backtest"
WALK_FORWARD = "walk_forward"
MONTE_CARLO = "monte_carlo"
HOLDOUT = "holdout"
KINDS = frozenset({DRILL, FIREWALL, BACKTEST, WALK_FORWARD, MONTE_CARLO, HOLDOUT})

REQUIRED_KEYS = ("utc_time", "kind", "candidate_id", "register_commit",
                 "strategy_name", "params", "metric_name", "metric_value", "n_bars")


def log_trial(record: Mapping[str, Any], path: Path | None = None) -> None:
    """Append ONE record. Missing keys or an unknown kind fail loudly."""
    missing = [k for k in REQUIRED_KEYS if k not in record]
    if missing:
        raise ValueError(f"trial record missing required key(s): {missing}")
    if record["kind"] not in KINDS:
        raise ValueError(f"unknown trial kind {record['kind']!r}")
    target = path or DEFAULT_TRIAL_LOG
    target.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(dict(record), sort_keys=True, default=str)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def read_trials(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or DEFAULT_TRIAL_LOG
    if not target.is_file():
        return []
    return [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def count_selection_trials(path: Path | None = None) -> tuple[int, dict[str, int]]:
    """The honest N for deflation (v1's policy, plus drills excluded).

    firewall and backtest records count 1 each; walk_forward counts its
    ``params.total_trials``; monte_carlo and holdout count 0 (a measuring stick
    pointed at a result we already had); drills count 0 and are reported.
    """
    seen = {"firewall": 0, "backtest": 0, "walk_forward_trials": 0,
            "monte_carlo_excluded": 0, "holdout_excluded": 0, "drills_excluded": 0}
    for record in read_trials(path):
        kind = record.get("kind")
        if kind == DRILL:
            seen["drills_excluded"] += 1
        elif kind == FIREWALL:
            seen["firewall"] += 1
        elif kind == BACKTEST:
            seen["backtest"] += 1
        elif kind == WALK_FORWARD:
            seen["walk_forward_trials"] += int(record["params"]["total_trials"])
        elif kind == MONTE_CARLO:
            seen["monte_carlo_excluded"] += 1
        elif kind == HOLDOUT:
            seen["holdout_excluded"] += 1
        else:
            raise ValueError(f"unknown trial kind {kind!r} in the qb2 trial log")
    return seen["firewall"] + seen["backtest"] + seen["walk_forward_trials"], seen
