"""The brake replay's report: docs/research/brake_replay_2026-10.md (QT-16 C1).

Kept apart from brake_replay.py (the arithmetic) so each stays one job and short.
If a firing the box requires did not happen, the report says STOP and the command
exits 1 -- the figures are never tuned to make it happen.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from qb2.research import brake_replay as br

TARGET = br.REPO_ROOT / "docs" / "research" / "brake_replay_2026-10.md"


def deepest(path: pd.Series, window: str) -> float:
    """The worst fall from the running peak on any day inside the window."""
    a, b = br.WINDOWS[window]
    drawdown = path / path.cummax() - 1.0
    inside = drawdown[(drawdown.index >= pd.Timestamp(a)) & (drawdown.index <= pd.Timestamp(b))]
    return float(inside.min()) if len(inside) else float("nan")


def fired(episodes: Sequence[br.Episode], level: str, window: str) -> str:
    """'new <date>' if it triggered inside; 'carried from <date>' if on from before."""
    a, b = br.WINDOWS[window]
    on = [e for e in episodes if e.level == level and e.start <= b
          and (e.end is None or e.end >= a)]
    new = [e.start for e in on if e.start >= a]
    if new:
        return f"new {min(new)}"
    return f"carried from {min(e.start for e in on)}" if on else "no"


def _compound(values: Sequence[float]) -> float:
    return float(np.prod([1.0 + v for v in values]) - 1.0) if values else 0.0


def table(paths: Mapping[str, pd.Series], found: Mapping[str, Sequence[br.Episode]]) -> list[str]:
    head = ["| path (in £) | days | " + " | ".join(
        f"{w}: 10% / 15% · worst fall" for w in br.WINDOWS) + " |",
        "|---|---|" + "---|" * len(br.WINDOWS)]
    for name, path in paths.items():
        cells = []
        for w in br.WINDOWS:
            if path.index.min() > pd.Timestamp(br.WINDOWS[w][1]):
                cells.append("not yet listed")
                continue
            cells.append(f"{fired(found[name], '10%', w)} / {fired(found[name], '15%', w)} "
                         f"· {deepest(path, w):.1%}")
        head.append(f"| {name} | {len(path):,} | " + " | ".join(cells) + " |")
    return head


def alarms(found: Mapping[str, Sequence[br.Episode]]) -> list[str]:
    rows = ["| path | 10% triggers outside the windows | false alarms | return missed in "
            "false alarms | return while braked, all outside episodes | 15% outside |",
            "|---|---|---|---|---|---|"]
    for name, episodes in found.items():
        outside = [e for e in episodes if e.window is None and e.level == "10%"]
        false = [e for e in outside if e.false_alarm]
        rows.append(f"| {name} | {len(outside)} | {len(false)} | "
                    f"{_compound([e.missed for e in false]):+.1%} | "
                    f"{_compound([e.missed for e in outside]):+.1%} | "
                    f"{sum(1 for e in episodes if e.window is None and e.level == '15%')} |")
    return rows


def episodes(found: Mapping[str, Sequence[br.Episode]]) -> list[str]:
    out = []
    for name, eps in found.items():
        out += [f"**{name}**", ""]
        out += [f"- {e.level} from {e.start} to {e.end or 'still on'}"
                f"{' (' + e.window + ')' if e.window else ''}: path {e.missed:+.1%}"
                f"{' · FALSE ALARM' if e.false_alarm else ''}" for e in eps]
        out.append("")
    return out


def main(argv: Sequence[str] | None = None, *, folder: Path = br.FOLDER,
         target: Path = TARGET) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args(argv)
    if args.refresh or not (folder / "manifest.json").is_file():
        br.store(folder=folder)
    raw, manifest = br.load(folder)
    paths, dropped = {}, {}
    for symbol, currency in br.PATHS.items():
        series = raw[symbol]
        if currency == "USD":
            series, dropped[symbol] = br.in_pounds(series, raw[br.FX])
        paths[symbol] = series[series.index >= pd.Timestamp(br.START)]
    found = {name: br.replay(path) for name, path in paths.items()}
    misses = br.required_misses(found)
    lines = ["# Brake replay, 2026-10 (QT-16 C1)", "",
             ("**STOP: a required firing did not happen: " + "; ".join(misses) + ".**")
             if misses else "**Every required firing happened.**", "",
             *table(paths, found), "", *alarms(found), "",
             "Data (outside the trading store, data/research/brake_replay/):", ""]
    lines += [f"- {s}: {m['first']} → {m['last']}, {m['rows']} rows, sha256 "
              f"`{m['sha256'][:16]}…`" + (f"; {dropped[s]} day(s) with no GBPUSD rate "
                                         "dropped" if dropped.get(s) else "")
              for s, m in manifest.items()]
    lines += ["", "## Every episode", "", *episodes(found)]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {target.name}: {'STOP' if misses else 'every required firing happened'}")
    return 1 if misses else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
