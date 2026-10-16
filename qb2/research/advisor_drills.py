"""The known-null gate re-proved for the monthly advisor book, on daily bars (QT-19 B2).

The three drills registered with the six (KN-A-RANDOM / GAP / PLANT-1d) go through the
SAME path as a trial (advisor_run.book_for and .score): the book, its slots, stops,
dividends, costs, the luck test and D3.

* **Gate 1 -- the worthless are rejected.** Random picks must FAIL; so must a 3% jump
  planted right after a marked month-end close (an honest buyer fills at the jumped
  open). Red-first: the fill moved onto the decision bar itself -> GAP must PASS.
* **Gate 2 -- the exploitable passes after costs.** A 0.3%-per-bar rise over the 20
  bars after a marked close must PASS at 1x and 2x. Red-first: the slot weights
  removed (each held name 1/n of the pot, the rest cash -- the old combine) -> it
  must FAIL. (KN-A-PLANT-1d, 0.1% a bar, was re-sized to v2 before any gate run;
  it is still run and reported.)

Marks: each (name, month) with a decision bar is MARKED with probability 0.2, else
ANTI with probability 0.25 (a mirror move, no marker), seeded by (0, bet, month).
Honest runs are logged kind=drill (counted 0); red-first runs are not logged.

CLI: ``python -m qb2.research.advisor_drills`` -- writes docs/research/
known_null_2026-10-16_QT19_advisor.md and its .json evidence.
"""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qb2.research import (advisor_book, advisor_data, advisor_run, fills, firewall, preregister,
                          report, stats, trial_log)
from qb2.signals.a_rules import SENTINEL_VOLUME

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT = REPO_ROOT / "docs" / "research" / "known_null_2026-10-16_QT19_advisor"


def marks(name: firewall.NameData) -> tuple[list[int], list[int]]:
    """(marked, anti) decision bars of one name."""
    days = pd.DatetimeIndex(name.bars.index).date
    ends = advisor_book.last_sessions(advisor_book.sessions(name.market, days[0], days[-1]))
    up: list[int] = []
    down: list[int] = []
    for t, day in enumerate(days):
        m = advisor_book.month_of(day)
        if ends.get(m) != day:
            continue
        u = np.random.default_rng(np.random.SeedSequence([0, name.bet, m])).random()
        (up if u < 0.2 else down if u < 0.4 else []).append(t)
    return up, down


def plant(data: Sequence[firewall.NameData], p: Mapping[str, Any]) -> list[firewall.NameData]:
    """Copies of the real bars with the registered pattern after each marked close."""
    if "pattern" not in p:
        return list(data)
    out = []
    for name in data:
        up, down = marks(name)
        n = len(name.bars)
        log = np.zeros(n)
        for sign, bars in ((1.0, up), (-1.0, down)):
            for t in bars:
                if p["pattern"] == "gap":
                    log[t + 1:] += sign * np.log1p(float(p["jump"]))
                else:
                    step = np.clip(np.arange(n) - t, 0, int(p["trend_bars"]))
                    log += sign * step * np.log1p(float(p["delta_per_bar"]))
        copy = name.bars.copy()
        for col in ("open", "high", "low", "close"):
            copy[col] = copy[col].to_numpy(dtype=float) * np.exp(log)
        copy["high"] = copy[["open", "high", "low", "close"]].max(axis=1)
        copy["low"] = copy[["open", "high", "low", "close"]].min(axis=1)
        volume = copy["volume"].to_numpy(dtype=float).copy()
        volume[up] = SENTINEL_VOLUME
        copy["volume"] = volume
        out.append(replace(name, bars=copy))
    return out


def same_bar_fills(data: Sequence[firewall.NameData]) -> list[firewall.NameData]:
    """BROKEN on purpose (Gate 1 red-first): a decision fills at its own bar's open."""
    return [replace(d, plan=fills.Schedule(len(d.bars), np.arange(len(d.bars), dtype=np.int64),
                                           np.ones(len(d.bars), dtype=bool), None, None, None))
            for d in data]


def drill(drill_id: str, data: Sequence[firewall.NameData], skipped: Sequence[str], *,
          stress: float = 1.0, broken: str | None = None, n_null: int = advisor_run.N_NULL,
          ) -> dict[str, Any]:
    token = preregister.require(drill_id)
    planted = plant(data, token.entry["parameters"])
    book, weighted = advisor_run.book_for(token.entry, planted)
    if broken == "same_bar_fill":
        weighted = same_bar_fills(weighted)
    elif broken == "no_slot_weights":
        weighted = [replace(d, weight=None) for d in weighted]
    result = advisor_run.score(token, weighted, book, stress=stress, skipped=skipped,
                               n_null=n_null, log_path=None if broken else
                               trial_log.DEFAULT_TRIAL_LOG)
    marked = result.observed.marked
    return {"drill": drill_id, "stress": stress, "broken": broken,
            "expect": str(token.entry["expect"]), "verdict": result.verdict.outcome,
            "failed": list(result.verdict.failed), "p": result.p_value,
            "dsr": result.deflated.get("dsr"), "trades": result.observed.trades,
            "net": stats.compute(marked, "1d").total_return,
            "d3": result.benchmark.total_return if result.benchmark else None,
            "start": str(result.start), "end": str(result.end),
            "report_md": report.render(result) if result.benchmark else ""}


HONEST = (("gate1", "KN-A-RANDOM-1d", 1.0), ("gate1", "KN-A-GAP-1d", 1.0),
          ("gate2", "KN-A-PLANT-v2-1d", 1.0), ("gate2", "KN-A-PLANT-v2-1d", 2.0),
          ("v1", "KN-A-PLANT-1d", 1.0), ("v1", "KN-A-PLANT-1d", 2.0))   # v1: reported beside
RED_FIRST = (("gate1", "KN-A-GAP-1d", 1.0, "same_bar_fill", "PASS"),
             ("gate2", "KN-A-PLANT-v2-1d", 1.0, "no_slot_weights", "FAIL"))


def main(argv: Sequence[str] | None = None) -> int:
    data, skipped, _ = advisor_data.load()
    runs: list[dict[str, Any]] = []
    for gate, did, stress in HONEST:
        t0 = time.monotonic()
        runs.append({"gate": gate, **drill(did, data, skipped, stress=stress),
                     "seconds": round(time.monotonic() - t0)})
        print(f"{did} {stress:g}x: {runs[-1]['verdict']} (expect {runs[-1]['expect']})", flush=True)
    for gate, did, stress, broken, want in RED_FIRST:
        out = drill(did, data, skipped, stress=stress, broken=broken)
        runs.append({"gate": gate, **out, "expect": want, "red_first": True})
        print(f"{did} BROKEN {broken}: {out['verdict']} (red-first needs {want})", flush=True)
    green = {g: all(r["verdict"] == r["expect"] for r in runs if r["gate"] == g
                    and not r.get("red_first")) for g in ("gate1", "gate2", "v1")}
    shown = {g: all(r["verdict"] == r["expect"] for r in runs if r["gate"] == g
                    and r.get("red_first")) for g in ("gate1", "gate2")}
    lines = ["# Known-null gate on the advisor's monthly book, daily bars (QT-19 B2)", ""]
    for g in ("gate1", "gate2", "v1"):
        lines += [f"## {g}: {'GREEN' if green[g] else 'RED'} · red-first "
                  f"{'shown' if shown[g] else 'NOT shown'}" if g != "v1" else
                  "## KN-A-PLANT-1d (0.1%/bar, superseded as Gate 2's instrument; reported)", ""]
        for r in (x for x in runs if x["gate"] == g):
            tag = f"BROKEN ({r['broken']})" if r.get("red_first") else "honest"
            lines += [f"- {r['drill']} at {r['stress']:g}× {tag}: expected {r['expect']}, got "
                      f"**{r['verdict']}** (net {r['net']:+.1%} vs D3 "
                      f"{(r['d3'] or 0):+.1%}, p {r['p'] if r['p'] is None else round(r['p'], 3)}, "
                      f"trades {r['trades']:,}; failed: {', '.join(r['failed']) or 'none'})"]
        lines.append("")
    for r in runs:
        lines += [f"## {r['drill']} {r['stress']:g}× {r.get('broken') or 'honest'}", "", r["report_md"]]
    OUT.with_suffix(".md").write_text("\n".join(lines), encoding="utf-8")
    OUT.with_suffix(".json").write_text(json.dumps(
        [{k: v for k, v in r.items() if k != "report_md"} for r in runs], indent=1), encoding="utf-8")
    print(f"gate1 {green['gate1']} red-first {shown['gate1']} · gate2 {green['gate2']} red-first "
          f"{shown['gate2']}")
    return 0 if green["gate1"] and green["gate2"] and all(shown.values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
