"""QT-15 A3: the daily store is topped up after hours, and stale is loud. Offline.

QT-14 found the daily clean store ending 2026-10-01 with nothing scheduled to top
it up. The fetcher is injected: no test here touches the network.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from qb2.data import clean_step, daily_step, universe
from qb2.ingest import daily
from qb2.research import benchmark
from qb2.tools import status_push

SATURDAY = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)     # Friday 9th finished
MONDAY = datetime(2026, 10, 12, 11, 0, tzinfo=timezone.utc)       # ...and now overdue
ENTRIES = [{"yfinance": "AAPL", "quote_currency": "USD", "exchange": "NASDAQ"},
           {"yfinance": "BP.L", "quote_currency": "GBX", "exchange": "London Stock Exchange"}]
ZONES = {"AAPL": "America/New_York", "BP.L": "Europe/London"}


class _Fetch:
    def __init__(self, fail: set[str] | None = None, last: str = "2026-10-09") -> None:
        self.calls: list[str] = []
        self.fail, self.last = fail or set(), last

    def __call__(self, symbol: str) -> pd.DataFrame:
        self.calls.append(symbol)
        if symbol in self.fail:
            raise ConnectionError("planted outage")
        index = pd.bdate_range(end=self.last, periods=30,
                               tz=ZONES.get(symbol, "Europe/London"))
        return pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0,
                             "volume": 1e6}, index=index)


def _run(tmp: Path, fetch: _Fetch, now: datetime = SATURDAY) -> str:
    return daily_step.run_if_due(now, clean_root=tmp / "clean", fetch=fetch,
                                 entries=ENTRIES, digest_dir=tmp / "digest")


def _files(tmp: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted((tmp / "clean" / "daily").glob("*"))}


def test_running_it_twice_changes_nothing(tmp_path: Path) -> None:
    fetch = _Fetch()
    first = _run(tmp_path, fetch)
    assert sorted(fetch.calls) == ["AAPL", "BP.L", daily.FX_PAIR]
    assert first == "Daily store: fresh to 2026-10-09 · OK"
    before = _files(tmp_path)
    second = _run(tmp_path, fetch)
    assert len(fetch.calls) == 3                       # nothing fetched again
    assert second == first and _files(tmp_path) == before
    digest = (tmp_path / "digest" / "digest-2026-10-10.md").read_text(encoding="utf-8")
    assert digest.count("Daily store:") == 1           # one current line, not one per run


def test_a_failed_fetch_is_named_and_retried_next_run(tmp_path: Path) -> None:
    line = _run(tmp_path, _Fetch(fail={"BP.L"}))
    assert "RED" in line and "1 not fetched, retrying: BP.L" in line
    retry = _Fetch()
    assert _run(tmp_path, retry) == "Daily store: fresh to 2026-10-09 · OK"
    assert retry.calls == ["BP.L"]                     # only the failed name


def test_a_broken_top_up_never_stops_the_recorder(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*a: Any, **k: Any) -> None:
        raise RuntimeError("planted")
    monkeypatch.setattr(daily, "ingest", broken)
    line = _run(tmp_path, _Fetch())                    # returns; does not raise
    assert line.startswith("Daily store: top-up failed (RuntimeError: planted)")
    assert line.endswith("RED")


def test_stale_is_red_on_the_digest_and_the_status_page(tmp_path: Path) -> None:
    line = _run(tmp_path, _Fetch(last="2026-10-08"))
    assert "RED" in line and "US ends 2026-10-08, 2026-10-09 has finished" in line
    page = status_push.build_status(tmp_path / "none.jsonl", tmp_path, SATURDAY,
                                    clean_root=tmp_path / "clean")
    assert "- Daily store: fresh to 2026-10-08 · OK" in page     # Friday not overdue yet
    page = status_push.build_status(tmp_path / "none.jsonl", tmp_path, MONDAY,
                                    clean_root=tmp_path / "clean")
    assert "- Daily store: fresh to 2026-10-08 · RED" in page
    never = status_push.build_status(tmp_path / "none.jsonl", tmp_path, SATURDAY,
                                     clean_root=tmp_path / "empty")
    assert "- Daily store: never topped up · RED" in never


def test_the_after_hours_step_tops_up_after_the_front_door(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[str] = []

    def clean(now: datetime, clean_root: Path | None = None) -> clean_step.StepResult:
        order.append("front door")
        return clean_step.StepResult(clean_step.Verdict(False, None, None), 0)

    def top_up(now: datetime, clean_root: Path | None = None) -> str:
        order.append("daily")
        return "Daily store: planted"

    monkeypatch.setattr(clean_step, "run", clean)
    result = clean_step.run_if_due(SATURDAY, after_hours=True, clean_root=tmp_path,
                                   daily=top_up)
    assert order == ["front door", "daily"]
    assert isinstance(result, clean_step.StepResult)
    assert result.lines[-1] == "Daily store: planted"
    again = clean_step.run_if_due(SATURDAY, after_hours=True, clean_root=tmp_path,
                                  daily=top_up)
    assert again == "already cleaned through 2026-10-09 · Daily store: planted"


def test_the_list_is_both_universes_plus_d3() -> None:
    names = [e["yfinance"] for e in daily_step.wanted()]
    assert len(names) == len(set(names)) == 50 + 171        # VWRP is a bot name today
    assert daily_step.D3_SERIES[0]["yfinance"] == benchmark.D3  # ...and stays in if not
    assert {benchmark.D3, benchmark.D3_FALLBACK} <= set(names)
    assert {"US", "LSE"} == {universe.market_of(e) for e in daily_step.wanted()}
