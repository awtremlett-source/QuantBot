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

# --------------------------------------------------------------------------- #
# Paper-trading journal (execution layer). Append-only by law: the ONLY UPDATE
# ever allowed on these tables is an order's pending -> filled transition
# (paper_state is mutable working state, not journal). Every order/fill/equity
# row is a permanent audit record of what the paper book decided and when.
# --------------------------------------------------------------------------- #

# One row per DECISION that changed the target weight. decision_event_time is
# the completed bar the signal was computed on; the fill happens at the NEXT
# bar's open (same discipline the firewall validated). UNIQUE(ticker,
# decision_event_time) makes catch-up re-runs idempotent: a bar decides once.
PAPER_ORDERS = """
CREATE TABLE IF NOT EXISTS paper_orders (
    id                    INTEGER PRIMARY KEY,
    ticker                TEXT NOT NULL,
    decision_event_time   TEXT NOT NULL,
    target_weight         REAL NOT NULL,
    created_knowable_time TEXT NOT NULL,
    status                TEXT NOT NULL
        CHECK (status IN ('pending', 'filled', 'cancelled')),
    UNIQUE (ticker, decision_event_time)
)
"""

# One row per executed fill. fill_event_time is the bar whose OPEN filled the
# order; fill_price is that open +/- slippage; deltas record exactly how the
# book moved (audit: state must always equal the sum of its fills).
PAPER_FILLS = """
CREATE TABLE IF NOT EXISTS paper_fills (
    order_id        INTEGER NOT NULL REFERENCES paper_orders(id),
    fill_event_time TEXT NOT NULL,
    fill_price      REAL NOT NULL,
    shares_delta    REAL NOT NULL,
    cash_delta      REAL NOT NULL,
    knowable_time   TEXT NOT NULL
)
"""

# Singleton working state per ticker (mutable; NOT part of the journal).
# last_decided_event_time is the catch-up cursor: every completed bar after it
# still owes a decision.
PAPER_STATE = """
CREATE TABLE IF NOT EXISTS paper_state (
    ticker                  TEXT NOT NULL UNIQUE,
    shares                  REAL NOT NULL,
    cash                    REAL NOT NULL,
    last_decided_event_time TEXT NOT NULL
)
"""

# Mark-to-market equity at each processed bar's close (cash + shares * close).
# UNIQUE(ticker, event_time) keeps re-runs idempotent.
PAPER_EQUITY = """
CREATE TABLE IF NOT EXISTS paper_equity (
    ticker     TEXT NOT NULL,
    event_time TEXT NOT NULL,
    equity     REAL NOT NULL,
    close      REAL NOT NULL,
    UNIQUE (ticker, event_time)
)
"""

CREATE_TABLES: tuple[str, ...] = (
    PRICE_RAW,
    PRICE_CLEAN,
    SENTIMENT_RAW,
    SENTIMENT_CLEAN,
    QUARANTINE,
    CORPORATE_ACTIONS,
    PAPER_ORDERS,
    PAPER_FILLS,
    PAPER_STATE,
    PAPER_EQUITY,
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
    # paper_orders is polled for pending orders on every loop run.
    "CREATE INDEX IF NOT EXISTS idx_paper_orders_ticker_status "
    "ON paper_orders (ticker, status)",
    # paper_fills is joined back to its order for audit reads.
    "CREATE INDEX IF NOT EXISTS idx_paper_fills_order_id "
    "ON paper_fills (order_id)",
)

# Everything init_db needs to run, in order: tables first, then indexes.
ALL_STATEMENTS: tuple[str, ...] = CREATE_TABLES + CREATE_INDEXES
