"""Append-only trial log -- the honest tally behind Deflated Sharpe (§7).

Every backtest, walk-forward, and Monte-Carlo run appends ONE line here. The log is
the record of how many times we pulled the slot-machine lever, and deflation needs
that count: with enough tries, some worthless strategy will look great by luck, so
the Deflated Sharpe penalises a result by how many trials preceded it. If trials went
unrecorded the penalty would be too small and we would fool ourselves.

That is why the log is APPEND-ONLY by construction: one JSON object per line (JSON
Lines), opened only in ``"a"`` mode. A run can add to history but never rewrite or
truncate it -- the tally can only ever grow. Any failure to write is RE-RAISED, never
swallowed (Scar #12): a silently-lost trial would understate the deflation count.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# The one canonical log; callers may override per-run (unit tests pass a temp path,
# or None to disable). data/ and *.jsonl are gitignored, so this never enters git.
DEFAULT_TRIAL_LOG = "data/trials.jsonl"

# Every trial record must carry at least these keys (see module docstring). Enforced
# at write time so a malformed record fails loudly rather than corrupting the tally.
REQUIRED_KEYS = (
    "utc_time",
    "kind",
    "strategy_name",
    "params",
    "metric_name",
    "metric_value",
    "n_bars",
)


def log_trial(record: dict[str, Any], path: str = DEFAULT_TRIAL_LOG) -> None:
    """Append ONE trial ``record`` as a single JSON line to ``path``.

    Append-only by construction: the file is opened in ``"a"`` mode, so an existing
    log can never be rewritten or truncated -- only extended. The parent directory is
    created if missing. Any error (a missing required key, a non-serialisable value,
    an OS failure) is RE-RAISED, never swallowed: a lost trial would understate the
    Deflated-Sharpe trial count and quietly flatter every later result.
    """
    missing = [k for k in REQUIRED_KEYS if k not in record]
    if missing:
        raise ValueError(f"trial record missing required key(s): {missing}")

    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    line = json.dumps(record, sort_keys=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    logger.debug(
        "logged trial: kind=%s strategy=%s", record["kind"], record["strategy_name"]
    )


def read_trials(path: str = DEFAULT_TRIAL_LOG) -> list[dict[str, Any]]:
    """Return every trial record in ``path`` in order (``[]`` if the file is absent)."""
    if not os.path.exists(path):
        return []
    records: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def count_trials(path: str = DEFAULT_TRIAL_LOG) -> int:
    """Return how many trials have been logged to ``path`` (``0`` if absent).

    Counts non-blank lines directly, so it stays cheap on a large log and never
    depends on parsing every record.
    """
    if not os.path.exists(path):
        return 0
    count = 0
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count
