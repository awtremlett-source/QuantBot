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
from datetime import datetime, timezone
from pathlib import Path

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

    target = manifest or MANIFEST
    now = datetime.now(timezone.utc)
    written: list[dict[str, object]] = []

    for ticker, market in probes:
        if not market_is_open(market, now):
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
        sample = delay_sample(market, last, now)
        if sample is None:
            continue
        sample = {**sample, "ticker": ticker, "probe": "sample_delay"}
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(sample, sort_keys=True) + "\n")
        written.append(sample)
    return written


def collected(manifest: Path | None = None) -> dict[str, list[float]]:
    """Every delay sample recorded so far, by market."""
    target = manifest or MANIFEST
    out: dict[str, list[float]] = {}
    if not target.exists():
        return out
    with target.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and row.get("kind") == "delay_sample":
                market = str(row.get("market"))
                age = row.get("age_seconds")
                if isinstance(age, (int, float)):
                    out.setdefault(market, []).append(float(age))
    return out


def sessions_covered(manifest: Path | None = None) -> dict[str, int]:
    """How many distinct days each market has samples from."""
    target = manifest or MANIFEST
    days: dict[str, set[str]] = {}
    if not target.exists():
        return {}
    with target.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and row.get("kind") == "delay_sample":
                stamp = str(row.get("at_utc", ""))[:10]
                if stamp:
                    days.setdefault(str(row.get("market")), set()).add(stamp)
    return {market: len(seen) for market, seen in days.items()}


def verdict(manifest: Path | None = None) -> str:
    """Plain words, and the word UNMEASURED when that is the truth."""
    samples = collected(manifest)
    sessions = sessions_covered(manifest)
    lines = ["QUOTE DELAY (FACTS row o)"]
    if not samples:
        lines.append(f"  UNMEASURED -- 0 samples. Needs {MIN_SAMPLES_PER_MARKET} "
                     f"per market across {MIN_SESSIONS} sessions.")
        return "\n".join(lines)

    for market in sorted(samples):
        ages = samples[market]
        enough = (len(ages) >= MIN_SAMPLES_PER_MARKET
                  and sessions.get(market, 0) >= MIN_SESSIONS)
        state = "MEASURED" if enough else "NOT YET ENOUGH"
        lines.append(
            f"  {market}: {state} -- {len(ages)} samples over "
            f"{sessions.get(market, 0)} session(s); median "
            f"{statistics.median(ages)/60:.1f} min, worst "
            f"{max(ages)/60:.1f} min")
        if not enough:
            lines.append(f"      needs {MIN_SAMPLES_PER_MARKET} samples over "
                         f"{MIN_SESSIONS} sessions before it may be quoted")
    return "\n".join(lines)


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
