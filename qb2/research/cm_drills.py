"""The combined model's birth certificate: its known-null drills on the LON arm (QT-27 E;
register commit 6be96dad: KN-CM-NULL, KN-CM-EDGE, KN-CM-BELOW). Scratch copies only -- nothing
here writes to the store.

* KN-CM-NULL (Gate 1, the worthless are rejected): each session's feature vectors are permuted
  among its names (numpy default_rng([0, the date's ordinal])), so features say nothing about a
  name's own outcome while every name keeps its real price moves. GREEN when, for both models at
  1x and 2x, the verdict is not PASS and the luck test is not passed (p >= 0.05, or INSUFFICIENT).
* KN-CM-EDGE / KN-CM-BELOW (Gate 2): a planted 18th feature F_p ~ N(0, 1) per (bet, session)
  (default_rng([0, the bet's index, the date's ordinal]), both lines of a bet sharing it); on a
  name's sessions with F_p > 0 its fill -> E return gets +X on a COPY of its bars. EDGE: X = 3 x
  the 2x round trip, GREEN when PASS for both models at 1x and 2x. BELOW: X = 0.5 x the 1x round
  trip, GREEN when not PASS and costs are what reject it (net mean per bar <= 0, or INSUFFICIENT).

Honest runs are logged kind=drill (counted 0) by the firewall itself. The red-firsts (E3) run on
deliberately broken code from docs/reports/QT-27_e3_redfirst.py.txt and are logged nowhere.

CLI: ``python -m qb2.research.cm_drills`` -> docs/research/known_null_2026-10-28_QT27_cm.{md,json}
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qb2.execution import costs
from qb2.model import features
from qb2.research import (cm_arm, firewall, holdout, p19_results, preregister, s6_run, simulate, stats,
                          trial_log, verdict)
from qb2.research.names import NameData
from qb2.signals import s6_rules
from qb2.tools import run_window
from qb2.tools.governor import assert_capped

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT = REPO_ROOT / "docs" / "research" / "known_null_2026-10-28_QT27_cm"
FP = "F_p"
DRILLS = ("KN-CM-NULL", "KN-CM-EDGE", "KN-CM-BELOW")
SIZE: dict[str, Callable[[NameData], float]] = {
    "KN-CM-EDGE": lambda d: 3.0 * costs.round_trip(d.instrument, simulate.STAKE_GBP, stress=2.0).fraction,
    "KN-CM-BELOW": lambda d: 0.5 * costs.round_trip(d.instrument, simulate.STAKE_GBP).fraction}


def fp(bet: int, day: date) -> float:
    return float(np.random.default_rng([0, bet, day.toordinal()]).standard_normal())


def plant(name: NameData, x: float) -> NameData:
    """A copy whose sessions with F_p > 0 carry +X from the fill to the session's end: the fill
    bar's high, low and close and every later price that session times (1 + X)."""
    bars, factor = name.bars.copy(), np.ones(len(name.bars))
    plan = name.plan
    for s0, s1, day in s6_rules.sessions(pd.DatetimeIndex(bars.index), name.market):
        f = int(plan.fills[s0])
        if fp(name.bet, day) > 0 and plan.usable[s0] and f < s1:
            factor[f:s1] = 1.0 + x
    fill_bar = factor > np.r_[1.0, factor[:-1]]                        # each planted run's first bar
    bars["open"] = bars["open"].to_numpy(float) * np.where(fill_bar, 1.0, factor)   # the entry price stays
    for col in ("high", "low", "close"):
        bars[col] = bars[col].to_numpy(float) * factor
    bars["high"] = bars[["open", "high", "low", "close"]].max(axis=1)
    bars["low"] = bars[["open", "high", "low", "close"]].min(axis=1)
    return replace(name, bars=bars)


def with_fp(data: Sequence[NameData]) -> cm_arm.Extra:
    bet = {d.symbol: d.bet for d in data}
    return lambda rows: rows.assign(**{FP: [fp(bet[s], d) for s, d in zip(rows["symbol"], rows["day"])]})


def shuffle(rows: pd.DataFrame) -> pd.DataFrame:
    """Each session's feature vectors permuted among that session's names (seeded by the date)."""
    out, cols = rows.copy(), list(features.FEATURES)
    for day, group in rows.groupby("day", sort=True):
        order = np.random.default_rng([0, day.toordinal()]).permutation(len(group))
        out.loc[group.index, cols] = group[cols].to_numpy()[order]
    return out


def arm_for(drill: str, base: Sequence[NameData], skipped: Sequence[str], vix: pd.DataFrame) -> cm_arm.Arm:
    if drill == "KN-CM-NULL":
        return cm_arm.assemble(drill, base, vix, skipped=skipped, extra=shuffle)
    planted = [plant(d, SIZE[drill](d)) for d in base]
    return cm_arm.assemble(drill, planted, vix, skipped=skipped, extra=with_fp(planted))


def columns(drill: str) -> tuple[str, ...]:
    return features.FEATURES if drill == "KN-CM-NULL" else (*features.FEATURES, FP)


def figures(drill: str, model: str, stress: float, r: firewall.FirewallResult,
            extras: Mapping[str, Any]) -> dict[str, Any]:
    flat = r.observed.marked.to_numpy(dtype=float)
    mean = float(flat.mean()) if len(flat) else 0.0
    outcome, p = r.verdict.outcome, r.p_value
    luck = p is not None and p < verdict.ALPHA and mean > 0
    green = {"KN-CM-NULL": outcome != verdict.PASS and (p is None or p >= verdict.ALPHA),
             "KN-CM-EDGE": outcome == verdict.PASS,
             "KN-CM-BELOW": outcome != verdict.PASS and (outcome == verdict.INSUFFICIENT or mean <= 0)}[drill]
    return {"drill": drill, "model": model, "stress": stress, "verdict": outcome,
            "failed": list(r.verdict.failed), "reasons": list(r.verdict.reasons), "p": p,
            "dsr": r.deflated.get("dsr"), "trades": r.observed.trades, "mean_per_bar": mean,
            "net": stats.compute(r.observed.marked, "1h").total_return if len(flat) else None,
            "vwrp": r.benchmark.total_return if r.benchmark else None, "start": str(r.start),
            "end": str(r.end), "green": green, "luck_and_positive": luck, "describe": dict(extras)}


def run(*, log_path: Path | None = trial_log.DEFAULT_TRIAL_LOG, n_null: int = cm_arm.N_NULL,
        say: Callable[[str], None] = print) -> list[dict[str, Any]]:
    entry = preregister.require("KN-CM-NULL").entry
    base, skipped = firewall.load("1h", entries=s6_run.arm_entries(entry))
    vix = holdout.research_bars(cm_arm.VIX, "1h", "US")
    out = []
    for drill in DRILLS:
        token = preregister.require(drill)
        if not token.is_drill:
            raise preregister.NotRegistered(f"{drill} is not registered as a drill")
        arm = arm_for(drill, base, skipped, vix)
        for model in token.entry["parameters"]["models"]:
            for stress in token.entry["parameters"]["stresses"]:
                run_window.wait_clear(say=say)            # box rule 0.3
                result, extras = cm_arm.score(token, arm, model, stress=float(stress), n_null=n_null,
                                              log_path=log_path, columns=columns(drill))
                out.append(figures(drill, model, float(stress), result, extras))
                say(f"  {drill} {model} {stress:g}x: {out[-1]['verdict']} -- {'GREEN' if out[-1]['green'] else 'RED'}")
    return out


def _line(r: Mapping[str, Any], extra: str) -> str:
    p = "—" if r["p"] is None else f"{float(r['p']):.3f}"
    return (f"| {r['drill']} | {r['model']} | {float(r['stress']):g}× | **{r['verdict']}** "
            f"({', '.join(r['failed']) or '—'}) | {int(r['trades']):,} | {p} | {float(r['mean_per_bar']):+.5%} | "
            f"{p19_results._pct(r['net'])} | {p19_results._pct(r['vwrp'])} | {extra} |")


def write_page(record: Mapping[str, Any], target: Path = OUT.with_suffix(".md")) -> str:
    """The birth certificate's page, from the honest runs and (once run) the red-firsts."""
    honest, red = list(record.get("honest", [])), dict(record.get("red_first") or {})
    gates = {g: all(r["green"] for r in honest if (r["drill"] == "KN-CM-NULL") == (g == 1)) for g in (1, 2)}
    head = "| drill | model | costs | verdict (failed checks) | OOS trades | luck p | net mean / bar | net | VWRP | "
    lines = [f"# Known-null gate for the combined model, {OUT.name[11:21]} (QT-27 E: LON arm, real clean store)", "",
             "Drills registered with the six trials (commit 6be96dad), run through the trials' own code "
             "(cm_arm.score -> the unchanged firewall). Honest runs logged kind=drill (counted 0); red-firsts on "
             "deliberately broken code, logged nowhere (docs/reports/QT-27_e3_redfirst.py.txt).", "",
             f"## Honest code: Gate 1 {'GREEN' if gates[1] else 'RED'} · Gate 2 {'GREEN' if gates[2] else 'RED'}", "",
             head + "gate |", "|---|---|---|---|---|---|---|---|---|---|"]
    lines += [_line(r, "GREEN" if r["green"] else "**RED**") for r in honest]
    if red:
        seen = dict(record.get("seen") or {})
        lines += ["", "## Red first, on deliberately broken code (nothing logged)", "", head + "red? |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        for breakage, runs in red.items():
            lines += [_line(r, f"{breakage}: {'**RED** ✓' if r['red'] else 'not red'}") for r in runs]
        lines += ["", "Seen: " + ", ".join(f"{k} {'YES' if v else 'NO'}" for k, v in seen.items())]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return f"written {target.name}: Gate 1 {'GREEN' if gates[1] else 'RED'}, Gate 2 {'GREEN' if gates[2] else 'RED'}"


def main(argv: Sequence[str] | None = None) -> int:
    assert_capped()                    # QT-23R: never outside the operator's cap
    args = list(argv or [])
    if args[:1] == ["--page"]:         # --page [red-first.json]: merge, then write the page
        record = json.loads(OUT.with_suffix(".json").read_text(encoding="utf-8"))
        if len(args) > 1:
            record.update(json.loads(Path(args[1]).read_text(encoding="utf-8")))
            OUT.with_suffix(".json").write_text(json.dumps(record, indent=1, default=str), encoding="utf-8")
        print(write_page(record))
        return 0
    runs = run()
    OUT.with_suffix(".json").write_text(json.dumps({"honest": runs}, indent=1, default=str), encoding="utf-8")
    gate1 = all(r["green"] for r in runs if r["drill"] == "KN-CM-NULL")
    gate2 = all(r["green"] for r in runs if r["drill"] != "KN-CM-NULL")
    print(write_page({"honest": runs}))
    return 0 if gate1 and gate2 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
