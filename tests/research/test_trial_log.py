"""Deterministic, fully-OFFLINE tests for the append-only trial log.

The trial log is the honest tally behind Deflated Sharpe: it must only ever GROW.
These tests prove appends accumulate, records round-trip through JSON, a missing file
reads as empty, malformed records are rejected loudly, and ``run_backtest`` writes
exactly one record per run (or none when logging is disabled).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from research.backtester import run_backtest
from research.strategy import BuyAndHold
from research.trial_log import count_trials, log_trial, read_trials


def _record(**overrides: Any) -> dict[str, Any]:
    """A valid trial record; override any field for a given test."""
    record: dict[str, Any] = {
        "utc_time": "2026-07-14T00:00:00Z",
        "kind": "backtest",
        "strategy_name": "BuyAndHold",
        "params": {"slippage_pct": 0.0005},
        "metric_name": "annualized_sharpe_net",
        "metric_value": 1.23,
        "n_bars": 100,
    }
    record.update(overrides)
    return record


def _prices() -> pd.DataFrame:
    """A tiny CLEAN-shaped, strictly rising price frame."""
    opens = [100.0, 110.0, 120.0, 130.0, 140.0]
    closes = [105.0, 115.0, 125.0, 135.0, 145.0]
    n = len(opens)
    return pd.DataFrame(
        {
            "event_time": [f"2024-01-{i + 1:02d}T00:00:00Z" for i in range(n)],
            "open": opens,
            "high": [max(o, c) + 1.0 for o, c in zip(opens, closes)],
            "low": [min(o, c) - 1.0 for o, c in zip(opens, closes)],
            "close": closes,
            "volume": [1_000_000] * n,
            "adj_close": closes,
        }
    )


def test_missing_file_reads_as_empty(tmp_path: Path) -> None:
    missing = str(tmp_path / "nope.jsonl")
    assert count_trials(missing) == 0
    assert read_trials(missing) == []


def test_two_appends_make_two_lines(tmp_path: Path) -> None:
    path = str(tmp_path / "trials.jsonl")
    log_trial(_record(kind="backtest"), path=path)
    log_trial(_record(kind="walk_forward"), path=path)

    assert count_trials(path) == 2
    assert [r["kind"] for r in read_trials(path)] == ["backtest", "walk_forward"]


def test_each_line_is_valid_json_with_required_keys(tmp_path: Path) -> None:
    path = str(tmp_path / "trials.jsonl")
    log_trial(_record(), path=path)

    with open(path, encoding="utf-8") as handle:
        lines = [ln for ln in handle.read().splitlines() if ln.strip()]
    assert len(lines) == 1

    parsed = json.loads(lines[0])  # each line is valid JSON on its own
    for key in (
        "utc_time",
        "kind",
        "strategy_name",
        "params",
        "metric_name",
        "metric_value",
        "n_bars",
    ):
        assert key in parsed


def test_read_trials_round_trips(tmp_path: Path) -> None:
    path = str(tmp_path / "trials.jsonl")
    record = _record(metric_value=0.75, n_bars=42, params={"slippage_pct": 0.001})
    log_trial(record, path=path)

    assert read_trials(path) == [record]


def test_append_only_never_shrinks(tmp_path: Path) -> None:
    path = str(tmp_path / "trials.jsonl")
    for i in range(3):
        log_trial(_record(n_bars=i), path=path)
    assert count_trials(path) == 3

    # Writing again only GROWS the file; it never rewrites or truncates prior lines.
    log_trial(_record(n_bars=99), path=path)
    assert count_trials(path) == 4
    assert read_trials(path)[0]["n_bars"] == 0  # the first line is still intact


def test_missing_required_key_raises(tmp_path: Path) -> None:
    path = str(tmp_path / "trials.jsonl")
    bad = _record()
    del bad["metric_value"]
    with pytest.raises(ValueError, match="required key"):
        log_trial(bad, path=path)
    # The bad write left no partial line behind.
    assert count_trials(path) == 0


def test_run_backtest_writes_exactly_one_record(tmp_path: Path) -> None:
    path = str(tmp_path / "trials.jsonl")
    prices = _prices()

    run_backtest(BuyAndHold(), prices, log_path=path)

    assert count_trials(path) == 1
    record = read_trials(path)[0]
    assert record["kind"] == "backtest"
    assert record["strategy_name"] == "BuyAndHold"
    # Verdict metric is risk-adjusted (Sharpe), not raw return.
    assert record["metric_name"] == "annualized_sharpe_net"
    assert record["n_bars"] == len(prices)


def test_run_backtest_log_path_none_writes_nothing(tmp_path: Path) -> None:
    path = str(tmp_path / "trials.jsonl")

    run_backtest(BuyAndHold(), _prices(), log_path=None)

    assert count_trials(path) == 0  # nothing was logged, anywhere
