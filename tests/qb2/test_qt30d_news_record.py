"""QT-30 D2: news, step 1 -- recording only. Offline: the SEC is planted."""

from __future__ import annotations

import ast
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from qb2.data import universe
from qb2.ingest import close_feeds, fresh_run, news_record

NOW = datetime(2026, 11, 9, 7, 0, tzinfo=UTC)
MAP = {"0": {"ticker": "AAPL", "cik_str": 320193}, "1": {"ticker": "MSFT", "cik_str": 789019}}


def subs(*rows: tuple[str, str, str]) -> dict[str, Any]:
    return {"filings": {"recent": {"form": [r[0] for r in rows], "filingDate": [r[1] for r in rows],
                                   "accessionNumber": [r[2] for r in rows],
                                   "acceptanceDateTime": ["2026-11-02T21:30:23.000Z"] * len(rows),
                                   "items": ["2.02,9.01"] * len(rows), "primaryDocDescription": ["8-K"] * len(rows)}}}


def fetcher(**by_cik: dict[str, Any]) -> Any:
    def fetch(url: str) -> Any:
        if url == news_record.TICKERS:
            return MAP
        cik = str(int(url.split("CIK")[1].split(".")[0]))
        if cik not in by_cik:
            raise OSError("not planted")
        return by_cik[cik]
    return fetch


def rows(folder: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in (folder / "sec_8k.jsonl").read_text(encoding="utf-8").splitlines()]


def run(folder: Path, fetch: Any, said: list[str] | None = None) -> int:
    return news_record.record(NOW, (said if said is not None else []).append, names=["AAPL", "MSFT", "NOPE"],
                              fetch=fetch, sleep=lambda s: None, folder=folder)


def test_only_recent_8ks_are_saved_with_the_secs_own_timestamp(tmp_path: Path) -> None:
    fresh = subs(("8-K", "2026-11-02", "a-1"), ("10-Q", "2026-11-02", "a-2"), ("8-K", "2026-01-02", "a-3"))
    assert run(tmp_path, fetcher(**{"320193": fresh, "789019": subs()})) == 1
    row = rows(tmp_path)[0]
    assert (row["ticker"], row["form"], row["accession"], row["accepted"]) == ("AAPL", "8-K", "a-1", "2026-11-02T21:30:23.000Z")
    assert row["source"] == "SEC EDGAR" and row["fetched_at"] == NOW.isoformat(timespec="seconds") and row["headline"]


def test_the_file_only_appends_and_never_saves_a_filing_twice(tmp_path: Path) -> None:
    fetch = fetcher(**{"320193": subs(("8-K", "2026-11-02", "a-1")), "789019": subs()})
    run(tmp_path, fetch)
    before = (tmp_path / "sec_8k.jsonl").read_text(encoding="utf-8")
    assert run(tmp_path, fetch) == 0
    assert (tmp_path / "sec_8k.jsonl").read_text(encoding="utf-8") == before
    later = fetcher(**{"320193": subs(("8-K", "2026-11-02", "a-1"), ("8-K", "2026-11-03", "a-9")), "789019": subs()})
    assert run(tmp_path, later) == 1
    assert (tmp_path / "sec_8k.jsonl").read_text(encoding="utf-8").startswith(before)


def test_one_name_failing_is_counted_and_said(tmp_path: Path) -> None:
    said: list[str] = []
    assert run(tmp_path, fetcher(**{"789019": subs(("8-K", "2026-11-02", "m-1"))}), said) == 1
    assert "1 failed" in said[0] and "OSError" in said[0]


def test_only_us_shares_are_asked_for() -> None:
    entries = [{"yfinance": "AAPL", "kind": "STOCK"}, {"yfinance": "BARC.L", "kind": "STOCK"},
               {"yfinance": "SPY", "kind": "ETF"}, {"yfinance": "AAPL", "kind": "STOCK"}]
    assert news_record.us_tickers(entries) == ["AAPL"]


def test_requests_stay_inside_the_secs_limit(tmp_path: Path) -> None:
    waits: list[float] = []
    fetch = fetcher(**{"320193": subs(), "789019": subs()})
    news_record.record(NOW, print, names=["AAPL", "MSFT"], fetch=fetch, sleep=waits.append, folder=tmp_path)
    assert waits == [news_record.SPACING_SECONDS] * 2 and 1 / news_record.SPACING_SECONDS <= 10


def test_it_runs_once_a_uk_day_and_never_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    def counted(now: datetime, say: Any, **k: Any) -> int:
        calls.append(1)
        return 0

    monkeypatch.setattr(news_record, "record", counted)
    monkeypatch.setattr(universe, "bot_entries", lambda: [])
    monkeypatch.setattr(universe, "advisor_entries", lambda: [])
    tmp_path.mkdir(exist_ok=True)
    news_record.step(NOW, print, folder=tmp_path)
    news_record.step(NOW, print, folder=tmp_path)
    assert calls == [1]

    def boom(now: datetime, say: Any, **k: Any) -> int:
        raise RuntimeError("no")

    monkeypatch.setattr(news_record, "record", boom)
    said: list[str] = []
    news_record.step(datetime(2026, 11, 10, 7, 0, tzinfo=UTC), said.append, folder=tmp_path)
    assert "News recording failed" in said[0]


def test_the_recorders_hook_records_after_cleaning_and_survives_a_fault(monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[str] = []

    def boom(*a: object, **k: object) -> None:
        order.append("news")
        raise RuntimeError("no")

    monkeypatch.setattr(close_feeds, "gather", lambda *a, **k: order.append("gather"))
    monkeypatch.setattr(fresh_run, "before_clean", lambda say: order.append("before"))
    monkeypatch.setattr(fresh_run, "after_clean", lambda say: order.append("after"))
    monkeypatch.setattr(news_record, "step", boom)
    said: list[str] = []
    assert fresh_run.around_clean(lambda after_hours: [], after_hours=False, say=said.append) == []
    assert order == ["gather", "before", "after", "news"] and any("News recording failed" in x for x in said)


def test_recording_only_nothing_reads_it_and_it_cannot_trade() -> None:
    root = Path(__file__).resolve().parents[2] / "qb2"
    readers = [p for p in root.rglob("*.py") if ("sec_8k" in p.read_text(encoding="utf-8") or
               "news_record" in p.read_text(encoding="utf-8")) and p.name != "news_record.py"]
    assert [p.name for p in readers] == ["fresh_run.py"]
    tree = ast.parse((root / "ingest" / "news_record.py").read_text(encoding="utf-8"))
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not any("execution" in str(m) or "advisor" in str(m) for m in imported)
