"""Keep the trial log OUT of the repo during the research test suite.

``run_backtest`` / ``walk_forward`` / ``null_distribution`` / ``assess_strategy`` all
default ``log_path`` to the real ``data/trials.jsonl``. This autouse fixture
transparently redirects any write aimed at that DEFAULT path into a per-test temp
file, so the offline suite never appends to the repo's ``data/`` directory. Tests that
pass an explicit path (their own temp file) or ``None`` are untouched -- only the
default is redirected.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from research import trial_log


@pytest.fixture(autouse=True)
def _redirect_default_trial_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    real_log_trial = trial_log.log_trial
    default_path = trial_log.DEFAULT_TRIAL_LOG
    sink = str(tmp_path / "trials.jsonl")

    def _redirected(record: dict[str, Any], path: str = default_path) -> None:
        # Only the shared default is redirected; explicit temp paths pass straight
        # through so tests can still inspect exactly what they logged.
        real_log_trial(record, path=sink if path == default_path else path)

    # backtester / walk_forward / monte_carlo all call ``trial_log.log_trial`` via the
    # module attribute, so patching it here covers every producer in one place.
    monkeypatch.setattr(trial_log, "log_trial", _redirected)
    yield
