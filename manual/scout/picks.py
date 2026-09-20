"""Pick history: the app's own accountability log.

Every day the boards are recorded to the database; afterwards each pick is
measured against the latest cached price. Over time this answers the question
the Journal can't: are the app's picks any good, independent of how you
traded them? For BUY picks a rise since pick is a good call; for SELL/AVOID
picks a fall since pick is a good call.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from .config import Config
from .store import Store

LONDON = ZoneInfo("Europe/London")


def record_board(store: Store, rows: list[dict], cfg: Config,
                 on_date: str | None = None) -> int:
    """Snapshot today's top-N buys and sells. Idempotent per day: re-scans on
    the same day simply refresh that day's record. Returns picks written."""
    if not rows:
        return 0
    date = on_date or datetime.now(LONDON).date().isoformat()
    written = 0
    for side, key in (("BUY", "buy"), ("SELL", "sell")):
        ranked = sorted(rows, key=lambda r: r[key].score, reverse=True)
        top = [r for r in ranked if r[key].score > 0][:cfg.top_n]
        picks = [{
            "ticker": r["ticker"], "name": r["name"],
            "score": r[key].score, "setup": r[key].setup,
            "px": r["snap"]["close"], "px_gbp": r["snap"]["close_gbp"],
        } for r in top]
        store.record_picks(date, side, picks)
        written += len(picks)
    return written


def performance(store: Store, picks: list[dict]) -> tuple[list[dict], dict]:
    """Enrich stored picks with latest price, % change since pick and bars
    elapsed. Returns (rows, aggregates)."""
    out: list[dict] = []
    for p in picks:
        row = dict(p)
        row["px_now"] = row["change_pct"] = row["bars_since"] = None
        df = store.get_prices(p["ticker"])
        if not df.empty and p.get("px"):
            last = float(df["close"].iloc[-1])
            row["px_now"] = last
            row["change_pct"] = (last - p["px"]) / p["px"] * 100.0
            row["bars_since"] = int((df.index > pd.Timestamp(p["date"])).sum())
        out.append(row)

    def _avg(side: str):
        vals = [r["change_pct"] for r in out
                if r["side"] == side and r["change_pct"] is not None]
        return sum(vals) / len(vals) if vals else None

    return out, {"buy_avg_pct": _avg("BUY"), "sell_avg_pct": _avg("SELL"),
                 "n": len(out)}
