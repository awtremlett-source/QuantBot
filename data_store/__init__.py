"""data_store: the QuantBot data layer's SQLite (WAL) system-of-record.

Two layers per data kind live here:

* ``*_raw``   -- what a source gave us, verbatim (one row per source).
* ``*_clean`` -- the single reconciled series the rest of the system reads.

This package is the *only* write path to the store (the single-writer law):
all inserts go through :mod:`data_store.store`, all inserts are idempotent, and
all reads are point-in-time (they never return data before it was knowable).

Import the API from the submodules, e.g.::

    from data_store import store
    from data_store.store import PriceClean
"""

from __future__ import annotations
