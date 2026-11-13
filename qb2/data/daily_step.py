"""The daily store's top-up, inside the after-hours step (QT-15 A3).

**Why.** QT-14 found the daily clean store ending 2026-10-01: qb2/ingest/daily.py
existed, but nothing scheduled ran it. Daily bars feed the advisor's trials, the
benchmark (D3) and the pound/dollar rate total_return needs.

**When.** clean_step.run_if_due calls :func:`run_if_due` after the front door on
every recorder run. It does the work once per finished trading day (the same
``target_session`` the clean step uses), with catch-up for free: each fetch takes
every bar from daily.HISTORY_START, so a day missed while the laptop was off is
filled by the next run. A name whose fetch fails is NAMED in the marker and only those names are
retried on the next run. A row whose session had not closed when fetched is refused at the door
(daily.unclosed, QT-25 B), NAMED in the line, and taken by the next top-up, which comes only once
that session has closed -- for ^VIX, once Cboe has settled its close (:func:`closed`, QT-29 D). A sane stored row whose re-fetch came back broken is kept, and a stored
close the provider changed is replaced -- both NAMED in the line (QT-26 B, daily.py -> refetch.py).
Nothing here raises into the recorder. QT-32: a market or a stop-driving name still lacking a finished
session is BEHIND (qb2/data/behind.py): retried every run, RED, and ``fetched_through`` -- what the advisor
and the bot pot call final -- is held before it; ``topped_up`` is the day the whole list was last fetched.

**What.** The bot universe, the advisor universe, VWRP (D3; VWRL, its fallback, is
already an advisor name), ^VIX (P10's "unsettled", QT-24) and GBPUSD=X.

**Stale is loud.** "Daily store: fresh to ... · OK/RED" goes into the day's digest
and onto the status page. RED: a market's newest daily bar is older than its last
finished session (real calendars, so a holiday is never a missing day), or ^VIX's newest
close trails VWRL's newest session by more than ONE London session (QT-24: one hand load of
^VIX went a week stale behind fresh US shares, and only the advisor's "unsettled" showed it).
"""

from __future__ import annotations

import json
import time as clock
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import exchange_calendars as xcals  # type: ignore[import-untyped]
import pandas as pd

from qb2.data import arrival, behind, universe
from qb2.data.front_door import CLEAN, REPO_ROOT
from qb2.ingest import daily

MARKER = "daily_step.json"
DIGEST_DIR = REPO_ROOT / "logs" / "digest"
PREFIX = "Daily store:"
D3_SERIES: tuple[dict[str, Any], ...] = (
    {"yfinance": "VWRP.L", "quote_currency": "GBP", "exchange": "London Stock Exchange"},)
GAUGE, LEAD, MAX_GAUGE_LAG = "^VIX", "VWRL.L", 1     # QT-24: London sessions ^VIX may trail VWRL
GAUGE_FINAL, NEW_YORK = time(16, 20), ZoneInfo("America/New_York")   # QT-29 D: Cboe settles 16:15 NY
GAUGE_SERIES: tuple[dict[str, Any], ...] = (
    {"yfinance": GAUGE, "quote_currency": "USD", "exchange": "Cboe (New York clock)"},)
Fetch = Callable[[str], pd.DataFrame | None]


def wanted() -> list[dict[str, Any]]:
    """Every name the daily store must hold, once each (FX is added by daily.ingest)."""
    out: dict[str, dict[str, Any]] = {}
    for entry in [*universe.bot_entries(), *universe.advisor_entries(), *D3_SERIES, *GAUGE_SERIES]:
        out.setdefault(str(entry["yfinance"]), dict(entry))
    return list(out.values())


def closed(symbol: str, market: str | None, day: date, now: datetime) -> bool | None:
    """Was ``symbol``'s row for ``day`` final at ``now``? Its exchange's session had closed -- and for
    ^VIX, Cboe had settled it too: VIX's official close is struck at 16:15 New York, after the bell, so
    its row waits for 16:20 on New York's own clock, whichever side of a clock change (QT-29 D: rows
    taken at 16:08 New York were corrected the next evening). None: no session that day, or no exchange."""
    from qb2.data import clean_step            # clean_step imports this module

    shut = None if market is None else clean_step.closed(market, day, now)
    if symbol != GAUGE or not shut:
        return shut
    return datetime.combine(day, GAUGE_FINAL, NEW_YORK) <= now


def stored(entries: Sequence[Mapping[str, Any]], clean_root: Path | None = None) -> dict[str, set[date]]:
    """Each name's stored sessions, on its exchange's own dates: the store read once a run."""
    out: dict[str, set[date]] = {}
    for entry in entries:
        frame = daily.load(str(entry["yfinance"]), clean_root)
        out[str(entry["yfinance"])] = set() if frame is None else set(pd.DatetimeIndex(frame.index).date)
    return out


def newest_by_market(entries: Sequence[Mapping[str, Any]], dates: Mapping[str, set[date]]) -> dict[str, str | None]:
    """market -> the newest daily bar any of its names holds (exchange's own date)."""
    newest: dict[str, date | None] = {universe.US: None, universe.LONDON: None}
    for entry in entries:
        if have := dates[str(entry["yfinance"])]:
            market, top = universe.market_of(entry), max(have)
            held = newest[market]
            newest[market] = top if held is None or top > held else held
    return {m: d.isoformat() if d else None for m, d in newest.items()}


def gauge_lag(clean_root: Path | None = None) -> str | None:
    """Why ^VIX is too old to stand beside VWRL, or None. One London session behind is allowed
    (a US-only holiday); more is RED in the top-up's own line, never only "unsettled"."""
    lead = daily.load(LEAD, clean_root)
    if lead is None or lead.empty:
        return None                                      # nothing for ^VIX to keep pace with
    gauge = daily.load(GAUGE, clean_root)
    if gauge is None or gauge.empty:
        return f"{GAUGE} never fetched"
    have, want = (pd.Timestamp(f.index.max()).date() for f in (gauge, lead))
    behind = len(xcals.get_calendar("XLON").sessions_in_range(
        pd.Timestamp(have + timedelta(days=1)), pd.Timestamp(want))) if want > have else 0
    return (f"{GAUGE} ends {have}, {behind} London sessions behind {LEAD}'s {want}"
            if behind > MAX_GAUGE_LAG else None)


def _read(marker: Path) -> dict[str, Any]:
    return dict(json.loads(marker.read_text(encoding="utf-8"))) if marker.is_file() else {}


def status_line(now: datetime, *, clean_root: Path | None = None,
                strict: bool = False) -> str:
    """The one line for the digest and the status page: the marker, and ^VIX against VWRL."""
    from qb2.data import clean_step            # clean_step imports this module

    seen = _read((clean_root or CLEAN) / MARKER)
    newest: dict[str, str | None] = dict(seen.get("newest") or {})
    if not newest:
        return f"{PREFIX} never topped up · RED"
    stale, (red, more) = [], behind.words(seen)              # QT-32: BEHIND is RED, strict or not
    for market in (m for m in (universe.US, universe.LONDON) if m not in dict(seen.get("behind") or {})):
        want = clean_step.expected_session(market, now, strict=strict)
        have = newest.get(market)
        if want is not None and (have is None or have < want.isoformat()):
            stale.append(f"{market} ends {have or 'never'}, {want} has finished")
    stale += red
    if (lag := gauge_lag(clean_root)) is not None:
        stale.append(lag)
    held = [d for d in newest.values() if d]
    fresh = min(held) if len(held) == len(newest) else "never"
    lost = list(seen.get("lost") or [])
    tail = (f" · {len(lost)} not fetched, retrying: {', '.join(lost[:6])}" if lost else "") + more
    early = [f"{name} {day}" for name, days in dict(seen.get("refused") or {}).items() for day in days]
    tail += (f" · {len(early)} row{'s' if len(early) > 1 else ''} refused, their session not closed when "
             f"fetched (fetched again once it has): {', '.join(early[:6])}") if early else ""
    kept = [f"{name} {day}" for name, days in dict(seen.get("kept") or {}).items() for day in days]
    tail += (f" · {len(kept)} stored row{'s' if len(kept) > 1 else ''} kept, its re-fetch came back broken "
             f"(set aside): {', '.join(kept[:6])}") if kept else ""          # QT-26 B
    moved = [f"{name} {d} {_fig(old)} → {_fig(new)}" for name, rows in dict(seen.get("corrected") or {}).items()
             for d, old, new in rows]
    tail += (f" · {len(moved)} close{'s' if len(moved) > 1 else ''} corrected by the provider (the newer one "
             f"kept): {', '.join(moved[-6:])}") if moved else ""
    why = f" ({'; '.join(stale)})" if stale else ""
    return f"{PREFIX} fresh to {fresh} · {'RED' if stale else 'OK'}{why}{tail}"


def _scan(names: Sequence[Mapping[str, Any]], seen: Mapping[str, Any], target: date, topped: str,
          now: datetime, clean_root: Path | None) -> tuple[behind.Found, dict[str, set[date]]]:
    """behind.scan on the store as it stands, from the floor the stop path last stood on."""
    dates = stored(names, clean_root)
    floor = str(seen.get("fetched_through") or target)          # a first top-up judges the tail only
    found = behind.scan(dates, {str(e["yfinance"]): universe.market_of(e) for e in names},
                        {**dict(seen.get("short") or {}), **dict(seen.get("behind") or {})},
                        floor=date.fromisoformat(floor), target=target, topped_up=date.fromisoformat(topped),
                        at=now.astimezone(timezone.utc).isoformat(timespec="seconds"))
    return found, dates


def _write(marker: Path, body: Mapping[str, Any]) -> None:
    """Whole or not at all (QT-32): a torn marker would stop every reader of the store."""
    marker.parent.mkdir(parents=True, exist_ok=True)
    part = marker.with_name(marker.name + ".part")
    part.write_text(json.dumps(body) + "\n", encoding="utf-8")
    part.replace(marker)


def _fig(x: float) -> str:
    """A close as the line shows it: pence-level for a price, finer for a rate near 1."""
    return f"{x:.2f}" if abs(x) >= 10 else f"{x:.4f}"


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
        topped = str(seen.get("topped_up") or seen.get("fetched_through") or "")   # QT-32: or an older marker
        lost, again, did = list(seen.get("lost") or []), set(seen.get("retry") or []), False
        watch = arrival.Watch()                                # QT-33 C: what each fetch sent
        names = list(entries) if entries is not None else wanted()
        if target is not None and (topped < target.isoformat() or lost or again or "topped_up" not in seen):
            fresh_day = topped < target.isoformat()
            if not fresh_day and "topped_up" not in seen:      # a pre-QT-32 marker: look before trusting it
                again = set(_scan(names, seen, target, topped, now, clean_root)[0].retry)
            todo = names if fresh_day else [e for e in names if e["yfinance"] in {*lost, *again}]
            start, outcome = clock.monotonic(), daily.DailyOutcome()
            if todo:
                outcome = daily.ingest(todo, fetch=watch.wrap(fetch or daily.fetch_daily), clean_root=clean_root, now=now,
                                       include_fx=fresh_day or daily.FX_PAIR in lost)
            took, topped = clock.monotonic() - start, target.isoformat() if fresh_day else topped
            found, dates = _scan(names, seen, target, topped, now, clean_root)
            done = {str(e["yfinance"]) for e in todo}

            def keep(key: str, new: Mapping[str, Any]) -> dict[str, Any]:   # a retry keeps the day's notes
                old = {} if fresh_day else {k: v for k, v in dict(seen.get(key) or {}).items() if k not in done}
                return {**old, **new}
            _write(marker, {
                "fetched_through": found.final, "topped_up": topped,
                "at": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
                "fetched": len(outcome.saved), "lost": sorted(outcome.lost), "refused": keep("refused", outcome.refused),
                "kept": keep("kept", outcome.kept), "corrected": keep("corrected", outcome.corrected),
                "behind": found.behind, "short": found.short, "retry": found.retry,
                "retried": 0 if fresh_day else len(todo), "retry_s": round(took, 1),
                "newest": newest_by_market(names, dates)})
            did = True
        # strict right after a top-up; otherwise the overdue rule, as clean_step's view
        line = status_line(now, clean_root=clean_root, strict=did) + arrival.note(now, target, names, watch, marker)
    except Exception as exc:                  # noqa: BLE001 - said, never fatal
        line = f"{PREFIX} top-up failed ({type(exc).__name__}: {exc}) · RED"
    try:
        _to_digest(now, line, digest_dir)
    except OSError as exc:
        line += f" (digest not written: {exc})"
    return line
