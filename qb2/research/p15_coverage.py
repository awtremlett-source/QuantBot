"""How much each arm may trade under P15 history (QT-18 A2) -- a measurement, not a trial.

Per arm (US, London shares, London ETFs, Mix): the share of name-sessions on which
a BUY may be sent at EVERY hourly decision of that session (p15.py's mask, history
rule and missing-quarter spans included). Two periods:

* the unsealed 1h period -- the trials' own bars, as firewall.load builds them;
* the holdout dates (2026-07-13 -> 2026-10-09) -- counted from the exchange
  calendar and the earnings rows ONLY: hourly slots are built from each session's
  open and close, so no sealed bar is read.

The box's STOP: the US arm below 80% in either period, or any share outside the
known stale-history five blocked on more than half its sessions.

CLI: ``python -m qb2.research.p15_coverage`` -> docs/research/p15_history_coverage_2026-10.md
"""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import exchange_calendars as xcals  # type: ignore[import-untyped]
import numpy as np
import pandas as pd

from qb2.data import universe
from qb2.research import fills, firewall, holdout, p15, p15_history

REPO_ROOT = Path(__file__).resolve().parents[2]
PAGE = REPO_ROOT / "docs" / "research" / "p15_history_coverage_2026-10.md"
HOLDOUT = (holdout.SEALED_FROM["1h"], date(2026, 10, 9))
STALE_FIVE = frozenset({"RR.L", "GLEN.L", "RIO.L", "AAL.L", "ULVR.L"})
US_FLOOR, NAME_FLOOR = 0.80, 0.50
ARMS = {"US": ("us_liquid",), "London shares": ("uk_share",), "London ETFs": ("uk_etf",),
        "Mix": ("us_liquid", "uk_share", "uk_etf")}


def calendar_slots(market: str, first: date, last: date) -> pd.DatetimeIndex:
    """Each session's hourly bar starts, from the exchange calendar alone."""
    cal = xcals.get_calendar(fills.CALENDARS[market])
    starts: list[pd.Timestamp] = []
    for session in cal.sessions_in_range(pd.Timestamp(first), pd.Timestamp(last)):
        t, close = pd.Timestamp(cal.session_open(session)), pd.Timestamp(cal.session_close(session))
        while t < close:
            starts.append(t)
            t += pd.Timedelta(hours=1)
    return pd.DatetimeIndex(starts).tz_convert(fills.EXCHANGE_TZ[market])


def per_session(index: pd.DatetimeIndex, allowed: np.ndarray, market: str) -> tuple[int, int]:
    """(sessions allowed at every decision, sessions)."""
    days = pd.DatetimeIndex(index).tz_convert(fills.EXCHANGE_TZ[market]).date
    every = pd.Series(allowed).groupby(days).all()
    return int(every.sum()), int(len(every))


def measure(entries: Sequence[Mapping[str, Any]], data: Sequence[firewall.NameData],
            clean_root: Path | None = None) -> dict[str, dict[str, tuple[int, int]]]:
    """symbol -> {"unsealed": (ok, n), "holdout": (ok, n)}."""
    bars = {d.symbol: d for d in data}
    out: dict[str, dict[str, tuple[int, int]]] = {}
    for e in entries:
        symbol, market, kind = str(e["yfinance"]), universe.market_of(e), str(e["kind"])
        row: dict[str, tuple[int, int]] = {}
        if symbol in bars:
            d = bars[symbol]
            may = d.plan.may_enter if d.plan.may_enter is not None else np.ones(len(d.bars), bool)
            row["unsealed"] = per_session(d.bars.index, may, market)
        slots = calendar_slots(market, *HOLDOUT)
        history = p15_history.load(symbol, market, clean_root) if kind != "ETF" else None
        mask = p15.mask(symbol, kind, slots, "1h", market,
                        history.frame if history else None, history)
        row["holdout"] = per_session(slots, mask, market)
        out[symbol] = row
    return out


def arm_share(counts: Mapping[str, Mapping[str, tuple[int, int]]],
              sleeves: Mapping[str, str], arm: str, period: str) -> float | None:
    rows = [c[period] for s, c in counts.items() if sleeves[s] in ARMS[arm] and period in c]
    total = sum(n for _, n in rows)
    return sum(ok for ok, _ in rows) / total if total else None


def stops(counts: Mapping[str, Mapping[str, tuple[int, int]]],
          sleeves: Mapping[str, str]) -> list[str]:
    out = [f"US arm {share:.1%} allowed ({period}) < {US_FLOOR:.0%}" for period in
           ("unsealed", "holdout") if (share := arm_share(counts, sleeves, "US", period))
           is not None and share < US_FLOOR]
    for symbol, c in sorted(counts.items()):
        for period, (ok, n) in c.items():
            if symbol not in STALE_FIVE and n and 1 - ok / n > NAME_FLOOR:
                out.append(f"{symbol} blocked on {1 - ok / n:.0%} of its {period} sessions")
    return out


def main(argv: Sequence[str] | None = None) -> int:
    entries = universe.bot_entries()
    sleeves = {str(e["yfinance"]): str(e["sleeve"]) for e in entries}
    data, skipped = firewall.load("1h", entries=entries)
    counts = measure(entries, data)
    lines = ["# P15 history: how much each arm may trade (QT-18 A2)", "",
             "A BUY counts as allowed on a name-session when p15.py's mask allows it at "
             "EVERY hourly decision of that session (history rule, missing-quarter spans). "
             "Holdout counted from the exchange calendar and earnings rows only -- no "
             f"sealed bar read. Skipped (no unsealed 1h bars): {skipped or 'none'}.", "",
             "| arm | unsealed | holdout 2026-07-13 → 2026-10-09 |", "|---|---|---|"]
    for arm in ARMS:
        cells = [arm_share(counts, sleeves, arm, p) for p in ("unsealed", "holdout")]
        lines.append(f"| {arm} | " + " | ".join("—" if c is None else f"{c:.1%}" for c in cells)
                     + " |")
    lines += ["", "| name | sleeve | unsealed allowed | holdout allowed | missing-quarter gaps |",
              "|---|---|---|---|---|"]
    for e in entries:
        s = str(e["yfinance"])
        c = counts[s]
        gaps = "" if e["kind"] == "ETF" else "; ".join(
            f"{g.after}→{g.before} (blocked {g.blocked_from}→{g.blocked_to})"
            for g in p15_history.load(s, universe.market_of(e)).gaps)
        cell = [f"{ok}/{n} ({ok / n:.0%})" if n else "—" for ok, n in
                (c.get("unsealed", (0, 0)), c["holdout"])]
        lines.append(f"| {s} | {sleeves[s]} | {cell[0]} | {cell[1]} | {gaps or '—'} |")
    found = stops(counts, sleeves)
    lines += ["", "**STOP: " + "; ".join(found) + "**" if found else
              "**No STOP:** the US arm is at or above 80% in both periods, and no share "
              "outside the stale five (RR.L, GLEN.L, RIO.L, AAL.L, ULVR.L) is blocked on "
              "more than half its sessions."]
    PAGE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:12]).encode("ascii", "replace").decode())   # cp1252 console
    print("STOP" if found else "no STOP", found)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
