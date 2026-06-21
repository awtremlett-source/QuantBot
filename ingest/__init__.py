"""ingest: the FRONT DOOR for data entering the store.

This package is the single, controlled entry point through which external data
becomes rows in the store. It is the *only* caller of :mod:`data_store`'s write
API (the single-writer law): every price bar is fetched, sanity/scale-checked,
and then either written to ``price_raw`` or routed to ``quarantine`` with a
specific reason -- nothing reaches the store unchecked, and nothing rejected is
silently dropped.

Scope of this brick: daily price bars, RAW only. Adjusted/CLEAN price data and
reconciliation are a later brick and are deliberately NOT done here.

Layout:

* :mod:`ingest.yfinance_source` -- fetch raw OHLCV from yfinance (isolated so
  tests can mock it and run fully offline).
* :mod:`ingest.front_door`      -- checks, quarantine, RAW write, reconciliation.
* ``python -m ingest``          -- the CLI (see :mod:`ingest.__main__`).
"""

from __future__ import annotations
