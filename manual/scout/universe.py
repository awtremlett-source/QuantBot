"""Universe handling: the list of LSE names TradeScout scans.

Shipped as manual/assets/universe.csv (best-effort FTSE 100 + 250 snapshot).
Index constituents drift over time -- the CSV is yours to edit, and the app's
"Add ticker" validates new entries with a single yfinance probe. Cross-check
availability inside Trading 212 before trading anything on paper.
"""
from __future__ import annotations

import csv
from pathlib import Path

from .config import PACKAGE_ROOT

# Shipped WITH the package (manual/assets/), not under the repo's data/:
# that folder is the engine's and the manual app must not reach into it.
UNIVERSE_PATH = PACKAGE_ROOT / "assets" / "universe.csv"
REQUIRED_COLUMNS = ["ticker", "name", "index", "sector", "currency", "stamp_duty"]
INDEX_TICKERS = {"^FTSE": "FTSE 100", "^FTMC": "FTSE 250"}


class UniverseError(Exception):
    pass


def load_universe(path: Path | None = None) -> list[dict]:
    path = path or UNIVERSE_PATH
    if not path.exists():
        raise UniverseError(f"Universe file not found: {path}")
    rows: list[dict] = []
    seen: set[str] = set()
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise UniverseError(f"Universe CSV missing columns: {missing}")
        for raw in reader:
            ticker = (raw.get("ticker") or "").strip().upper()
            if not ticker or ticker in seen:
                continue
            seen.add(ticker)
            rows.append({
                "ticker": ticker,
                "name": (raw.get("name") or ticker).strip(),
                "index": (raw.get("index") or "").strip(),
                "sector": (raw.get("sector") or "Unknown").strip(),
                "currency": (raw.get("currency") or "GBp").strip(),
                "stamp_duty": (raw.get("stamp_duty") or "Y").strip().upper(),
            })
    if not rows:
        raise UniverseError("Universe CSV contains no tickers")
    return rows


def universe_tickers(rows: list[dict]) -> list[str]:
    return [r["ticker"] for r in rows]


def row_for(rows: list[dict], ticker: str) -> dict | None:
    for r in rows:
        if r["ticker"] == ticker:
            return r
    return None


def append_ticker(entry: dict, path: Path | None = None) -> None:
    """Append a validated entry to the CSV (caller validates via yfinance)."""
    path = path or UNIVERSE_PATH
    existing = {r["ticker"] for r in load_universe(path)}
    ticker = entry["ticker"].strip().upper()
    if ticker in existing:
        raise UniverseError(f"{ticker} already in universe")
    with open(path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=REQUIRED_COLUMNS)
        writer.writerow({
            "ticker": ticker,
            "name": entry.get("name", ticker),
            "index": entry.get("index", "Custom"),
            "sector": entry.get("sector", "Unknown"),
            "currency": entry.get("currency", "GBp"),
            "stamp_duty": entry.get("stamp_duty", "Y"),
        })


def probe_ticker(ticker: str) -> dict:
    """One polite yfinance probe used by the Add-ticker dialog. Network call --
    only ever triggered by an explicit user action, never in a scan loop."""
    import yfinance as yf  # local import: keeps module importable offline
    t = yf.Ticker(ticker)
    fi = t.fast_info
    currency = getattr(fi, "currency", None) or "GBp"
    price = getattr(fi, "last_price", None)
    if price is None:
        raise UniverseError(f"No price data returned for {ticker}")
    return {"ticker": ticker.upper(), "currency": currency,
            "name": ticker.upper(), "index": "Custom",
            "sector": "Unknown", "stamp_duty": "Y"}
