"""How a 3 x ATR stop would have behaved on the advisor list (QT-16 C2). DESCRIPTION ONLY.

**Choosing k from this table would be a TRIAL.** A multiple picked because it
looked best on these bars is fitted to them; it would have to be pre-registered,
counted in the trial log and judged out of sample like any other candidate. So
nothing here chooses anything: k stays 3, the starting figure (qb2/guard/stops.py).

QT-17 A1: the QT-16 version read the clean store's daily bars itself and so READ
THE SEALED YEAR (from 2025-10-10): "sealed daily year viewed for the stop
description, 2026-10-12, no parameter chosen" (SCARS #25, trial log). Its page is
kept, marked superseded. This version reads through the holdout door: UNSEALED
daily bars only (to 2025-10-09). Any future choice of stop k must not use the
sealed year either.

Method, fixed before the run. Every advisor name, its unsealed daily bars. An entry at every 21st close (monthly, so entries rarely
overlap); the stop at entry - 3 x Wilder ATR(14) that day, trailed each day to
max(old, close - 3 x ATR) and never lowered; watched for up to 63 trading days.
Triggered: a day's LOW at or below the stop. Then the move from the stop level to
the close 20 trading days later: above zero, the price came back (the stop sold a
dip); below zero, it kept falling (the stop saved money).

CLI: ``python -m qb2.research.stop_description``
"""

from __future__ import annotations

import math
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from qb2.data import access, universe
from qb2.guard import stops
from qb2.research import holdout
from qb2.signals.indicators import atr_wilder

EVERY, WATCH, AFTER = 21, 63, 20
REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET = REPO_ROOT / "docs" / "research" / "stop_description_2026-10.md"
SUPERSEDED = REPO_ROOT / "docs" / "research" / "stop_description_2026-10_SUPERSEDED_sealed_year.md"


@dataclass(frozen=True, slots=True)
class Outcome:
    symbol: str
    distance: float               # stop distance at entry, as a share of the price
    stopped: bool
    days: int | None
    after: float | None           # stop level -> close 20 days later


def walk(bars: pd.DataFrame, symbol: str, k: float = stops.STOP_K) -> list[Outcome]:
    atr = atr_wilder(bars, stops.ATR_PERIOD).to_numpy(dtype=float)
    close, low = bars["close"].to_numpy(dtype=float), bars["low"].to_numpy(dtype=float)
    out = []
    for start in range(stops.ATR_PERIOD, len(bars) - 1, EVERY):
        level = close[start] - k * atr[start]
        if not math.isfinite(level) or level <= 0:
            continue
        hit = None
        for day in range(start + 1, min(start + 1 + WATCH, len(bars))):
            if low[day] <= level:
                hit = day
                break
            level = max(level, close[day] - k * atr[day])
        after = (close[hit + AFTER] / level - 1.0
                 if hit is not None and hit + AFTER < len(bars) else None)
        out.append(Outcome(symbol, k * atr[start] / close[start], hit is not None,
                           None if hit is None else hit - start, after))
    return out


def summary(outcomes: Sequence[Outcome]) -> dict[str, float]:
    stopped = [o for o in outcomes if o.stopped]
    after = [o.after for o in stopped if o.after is not None]
    days = [o.days for o in stopped if o.days is not None]
    return {"entries": float(len(outcomes)),
            "stopped": len(stopped) / len(outcomes) if outcomes else math.nan,
            "distance": float(np.median([o.distance for o in outcomes])) if outcomes else math.nan,
            "days": float(np.median(days)) if days else math.nan,
            "after": float(np.median(after)) if after else math.nan,
            "came_back": float(np.mean([a > 0 for a in after])) if after else math.nan,
            "measured_after": float(len(after))}


def run(entries: Sequence[Mapping[str, object]], clean_root: Path | None = None
        ) -> tuple[dict[str, list[Outcome]], list[str]]:
    by_market: dict[str, list[Outcome]] = {"US": [], "LSE": []}
    skipped = []
    for entry in entries:
        symbol, market = str(entry["yfinance"]), universe.market_of(entry)
        try:
            bars = holdout.research_bars(symbol, "1d", market, clean_root=clean_root)
        except access.AccessRefused:
            bars = None
        if bars is None or len(bars) < stops.ATR_PERIOD + AFTER:
            skipped.append(symbol)
            continue
        by_market[market] += walk(bars, symbol)
    return by_market, skipped


def report(by_market: Mapping[str, Sequence[Outcome]], skipped: Sequence[str],
           first: str, last: str) -> str:
    rows = ["| | entries | stop distance at entry (median) | stopped within 63 days | "
            "median days to the stop | median move, stop → 20 days later | came back above "
            "the stop |", "|---|---|---|---|---|---|---|"]
    for name, group in (("US names", by_market["US"]), ("London names", by_market["LSE"]),
                        ("all", [*by_market["US"], *by_market["LSE"]])):
        s = summary(group)
        rows.append(f"| {name} | {s['entries']:,.0f} | {s['distance']:.1%} below | "
                    f"{s['stopped']:.0%} | {s['days']:.0f} | {s['after']:+.1%} "
                    f"(of {s['measured_after']:,.0f}) | {s['came_back']:.0%} |")
    return "\n".join([
        "# How a 3 × ATR stop would have behaved (QT-16 C2; re-run QT-17 A1, unsealed) — "
        "description only", "",
        "**Choosing k from this table would be a trial.** It would have to be "
        "pre-registered, counted, and judged on bars it was not chosen on. k stays 3.", "",
        f"Advisor list, UNSEALED daily bars {first} → {last}, read through the holdout "
        "door (QT-17 A1; the QT-16 page read the sealed year and is kept, superseded, as "
        f"{SUPERSEDED.name}). Method: qb2/research/stop_description.py.",
        "", *rows, "", f"Left out (too few bars): {', '.join(skipped) or 'none'}.", ""])


def main(argv: Sequence[str] | None = None) -> int:
    entries = universe.advisor_entries()
    by_market, skipped = run(entries)
    spans = [holdout.research_bars(str(e["yfinance"]), "1d", universe.market_of(e))
             for e in entries[:5]]
    first = min(str(s.index.min().date()) for s in spans)
    last = max(str(s.index.max().date()) for s in spans)
    text = report(by_market, skipped, first, last)
    TARGET.write_text(text, encoding="utf-8")
    print(f"wrote {TARGET.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
