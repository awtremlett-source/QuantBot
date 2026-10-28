"""The combined model's birth certificate: its known-null drills on the LON arm, on scratch copies
only (nothing here writes to the store). Honest runs are logged kind=drill (counted 0) by the
firewall; red-firsts run on deliberately broken code (docs/reports/QT-27_e3_redfirst.py.txt,
QT-28_d2_redfirst.py.txt) and are logged nowhere.

* NULL: each session's feature vectors permuted among its names (default_rng([0, the date's
  ordinal])); every name keeps its real price moves. EDGE / BELOW: a planted 18th feature F_p ~ N(0, 1)
  per (bet, session) (default_rng([0, the bet's index, the ordinal]), shared by a bet's lines); sessions
  with F_p > 0 get +X from the fill to E on a COPY of the bars. EDGE X = 3 x the 2x round trip; BELOW
  X = 0.5 (v1) or k = 0.9 (v2) x the 1x round trip.
* v1 (QT-27, register 6be96dad), the words registered then: NULL GREEN = not PASS and luck p >= 0.05
  (or INSUFFICIENT); EDGE = PASS; BELOW = not PASS and net mean per bar <= 0 (or INSUFFICIENT).
* v2 (QT-28, register 787d4a27), the firewall's OWN verdict over all four runs (ridge, gbt x 1x, 2x):
  EDGE-v2 = PASS; NULL-v2, BELOW-v2 = not PASS. Gate 1 (verdict.judge) = luck p < 0.05 AND a positive
  net mean per bar; a red-first shows when it clears Gate 1 or PASSes (leak: on gbt; costs off: either).

CLI: ``python -m qb2.research.cm_drills [--v1] [--page [red.json]]`` -> docs/research/known_null_*_QT28_cm
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
OUT_V2 = OUT.with_name("known_null_2026-10-28_QT28_cm")
FP = "F_p"
DRILLS = ("KN-CM-NULL", "KN-CM-EDGE", "KN-CM-BELOW")
DRILLS_V2 = tuple(f"{d}-v2" for d in DRILLS)
K_BELOW_V2 = 0.9                       # KN-CM-BELOW-v2's k, by the size rule in its register note
CELLS = frozenset((m, s) for m in ("ridge", "gbt") for s in (1.0, 2.0))   # each drill's four runs
RED_FIRSTS = ("fold_boundary_leaked", "costs_off")


def _x(k: float, stress: float = 1.0) -> Callable[[NameData], float]:
    return lambda d: k * costs.round_trip(d.instrument, simulate.STAKE_GBP, stress=stress).fraction


SIZE: dict[str, Callable[[NameData], float]] = {"KN-CM-EDGE": _x(3.0, 2.0), "KN-CM-EDGE-v2": _x(3.0, 2.0),
                                                "KN-CM-BELOW": _x(0.5), "KN-CM-BELOW-v2": _x(K_BELOW_V2)}


def check_entry(entry: Mapping[str, Any]) -> None:
    """A drill is refused unless its models, stresses and (BELOW-v2) k are what this code runs."""
    p = entry["parameters"]
    if {(str(m), float(s)) for m in p["models"] for s in p["stresses"]} != CELLS or (
            entry["id"] == "KN-CM-BELOW-v2" and p.get("k") != K_BELOW_V2):
        raise ValueError(f"{entry['id']}: models, stresses or k not as this code implements")


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
    if drill.startswith("KN-CM-NULL"):
        return cm_arm.assemble(drill, base, vix, skipped=skipped, extra=shuffle)
    planted = [plant(d, SIZE[drill](d)) for d in base]
    return cm_arm.assemble(drill, planted, vix, skipped=skipped, extra=with_fp(planted))


def columns(drill: str) -> tuple[str, ...]:
    return features.FEATURES if drill.startswith("KN-CM-NULL") else (*features.FEATURES, FP)


def gate1(p: float | None, mean: float) -> bool:
    """The firewall's Gate 1, both halves (verdict.judge's luck and positive)."""
    return p is not None and p < verdict.ALPHA and mean > 0


def green(drill: str, outcome: str, p: float | None, mean: float) -> bool:
    """One run's gate: v2 = the firewall's verdict alone; v1 = the words registered in 6be96dad."""
    if drill in DRILLS_V2:
        return (outcome == verdict.PASS) == (drill == "KN-CM-EDGE-v2")
    return {"KN-CM-NULL": outcome != verdict.PASS and (p is None or p >= verdict.ALPHA),
            "KN-CM-EDGE": outcome == verdict.PASS,
            "KN-CM-BELOW": outcome != verdict.PASS and (outcome == verdict.INSUFFICIENT or mean <= 0)}[drill]


def gates(runs: Sequence[Mapping[str, Any]], drills: Sequence[str]) -> dict[str, bool]:
    """Each drill GREEN only when all four of its runs are there and each one is green."""
    return {d: {(r["model"], float(r["stress"])) for r in runs if r["drill"] == d} == CELLS
            and all(r["green"] for r in runs if r["drill"] == d) for d in drills}


def shows(r: Mapping[str, Any]) -> bool:
    """A red-first run shows: it clears the firewall's Gate 1, or it PASSes."""
    return r["verdict"] == verdict.PASS or bool(r["luck_and_positive"])


def seen(red: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, bool]:
    """QT-28 B3: the leaked fold boundary must show on gbt (ridge reported); costs off on either model."""
    return {"fold_boundary_leaked": any(shows(r) for r in red.get(RED_FIRSTS[0], []) if r["model"] == "gbt"),
            "costs_off": any(shows(r) for r in red.get(RED_FIRSTS[1], []))}


def proven(record: Mapping[str, Any]) -> bool:
    """The birth certificate (QT-28 D3): every v2 gate GREEN and both red-firsts SEEN."""
    found = dict(record.get("seen") or {})
    return all([*gates(record.get("honest", []), DRILLS_V2).values(), set(found) == set(RED_FIRSTS), *found.values()])


def figures(drill: str, model: str, stress: float, r: firewall.FirewallResult,
            extras: Mapping[str, Any]) -> dict[str, Any]:
    flat = r.observed.marked.to_numpy(dtype=float)
    mean = float(flat.mean()) if len(flat) else 0.0
    outcome, p = r.verdict.outcome, r.p_value
    return {"drill": drill, "model": model, "stress": stress, "verdict": outcome,
            "failed": list(r.verdict.failed), "reasons": list(r.verdict.reasons), "p": p,
            "dsr": r.deflated.get("dsr"), "trades": r.observed.trades, "mean_per_bar": mean,
            "net": stats.compute(r.observed.marked, "1h").total_return if len(flat) else None,
            "vwrp": r.benchmark.total_return if r.benchmark else None, "start": str(r.start),
            "end": str(r.end), "green": green(drill, outcome, p, mean), "luck_and_positive": gate1(p, mean),
            "describe": dict(extras)}


def run(*, drills: Sequence[str] = DRILLS_V2, log_path: Path | None = trial_log.DEFAULT_TRIAL_LOG,
        n_null: int = cm_arm.N_NULL, say: Callable[[str], None] = print) -> list[dict[str, Any]]:
    entry = preregister.require(drills[0]).entry
    base, skipped = firewall.load("1h", entries=s6_run.arm_entries(entry))
    vix = holdout.research_bars(cm_arm.VIX, "1h", "US")
    out = []
    for drill in drills:
        token = preregister.require(drill)
        if not token.is_drill:
            raise preregister.NotRegistered(f"{drill} is not registered as a drill")
        check_entry(token.entry)
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


def write_page(record: Mapping[str, Any], target: Path = OUT_V2.with_suffix(".md")) -> str:
    """The birth certificate's page, from the honest runs and (once run) the red-firsts."""
    honest, red = list(record.get("honest", [])), dict(record.get("red_first") or {})
    if v2 := any(str(r["drill"]).endswith("-v2") for r in honest):
        said = " · ".join(f"{d} {'GREEN' if ok else 'RED'}" for d, ok in gates(honest, DRILLS_V2).items())
    else:
        g = {n: all(r["green"] for r in honest if (r["drill"] == "KN-CM-NULL") == (n == 1)) for n in (1, 2)}
        said = f"Gate 1 {'GREEN' if g[1] else 'RED'} · Gate 2 {'GREEN' if g[2] else 'RED'}"
    box = ("QT-28 D: drills v2, register 787d4a27, judged by the firewall's own verdicts" if v2 else
           "QT-27 E: drills registered with the six trials, register 6be96dad")
    head = "| drill | model | costs | verdict (failed checks) | OOS trades | luck p | net mean / bar | net | VWRP | "
    lines = [f"# Known-null gate for the combined model, {target.name[11:21]} ({box}; LON arm, real clean store)",
             "", "Run through the trials' own code (cm_arm.score -> the unchanged firewall). Honest runs logged "
             "kind=drill (counted 0); red-firsts on deliberately broken code, logged nowhere "
             f"(docs/reports/{'QT-28_d2' if v2 else 'QT-27_e3'}_redfirst.py.txt).", "",
             f"## Honest code: {said}", "", head + "gate |", "|---|---|---|---|---|---|---|---|---|---|"]
    lines += [_line(r, "GREEN" if r["green"] else "**RED**") for r in honest]
    if red:
        found = dict(record.get("seen") or {})
        lines += ["", "## Red first, on deliberately broken code (nothing logged)", "", head + "red? |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        for breakage, runs in red.items():
            lines += [_line(r, f"{breakage}: {'**RED** ✓' if r['red'] else 'not red'}") for r in runs]
        lines += ["", "Seen: " + ", ".join(f"{k} {'YES' if v else 'NO'}" for k, v in found.items())]
    if v2:
        said += f"; birth certificate {(word := ('PROVEN' if proven(record) else 'NOT PROVEN') if red else 'pending')}"
        lines += ["", f"**Birth certificate: {word}** (PROVEN = every v2 gate GREEN and both red-firsts SEEN)."]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return f"written {target.name}: {said}"


def main(argv: Sequence[str] | None = None) -> int:
    assert_capped()                    # QT-23R: never outside the operator's cap
    args = list(argv or [])
    drills, out = (DRILLS, OUT) if "--v1" in args else (DRILLS_V2, OUT_V2)
    args = [a for a in args if a != "--v1"]
    if args[:1] == ["--page"]:         # --page [red-first.json]: merge, then write the page
        record = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
        if len(args) > 1:
            record.update(json.loads(Path(args[1]).read_text(encoding="utf-8")))
            record["seen"] = seen(record["red_first"])           # one judge of the red-firsts
            out.with_suffix(".json").write_text(json.dumps(record, indent=1, default=str), encoding="utf-8")
        print(write_page(record, out.with_suffix(".md")))
        return 0
    runs = run(drills=drills)
    out.with_suffix(".json").write_text(json.dumps({"honest": runs}, indent=1, default=str), encoding="utf-8")
    print(write_page({"honest": runs}, out.with_suffix(".md")))
    return 0 if all(gates(runs, drills).values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
