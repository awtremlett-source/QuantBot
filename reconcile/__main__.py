"""Command-line entry point for RAW->CLEAN price reconciliation.

Usage::

    python -m reconcile --tickers NVDA [--tickers ...] --db data/quantbot.db

``--tickers`` accepts one or more symbols (e.g. ``--tickers NVDA AAPL MSFT``).

LIVE SMOKE TEST (manual -- this hits the network to fetch corporate actions and
is NOT part of the test suite). Ingest first, then reconcile, then read CLEAN.
Run exactly:

    python -m reconcile --tickers NVDA --db data/quantbot.db

Then inspect the printed ReconciliationSummary and the now-populated
``price_clean`` table in ``data/quantbot.db`` (this is the table ``read_price_asof``
serves). ``corporate_actions`` will list the splits/dividends that were fetched.
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from reconcile.clean_prices import reconcile


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments, ensure the DB directory exists, reconcile, print summary."""
    parser = argparse.ArgumentParser(
        prog="reconcile",
        description="RAW->CLEAN split-adjusted price reconciliation into the store.",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        required=True,
        metavar="SYMBOL",
        help="One or more ticker symbols, e.g. --tickers NVDA AAPL",
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

    summary = reconcile(args.tickers, db_path)
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
