"""ADV-0 described (QT-23 E): the advisor's default run over history -- a DESCRIPTION, not a gate.

ADV-0 (registered 8fb2c49) on VWRL's UNSEALED daily bars, 2014-03-31 -> 2025-10-09, and the 2020
and 2022 calendar years, at 1x and 2x costs; beside it a plain VWRL hold (the same first fill, held
throughout, the same dividends) and D3 (VWRP; VWRL before VWRP's first traded close) over the
same dates. Reported: total return, times the stop fired, re-buys, sessions in cash, the gain or
loss from the stop (ADV-0 minus the plain hold), the worst fall (maximum drawdown). BRAKES ARE NOT
APPLIED inside back-tests (the S6 rule): live, the advisor pot's brake can make a re-buy wait.
COUNTED: one trial-log line, kind backtest, when it runs (N 54 -> 55).

The rule, back-test form (:func:`path`): the first week's last London session on/after the start
-> BUY at the next open. Stop = fill x (1 - f); at each close the cross first (close <= level ->
SELL at the next open), else raised to max(old, close x (1 - f)) -- guard/stops.fall_level, the one
copy. f = 15%, 10% when VIX's latest close before the day is above 30 or none within 5 days. After
an exit: L = the lowest close from the exit's fill bar on; a close >= L x 1.10 -> BUY at the next
open. P13 at 12 months: re-justified at a review, no trade, a fresh stop no lower.
CLI: python -m qb2.research.adv0_describe   (inside the cap)
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from qb2.execution import costs
from qb2.guard import stops
from qb2.research import advisor_data, benchmark, firewall, holdout, preregister, simulate, stats, trial_log
from qb2.tools.governor import assert_capped

REPO_ROOT = holdout.REPO_ROOT
OUT = REPO_ROOT / "docs" / "research" / "ADV-0_described_2026-10"
REBUY, VIX_DAYS, STRESSES = 0.10, 5, (1.0, 2.0)
SPANS = {"2014-03-31 -> 2025-10-09": (date(2014, 3, 31), date(2025, 10, 9)),
         "2020": (date(2020, 1, 1), date(2020, 12, 31)), "2022": (date(2022, 1, 1), date(2022, 12, 31))}


@dataclass
class Path:
    held: np.ndarray                                   # 1.0 = held through that bar's close
    fills: list[tuple[int, str]] = field(default_factory=list)       # (bar, BUY/SELL) at its open
    fired: int = 0                                     # the stop crossed at a close


def rebuy_signal(close: float, low: float) -> bool:
    """R6, its ONE copy (the live job's too): a close at least 10% above the lowest close since the
    exit -- compared to the micro-penny, so a 2-decimal price exactly 10% up counts (95.00 -> 104.50)."""
    return round(close, 6) >= round(low * (1 + REBUY), 6)


def unsettled(days: Sequence[date], vix_days: np.ndarray, vix: np.ndarray) -> np.ndarray:
    """P10 per bar: VIX's latest close dated BEFORE the day above 30, or none within 5 days."""
    out = np.ones(len(days), dtype=bool)
    for t, d in enumerate(days):
        j = int(np.searchsorted(vix_days, np.datetime64(d), side="left")) - 1
        if j >= 0 and (np.datetime64(d) - vix_days[j]).astype(int) <= VIX_DAYS and np.isfinite(vix[j]):
            out[t] = vix[j] > stops.VIX_UNSETTLED
    return out


def path(days: Sequence[date], opens: np.ndarray, closes: np.ndarray, jumpy: np.ndarray,
         start: date, first_fill: int | None = None) -> Path:
    """ADV-0's held path, bar by bar. ``first_fill`` forces the first BUY's fill bar (a test pins
    the live job's own first fill with it); else the first week's last session decides it."""
    n, out = len(days), Path(np.zeros(len(days)))
    weeks = pd.DatetimeIndex(days).isocalendar()
    last_of_week = np.r_[(weeks.week.to_numpy()[1:] != weeks.week.to_numpy()[:-1]), True]
    if first_fill is None:
        decide = next((t for t in range(n) if days[t] >= start and last_of_week[t]), None)
        first_fill = None if decide is None or decide + 1 >= n else decide + 1
    on, level, low, pending, opened = False, np.nan, np.inf, {}, None
    if first_fill is not None:
        pending[first_fill] = "BUY"
    for t in range(n):
        f = stops.FALLS[bool(jumpy[t])]
        side = pending.pop(t, None)
        if side == "BUY" and not on:
            on, level, opened, low = True, stops.fall_level(opens[t], f), days[t], np.inf
            out.fills.append((t, side))
        elif side == "SELL" and on:
            on, low = False, np.inf
            out.fills.append((t, side))
        out.held[t] = 1.0 if on else 0.0
        if on:
            if closes[t] <= level:                       # crossed: SELL at the next open
                out.fired += 1
                if t + 1 < n:
                    pending[t + 1] = "SELL"
            else:
                level = stops.fall_level(closes[t], f, level)
                if opened and last_of_week[t] and pd.Timestamp(days[t]) >= pd.Timestamp(opened) + pd.DateOffset(months=12):
                    opened = days[t]                     # P13: re-justified, no trade, no lower
        elif out.fills:                                  # out after an exit: the re-buy watch
            low = min(low, closes[t])
            if rebuy_signal(closes[t], low) and t + 1 < n and t + 1 not in pending:
                pending[t + 1] = "BUY"
    return out


def describe(bars: pd.DataFrame, income: np.ndarray, jumpy: np.ndarray, start: date, end: date,
             instrument: costs.Instrument) -> dict[str, Any]:
    days = list(holdout.local_index(bars.index, "LSE").date)
    keep = np.array([start <= d <= end for d in days])
    b, inc, jump = bars[keep], income[keep], jumpy[keep]
    d = [x for x, k in zip(days, keep) if k]
    o, c = b["open"].to_numpy(dtype=float), b["close"].to_numpy(dtype=float)
    p = path(d, o, c, jump, start)
    if not p.fills:
        return {"from": str(start), "to": str(end), "note": "no fill in the span"}
    first = p.fills[0][0]
    plain = np.where(np.arange(len(d)) >= first, 1.0, 0.0)
    out: dict[str, Any] = {"from": str(d[first]), "to": str(d[-1]), "sessions": len(d) - first,
                              "stop_fired": p.fired, "rebuys": sum(s == "BUY" for _, s in p.fills) - 1,
                              "sessions_in_cash": int((p.held[first:] == 0).sum())}
    for s in STRESSES:
        legs = simulate.leg_fractions(instrument, s)
        a = stats.compute(simulate.run(o, c, p.held, legs, 0.0, inc).net[first:], "1d", "LSE")
        h = stats.compute(simulate.run(o, c, plain, legs, 0.0, inc).net[first:], "1d", "LSE")
        out[f"{s:g}x"] = {"adv0": a.total_return, "plain_hold": h.total_return,
                          "stop_gain": a.total_return - h.total_return,
                          "adv0_worst_fall": a.max_drawdown, "plain_worst_fall": h.max_drawdown}
    d3 = benchmark.over(d[first], d[-1])
    out["d3"] = {"symbol": d3.symbol, "total_return": d3.total_return}
    return out


def main(argv: Sequence[str] | None = None) -> int:
    assert_capped()                    # QT-23R: never outside the operator's cap
    token = preregister.require("ADV-0")
    entry = next(e for e in advisor_data.entries() if e["yfinance"] == "VWRL.L")
    bars = holdout.research_bars("VWRL.L", "1d", "LSE")
    holdout.check_unsealed(bars.index, "1d", "LSE", None)
    income, counts = advisor_data.income("VWRL.L", "LSE", bars)
    vix = advisor_data.vix(None)
    days = list(holdout.local_index(bars.index, "LSE").date)
    jumpy = unsettled(days, np.asarray(holdout.local_index(vix.index, "US").date, dtype="datetime64[D]"),
                      vix.to_numpy(dtype=float))
    runs = {k: describe(bars, income, jumpy, a, b, firewall.instrument_of(entry)) for k, (a, b) in SPANS.items()}
    whole = runs["2014-03-31 -> 2025-10-09"]
    trial_log.log_trial({"utc_time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         "kind": trial_log.BACKTEST, "candidate_id": "ADV-0", "register_commit": token.commit,
                         "strategy_name": str(token.entry["rule"]),
                         "params": {"box": "QT-23 E", "described": True, "dividends": counts, "spans": list(SPANS)},
                         "metric_name": "total_return_net_2x", "metric_value": whole["2x"]["adv0"],
                         "n_bars": whole["sessions"]})
    OUT.with_suffix(".json").write_text(json.dumps(runs, indent=1, default=str), encoding="utf-8")
    OUT.with_suffix(".md").write_text(page(runs, counts), encoding="utf-8")
    print(json.dumps(runs, indent=1, default=str))
    return 0


def page(runs: dict[str, dict[str, Any]], counts: dict[str, int]) -> str:
    lines = ["# ADV-0 described: hold VWRL, the big-fall stop, the 10% re-buy (QT-23 E)", "",
             "A DESCRIPTION, not a gate (registered 8fb2c49). Unsealed bars only; brakes NOT applied "
             "(the S6 rule). Dividends: " + advisor_data.counts_text(counts) + ". Counted: N 54 -> 55.", ""]
    for name, r in runs.items():
        lines += [f"## {name}: {r.get('from')} -> {r.get('to')}", ""]
        if "note" in r:
            lines += [str(r["note"]), ""]
            continue
        lines += [f"Stop fired {r['stop_fired']} times; re-bought {r['rebuys']} times; "
                  f"{r['sessions_in_cash']} of {r['sessions']} sessions in cash.", "",
                  "| costs | ADV-0 | plain VWRL hold | gain from the stop | ADV-0 worst fall | hold worst fall |",
                  "|---|---|---|---|---|---|"]
        for s in ("1x", "2x"):
            x = r[s]
            lines.append(f"| {s} | {x['adv0']:+.1%} | {x['plain_hold']:+.1%} | {x['stop_gain']:+.1%} | "
                         f"{x['adv0_worst_fall']:.1%} | {x['plain_worst_fall']:.1%} |")
        lines += ["", f"D3 ({r['d3']['symbol']}) over the same dates: {r['d3']['total_return']:+.1%}.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
