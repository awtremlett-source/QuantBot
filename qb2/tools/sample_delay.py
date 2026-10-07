"""Measure how stale our prices are. Small, fast, and safe to run every 15 minutes.

FACTS.md row o has been UNMEASURED twice, both times for the same reason: the
markets were shut when someone remembered to look. The recorder does take samples,
but only as a side effect of a full 226-name capture -- and those runs now take over
an hour and get refused by the scheduler, so the samples never arrive.

So this exists separately: two tickers, one request each, a few seconds. It can be
scheduled every quarter of an hour without being a burden, which is how a number
gets measured without anyone having to remember.

What it measures: the age of the newest CLOSED bar while the market is open. That
is the delay that matters -- if the freshest price we can see is fifteen minutes
old, then a "same-day" bot is acting on fifteen-minute-old information and every
backtest must simulate that lag (which is why P4 and the firewall both depend on
this number).

Outside market hours it records NOTHING and says so. A bar that is old because the
exchange is shut says nothing about the feed, and mistaking one for the other is
exactly how row o went wrong the first time.
"""

from __future__ import annotations

import json
import statistics
from collections.abc import Sequence
from datetime import date, datetime, timezone
from pathlib import Path

from qb2.tools import delay_count

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "data" / "raw" / "intraday" / "manifest.jsonl"

# One liquid name per market is enough: we are measuring the FEED, not the share.
PROBES: tuple[tuple[str, str], ...] = (("AAPL", "US"), ("BP.L", "LSE"))

# The plan's bar for calling row o measured.
MIN_SAMPLES_PER_MARKET = 20
MIN_SESSIONS = 3


def take_samples(probes: Sequence[tuple[str, str]] = PROBES,
                 manifest: Path | None = None) -> list[dict[str, object]]:
    """One sample per open market. Returns what it wrote, which may be nothing."""
    import warnings

    import yfinance as yf

    from qb2.ingest.recorder import delay_sample, market_is_open
    from qb2.tools import clock as clock_module

    target = manifest or MANIFEST
    now = datetime.now(timezone.utc)
    written: list[dict[str, object]] = []
    # Asked once per run rather than once per ticker: the two probes are seconds
    # apart, so one answer describes both, and three servers do not need pinging
    # twice to learn the same thing.
    clock_check = clock_module.check()

    for ticker, market in probes:
        # Weekday hours AND the real calendar: holidays and half-days are shut.
        if not (market_is_open(market, now)
                and delay_count.in_full_session(market, now)):
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            frame = yf.Ticker(ticker).history(period="1d", interval="1m")
        if frame.empty:
            continue
        # The newest bar may still be forming; the one before it is closed.
        closed = frame.iloc[:-1]
        if closed.empty:
            continue
        last = closed.index[-1].to_pydatetime()
        sample = delay_sample(market, last, now, clock_check=clock_check)
        if sample is None:
            continue
        sample = {**sample, "ticker": ticker, "probe": "sample_delay"}
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(sample, sort_keys=True) + "\n")
        written.append(sample)
    return written


def collected(manifest: Path | None = None,
              verified_only: bool = False) -> dict[str, list[float]]:
    """Delay samples by market -- only the ones delay_count says may count.

    ``verified_only`` keeps just the readings taken with a checked clock. An
    unverified reading is not wrong -- it is unknown, and the difference matters
    when deciding whether row o may be quoted.
    """
    out: dict[str, list[float]] = {}
    rows = delay_count.read_samples(manifest or MANIFEST)
    for row in delay_count.countable(rows, verified_only=verified_only):
        age = row["age_seconds"]
        if isinstance(age, (int, float)):
            out.setdefault(str(row["market"]), []).append(float(age))
    return out


def sessions_covered(manifest: Path | None = None,
                     verified_only: bool = False) -> dict[str, int]:
    """How many distinct FULL sessions each market has countable samples from."""
    days: dict[str, set[str]] = {}
    rows = delay_count.read_samples(manifest or MANIFEST)
    for row in delay_count.countable(rows, verified_only=verified_only):
        days.setdefault(str(row["market"]), set()).add(str(row["at_utc"])[:10])
    return {market: len(seen) for market, seen in days.items()}


def verdict(manifest: Path | None = None, today: date | None = None) -> str:
    """Plain words, and the word UNMEASURED when that is the truth.

    Only readings taken with a CHECKED clock count towards the threshold. A
    reading from an unverified clock is not wrong, it is unknown -- and a day of
    unreachable time servers must not quietly satisfy the bar at which row o is
    allowed to be quoted.
    """
    everything = collected(manifest)
    samples = collected(manifest, verified_only=True)
    sessions = sessions_covered(manifest, verified_only=True)
    unverified = {m: len(everything.get(m, [])) - len(samples.get(m, []))
                  for m in everything}
    lines = ["QUOTE DELAY (FACTS row o)"]
    # The meter rides in the verdict because every recorder run prints this.
    meter = [f"  meter {m['market']}: {m['status']} -- {m['detail']}"
             for m in delay_count.session_meter(manifest or MANIFEST, today=today)]
    if not samples:
        total = sum(len(v) for v in everything.values())
        lines.append(
            f"  UNMEASURED -- 0 readings taken with a checked clock. Needs "
            f"{MIN_SAMPLES_PER_MARKET} per market across {MIN_SESSIONS} sessions.")
        if total:
            lines.append(
                f"      ({total} unverified reading(s) on record and NOT counted: "
                "the clock they were taken on was never checked)")
        return "\n".join(lines + meter)

    for market in sorted(samples):
        ages = samples[market]
        enough = (len(ages) >= MIN_SAMPLES_PER_MARKET
                  and sessions.get(market, 0) >= MIN_SESSIONS)
        state = "MEASURED" if enough else "NOT YET ENOUGH"
        lines.append(
            f"  {market}: {state} -- {len(ages)} clock-checked samples over "
            f"{sessions.get(market, 0)} session(s); median "
            f"{statistics.median(ages)/60:.1f} min, worst "
            f"{max(ages)/60:.1f} min")
        if unverified.get(market):
            lines.append(f"      plus {unverified[market]} unverified reading(s), "
                         "not counted")
        if not enough:
            lines.append(f"      needs {MIN_SAMPLES_PER_MARKET} samples over "
                         f"{MIN_SESSIONS} sessions before it may be quoted")
    for market, count in sorted(unverified.items()):
        if market not in samples and count:
            lines.append(f"  {market}: UNMEASURED -- {count} unverified "
                         "reading(s) only, none with a checked clock")
    return "\n".join(lines + meter)


def main() -> None:
    written = take_samples()
    if written:
        for sample in written:
            age = sample["age_seconds"]
            minutes = (float(age) / 60 if isinstance(age, (int, float)) else 0.0)
            print(f"  sampled {sample['market']}: {minutes:.1f} min old")
    else:
        print("  no samples: both markets are shut (recording nothing is correct)")
    print(verdict())


if __name__ == "__main__":
    main()
