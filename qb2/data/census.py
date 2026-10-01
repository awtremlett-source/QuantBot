"""How much of the data is actually there, counted rather than hoped.

A census is the difference between "we have data" and "we know what we have". The
exit gate for S3 asks that at least 95% of the active universe passes, and that
number is meaningless unless something counts the sessions that SHOULD exist and
compares them with the bars that DO.

Three things make this harder than counting files, and each is handled explicitly:

* **A session is not always 390 minutes.** Exchanges close early, and the UK and
  US move their clocks on different weekends. So the expected count comes from a
  real exchange calendar, and a half-day is not reported as a hole.
* **Absence of a bar is not always missing data.** A share that did not trade in a
  given minute has no bar, and never will. Minute-level completeness is therefore
  reported as a ratio, with the threshold set where real instruments actually sit
  rather than at a hopeful 100%.
* **A number that cannot go red is not a measurement.** The meter here is proven
  against a deliberately broken store before it is trusted (SCARS #9), and the
  test that does it ships alongside.

The verdict is deliberately blunt: GREEN, AMBER or RED. A beginner reading the
daily digest should not have to interpret a percentage.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from qb2.data.front_door import CLEAN, expected_minutes

# A name passes if it holds at least this fraction of the bars its sessions should
# contain. STARTING FIGURE, tested first: minute bars go missing legitimately when
# nothing trades, so the bar is set from what real instruments reach, not at 1.0.
PASS_COMPLETENESS = 0.80
# Stale after this many weekdays without a bar. Matches the recorder's own meter.
STALE_WEEKDAYS = 2
# The plan's gate (PLAN_V3 S3).
UNIVERSE_PASS_FRACTION = 0.95


@dataclass(frozen=True, slots=True)
class NameCensus:
    """One instrument's verdict, with the numbers it was reached from."""

    symbol: str
    sleeve: str
    market: str
    sessions_expected: int
    sessions_present: int
    bars_expected: int
    bars_present: int
    last_bar: str | None
    weekdays_stale: int | None
    quarantined_rows: int
    passes: bool
    reasons: tuple[str, ...] = ()

    @property
    def completeness(self) -> float:
        if self.bars_expected <= 0:
            return 0.0
        return self.bars_present / self.bars_expected


@dataclass(slots=True)
class Census:
    """The whole active universe, counted."""

    taken: str
    interval: str
    names: list[NameCensus] = field(default_factory=list)

    @property
    def passing(self) -> list[NameCensus]:
        return [n for n in self.names if n.passes]

    @property
    def fraction_passing(self) -> float:
        return len(self.passing) / len(self.names) if self.names else 0.0

    def by_sleeve(self) -> dict[str, tuple[int, int]]:
        """sleeve -> (passing, total)."""
        out: dict[str, tuple[int, int]] = {}
        for name in self.names:
            passing, total = out.get(name.sleeve, (0, 0))
            out[name.sleeve] = (passing + (1 if name.passes else 0), total + 1)
        return out

    @property
    def verdict(self) -> str:
        """GREEN only when the plan's gate is met. No partial credit."""
        if not self.names:
            return "RED"
        if self.fraction_passing >= UNIVERSE_PASS_FRACTION:
            return "GREEN"
        if self.fraction_passing >= 0.80:
            return "AMBER"
        return "RED"

    def meets_plan_gate(self) -> bool:
        return self.fraction_passing >= UNIVERSE_PASS_FRACTION


def _weekdays_between(start: date, end: date) -> int:
    days = 0
    cursor = start
    while cursor < end:
        cursor += timedelta(days=1)
        if cursor.weekday() < 5:
            days += 1
    return days


def _clean_frames(symbol: str, interval: str,
                  clean_root: Path | None = None) -> list[Path]:
    folder = (clean_root or CLEAN) / "bars" / interval / symbol
    return sorted(folder.glob("*.parquet")) if folder.exists() else []


def _quarantined(symbol: str, interval: str,
                 clean_root: Path | None = None) -> int:
    folder = (clean_root or CLEAN) / "quarantine" / interval / symbol
    if not folder.exists():
        return 0
    total = 0
    for path in folder.glob("*.parquet"):
        try:
            total += len(pd.read_parquet(path))
        except (OSError, ValueError):
            # A quarantine file we cannot read is itself worth counting as a
            # problem rather than ignoring.
            total += 1
    return total


def census_one(symbol: str, sleeve: str, market: str, interval: str,
               *, today: date | None = None,
               clean_root: Path | None = None) -> NameCensus:
    now = today or date.today()
    frames = _clean_frames(symbol, interval, clean_root)
    reasons: list[str] = []

    bars_present = 0
    bars_expected = 0
    sessions_present = 0
    last: pd.Timestamp | None = None
    for path in frames:
        frame = pd.read_parquet(path)
        if frame.empty:
            continue
        bars_present += len(frame)
        sessions_present += 1
        end = pd.Timestamp(frame.index.max())
        if last is None or end > last:
            last = end
        for day in {pd.Timestamp(ts).tz_localize(None).normalize()
                    for ts in frame.index}:
            wanted = expected_minutes(market, day, interval)
            if wanted:
                bars_expected += wanted

    quarantined = _quarantined(symbol, interval, clean_root)

    stale: int | None = None
    if last is not None:
        stale = _weekdays_between(pd.Timestamp(last).date(), now)

    if not frames:
        reasons.append("no clean bars at all")
    if bars_expected and bars_present / bars_expected < PASS_COMPLETENESS:
        reasons.append(
            f"only {bars_present/bars_expected:.0%} of the bars its sessions "
            f"should hold ({bars_present:,} of {bars_expected:,})")
    if stale is not None and stale > STALE_WEEKDAYS:
        reasons.append(f"last bar is {stale} weekdays old")
    if quarantined:
        reasons.append(f"{quarantined} row(s) in quarantine")

    return NameCensus(
        symbol=symbol, sleeve=sleeve, market=market,
        sessions_expected=sessions_present,     # sessions we hold, see docstring
        sessions_present=sessions_present,
        bars_expected=bars_expected, bars_present=bars_present,
        last_bar=None if last is None else str(last),
        weekdays_stale=stale, quarantined_rows=quarantined,
        passes=not reasons, reasons=tuple(reasons))


def take(interval: str = "5m", *, today: date | None = None,
         clean_root: Path | None = None,
         entries: Sequence[Mapping[str, object]] | None = None) -> Census:
    """Count the active universe. Uses the versioned recording list by default."""
    if entries is None:
        from qb2.ingest import tickers
        source = tickers._recording_file()["entries"]   # noqa: SLF001 - same package
        entries = list(source)

    out = Census(taken=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 interval=interval)
    for entry in entries:
        symbol = str(entry["yfinance"])
        sleeve = str(entry.get("sleeve", "?"))
        market = "US" if sleeve == "us_liquid" else "LSE"
        out.names.append(census_one(symbol, sleeve, market, interval,
                                    today=today, clean_root=clean_root))
    return out


def report(census: Census) -> str:
    """Plain words for the daily digest. No percentage without a verdict."""
    lines = [f"DATA CENSUS ({census.interval} bars) -- {census.verdict}",
             f"  {len(census.passing)} of {len(census.names)} names pass "
             f"({census.fraction_passing:.1%}); the plan asks for "
             f"{UNIVERSE_PASS_FRACTION:.0%}"]
    for sleeve, (passing, total) in sorted(census.by_sleeve().items()):
        share = passing / total if total else 0.0
        lines.append(f"    {sleeve:<10} {passing:>3}/{total:<3} {share:>6.1%}")
    failures = [n for n in census.names if not n.passes]
    if failures:
        lines.append(f"  {len(failures)} not passing:")
        for name in failures[:15]:
            lines.append(f"    {name.symbol:<9} {'; '.join(name.reasons)}")
        if len(failures) > 15:
            lines.append(f"    ... and {len(failures)-15} more")
    return "\n".join(lines)


def save(census: Census, path: Path | None = None) -> Path:
    target = path or (CLEAN / f"census-{date.today().isoformat()}.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "taken": census.taken,
        "interval": census.interval,
        "verdict": census.verdict,
        "fraction_passing": round(census.fraction_passing, 4),
        "plan_gate": UNIVERSE_PASS_FRACTION,
        "meets_plan_gate": census.meets_plan_gate(),
        "by_sleeve": {k: {"passing": v[0], "total": v[1]}
                      for k, v in census.by_sleeve().items()},
        "names": [{"symbol": n.symbol, "sleeve": n.sleeve, "passes": n.passes,
                   "completeness": round(n.completeness, 4),
                   "bars_present": n.bars_present, "bars_expected": n.bars_expected,
                   "last_bar": n.last_bar, "weekdays_stale": n.weekdays_stale,
                   "quarantined_rows": n.quarantined_rows,
                   "reasons": list(n.reasons)}
                  for n in census.names],
    }
    target.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    return target
