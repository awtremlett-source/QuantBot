"""Command-line entry point for the front-door price ingest.

Usage::

    python -m ingest --tickers NVDA [--start YYYY-MM-DD] [--end YYYY-MM-DD] \
        --db data/quantbot.db

``--tickers`` accepts one or more symbols (e.g. ``--tickers NVDA AAPL MSFT``).

LIVE SMOKE TEST (manual -- this hits the network and is NOT part of the test
suite). Run exactly:

    python -m ingest --tickers NVDA --start 2024-01-01 --db data/quantbot.db

Then inspect the printed ReconciliationSummary and the ``price_raw`` /
``quarantine`` tables in ``data/quantbot.db``.
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from ingest.front_door import ingest


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments, ensure the DB directory exists, run ingest, print summary."""
    parser = argparse.ArgumentParser(
        prog="ingest",
        description="Front-door ingest of daily RAW price bars into the store.",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        required=True,
        metavar="SYMBOL",
        help="One or more ticker symbols, e.g. --tickers NVDA AAPL",
    )
    parser.add_argument(
        "--start",
        default=None,
        metavar="YYYY-MM-DD",
        help="Inclusive start date passed to the data source (optional).",
    )
    parser.add_argument(
        "--end",
        default=None,
        metavar="YYYY-MM-DD",
        help="Exclusive end date passed to the data source (optional).",
    )
    parser.add_argument(
        "--db",
        required=True,
        metavar="PATH",
        help="Path to the SQLite database, e.g. data/quantbot.db",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)  # ensure data/ exists

    summary = ingest(args.tickers, db_path, start=args.start, end=args.end)
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
