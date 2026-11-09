"""News, step 1 (QT-30 D): record US company filings for the universe names. Recording only.

Nothing here scores, trades or advises: no module reads this file yet, and the first news trial is a
draft the operator has not registered (docs/research/news_sources_2026-11-09_QT30.md).
Source: SEC EDGAR's 8-K filings, free and public, with the moment the SEC accepted each one. UK
announcements have no free feed we may use, so they are not recorded (same note).
Once a UK day, riding the recorder's own run, at 4 requests a second against the SEC's limit of 10.
A plain agent name is sent and no contact details: adding one is the operator's decision (report).
Append-only: data/raw/news/sec_8k.jsonl; each row carries its fetch time. Never stops the recorder.
"""

from __future__ import annotations

import json
import time
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from qb2.data import universe

REPO_ROOT = Path(__file__).resolve().parents[2]
FOLDER = REPO_ROOT / "data" / "raw" / "news"
FILE, MARKER = FOLDER / "sec_8k.jsonl", FOLDER / "last_day.txt"
TICKERS = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
AGENT = "QuantBot-news-recorder"
SPACING_SECONDS = 0.25                 # 4 a second; the SEC allows 10
LOOKBACK_DAYS = 7                      # enough to catch up after the PC has been off
FORMS = frozenset({"8-K", "8-K/A"})
UK = ZoneInfo("Europe/London")

Fetch = Callable[[str], Any]
Say = Callable[[str], None]


def get_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=20.0) as response:      # noqa: S310 - https, fixed hosts
        return json.load(response)


def us_tickers(entries: Iterable[Mapping[str, Any]]) -> list[str]:
    """The universe's US shares, by the SEC's spelling. London lines are not on EDGAR."""
    return sorted({str(e["yfinance"]) for e in entries if str(e.get("kind")) == "STOCK"
                   and not str(e["yfinance"]).endswith(".L")})


def ciks(payload: Mapping[str, Mapping[str, Any]]) -> dict[str, int]:
    return {str(row["ticker"]): int(row["cik_str"]) for row in payload.values()}


def filings(payload: Mapping[str, Any], ticker: str, cik: int, since: str, stamp: str) -> list[dict[str, Any]]:
    """This company's 8-Ks filed on or after ``since``, the SEC's own words and timestamp unchanged."""
    recent = payload["filings"]["recent"]
    return [{"ticker": ticker, "cik": cik, "form": form, "accession": recent["accessionNumber"][i],
             "accepted": recent["acceptanceDateTime"][i], "filed": recent["filingDate"][i],
             "items": recent["items"][i], "headline": recent["primaryDocDescription"][i],
             "source": "SEC EDGAR", "fetched_at": stamp}
            for i, form in enumerate(recent["form"]) if form in FORMS and recent["filingDate"][i] >= since]


def _seen(path: Path) -> set[tuple[str, str]]:
    out = set()
    for line in path.read_text(encoding="utf-8").splitlines() if path.is_file() else []:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue                   # a half-written last line: the file is only added to
        out.add((str(row["ticker"]), str(row["accession"])))
    return out


def record(now: datetime, say: Say, *, names: Iterable[str], fetch: Fetch = get_json,
           sleep: Callable[[float], None] = time.sleep, folder: Path = FOLDER) -> int:
    """Append new filings; one name failing is counted and said. Returns how many rows were added."""
    target, stamp = folder / FILE.name, now.astimezone(timezone.utc).isoformat(timespec="seconds")
    known, added, failed = _seen(target), 0, 0
    mapping, since = ciks(fetch(TICKERS)), (now - timedelta(days=LOOKBACK_DAYS)).date().isoformat()
    wanted = [t for t in names if t in mapping]
    folder.mkdir(parents=True, exist_ok=True)
    for ticker in wanted:
        sleep(SPACING_SECONDS)
        try:
            rows = filings(fetch(SUBMISSIONS.format(cik=mapping[ticker])), ticker, mapping[ticker], since, stamp)
        except Exception as exc:              # noqa: BLE001 - counted and said below, never fatal
            failed += 1
            last_error = f"{type(exc).__name__}: {exc}"
            continue
        fresh = [r for r in rows if (r["ticker"], r["accession"]) not in known]
        with target.open("a", encoding="utf-8") as handle:
            handle.writelines(json.dumps(r, sort_keys=True) + "\n" for r in fresh)
        added += len(fresh)
    say(f"  News recording: {len(wanted)} US names read, {added} new filings saved, {failed} failed"
        + (f" (last: {last_error})" if failed else ""))
    return added


def step(now: datetime, say: Say, *, folder: Path = FOLDER) -> None:
    """The recorder's call: once a UK day. Recording only, and never fatal."""
    today, marker = now.astimezone(UK).date().isoformat(), folder / MARKER.name
    try:
        if marker.is_file() and marker.read_text(encoding="utf-8").strip() == today:
            return
        record(now, say, names=us_tickers([*universe.bot_entries(), *universe.advisor_entries()]), folder=folder)
        marker.write_text(today + "\n", encoding="utf-8")
    except Exception as exc:              # noqa: BLE001 - said, never fatal
        say(f"  News recording failed: {type(exc).__name__}: {exc}")
