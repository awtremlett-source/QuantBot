"""SQLite DDL for the data store: RAW and CLEAN tables plus their indexes.

Two layers per data kind:

* ``*_raw``   -- exactly what a source delivered (one row *per source*), so we
  can always re-derive CLEAN and audit where a number came from.
* ``*_clean`` -- the single reconciled series the rest of the system reads.

Every row carries two timestamps (both canonical UTC ISO-8601 text):

* ``event_time``    -- when the thing happened (the bar's session; the metric's
  reference moment).
* ``knowable_time`` -- the earliest moment we could legitimately have KNOWN the
  value. Point-in-time reads filter on this to prevent lookahead bias (using
  data before it existed).

Daily bars today -- and the schema needs NO change for intraday, because
``event_time`` is a full UTC timestamp rather than a date. A 1-minute bar is
simply a finer ``event_time``; the same tables and indexes serve it unchanged.
"""

from __future__ import annotations

PRICE_RAW = """
CREATE TABLE IF NOT EXISTS price_raw (
    ticker        TEXT    NOT NULL,
    event_time    TEXT    NOT NULL,
    open          REAL    NOT NULL,
    high          REAL    NOT NULL,
    low           REAL    NOT NULL,
    close         REAL    NOT NULL,
    volume        INTEGER NOT NULL,
    knowable_time TEXT    NOT NULL,
    source        TEXT    NOT NULL,
    UNIQUE (ticker, event_time, source)
)
"""

PRICE_CLEAN = """
CREATE TABLE IF NOT EXISTS price_clean (
    ticker        TEXT    NOT NULL,
    event_time    TEXT    NOT NULL,
    open          REAL    NOT NULL,
    high          REAL    NOT NULL,
    low           REAL    NOT NULL,
    close         REAL    NOT NULL,
    volume        INTEGER NOT NULL,
    adj_close     REAL    NOT NULL,
    knowable_time TEXT    NOT NULL,
    source        TEXT    NOT NULL,
    UNIQUE (ticker, event_time)
)
"""

SENTIMENT_RAW = """
CREATE TABLE IF NOT EXISTS sentiment_raw (
    ticker        TEXT NOT NULL,
    event_time    TEXT NOT NULL,
    metric        TEXT NOT NULL,
    value         REAL NOT NULL,
    knowable_time TEXT NOT NULL,
    source        TEXT NOT NULL,
    UNIQUE (ticker, event_time, metric, source)
)
"""

SENTIMENT_CLEAN = """
CREATE TABLE IF NOT EXISTS sentiment_clean (
    ticker        TEXT NOT NULL,
    event_time    TEXT NOT NULL,
    metric        TEXT NOT NULL,
    value         REAL NOT NULL,
    knowable_time TEXT NOT NULL,
    source        TEXT NOT NULL,
    UNIQUE (ticker, event_time, metric)
)
"""

# Append-only incident log for rows rejected at a write boundary (the "front
# door"). Quarantine, never delete: a rejected row is preserved here verbatim
# (as JSON in ``payload``) with a specific ``reason``, so nothing is silently
# dropped and every rejection is auditable. ``event_time`` is nullable because a
# row may be rejected precisely because its event_time was missing/unparseable.
QUARANTINE = """
CREATE TABLE IF NOT EXISTS quarantine (
    domain        TEXT NOT NULL,
    ticker        TEXT NOT NULL,
    event_time    TEXT,
    payload       TEXT NOT NULL,
    reason        TEXT NOT NULL,
    knowable_time TEXT NOT NULL
)
"""

# Reference table of corporate actions (splits, dividends) used by the RAW->CLEAN
# reconciliation to adjust the price series. Not a RAW/CLEAN price layer itself:
# it is the small, separately-sourced fact set the cleaner reads alongside
# ``price_raw`` to derive ``price_clean``. ``value`` is overloaded by
# ``action_type`` -- a split ratio (e.g. 10.0 for 10-for-1) or a cash dividend
# amount. UNIQUE keeps it idempotent across re-fetches of the same action.
CORPORATE_ACTIONS = """
CREATE TABLE IF NOT EXISTS corporate_actions (
    ticker        TEXT NOT NULL,
    event_time    TEXT NOT NULL,
    action_type   TEXT NOT NULL,
    value         REAL NOT NULL,
    knowable_time TEXT NOT NULL,
    source        TEXT NOT NULL,
    UNIQUE (ticker, event_time, action_type, source)
)
"""

CREATE_TABLES: tuple[str, ...] = (
    PRICE_RAW,
    PRICE_CLEAN,
    SENTIMENT_RAW,
    SENTIMENT_CLEAN,
    QUARANTINE,
    CORPORATE_ACTIONS,
)

# The four tables, by name, for index generation.
_TABLE_NAMES: tuple[str, ...] = (
    "price_raw",
    "price_clean",
    "sentiment_raw",
    "sentiment_clean",
)

# Every table gets the same two access patterns indexed:
#   (ticker, event_time)    -- "the series for X over a window"
#   (ticker, knowable_time) -- "what was knowable about X as of T" (point-in-time)
# (On CLEAN tables the (ticker, event_time) index overlaps the UNIQUE constraint;
# we create it explicitly anyway so every table is indexed identically.)
CREATE_INDEXES: tuple[str, ...] = tuple(
    f"CREATE INDEX IF NOT EXISTS idx_{table}_{column} "
    f"ON {table} (ticker, {column})"
    for table in _TABLE_NAMES
    for column in ("event_time", "knowable_time")
) + (
    # quarantine is keyed differently (domain + ticker), so it indexes separately.
    "CREATE INDEX IF NOT EXISTS idx_quarantine_domain_ticker "
    "ON quarantine (domain, ticker)",
    # corporate_actions is read by (ticker, event_time) when adjusting a series.
    "CREATE INDEX IF NOT EXISTS idx_corporate_actions_ticker_event_time "
    "ON corporate_actions (ticker, event_time)",
)

# Everything init_db needs to run, in order: tables first, then indexes.
ALL_STATEMENTS: tuple[str, ...] = CREATE_TABLES + CREATE_INDEXES
