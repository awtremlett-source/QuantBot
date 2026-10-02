"""When each company reports, and -- just as important -- when we could have known.

Why this exists at all: a bot that trades the same day will, sooner or later, be
holding a share at the moment it announces its results. That is not a trade, it is
a coin-flip on news nobody has seen, and PLAN_V3's P13 and the S5 earnings check
both depend on being able to say "do not open a position into this date".

**knowable_time is the whole point of the file.** Every row records the moment WE
fetched it. A back-test may only use a row whose ``knowable_time`` is at or before
the simulated moment. Without it, the data quietly tells the strategy that it knew
on Monday what was only published on Thursday, and the back-test prints a number
that cannot be earned. Earnings dates are especially dangerous this way because
they MOVE: a company announces "we will report on the 29th", then shifts it.

Three honesty rules, each of which cost something to learn elsewhere:

* **An ETF has no earnings.** It is a basket, not a company. ETFs are recorded as
  ``N/A`` and must never be counted as missing data, or the coverage number
  becomes meaningless and every census goes red for a reason that is not real.
* **A name we could not fetch is listed by name**, never filled in from a guess
  and never silently dropped.
* **The timestamps come back in New York time even for London shares**, which is
  the provider's doing, not ours. The DATE is what we use; the hour is recorded as
  given and marked unreliable rather than being "corrected" into something that
  looks precise.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from qb2.data.front_door import (CLEAN, WriterLock, _append_manifest,
                                 _write_parquet_atomically)

REPO_ROOT = Path(__file__).resolve().parents[2]
EARNINGS_DIR = CLEAN / "earnings"

# How far back to ask. The provider gives about 25 rows, which reaches 2020 for a
# quarterly reporter -- more than the intraday history will ever cover.
LIMIT = 40


@dataclass(frozen=True, slots=True)
class Coverage:
    """What we have for one name, and why if we have nothing."""

    symbol: str
    sleeve: str
    kind: str                     # "STOCK" or "ETF"
    rows: int
    past: int
    announced: int
    status: str                   # "OK" | "N/A (ETF)" | "MISSING"
    reason: str = ""


def _fetch(symbol: str) -> pd.DataFrame | None:
    import warnings

    import yfinance as yf

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        frame = yf.Ticker(symbol).get_earnings_dates(limit=LIMIT)
    if frame is None or len(frame) == 0:
        return None
    return frame


def to_rows(symbol: str, frame: pd.DataFrame, knowable: datetime,
            now: datetime) -> pd.DataFrame:
    """One row per announcement, with the time we could have known it."""
    out = pd.DataFrame({
        "symbol": symbol,
        "earnings_at": [pd.Timestamp(i).tz_convert("UTC") for i in frame.index],
    })
    out["earnings_date"] = [ts.date().isoformat() for ts in out["earnings_at"]]
    out["when"] = ["announced" if ts > pd.Timestamp(now) else "past"
                   for ts in out["earnings_at"]]
    # Recorded, not trusted: the provider returns New York time for London names.
    out["time_of_day_reliable"] = False
    out["knowable_time"] = knowable.isoformat()
    out["source"] = "yfinance.get_earnings_dates"
    for column, name in (("EPS Estimate", "eps_estimate"),
                         ("Reported EPS", "eps_reported")):
        if column in frame.columns:
            out[name] = list(frame[column])
    return out.sort_values("earnings_at").reset_index(drop=True)


def collect(entries: Sequence[Mapping[str, object]], *,
            clean_root: Path | None = None,
            now: datetime | None = None) -> list[Coverage]:
    """Fetch and store earnings dates for the given universe entries."""
    moment = now or datetime.now(timezone.utc)
    target = (clean_root or CLEAN) / "earnings"
    target.mkdir(parents=True, exist_ok=True)
    found: list[Coverage] = []

    with WriterLock((clean_root or CLEAN) / "earnings.lock"):
        for entry in entries:
            symbol = str(entry["yfinance"])
            sleeve = str(entry.get("sleeve", "?"))
            kind = str(entry.get("kind") or "STOCK")

            if kind == "ETF":
                found.append(Coverage(symbol, sleeve, kind, 0, 0, 0, "N/A (ETF)",
                                      "a basket of shares does not report results"))
                continue

            try:
                frame = _fetch(symbol)
            except Exception as exc:                      # noqa: BLE001
                found.append(Coverage(symbol, sleeve, kind, 0, 0, 0, "MISSING",
                                      f"{type(exc).__name__}: {exc}"))
                continue
            if frame is None:
                found.append(Coverage(symbol, sleeve, kind, 0, 0, 0, "MISSING",
                                      "provider returned no earnings dates"))
                continue

            rows = to_rows(symbol, frame, moment, moment)
            destination = target / f"{symbol}.parquet"
            _write_parquet_atomically(rows, destination)
            _append_manifest({
                "event": "earnings",
                "at": moment.isoformat(timespec="seconds"),
                "symbol": symbol,
                "rows": int(len(rows)),
                "past": int((rows["when"] == "past").sum()),
                "announced": int((rows["when"] == "announced").sum()),
                "knowable_time": moment.isoformat(),
                "destination": destination.name,
            }, clean_root)
            found.append(Coverage(
                symbol, sleeve, kind, len(rows),
                int((rows["when"] == "past").sum()),
                int((rows["when"] == "announced").sum()), "OK"))
    return found


def report(coverage: Sequence[Coverage]) -> str:
    """Coverage per sleeve, with ETFs excluded from the denominator."""
    lines = ["EARNINGS DATES"]
    sleeves = sorted({c.sleeve for c in coverage})
    for sleeve in sleeves:
        rows = [c for c in coverage if c.sleeve == sleeve]
        expected = [c for c in rows if c.status != "N/A (ETF)"]
        ok = [c for c in expected if c.status == "OK"]
        na = [c for c in rows if c.status == "N/A (ETF)"]
        share = f"{len(ok)/len(expected):.0%}" if expected else "n/a"
        lines.append(
            f"  {sleeve:<10} {len(ok)}/{len(expected)} of the names that CAN have "
            f"earnings ({share})" + (f", {len(na)} ETFs marked N/A" if na else ""))
    missing = [c for c in coverage if c.status == "MISSING"]
    if missing:
        lines.append(f"  {len(missing)} missing, named rather than guessed:")
        for c in missing:
            lines.append(f"    {c.symbol:<9} {c.reason}")
    announced = sum(c.announced for c in coverage)
    lines.append(f"  {announced} future announcement(s) on record")
    return "\n".join(lines)


def load(symbol: str, clean_root: Path | None = None) -> pd.DataFrame | None:
    path = (clean_root or CLEAN) / "earnings" / f"{symbol}.parquet"
    return pd.read_parquet(path) if path.is_file() else None


def knowable_at(frame: pd.DataFrame, moment: datetime) -> pd.DataFrame:
    """Only the rows we could honestly have known at ``moment``.

    This is the function a back-test must go through. Reading the parquet file
    directly would hand it tomorrow's announcements.
    """
    knowable = pd.to_datetime(frame["knowable_time"], utc=True)
    cutoff = pd.Timestamp(moment)
    cutoff = (cutoff.tz_localize("UTC") if cutoff.tzinfo is None
              else cutoff.tz_convert("UTC"))
    return frame[knowable <= cutoff]


def main() -> None:
    universe = sorted((REPO_ROOT / "docs" / "universe").glob("bot-universe-*.json"))
    entries = json.loads(universe[-1].read_text(encoding="utf-8"))["entries"]
    coverage = collect(entries)
    print(report(coverage))


if __name__ == "__main__":
    main()
