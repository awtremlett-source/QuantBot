"""Run the recorder once. This is what the scheduled task calls.

Catch-up safe by design: it resumes from the last saved bar, so a missed run is
harmless as long as the gap fits inside the provider's window. It prints a short,
countable summary and ends with the freshness meter, because a recorder nobody
checks is a recorder that has already stopped.

CLI: ``python -m qb2.tools.record_now [--backfill] [--interval 1m]``
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import datetime, timezone

from qb2.ingest import recorder, tickers


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="record_now", description="Capture intraday bars once.")
    parser.add_argument("--interval", default="1m",
                        choices=sorted(recorder.MAX_DAYS_PER_REQUEST))
    parser.add_argument("--backfill", action="store_true",
                        help="also fetch the 5m and 1h history (one-time)")
    args = parser.parse_args(argv)

    started = datetime.now(timezone.utc)
    entries = tickers.recording_list()
    print(f"[{started:%Y-%m-%d %H:%M:%S}Z] recorder: {len(entries)} names, "
          f"LSE open={recorder.market_is_open('LSE', started)}, "
          f"US open={recorder.market_is_open('US', started)}")

    intervals = [args.interval]
    if args.backfill:
        intervals += [i for i in recorder.BACKFILL_PERIOD if i != args.interval]

    failures = 0
    for interval in intervals:
        outcome = recorder.capture(entries, interval)
        failures += len(outcome.errors)
        print(f"  {interval}: {outcome.rows_saved:,} bars in "
              f"{len(outcome.captures)} files · {len(outcome.lost)} LOST · "
              f"{outcome.quarantined} quarantined · "
              f"{len(outcome.delay_samples)} delay samples · "
              f"{len(outcome.errors)} errors")

    for meter in recorder.freshness():
        marker = "RED " if meter["status"] == "RED" else "OK  "
        print(f"  freshness {marker}{meter['interval']:>3}: {meter['detail']}")

    # A non-zero exit lets the scheduled task's history show a bad run, but a
    # few dead symbols are normal and must not look like a failed run.
    return 1 if failures > len(entries) // 2 else 0


if __name__ == "__main__":
    raise SystemExit(main())
