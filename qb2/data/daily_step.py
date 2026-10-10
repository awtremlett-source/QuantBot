"""The daily store's top-up, inside the after-hours step (QT-15 A3).

**Why.** QT-14 found the daily clean store ending 2026-10-01: qb2/ingest/daily.py
existed, but nothing scheduled ran it. Daily bars feed the advisor's trials, the
benchmark (D3) and the pound/dollar rate total_return needs.

**When.** clean_step.run_if_due calls :func:`run_if_due` after the front door on
every recorder run. It does the work once per finished trading day (the same
``target_session`` the clean step uses), with catch-up for free: each fetch takes
daily.HISTORY of bars, so a day missed while the laptop was off is filled by the
next run. A name whose fetch fails is NAMED in the marker and only those names are
retried on the next run. Nothing here raises into the recorder.

**What.** The bot universe, the advisor universe, VWRP (D3; VWRL, its fallback, is
already an advisor name) and GBPUSD=X.

**Stale is loud.** "Daily store: fresh to ... · OK/RED" goes into the day's digest
and onto the status page. RED: a market's newest daily bar is older than its last
finished session (real calendars, so a holiday is never a missing day).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from qb2.data import universe
from qb2.data.front_door import CLEAN, REPO_ROOT
from qb2.ingest import daily

MARKER = "daily_step.json"
DIGEST_DIR = REPO_ROOT / "logs" / "digest"
PREFIX = "Daily store:"
D3_SERIES: tuple[dict[str, Any], ...] = (
    {"yfinance": "VWRP.L", "quote_currency": "GBP", "exchange": "London Stock Exchange"},)
Fetch = Callable[[str], pd.DataFrame | None]


def wanted() -> list[dict[str, Any]]:
    """Every name the daily store must hold, once each (FX is added by daily.ingest)."""
    out: dict[str, dict[str, Any]] = {}
    for entry in [*universe.bot_entries(), *universe.advisor_entries(), *D3_SERIES]:
        out.setdefault(str(entry["yfinance"]), dict(entry))
    return list(out.values())


def newest_by_market(entries: Sequence[Mapping[str, Any]],
                     clean_root: Path | None = None) -> dict[str, str | None]:
    """market -> the newest daily bar any of its names holds (exchange's own date)."""
    newest: dict[str, date | None] = {universe.US: None, universe.LONDON: None}
    for entry in entries:
        frame = daily.load(str(entry["yfinance"]), clean_root)
        if frame is None or frame.empty:
            continue
        market, last = universe.market_of(entry), pd.Timestamp(frame.index.max()).date()
        held = newest[market]
        newest[market] = last if held is None or last > held else held
    return {m: d.isoformat() if d else None for m, d in newest.items()}


def _read(marker: Path) -> dict[str, Any]:
    return dict(json.loads(marker.read_text(encoding="utf-8"))) if marker.is_file() else {}


def status_line(now: datetime, *, clean_root: Path | None = None,
                strict: bool = False) -> str:
    """The one line for the digest and the status page. Reads only the marker."""
    from qb2.data import clean_step            # clean_step imports this module

    seen = _read((clean_root or CLEAN) / MARKER)
    newest: dict[str, str | None] = dict(seen.get("newest") or {})
    if not newest:
        return f"{PREFIX} never topped up · RED"
    stale = []
    for market in (universe.US, universe.LONDON):
        want = clean_step.expected_session(market, now, strict=strict)
        have = newest.get(market)
        if want is not None and (have is None or have < want.isoformat()):
            stale.append(f"{market} ends {have or 'never'}, {want} has finished")
    held = [d for d in newest.values() if d]
    fresh = min(held) if len(held) == len(newest) else "never"
    lost = list(seen.get("lost") or [])
    tail = f" · {len(lost)} not fetched, retrying: {', '.join(lost[:6])}" if lost else ""
    why = f" ({'; '.join(stale)})" if stale else ""
    return f"{PREFIX} fresh to {fresh} · {'RED' if stale else 'OK'}{why}{tail}"


def _to_digest(now: datetime, line: str, digest_dir: Path | None) -> None:
    """Keep exactly one current "Daily store:" line in today's digest."""
    today = now.astimezone(ZoneInfo("Europe/London")).date().isoformat()  # as clean_step
    path = (digest_dir or DIGEST_DIR) / f"digest-{today}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = path.read_text(encoding="utf-8") if path.is_file() else \
        f"# QB2 daily digest {today}\n\n"
    kept = [x for x in body.splitlines() if not x.strip().startswith(PREFIX)]
    path.write_text("\n".join(kept).rstrip("\n") + f"\n    {line}\n", encoding="utf-8")


def run_if_due(now: datetime, *, clean_root: Path | None = None,
               fetch: Fetch | None = None,
               entries: Sequence[Mapping[str, Any]] | None = None,
               digest_dir: Path | None = None) -> str:
    """Top up if due; always return (and digest) the current line. Never raises."""
    from qb2.data import clean_step            # clean_step imports this module

    try:
        marker = (clean_root or CLEAN) / MARKER
        seen, target = _read(marker), clean_step.target_session(now)
        through = str(seen.get("fetched_through") or "")
        lost, did = list(seen.get("lost") or []), False
        names = list(entries) if entries is not None else wanted()
        if target is not None and (through < target.isoformat() or lost):
            fresh_day = through < target.isoformat()
            todo = names if fresh_day else [e for e in names if e["yfinance"] in lost]
            outcome = daily.ingest(todo, fetch=fetch, clean_root=clean_root, now=now,
                                   include_fx=fresh_day or daily.FX_PAIR in lost)
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(json.dumps({
                "fetched_through": target.isoformat() if fresh_day else through,
                "at": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
                "fetched": len(outcome.saved), "lost": sorted(outcome.lost),
                "newest": newest_by_market(names, clean_root)}) + "\n", encoding="utf-8")
            did = True
        # strict right after a top-up; otherwise the overdue rule, as clean_step's view
        line = status_line(now, clean_root=clean_root, strict=did)
    except Exception as exc:                  # noqa: BLE001 - said, never fatal
        line = f"{PREFIX} top-up failed ({type(exc).__name__}: {exc}) · RED"
    try:
        _to_digest(now, line, digest_dir)
    except OSError as exc:
        line += f" (digest not written: {exc})"
    return line
