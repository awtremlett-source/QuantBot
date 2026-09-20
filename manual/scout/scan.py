"""Scan the cached universe and produce board rows; derive exit flags for
open positions. Pure cache reads -- no network anywhere in this module."""
from __future__ import annotations

from .config import Config
from .indicators import MIN_BARS, snapshot
from .scoring import buy_score, sell_score
from .store import Store


def scan_universe(store: Store, universe_rows: list[dict], cfg: Config,
                  progress_cb=None) -> list[dict]:
    """Return one dict per scoreable ticker:
    {ticker, name, sector, index, stamp_duty, snap, buy, sell}."""
    rows: list[dict] = []
    total = len(universe_rows)
    for i, u in enumerate(universe_rows, start=1):
        if progress_cb and (i % 25 == 0 or i == total):
            progress_cb(i, total, f"Scoring {u['ticker']}")
        df = store.get_prices(u["ticker"])
        if len(df) < MIN_BARS:
            continue
        snap = snapshot(df, u.get("currency", "GBp"))
        if snap is None:
            continue
        rows.append({
            "ticker": u["ticker"], "name": u["name"],
            "sector": u.get("sector", ""), "index": u.get("index", ""),
            "stamp_duty": u.get("stamp_duty", "Y"),
            "snap": snap,
            "buy": buy_score(snap, cfg),
            "sell": sell_score(snap, cfg),
        })
    return rows


def exit_flags(snap: dict, trade: dict, atr_trail_mult: float = 2.0) -> list[str]:
    """Plain-English reasons to consider closing an open long."""
    flags: list[str] = []
    close = snap.get("close_gbp")
    stop = trade.get("stop_px")
    if close is not None and stop is not None and close <= stop:
        flags.append("STOP BREACHED")
    sma50 = snap.get("sma50")
    if sma50 is not None and snap.get("close") is not None \
            and snap["close"] < sma50:
        flags.append("Below 50-day")
    rsi = snap.get("rsi")
    if rsi is not None and rsi > 75:
        flags.append(f"RSI {rsi:.0f} \u2014 stretched")
    if (snap.get("macd_hist") is not None
            and snap.get("macd_hist_delta") is not None
            and snap["macd_hist"] < 0 and snap["macd_hist_delta"] < 0):
        flags.append("MACD rolled negative")
    atr_gbp = snap.get("atr_gbp")
    if close is not None and atr_gbp and stop is not None:
        trail = close - atr_trail_mult * atr_gbp
        if trail > stop:
            flags.append(f"Trail stop up to \u00a3{trail:,.2f}")
    return flags


VERDICT_ORDER = {"SELL OUT": 0, "BEWARE": 1, "HOLD": 2}


def position_verdict(snap: dict, trade: dict,
                     sell_score_val: int | None = None) -> dict:
    """One clear instruction per holding: HOLD, BEWARE or SELL OUT,
    with the reason in plain words and any tips underneath."""
    flags = exit_flags(snap, trade)
    trail_tips = [f for f in flags if f.startswith("Trail stop")]
    warnings = [f for f in flags if not f.startswith("Trail stop")]

    if any("STOP BREACHED" in f for f in warnings):
        verdict = "SELL OUT"
        headline = ("Price has fallen to your sell alert \u2014 "
                    "time to sell.")
    elif sell_score_val is not None and sell_score_val >= 65:
        verdict = "SELL OUT"
        headline = ("This stock now looks weak on most measures \u2014 "
                    "consider selling.")
    elif warnings or (sell_score_val or 0) >= 45:
        verdict = "BEWARE"
        first = warnings[0] if warnings else ""
        if "Below 50-day" in first:
            headline = ("Slipped below its 50-day average \u2014 "
                        "an early warning sign.")
        elif "stretched" in first:
            headline = ("It has run hot \u2014 pullbacks are common "
                        "from here.")
        elif "MACD" in first:
            headline = "Its momentum has rolled over \u2014 watch it."
        else:
            headline = "Some weakness showing \u2014 keep an eye on it."
    else:
        verdict = "HOLD"
        headline = "Trend intact \u2014 nothing to do."

    details = []
    for tip in trail_tips:
        level = tip.split("to ", 1)[-1]
        details.append(f"Tip: you could raise your sell alert to {level} "
                       "to lock in more.")
    details += [w for w in warnings[1:]]
    return {"verdict": verdict, "headline": headline, "details": details}
