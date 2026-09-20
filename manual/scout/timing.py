"""Timing Dial: is today a good or bad day to be putting on new trades?

Four checks, each worth 25 points, each explainable in one sentence:

  Trend   -- are the FTSE 100 and FTSE 250 themselves in uptrends?
  Breadth -- what share of the whole universe is above its 200-day average?
  Fear    -- is the VIX calm, jumpy, or in a storm?
  Flow    -- is money chasing cyclicals (risk-on) or hiding in defensives?

Checks with no data are excluded and the score is rescaled, so a missing
VIX never silently drags the dial down. The final state is asymmetric on
purpose (an old ATLAS rule): it takes three straight qualifying days to
UPGRADE the dial, but a bad day DOWNGRADES it immediately.
"""
from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from .config import Config
from .context import classify_index
from .store import Store

LONDON = ZoneInfo("Europe/London")
VIX_TICKER = "^VIX"
EXTRA_TICKERS = [VIX_TICKER]

STATES = ("ROUGH", "MIXED", "GOOD")
RANK = {s: i for i, s in enumerate(STATES)}
COLOURS = {"GOOD": "#3fb950", "MIXED": "#d29922", "ROUGH": "#f85149"}
GUIDANCE = {
    "GOOD": "Tide is with you \u2014 buying setups deserve normal size.",
    "MIXED": "Be picky \u2014 fewer trades, favour the strongest names only.",
    "ROUGH": "Mostly stand aside \u2014 protect what you hold, tiny size if "
             "you must.",
}

CYCLICAL_SECTORS = {"Banks", "Mining", "Housebuilders", "Retail",
                    "Airlines", "Travel & Leisure", "Construction",
                    "Luxury Goods", "Recruitment", "Automotive"}
DEFENSIVE_SECTORS = {"Utilities", "Pharmaceuticals", "Tobacco",
                     "Food Retail", "Consumer Health", "Beverages",
                     "Gold ETC", "Food Producers"}


def _check(name: str, points: int | None, line: str) -> dict:
    """points: 25 good / 12 middling / 0 bad / None = no data (excluded)."""
    glyph = {25: "\u2713", 12: "\u26a0", 0: "\u2717", None: "\u2013"}[points]
    return {"name": name, "points": points, "line": line, "glyph": glyph}


def timing_checks(store: Store, rows: list[dict],
                  cfg: Config) -> list[dict]:
    checks: list[dict] = []

    # ---- Trend: the indexes themselves ----
    states = {label: classify_index(store.get_prices(t))
              for t, label in (("^FTSE", "FTSE 100"), ("^FTMC", "FTSE 250"))}
    on = sum(1 for v in states.values() if v == "Risk-On")
    off = sum(1 for v in states.values() if v == "Risk-Off")
    detail = ", ".join(f"{k} {v.lower()}" for k, v in states.items())
    if on == 2:
        checks.append(_check("Trend", 25, f"Both indexes in uptrends "
                                          f"({detail})."))
    elif off == 2:
        checks.append(_check("Trend", 0, f"Both indexes in downtrends "
                                         f"({detail})."))
    else:
        checks.append(_check("Trend", 12, f"Indexes mixed ({detail})."))

    # ---- Breadth: share of the universe above its 200-day ----
    counted = above = 0
    for r in rows:
        snap = r["snap"]
        if snap.get("sma200") is not None:
            counted += 1
            if snap["close"] > snap["sma200"]:
                above += 1
    if counted >= 50:
        pct = above / counted * 100
        line = (f"{pct:.0f}% of stocks are above their 200-day average "
                f"({above} of {counted}).")
        checks.append(_check("Breadth", 25 if pct > 60 else
                             (12 if pct >= 40 else 0), line))
    else:
        checks.append(_check("Breadth", None,
                             "Not enough scored stocks yet to judge "
                             "breadth."))

    # ---- Fear: the VIX ----
    vix = store.get_prices(VIX_TICKER)
    if len(vix) >= 11:
        level = float(vix["close"].iloc[-1])
        ago = float(vix["close"].iloc[-11])
        rising = ago > 0 and (level / ago - 1) > 0.20
        if level > 28:
            checks.append(_check("Fear", 0,
                                 f"VIX {level:.0f} \u2014 storm conditions."))
        elif level >= 20 or rising:
            why = "and climbing fast" if rising and level < 20 else "jumpy"
            checks.append(_check("Fear", 12, f"VIX {level:.0f} \u2014 {why}."))
        else:
            checks.append(_check("Fear", 25, f"VIX {level:.0f} \u2014 calm."))
    else:
        checks.append(_check("Fear", None,
                             "No VIX data cached yet \u2014 update prices."))

    # ---- Flow: cyclicals vs defensives over 3 months ----
    def _avg_roc(sectors: set[str]) -> tuple[float | None, int]:
        vals = [r["snap"]["roc63"] for r in rows
                if r.get("sector") in sectors
                and r["snap"].get("roc63") is not None]
        return (sum(vals) / len(vals), len(vals)) if vals else (None, 0)

    cyc, n_cyc = _avg_roc(CYCLICAL_SECTORS)
    dfn, n_dfn = _avg_roc(DEFENSIVE_SECTORS)
    if cyc is not None and dfn is not None and n_cyc >= 5 and n_dfn >= 5:
        gap = cyc - dfn
        if gap > 2:
            checks.append(_check("Flow", 25,
                                 f"Money is chasing growth \u2014 cyclicals "
                                 f"beating defensives by {gap:.1f}% over "
                                 f"3 months."))
        elif gap < -2:
            checks.append(_check("Flow", 0,
                                 f"Money is hiding \u2014 defensives beating "
                                 f"cyclicals by {abs(gap):.1f}% over "
                                 f"3 months."))
        else:
            checks.append(_check("Flow", 12,
                                 "No clear leader between cyclicals and "
                                 "defensives."))
    else:
        checks.append(_check("Flow", None,
                             "Not enough sector data yet to judge flows."))
    return checks


def _raw_state(score: int) -> str:
    if score >= 70:
        return "GOOD"
    if score >= 40:
        return "MIXED"
    return "ROUGH"


def _apply_persistence(store: Store, raw: str, on_date: str) -> str:
    """Downgrade instantly; upgrade only after 3 straight qualifying days."""
    history = json.loads(store.get_setting("timing_history") or "[]")
    history = [h for h in history if h["date"] != on_date]
    history.append({"date": on_date, "raw": raw})
    history = history[-5:]
    store.set_setting("timing_history", json.dumps(history))

    effective = store.get_setting("timing_effective")
    if effective not in STATES:
        effective = raw                      # first ever run adopts raw
    elif RANK[raw] <= RANK[effective]:
        effective = raw                      # same or worse: apply now
    else:
        recent = history[-3:]
        if (len(recent) == 3
                and all(RANK[h["raw"]] >= RANK[raw] for h in recent)):
            effective = raw                  # 3 straight days earn the upgrade
    store.set_setting("timing_effective", effective)
    return effective


def timing_dial(store: Store, rows: list[dict], cfg: Config,
                on_date: str | None = None) -> dict:
    on_date = on_date or datetime.now(LONDON).date().isoformat()
    checks = timing_checks(store, rows, cfg)
    scored = [c for c in checks if c["points"] is not None]
    max_pts = 25 * len(scored)
    score = int(round(sum(c["points"] for c in scored) / max_pts * 100)) \
        if max_pts else 50
    raw = _raw_state(score)
    effective = _apply_persistence(store, raw, on_date)
    pending = ""
    if RANK[raw] > RANK[effective]:
        pending = (" (looking better \u2014 needs a couple more days like "
                   "this before the dial upgrades)")
    return {"score": score, "state": effective, "raw_state": raw,
            "colour": COLOURS[effective],
            "guidance": GUIDANCE[effective] + pending,
            "checks": checks}
