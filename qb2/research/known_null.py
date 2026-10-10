"""The known-null gate: proof the firewall can tell luck from an edge (S4).

Run on the REAL clean store (unsealed bars of the agreed 50), in two halves, each
built so it goes RED on exactly the breakage it guards against:

* **Gate 1 -- the worthless are rejected.** A coin-flip (5m and daily) must FAIL,
  and so must a pattern only an impossible instant fill could catch
  (KN-INSTANT-5m). Remove the delay rule and that drill passes: Gate 1 RED.
* **Gate 2 -- the exploitable passes after costs.** A trend deliberately planted
  into copies of real bars must PASS at 1x and 2x costs (5m and daily), and the
  same trend shrunk to 0.7 of each name's round-trip cost must FAIL
  (KN-PLANT-SMALL-5m). Switch costs off and that drill passes: Gate 2 RED.

Every drill is pre-registered (docs/research/preregistered.json, kind "drill")
and logged with kind="drill", which the trial count excludes.

CLI: ``python -m qb2.research.known_null`` -- runs the gate, writes the reports.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qb2.execution import costs
from qb2.research import fills, firewall, monte_carlo, preregister, report, simulate, trial_log
from qb2.research.strategy import Strategy

SENTINEL_VOLUME = 777_777_777.0          # the planted marker; no real bar has it
REPO_ROOT = Path(__file__).resolve().parents[2]
REPORTS = REPO_ROOT / "docs" / "research"


class Harvester:
    """Long for ``hold`` decisions from each planted marker bar -- causal by design."""

    def __init__(self, hold: int) -> None:
        self.hold = int(hold)
        self.name = f"planted_harvester(hold={hold})"

    def weights(self, bars: pd.DataFrame) -> pd.Series:
        marked = (bars["volume"] == SENTINEL_VOLUME).astype(float)
        return marked.rolling(self.hold, min_periods=1).max().fillna(0.0)


def positions_in_blocks(index: pd.DatetimeIndex, interval: str, market: str,
                        block: int) -> np.ndarray:
    """Each bar's place in its block: its session (5m) or a fixed run of bars (1d)."""
    if interval == "1d":
        return np.arange(len(index)) % block
    local = pd.DatetimeIndex(index).tz_convert(fills.EXCHANGE_TZ[market])
    return np.asarray(pd.Series(local.date).groupby(local.date).cumcount(), dtype=np.int64)


def plant(bars: pd.DataFrame, instrument: costs.Instrument, market: str,
          interval: str, p: Mapping[str, Any]) -> pd.DataFrame:
    """A copy of real bars with the registered pattern planted in every block."""
    out = bars.copy()
    where = positions_in_blocks(out.index, interval, market, int(p.get("block", 0)) or 1)
    marker, need = int(p["marker_bar"]), int(p["block_bars_needed"])
    sizes = pd.Series(where).groupby((where == 0).cumsum()).transform("size").to_numpy()
    room = sizes >= need
    factor = np.ones(len(out))
    if p["pattern"] == "trend":
        delta = float(p.get("delta_per_bar", 0.0))
        if "edge_vs_round_trip" in p:              # sized to this name's own costs
            trip = costs.round_trip(instrument, simulate.STAKE_GBP).fraction
            delta = float(p["edge_vs_round_trip"]) * trip / int(p["steps_caught"][market])
        up0, n = marker + int(p["up_start"]), int(p["up_bars"])
        step = np.clip(where - up0 + 1, 0, n) - np.clip(where - (up0 + n) + 1, 0, n)
        factor = (1.0 + delta) ** step
    elif p["pattern"] == "instant":
        jump = 1.0 + float(p["delta"])
        out.loc[(where == marker + 1) & room, "close"] *= jump   # inside one bar...
        out.loc[(where == marker + 2) & room, "open"] *= jump    # ...still there at the
    else:                                                         # next open, then gone
        raise ValueError(f"unknown planted pattern {p['pattern']!r}")
    factor = np.where(room, factor, 1.0)
    for col in ("open", "high", "low", "close"):
        out[col] = out[col].to_numpy() * factor
    out["high"] = out[["open", "high", "low", "close"]].max(axis=1)
    out["low"] = out[["open", "high", "low", "close"]].min(axis=1)
    out.loc[(where == marker) & room, "volume"] = SENTINEL_VOLUME
    return out


def strategy_for(entry: Mapping[str, Any]) -> Callable[[firewall.NameData], Strategy]:
    p = entry["parameters"]
    if entry["rule"] == "coin_flip":
        return lambda name: monte_carlo.RandomStrategy(
            float(p["prob_long"]),
            int(np.random.SeedSequence([int(p["seed"]), name.bet]).generate_state(1)[0]))
    if entry["rule"] == "planted_harvester":
        return lambda name: Harvester(int(p["hold"]))
    raise ValueError(f"{entry['id']}: rule {entry['rule']!r} is not a drill rule")


def with_pattern(data: Sequence[firewall.NameData], interval: str,
                 p: Mapping[str, Any] | None) -> list[firewall.NameData]:
    if not p or "pattern" not in p:
        return list(data)
    return [replace(d, bars=plant(d.bars, d.instrument, d.market, interval, p)) for d in data]


@dataclass(frozen=True, slots=True)
class DrillRun:
    drill_id: str
    stress: float
    expect: str
    result: firewall.FirewallResult

    @property
    def green(self) -> bool:
        return self.result.verdict.outcome == self.expect


GATE1 = (("KN-COIN-5m", 1.0), ("KN-INSTANT-5m", 1.0), ("KN-COIN-1d", 1.0))
GATE2 = (("KN-PLANT-5m", 1.0), ("KN-PLANT-5m", 2.0), ("KN-PLANT-1d", 1.0),
         ("KN-PLANT-1d", 2.0), ("KN-PLANT-SMALL-5m", 1.0))


def run_gate(*, base: Mapping[str, Sequence[firewall.NameData]],
             skipped: Mapping[str, Sequence[str]] | None = None,
             require: Callable[[str], preregister.Registered] = preregister.require,
             n_null: int = monte_carlo.DEFAULT_TRIALS, log_path: Path | None = None,
             **kw: Any) -> dict[str, list[DrillRun]]:
    """Both gates. ``base`` holds each bar size's loaded names (loaded once)."""
    out: dict[str, list[DrillRun]] = {"gate1": [], "gate2": []}
    for gate, drills in (("gate1", GATE1), ("gate2", GATE2)):
        for drill_id, stress in drills:
            token = require(drill_id)
            entry = token.entry
            interval = str(entry["bar_size"])
            data = with_pattern(base[interval], interval, entry["parameters"])
            result = firewall.score(token, strategy_for(entry), data, interval=interval,
                                    stress=stress, n_null=n_null,
                                    skipped=(skipped or {}).get(interval, ()),
                                    log_path=log_path, **kw)
            out[gate].append(DrillRun(drill_id, stress, str(entry["expect"]), result))
    return out


def colour(runs: Sequence[DrillRun]) -> str:
    return "GREEN" if runs and all(r.green for r in runs) else "RED"


def main(argv: Sequence[str] | None = None) -> int:
    base, skipped = {}, {}
    for interval in ("5m", "1d"):
        base[interval], skipped[interval] = firewall.load(interval)
    runs = run_gate(base=base, skipped=skipped,
                    log_path=trial_log.DEFAULT_TRIAL_LOG)
    lines = [f"# Known-null gate, {date.today().isoformat()} (QT-14, real clean store)", ""]
    for gate, title in (("gate1", "Gate 1 -- the worthless are rejected"),
                        ("gate2", "Gate 2 -- the exploitable passes after costs")):
        lines += [f"## {title}: {colour(runs[gate])}", ""]
        for run in runs[gate]:
            lines += [f"Expected {run.expect}, got {run.result.verdict.outcome} "
                      f"({'GREEN' if run.green else 'RED'}).", "",
                      report.render(run.result), ""]
    target = REPORTS / f"known_null_{date.today().isoformat()}.md"
    target.write_text("\n".join(lines), encoding="utf-8")
    print(f"Gate 1 {colour(runs['gate1'])} · Gate 2 {colour(runs['gate2'])} -> {target.name}")
    return 0 if colour(runs["gate1"]) == colour(runs["gate2"]) == "GREEN" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
