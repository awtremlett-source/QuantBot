"""Risk box: turn a snapshot into a concrete paper-trade plan in pounds.

Stop  = close - atr_stop_mult x ATR (both in GBP).
Shares = floor(bankroll x risk% / risk-per-share).
Costs = stamp duty (if flagged 'Y' in the universe) + PTM levy above the
threshold. Cost rates live in config.json -- verify current rates yourself.
"""
from __future__ import annotations

import math

from .config import Config


def plan(snap: dict, cfg: Config, stamp_duty_flag: str = "Y",
         max_value_gbp: float | None = None) -> dict:
    close = snap.get("close_gbp")
    atr = snap.get("atr_gbp")
    if close is None or atr is None:
        return {"ok": False, "why": "Not a sterling quote \u2014 sizing unavailable"}
    if atr <= 0:
        return {"ok": False, "why": "ATR is zero \u2014 cannot place a stop"}

    stop = close - cfg.atr_stop_mult * atr
    if stop <= 0:
        return {"ok": False,
                "why": "ATR stop lands below zero \u2014 too volatile to size"}

    risk_per_share = close - stop
    risk_budget = cfg.bankroll_gbp * cfg.risk_pct / 100.0
    shares = math.floor(risk_budget / risk_per_share)
    if shares < 1:
        return {"ok": False,
                "why": "Risk per share exceeds the whole risk budget"}

    ladder_capped = False
    if max_value_gbp is not None and shares * close > max_value_gbp:
        shares = math.floor(max_value_gbp / close)
        ladder_capped = True
        if shares < 1:
            return {"ok": False,
                    "why": "Your 50% money-ladder slot is too small for "
                           "even one share of this — bank something "
                           "or pick a cheaper stock."}
    value = shares * close
    stamp = value * cfg.stamp_duty_pct / 100.0 if stamp_duty_flag == "Y" else 0.0
    ptm = cfg.ptm_levy_gbp if value > cfg.ptm_threshold_gbp else 0.0
    costs = stamp + ptm
    pct_bankroll = value / cfg.bankroll_gbp * 100.0 if cfg.bankroll_gbp else 0.0

    warnings = []
    if ladder_capped:
        warnings.append(f"Size capped by your 50% money ladder "
                        f"(this slot: £{max_value_gbp:,.0f}).")
    if pct_bankroll > 20.0:
        warnings.append(f"Position is {pct_bankroll:.0f}% of bankroll "
                        "\u2014 concentrated for a single name")

    return {
        "ok": True,
        "entry_gbp": close,
        "stop_gbp": stop,
        "risk_per_share_gbp": risk_per_share,
        "shares": shares,
        "value_gbp": value,
        "risk_gbp": shares * risk_per_share,
        "stamp_gbp": stamp,
        "ptm_gbp": ptm,
        "costs_gbp": costs,
        "breakeven_pct": (costs / value * 100.0) if value else 0.0,
        "pct_bankroll": pct_bankroll,
        "warnings": warnings,
    }
