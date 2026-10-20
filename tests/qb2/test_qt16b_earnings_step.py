"""QT-16 B5: earnings dates refreshed by the after-hours step. Offline (fetch stubbed)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from qb2.data import daily_step, earnings_step
from qb2.ingest import earnings
from qb2.tools import status_push

MONDAY_NIGHT = datetime(2026, 10, 12, 21, 30, tzinfo=timezone.utc)   # both markets shut
TUESDAY_NIGHT = datetime(2026, 10, 13, 21, 30, tzinfo=timezone.utc)
ENTRIES = [{"yfinance": "AAPL", "kind": "STOCK", "sleeve": "us"},
           {"yfinance": "MSFT", "kind": "STOCK", "sleeve": "us"},
           {"yfinance": "ISF.L", "kind": "ETF", "sleeve": "uk_etf"}]


class _Provider:
    def __init__(self, missing: tuple[str, ...] = ()) -> None:
        self.calls: list[str] = []
        self.missing = missing

    def __call__(self, symbol: str) -> pd.DataFrame | None:
        self.calls.append(symbol)
        if symbol in self.missing:
            return None
        return pd.DataFrame({"EPS Estimate": [1.0, 1.1]}, index=pd.DatetimeIndex(
            ["2026-07-30 16:00", "2026-10-29 16:00"], tz="America/New_York"))


def _run(tmp_path: Path, now: datetime, provider: _Provider) -> str:
    return earnings_step.run_if_due(now, clean_root=tmp_path, fetch=provider, entries=ENTRIES)


def test_once_per_finished_day_and_etfs_are_never_asked(tmp_path: Path) -> None:
    provider = _Provider()
    line = _run(tmp_path, MONDAY_NIGHT, provider)
    assert provider.calls == ["AAPL", "MSFT"]
    assert line == "Earnings: fresh to 2026-10-12 · coverage 100.0% · OK"
    _run(tmp_path, MONDAY_NIGHT, provider)
    assert provider.calls == ["AAPL", "MSFT"]                  # not due again today


def test_each_fetch_is_kept_as_its_own_snapshot(tmp_path: Path) -> None:
    provider = _Provider()
    _run(tmp_path, MONDAY_NIGHT, provider)
    _run(tmp_path, TUESDAY_NIGHT, provider)                    # the catch-up / next day
    rows = earnings.load("AAPL", tmp_path)
    assert rows is not None and len(rows) == 4
    assert rows["knowable_time"].nunique() == 2                # Monday's view survives


def test_stale_or_thin_coverage_is_red_and_names_the_missing(tmp_path: Path) -> None:
    assert earnings_step.status_line(MONDAY_NIGHT, clean_root=tmp_path) == \
        "Earnings: never fetched · RED"
    _run(tmp_path, MONDAY_NIGHT, _Provider(missing=("MSFT",)))
    line = earnings_step.status_line(MONDAY_NIGHT, clean_root=tmp_path)
    assert "coverage 50.0% · RED" in line and "no date for MSFT" in line
    marker = json.loads((tmp_path / earnings_step.MARKER).read_text(encoding="utf-8"))
    assert marker["can_report"] == 2                           # the ETF is not a denominator
    late = earnings_step.status_line(TUESDAY_NIGHT, clean_root=tmp_path)
    assert "RED" in late and "2026-10-13 has finished" in late


def test_a_broken_refresh_says_so_and_never_raises(tmp_path: Path) -> None:
    def explode(symbol: str) -> pd.DataFrame | None:
        raise ConnectionError("provider down")
    line = earnings_step.run_if_due(MONDAY_NIGHT, clean_root=tmp_path, fetch=explode,
                                    entries=ENTRIES)
    assert "coverage 0.0% · RED" in line
    broken = earnings_step.run_if_due(MONDAY_NIGHT, clean_root=tmp_path / "x",
                                      entries=[{"no": "symbol"}])
    assert broken.startswith("Earnings: refresh failed") and broken.endswith("RED")


def test_the_daily_top_up_runs_first_then_earnings(monkeypatch: pytest.MonkeyPatch,
                                                  tmp_path: Path) -> None:
    order: list[str] = []

    def step(name: str, line: str) -> object:
        def run(now: datetime, clean_root: Path | None = None) -> str:
            order.append(name)
            return line
        return run
    monkeypatch.setattr(daily_step, "run_if_due", step("daily", "Daily store: x"))
    monkeypatch.setattr(earnings_step, "run_if_due", step("earnings", "Earnings: y"))
    def advisor(now: datetime, root: Path | None) -> str:
        order.append("advisor")
        return "Advisor: z"
    line = earnings_step.after_daily(MONDAY_NIGHT, clean_root=tmp_path, digest_dir=tmp_path, advisor=advisor)
    # QT-23 D: the advisor is the chain's third step, after the top-up and earnings
    assert order == ["daily", "earnings", "advisor"] and line == "Daily store: x · Earnings: y · Advisor: z"
    assert "Earnings: y" in (tmp_path / "digest-2026-10-12.md").read_text(encoding="utf-8")


def test_the_status_page_carries_the_earnings_line(tmp_path: Path) -> None:
    _run(tmp_path, MONDAY_NIGHT, _Provider())
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text("", encoding="utf-8")
    text = status_push.build_status(manifest, tmp_path, MONDAY_NIGHT, clean_root=tmp_path)
    assert "- Earnings: fresh to 2026-10-12 · coverage 100.0% · OK" in text
