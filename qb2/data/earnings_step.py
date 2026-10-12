"""Earnings dates kept fresh, inside the after-hours step (QT-16 B5).

**Why.** The S5 earnings check (qb2/guard/earnings_window.py) blocks a bot entry
when a share's next date is unknown, so stale dates would quietly block everything
-- or, worse, miss a date that moved. qb2/ingest/earnings.py existed; nothing ran
it after a one-off fetch on 2 Oct.

**When.** After the daily top-up on every recorder run (clean_step.run_if_due ->
:func:`after_daily`); the work happens once per finished trading day (the same
``target_session`` the clean step uses). Catch-up for free: a missed day is
covered by the next fetch, which returns every date on record. Never raises into
the recorder.

**What.** Every bot and advisor name; ETFs are N/A, never missing. Each fetch is
appended as a new snapshot (earnings.with_history).

**Loud.** "Earnings: fresh to ... · coverage ...% · OK/RED" in the digest and on
the status page. RED: never fetched, older than the last finished session, or
coverage of the names that CAN report below MIN_COVERAGE.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from qb2.data import daily_step, universe
from qb2.data.front_door import CLEAN
from qb2.ingest import earnings

MARKER = "earnings_step.json"
PREFIX = "Earnings:"
MIN_COVERAGE = 0.90            # STARTING FIGURE: of the names that can report results
Fetch = Callable[[str], pd.DataFrame | None]


def wanted() -> list[dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for entry in [*universe.bot_entries(), *universe.advisor_entries()]:
        out.setdefault(str(entry["yfinance"]), dict(entry))
    return list(out.values())


def _read(marker: Path) -> dict[str, Any]:
    return dict(json.loads(marker.read_text(encoding="utf-8"))) if marker.is_file() else {}


def status_line(now: datetime, *, clean_root: Path | None = None) -> str:
    from qb2.data import clean_step            # clean_step imports this module

    seen = _read((clean_root or CLEAN) / MARKER)
    through = str(seen.get("fetched_through") or "")
    if not through:
        return f"{PREFIX} never fetched · RED"
    want = clean_step.target_session(now)
    share = float(seen.get("coverage", 0.0))
    reasons = ([f"{want} has finished"] if want and through < want.isoformat() else [])
    reasons += [f"coverage under {MIN_COVERAGE:.0%}"] if share < MIN_COVERAGE else []
    missing = list(seen.get("missing") or [])
    tail = f" · no date for {', '.join(missing[:6])}" if missing else ""
    why = f" ({'; '.join(reasons)})" if reasons else ""
    return (f"{PREFIX} fresh to {through} · coverage {share:.1%} · "
            f"{'RED' if reasons else 'OK'}{why}{tail}")


def run_if_due(now: datetime, *, clean_root: Path | None = None, fetch: Fetch | None = None,
               entries: Sequence[Mapping[str, Any]] | None = None) -> str:
    """Fetch if due; always return the current line. Never raises."""
    from qb2.data import clean_step

    try:
        marker = (clean_root or CLEAN) / MARKER
        seen, target = _read(marker), clean_step.target_session(now)
        if target is not None and str(seen.get("fetched_through") or "") < target.isoformat():
            found = earnings.collect(list(entries if entries is not None else wanted()),
                                     clean_root=clean_root, now=now,
                                     **({"fetch": fetch} if fetch else {}))
            can = [c for c in found if c.status != "N/A (ETF)"]
            ok = [c for c in can if c.status == "OK"]
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(json.dumps({
                "fetched_through": target.isoformat(),
                "at": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
                "names": len(found), "can_report": len(can), "ok": len(ok),
                "coverage": len(ok) / len(can) if can else 0.0,
                "missing": sorted(c.symbol for c in can if c.status != "OK")}) + "\n",
                encoding="utf-8")
        line = status_line(now, clean_root=clean_root)
    except Exception as exc:                  # noqa: BLE001 - said, never fatal
        line = f"{PREFIX} refresh failed ({type(exc).__name__}: {exc}) · RED"
    return line


def after_daily(now: datetime, *, clean_root: Path | None = None,
                digest_dir: Path | None = None) -> str:
    """The after-hours chain after the front door: the daily top-up, THEN earnings."""
    daily = daily_step.run_if_due(now, clean_root=clean_root)
    line = run_if_due(now, clean_root=clean_root)
    return f"{daily} · {line}{_digest(now, line, digest_dir)}"


def _digest(now: datetime, line: str, digest_dir: Path | None = None) -> str:
    """Keep one current "Earnings:" line in today's digest; say so if it cannot."""
    today = now.astimezone(ZoneInfo("Europe/London")).date().isoformat()
    path = (digest_dir or daily_step.DIGEST_DIR) / f"digest-{today}.md"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        body = (path.read_text(encoding="utf-8") if path.is_file()
                else f"# QB2 daily digest {today}\n\n")
        kept = [x for x in body.splitlines() if not x.strip().startswith(PREFIX)]
        path.write_text("\n".join(kept).rstrip("\n") + f"\n    {line}\n", encoding="utf-8")
    except OSError as exc:
        return f" (digest not written: {exc})"
    return ""


