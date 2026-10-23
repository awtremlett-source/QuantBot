"""S-07 described (QT-24 D): the slow trend filter run over history -- a DESCRIPTION, not a gate.

S-07 (registered cd3e863) on VWRL's UNSEALED daily bars, described exactly as ADV-0 was
(QT-23 E): the same spans (2014-03-31 -> 2025-10-09, the 2020 and 2022 calendar years), the same
runner (adv0_describe.describe, with S-07's rule), 1x and 2x costs, the same dividends, beside plain
VWRL hold (the same first fill, held throughout) and ADV-0's own described figures
(docs/research/ADV-0_described_2026-10.json); D3 beside. The month-end averages read the unsealed
history before each span (from 2012) to DECIDE, never to score. No brake (the S6 rule).
COUNTED: one trial-log line, kind backtest, when it runs (N 55 -> 56).
CLI: python -m qb2.research.s07_describe   (inside the cap)
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from datetime import date, datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from qb2.research import adv0_describe as adv0
from qb2.research import advisor_data, firewall, holdout, preregister, trend_filter, trial_log
from qb2.tools.governor import assert_capped

OUT = adv0.REPO_ROOT / "docs" / "research" / "S-07_described_2026-10"
NAMES = {"adv0": "s07", "stop_gain": "gain_vs_hold", "adv0_worst_fall": "s07_worst_fall",
         "stop_fired": "switched_out", "rebuys": "switched_back_in"}   # the runner's keys, for S-07


def signal(bars: pd.DataFrame) -> np.ndarray:
    """Per bar, over the whole history: (month-end, week-end, above) -- sliced with each span."""
    days = list(holdout.local_index(bars.index, "LSE").date)
    month_end, week_end = trend_filter.calendar_ends(days)
    up = trend_filter.above(bars["close"].to_numpy(dtype=float), month_end)
    return np.column_stack([month_end, week_end, up]).astype(float)


def rule(days: Sequence[date], opens: np.ndarray, closes: np.ndarray, sig: np.ndarray,
         start: date) -> adv0.Path:
    """S-07 in the runner's shape (adv0_describe.path's): the held path and its fills."""
    book = trend_filter.fills(days, sig[:, 0] > 0, sig[:, 1] > 0, sig[:, 2], start)
    return adv0.Path(trend_filter.held(len(days), book), book, sum(s == trend_filter.SELL for _, s in book))


def renamed(run: dict[str, Any]) -> dict[str, Any]:
    return {NAMES.get(k, k): renamed(v) if isinstance(v, dict) else v for k, v in run.items()}


def main(argv: Sequence[str] | None = None) -> int:
    assert_capped()                    # QT-23R: never outside the operator's cap
    token = preregister.require("S-07")
    entry = next(e for e in advisor_data.entries() if e["yfinance"] == "VWRL.L")
    bars = holdout.research_bars("VWRL.L", "1d", "LSE")
    holdout.check_unsealed(bars.index, "1d", "LSE", None)
    income, counts = advisor_data.income("VWRL.L", "LSE", bars)
    sig, instrument = signal(bars), firewall.instrument_of(entry)
    runs = {k: renamed(adv0.describe(bars, income, sig, a, b, instrument, rule=rule))
            for k, (a, b) in adv0.SPANS.items()}
    whole = runs["2014-03-31 -> 2025-10-09"]
    trial_log.log_trial({"utc_time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         "kind": trial_log.BACKTEST, "candidate_id": "S-07", "register_commit": token.commit,
                         "strategy_name": str(token.entry["rule"]),
                         "params": {"box": "QT-24 D", "described": True, "dividends": counts,
                                    "spans": list(adv0.SPANS)},
                         "metric_name": "total_return_net_2x", "metric_value": whole["2x"]["s07"],
                         "n_bars": whole["sessions"]})
    beside = json.loads(adv0.OUT.with_suffix(".json").read_text(encoding="utf-8"))
    OUT.with_suffix(".json").write_text(json.dumps({"S-07": runs, "ADV-0 (QT-23 E)": beside}, indent=1,
                                                   default=str), encoding="utf-8")
    OUT.with_suffix(".md").write_text(page(runs, beside, counts, token.commit), encoding="utf-8")
    print(json.dumps(runs, indent=1, default=str))
    return 0


def page(runs: dict[str, dict[str, Any]], adv: dict[str, dict[str, Any]], counts: dict[str, int],
         commit: str) -> str:
    lines = ["# S-07 described: hold VWRL while its month-end close is above its 10-month average "
             "(QT-24 D)", "",
             f"A DESCRIPTION, not a gate (registered {commit[:7]}). Hypothesis: a slow trend filter "
             "cuts crash depth with fewer whipsaws than a 15% stop. Unsealed bars only; no brake (the "
             "S6 rule). Dividends: " + advisor_data.counts_text(counts) + ". Counted: N 55 -> 56.", ""]
    for name, r in runs.items():
        a = adv.get(name, {})
        lines += [f"## {name}: {r.get('from')} -> {r.get('to')}", ""]
        if "note" in r:
            lines += [str(r["note"]), ""]
            continue
        lines += [f"S-07 switched out {r['switched_out']} times and back in {r['switched_back_in']} times; "
                  f"{r['sessions_in_cash']} of {r['sessions']} sessions in cash. ADV-0 (from {a.get('from')}): "
                  f"its stop fired {a.get('stop_fired')} times, {a.get('sessions_in_cash')} sessions in cash.", "",
                  "| costs | S-07 | ADV-0 | plain VWRL hold | S-07 worst fall | ADV-0 worst fall | hold worst fall |",
                  "|---|---|---|---|---|---|---|"]
        for s in ("1x", "2x"):
            x, y = r[s], a.get(s, {})
            lines.append(f"| {s} | {x['s07']:+.1%} | {y.get('adv0', float('nan')):+.1%} | {x['plain_hold']:+.1%} | "
                         f"{x['s07_worst_fall']:.1%} | {y.get('adv0_worst_fall', float('nan')):.1%} | "
                         f"{x['plain_worst_fall']:.1%} |")
        lines += ["", f"D3 ({r['d3']['symbol']}) over S-07's dates: {r['d3']['total_return']:+.1%}.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
