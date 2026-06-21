"""reconcile: turn RAW price bars into the CLEAN, adjusted series.

This package derives ``price_clean`` from data already in the store. It reads
``price_raw`` plus a small, separately-sourced ``corporate_actions`` table and
writes the reconciled, split-adjusted series the rest of the system reads
(``read_price_asof`` serves ``price_clean``).

Like ingest, it writes ONLY through the :mod:`data_store` write API (the
single-writer law) and routes any row that fails a sanity check to
``quarantine`` rather than to ``price_clean`` -- nothing reconciled is admitted
unchecked, and nothing rejected is silently dropped.

SCOPE: split adjustment ONLY. Dividend adjustment is deliberately OUT OF SCOPE
in this brick (dividends are still fetched and persisted to ``corporate_actions``
for a later refinement, but they do not yet affect prices). See
:func:`reconcile.clean_prices.reconcile`.

Layout:

* :mod:`reconcile.corporate_actions` -- fetch splits/dividends from yfinance
  (isolated so tests can mock it and run fully offline).
* :mod:`reconcile.clean_prices`      -- split-adjust, sanity-check, write CLEAN,
  reconciliation summary.
* ``python -m reconcile``            -- the CLI (see :mod:`reconcile.__main__`).
"""

from __future__ import annotations
