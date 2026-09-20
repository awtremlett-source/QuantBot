"""Paper-trade journal: the learning loop.

R-multiple = (exit - entry) / (entry - stop). Expectancy is the average R
across closed trades -- the single number that says whether the process is
working. All money values are pounds.
"""
from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from .store import Store

LONDON = ZoneInfo("Europe/London")


def _now() -> str:
    return datetime.now(LONDON).strftime("%Y-%m-%d %H:%M")


def open_trade(store: Store, *, ticker: str, name: str, entry_px: float,
               stop_px: float, shares: float, risk_gbp: float,
               open_costs_gbp: float, setup_type: str, thesis: str,
               checklist: dict | None = None) -> int:
    return store.insert_trade(
        opened_at=_now(), ticker=ticker, name=name, direction="LONG",
        entry_px=entry_px, stop_px=stop_px, shares=shares, risk_gbp=risk_gbp,
        open_costs_gbp=open_costs_gbp, setup_type=setup_type or "\u2014",
        thesis=thesis, checklist_json=json.dumps(checklist or {}))


def close_trade(store: Store, trade_id: int, *, exit_px: float,
                exit_reason: str, lessons: str = "") -> dict:
    trade = store.get_trade(trade_id)
    if trade is None:
        raise ValueError(f"No trade with id {trade_id}")
    if trade.get("closed_at"):
        raise ValueError(f"Trade {trade_id} already closed")
    entry, stop = trade["entry_px"], trade["stop_px"]
    shares = trade["shares"]
    pnl = shares * (exit_px - entry) - (trade.get("open_costs_gbp") or 0.0)
    denom = entry - stop
    r_multiple = (exit_px - entry) / denom if denom > 0 else None
    store.update_trade(trade_id, closed_at=_now(), exit_px=exit_px,
                       exit_reason=exit_reason, pnl_gbp=pnl,
                       r_multiple=r_multiple, lessons=lessons)
    return store.get_trade(trade_id)


def stats(trades: list[dict]) -> dict:
    closed = [t for t in trades if t.get("closed_at")]
    n = len(closed)
    if n == 0:
        return {"count": 0, "wins": 0, "win_rate": 0.0, "avg_r": None,
                "expectancy_r": None, "total_pnl_gbp": 0.0, "by_setup": {}}
    wins = sum(1 for t in closed if (t.get("pnl_gbp") or 0) > 0)
    rs = [t["r_multiple"] for t in closed if t.get("r_multiple") is not None]
    avg_r = sum(rs) / len(rs) if rs else None
    total_pnl = sum(t.get("pnl_gbp") or 0.0 for t in closed)

    by_setup: dict[str, dict] = {}
    for t in closed:
        key = t.get("setup_type") or "\u2014"
        b = by_setup.setdefault(key, {"count": 0, "wins": 0, "rs": []})
        b["count"] += 1
        if (t.get("pnl_gbp") or 0) > 0:
            b["wins"] += 1
        if t.get("r_multiple") is not None:
            b["rs"].append(t["r_multiple"])
    for key, b in by_setup.items():
        b["win_rate"] = b["wins"] / b["count"] * 100.0
        b["avg_r"] = sum(b["rs"]) / len(b["rs"]) if b["rs"] else None
        del b["rs"]

    return {"count": n, "wins": wins, "win_rate": wins / n * 100.0,
            "avg_r": avg_r, "expectancy_r": avg_r,
            "total_pnl_gbp": total_pnl, "by_setup": by_setup}
