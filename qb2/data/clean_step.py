"""The after-hours step: raw -> clean, the two censuses, the minute labels (QT-13b).

**Why.** QT-13: nothing scheduled ran the front door; the clean store stopped on
2 Oct, the 1m census read 0.0% for three days, nothing went red. QT-15 A3: the
daily store's top-up (daily_step.py) follows the front door on every call.

**When.** Inside the recorder's run, AFTER sampling and fetches, on the first run
once a trading day has finished (New York closes last, 21:00 UK): often the next
07:00 run. It catches up every day: the front door takes every raw file not yet in.

**Stale is loud.** RED when a census is below its gate, or a market's newest
clean bar is older than its last finished session (real calendars: a holiday is
never a missing day). The hourly view counts a session only once its step is
overdue (10:00 UK next weekday), so 21:50 cannot cry wolf about tonight.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import exchange_calendars as xcals  # type: ignore[import-untyped]
import pandas as pd

from qb2.data import access, census, daily_step, front_door
from qb2.data.front_door import CLEAN, REPO_ROOT

UK = ZoneInfo("Europe/London")
CALENDARS = {"US": "XNYS", "LSE": "XLON"}
# The 5m gate is PLAN_V3's. The 1m census has no plan gate (it only feeds the
# labels); 0.50 is a STARTING FIGURE under the 2026-10-07 standing GO, set below
# QT-13's rebuild (74.7%) so that only a collapse like 7-9 Oct's 0.0% trips it.
GATES = {"5m": census.UNIVERSE_PASS_FRACTION, "1m": 0.50}
DUE_BY = time(10, 0)                 # UK, on the next weekday after the session
DIGEST_DIR = REPO_ROOT / "logs" / "digest"
MARKER = "after_hours.json"


def _closed(market: str, day: date, now: datetime) -> bool | None:
    """Has ``market``'s session on ``day`` closed? None: it did not trade."""
    cal, stamp = xcals.get_calendar(CALENDARS[market]), pd.Timestamp(day)
    if not cal.is_session(stamp):
        return None
    return bool(cal.session_close(stamp) <= pd.Timestamp(now))


def due_by(session: date) -> datetime:
    """When the step for ``session`` must have run: 10:00 UK, next weekday."""
    day = session + timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return datetime.combine(day, DUE_BY, UK)


def expected_session(market: str, now: datetime, *, strict: bool) -> date | None:
    """Newest session the store must hold. strict: closed; else: step overdue."""
    day = now.astimezone(UK).date()
    for _ in range(20):
        if _closed(market, day, now) and (strict or due_by(day) <= now):
            return day
        day -= timedelta(days=1)
    return None


def target_session(now: datetime) -> date | None:
    """The newest day on which every market that traded has closed."""
    day = now.astimezone(UK).date()
    for _ in range(20):
        closed = [c for c in (_closed(m, day, now) for m in CALENDARS) if c is not None]
        if closed and all(closed):
            return day
        day -= timedelta(days=1)
    return None


# ------------------------------------------------------------ the verdict --

@dataclass(frozen=True, slots=True)
class Summary:
    """One census, reduced to what the alarm needs."""

    interval: str
    fraction: float
    newest: Mapping[str, date | None]           # market -> newest clean bar

    @classmethod
    def of(cls, interval: str, fraction: float,
           rows: Sequence[tuple[str, str | None]]) -> Summary:
        newest: dict[str, date | None] = {m: None for m in CALENDARS}
        for sleeve, last in rows:
            market = "US" if sleeve == "us_liquid" else "LSE"     # census.take's rule
            day, held = (pd.Timestamp(last).date() if last else None), newest[market]
            newest[market] = day if held is None or (day and day > held) else held
        return cls(interval, fraction, newest)

    @classmethod
    def from_census(cls, taken: census.Census) -> Summary:
        return cls.of(taken.interval, taken.fraction_passing,
                      [(n.sleeve, n.last_bar) for n in taken.names])


@dataclass(frozen=True, slots=True)
class Verdict:
    red: bool
    fresh_to: date | None
    fraction_5m: float | None
    reasons: tuple[str, ...] = ()

    def line(self) -> str:
        share = "none" if self.fraction_5m is None else f"{self.fraction_5m:.1%}"
        return (f"Clean store: fresh to {self.fresh_to or 'never'} · 5m census "
                f"{share} · {'RED' if self.red else 'OK'}")


def judge(summaries: Sequence[Summary], now: datetime, *, strict: bool) -> Verdict:
    """RED on a census below its gate, a stale market, or a census missing."""
    reasons, held = [], []  # type: tuple[list[str], list[date | None]]
    found = {s.interval: s for s in summaries}
    for interval, gate in GATES.items():
        summary = found.get(interval)
        if summary is None:
            reasons.append(f"no {interval} census on file")
            held.append(None)
            continue
        if summary.fraction < gate:
            reasons.append(f"{interval} census {summary.fraction:.1%} is below its "
                           f"{gate:.0%} gate")
        for market in CALENDARS:
            have, want = summary.newest.get(market), expected_session(
                market, now, strict=strict)
            held.append(have)
            if want is not None and (have is None or have < want):
                reasons.append(f"{interval} {market} clean bars end {have or 'never'}, "
                               f"but the {want} session has finished")
    fresh = None if not held or None in held else min(d for d in held if d)
    five = found.get("5m")
    return Verdict(bool(reasons), fresh, five.fraction if five else None,
                   tuple(reasons))


def _newest_saved(root: Path, pattern: str) -> Summary | None:
    files = sorted(root.glob(pattern))
    if not files:
        return None
    body = json.loads(files[-1].read_text(encoding="utf-8"))
    return Summary.of(str(body["interval"]), float(body["fraction_passing"]),
                      [(str(n["sleeve"]), n.get("last_bar")) for n in body["names"]])


def status_verdict(now: datetime, *, clean_root: Path | None = None) -> Verdict:
    """The hourly view, from the censuses the last step saved. Reads only."""
    root = clean_root or CLEAN
    found = [s for s in (_newest_saved(root, "census-2*.json"),
                         _newest_saved(root, "census-1m-*.json")) if s is not None]
    return judge(found, now, strict=False)


# --------------------------------------------------------------- the step --

def is_due(now: datetime, marker: Path, *, after_hours: bool) -> tuple[bool, str]:
    """Due once per finished day; a RED clean is retried, but only after hours."""
    target = target_session(now)
    if target is None:
        return False, "no finished trading day"
    seen = json.loads(marker.read_text(encoding="utf-8")) if marker.is_file() else {}
    through = str(seen.get("cleaned_through", ""))             # "" sorts first
    if through < target.isoformat():
        return True, f"{target} not yet cleaned (cleaned through {through or 'never'})"
    if seen.get("red") and after_hours:
        return True, f"the last clean ({through}) was RED: retrying after hours"
    return False, f"already cleaned through {through}"


def mark_done(now: datetime, marker: Path, *, red: bool) -> None:
    target = target_session(now)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({
        "cleaned_through": target.isoformat() if target else "",
        "at": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "red": red}) + "\n", encoding="utf-8")


@dataclass(slots=True)
class StepResult:
    verdict: Verdict
    files_written: int
    lines: list[str] = field(default_factory=list)
    complaints: list[str] = field(default_factory=list)


def run(now: datetime, *, clean_root: Path | None = None, raw_root: Path | None = None,
        entries: Sequence[Mapping[str, object]] | None = None,
        digest_dir: Path | None = None) -> StepResult:
    """Front door, then the 5m and 1m censuses, then the labels, then the digest."""
    root = clean_root or CLEAN
    tally = front_door.ingest(clean_root=clean_root, raw_root=raw_root)
    complaints = [f"raw file skipped, unreadable (half-written?): {name}"
                  for name in tally.unreadable]
    today = now.astimezone(UK).date()
    five = census.take("5m", today=today, clean_root=clean_root, entries=entries)
    one = census.take("1m", today=today, clean_root=clean_root, entries=entries)
    census.save(five, root / f"census-{today.isoformat()}.json")
    census.save(one, root / f"census-1m-{today.isoformat()}.json")

    labels_path = root / access.LABELS_PATH.name
    labels = access.load_labels(labels_path)
    if access.census_unchanged_by_labels(one):
        labels = access.update_labels(one, labels)
        access.save_labels(labels, labels_path)
    else:
        complaints.append("the minute census and the labels disagree about which "
                          "names exist -- refusing to relabel")

    verdict = judge([Summary.from_census(five), Summary.from_census(one)], now,
                    strict=True)
    complaints += [f"RED: {reason}" for reason in verdict.reasons]
    per_sleeve = access.counts_by_sleeve(labels, entries or [
        {"yfinance": n.symbol, "sleeve": n.sleeve} for n in one.names])
    lines = [f"clean: {tally.files_written} written, {tally.files_skipped_unchanged} "
             f"unchanged, {len(tally.unreadable)} unreadable, "
             f"{tally.rows_quarantined} rows quarantined",
             *census.report(five).splitlines(),
             f"1m census: {one.fraction_passing:.1%} of {len(one.names)} names "
             f"(gate {GATES['1m']:.0%}, labels only)",
             "minute labels: " + " · ".join(
                 f"{sleeve} {c[access.MINUTE_OK]} OK / {c[access.FIVE_MIN_ONLY]} 5m-only"
                 for sleeve, c in sorted(per_sleeve.items())),
             verdict.line()]
    digest = (digest_dir or DIGEST_DIR) / f"digest-{today.isoformat()}.md"
    digest.parent.mkdir(parents=True, exist_ok=True)
    digest.write_text(f"# QB2 daily digest {today.isoformat()}\n\n" + "".join(
        f"    {line}\n" for line in [*lines, *complaints]), encoding="utf-8")
    return StepResult(verdict, tally.files_written, lines, complaints)


def run_if_due(now: datetime, *, after_hours: bool, clean_root: Path | None = None,
               daily: Callable[..., str] = daily_step.run_if_due) -> StepResult | str:
    """What record_now calls. The result, or why it did not run; then the daily top-up."""
    marker = (clean_root or CLEAN) / MARKER
    due, why = is_due(now, marker, after_hours=after_hours)
    result = run(now, clean_root=clean_root) if due else why
    if isinstance(result, StepResult):
        mark_done(now, marker, red=result.verdict.red)
        result.lines.append(daily(now, clean_root=clean_root))
        return result
    return f"{result} · {daily(now, clean_root=clean_root)}"
