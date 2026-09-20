"""SQLite storage for TradeScout. All state lives under data/manual/."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import STATE_DIR

# The manual app's OWN database. It never opens the engine's
# data/quantbot.db -- the one read-only doorway is manual/bot_readonly.py.
DEFAULT_DB_PATH = STATE_DIR / "trade_scout.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    ticker TEXT NOT NULL,
    date   TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL, volume REAL,
    PRIMARY KEY (ticker, date)
);
CREATE TABLE IF NOT EXISTS meta (
    ticker TEXT PRIMARY KEY,
    payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS watchlist (
    ticker TEXT PRIMARY KEY,
    added_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opened_at TEXT NOT NULL,
    ticker TEXT NOT NULL,
    name TEXT,
    direction TEXT NOT NULL DEFAULT 'LONG',
    entry_px REAL NOT NULL,
    stop_px REAL NOT NULL,
    shares REAL NOT NULL,
    risk_gbp REAL,
    open_costs_gbp REAL DEFAULT 0,
    setup_type TEXT,
    thesis TEXT,
    checklist_json TEXT,
    closed_at TEXT,
    exit_px REAL,
    exit_reason TEXT,
    pnl_gbp REAL,
    r_multiple REAL,
    lessons TEXT
);
CREATE TABLE IF NOT EXISTS picks (
    date TEXT NOT NULL,
    side TEXT NOT NULL,
    rank INTEGER NOT NULL,
    ticker TEXT NOT NULL,
    name TEXT,
    score INTEGER,
    setup TEXT,
    px REAL,
    px_gbp REAL,
    PRIMARY KEY (date, side, rank)
);
"""


class Store:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # One connection shared across the GUI thread and worker
        # threads; every access below is serialised by _lock.
        self.conn = sqlite3.connect(str(self.db_path),
                                    check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        with self._lock:
            self.conn.close()

        # ---------------- prices ----------------
    def upsert_prices(self, ticker: str, df: pd.DataFrame) -> int:
        """Insert-or-replace daily bars. Index must be datetime-like; columns
        open/high/low/close/volume (lowercase). Returns rows written."""
        with self._lock:
            if df is None or df.empty:
                return 0
            rows = []
            for idx, row in df.iterrows():
                date = pd.Timestamp(idx).strftime("%Y-%m-%d")
                close = row.get("close")
                if close is None or pd.isna(close):
                    continue
                rows.append((
                    ticker, date,
                    _num(row.get("open")), _num(row.get("high")),
                    _num(row.get("low")), _num(close), _num(row.get("volume")),
                ))
            if not rows:
                return 0
            self.conn.executemany(
                "INSERT OR REPLACE INTO prices (ticker,date,open,high,low,close,volume) "
                "VALUES (?,?,?,?,?,?,?)", rows)
            self.conn.commit()
            return len(rows)

    def get_prices(self, ticker: str) -> pd.DataFrame:
        with self._lock:
            cur = self.conn.execute(
                "SELECT date,open,high,low,close,volume FROM prices "
                "WHERE ticker=? ORDER BY date", (ticker,))
            recs = cur.fetchall()
            if not recs:
                return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
            df = pd.DataFrame([dict(r) for r in recs])
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
            return df[["open", "high", "low", "close", "volume"]].astype(float)

    def last_date(self, ticker: str) -> str | None:
        with self._lock:
            cur = self.conn.execute(
                "SELECT MAX(date) AS d FROM prices WHERE ticker=?", (ticker,))
            row = cur.fetchone()
            return row["d"] if row and row["d"] else None

    def bar_count(self, ticker: str) -> int:
        with self._lock:
            cur = self.conn.execute(
                "SELECT COUNT(*) AS n FROM prices WHERE ticker=?", (ticker,))
            return int(cur.fetchone()["n"])

    def tickers_with_data(self) -> list[str]:
        with self._lock:
            cur = self.conn.execute("SELECT DISTINCT ticker FROM prices")
            return [r["ticker"] for r in cur.fetchall()]

        # ---------------- meta / settings ----------------
    def set_meta(self, ticker: str, **kwargs) -> None:
        with self._lock:
            payload = self.get_meta(ticker)
            payload.update(kwargs)
            self.conn.execute(
                "INSERT OR REPLACE INTO meta (ticker,payload) VALUES (?,?)",
                (ticker, json.dumps(payload)))
            self.conn.commit()

    def get_meta(self, ticker: str) -> dict:
        with self._lock:
            cur = self.conn.execute("SELECT payload FROM meta WHERE ticker=?", (ticker,))
            row = cur.fetchone()
            return json.loads(row["payload"]) if row else {}

    def set_setting(self, key: str, value: str) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)", (key, value))
            self.conn.commit()

    def get_setting(self, key: str) -> str | None:
        with self._lock:
            cur = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,))
            row = cur.fetchone()
            return row["value"] if row else None

        # ---------------- watchlist ----------------
    def watchlist(self) -> list[str]:
        with self._lock:
            cur = self.conn.execute("SELECT ticker FROM watchlist ORDER BY ticker")
            return [r["ticker"] for r in cur.fetchall()]

    def watch(self, ticker: str, on: bool) -> None:
        with self._lock:
            if on:
                self.conn.execute(
                    "INSERT OR IGNORE INTO watchlist (ticker,added_at) VALUES (?,?)",
                    (ticker, _now()))
            else:
                self.conn.execute("DELETE FROM watchlist WHERE ticker=?", (ticker,))
            self.conn.commit()

        # ---------------- pick history ----------------
    def record_picks(self, date: str, side: str, picks: list[dict]) -> None:
        """Overwrite the recorded board for (date, side) -- idempotent."""
        with self._lock:
            self.conn.execute(
                "DELETE FROM picks WHERE date=? AND side=?", (date, side))
            self.conn.executemany(
                "INSERT INTO picks "
                "(date,side,rank,ticker,name,score,setup,px,px_gbp) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                [(date, side, i + 1, p["ticker"], p.get("name"),
                  p.get("score"), p.get("setup"), p.get("px"),
                  p.get("px_gbp")) for i, p in enumerate(picks)])
            self.conn.commit()

    def list_picks(self, limit: int = 600) -> list[dict]:
        with self._lock:
            cur = self.conn.execute(
                "SELECT * FROM picks ORDER BY date DESC, side ASC, rank ASC"
                " LIMIT ?", (limit,))
            return [dict(r) for r in cur.fetchall()]

    # ---------------- trades ----------------
    def insert_trade(self, **fields) -> int:
        with self._lock:
            cols = ",".join(fields)
            marks = ",".join("?" for _ in fields)
            cur = self.conn.execute(
                f"INSERT INTO trades ({cols}) VALUES ({marks})", tuple(fields.values()))
            self.conn.commit()
            return int(cur.lastrowid)

    def update_trade(self, trade_id: int, **fields) -> None:
        with self._lock:
            assign = ",".join(f"{k}=?" for k in fields)
            self.conn.execute(
                f"UPDATE trades SET {assign} WHERE id=?", (*fields.values(), trade_id))
            self.conn.commit()

    def get_trade(self, trade_id: int) -> dict | None:
        with self._lock:
            cur = self.conn.execute("SELECT * FROM trades WHERE id=?", (trade_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def delete_trade(self, trade_id: int) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM trades WHERE id=?", (trade_id,))
            self.conn.commit()

    def list_trades(self, open_only: bool = False) -> list[dict]:
        with self._lock:
            q = "SELECT * FROM trades"
            if open_only:
                q += " WHERE closed_at IS NULL"
            q += " ORDER BY opened_at DESC, id DESC"
            return [dict(r) for r in self.conn.execute(q).fetchall()]


def _num(v):
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(f) else f


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
