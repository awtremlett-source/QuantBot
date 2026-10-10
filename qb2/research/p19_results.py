"""P19's results, summarised per trial and written as one page (QT-15 B3).

Every figure is on the compounded basis (stats.compute, QT-15 A1) and the
benchmark is VWRP over the SAME dates. The headline is what the trial is judged
on: NET after 2x costs with the survivorship mark-down; 1x is shown beside it.
Per-sleeve figures (us_liquid, uk_etf, uk_share) are DESCRIPTION ONLY: choosing a
sleeve after seeing them would be a NEW trial that must be registered first.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from qb2.research import bet_groups, firewall, report, stats
from qb2.research.benchmark import MissingBenchmark

SLEEVE_WARNING = ("Description only. Picking a sleeve (or a market) because it "
                  "looks better here would be a NEW trial: it must be registered, "
                  "and counted, before it is run.")


def summarise(result: firewall.FirewallResult,
              names: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    seen, one = result.observed, result.observed_1x
    m2 = stats.compute(seen.marked, result.interval)
    m1 = stats.compute(one.marked, result.interval) if one is not None else m2
    by = {str(e["yfinance"]): str(e.get("sleeve", "?")) for e in names}
    sleeves: dict[str, dict[str, Any]] = {}
    for sleeve in sorted(set(by.values())):
        members = {s: f for s, f in seen.parts.items() if by.get(s) == sleeve}
        if members:
            line = bet_groups.combine({s: f["marked"].astype(float)
                                       for s, f in members.items()})
            sleeves[sleeve] = {
                "names": len(members),
                "trades": int(sum(int(f["entries"].sum()) for f in members.values())),
                "marked_2x": stats.compute(line, result.interval).total_return}
    try:
        rendered = report.render(result)
    except MissingBenchmark as why:
        rendered = f"(report not rendered: {why})\n"
    mark = result.benchmark
    return {
        "id": result.candidate_id, "bars": result.interval, "names": result.names,
        "effective_n": result.effective_n, "skipped": list(result.skipped),
        "oos_start": str(result.start), "oos_end": str(result.end), "n_bars": m2.bars,
        "trades": seen.trades, "marked_2x": m2.total_return, "marked_1x": m1.total_return,
        "net_2x": stats.compute(seen.net, result.interval).total_return,
        "gross": stats.compute(seen.gross, result.interval).total_return,
        "max_dd_2x": m2.max_drawdown, "sharpe": m2.sharpe_per_bar,
        "vwrp": mark.total_return if mark else None, "vwrp_symbol": mark.symbol if mark
        else None, "p": result.p_value, "dsr": result.deflated.get("dsr"),
        "n_trials": result.deflated.get("n_trials"), "null_mean": result.null_mean,
        "null_std": result.null_std, "verdict": result.verdict.outcome,
        "reasons": list(result.verdict.reasons), "sleeves": sleeves, "report_md": rendered}


def _pct(x: float | None) -> str:
    return "—" if x is None or not math.isfinite(float(x)) else f"{float(x):+.2%}"


def _num(x: float | None, places: int = 3) -> str:
    return "—" if x is None else f"{float(x):.{places}f}"


def table(records: Sequence[Mapping[str, Any]],
          universes: Mapping[str, str]) -> list[str]:
    lines = ["| id | bars | universe | OOS dates | trades | net 1× | net 2× | VWRP same "
             "dates | max DD (2×) | p vs coin-flip | DSR (N) | verdict | holdout |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in records:
        hold = r.get("holdout")
        lines.append(
            f"| {r['id']} | {r['bars']} | {universes.get(r['id'], '?')} | "
            f"{r['oos_start']} → {r['oos_end']} | {r['trades']:,} | {_pct(r['marked_1x'])} | "
            f"**{_pct(r['marked_2x'])}** | {_pct(r['vwrp'])} | {_pct(r['max_dd_2x'])} | "
            f"{_num(r['p'])} | {_num(r['dsr'])} ({_num(r['n_trials'], 0)}) | "
            f"**{r['verdict']}** | {hold['verdict'] if hold else 'not run (no PASS)'} |")
    return lines


def sleeve_table(records: Sequence[Mapping[str, Any]]) -> list[str]:
    names = sorted({s for r in records for s in r["sleeves"]})
    lines = [f"> {SLEEVE_WARNING}", "",
             "| id | " + " | ".join(f"{s} net 2× (trades)" for s in names) + " |",
             "|---|" + "---|" * len(names)]
    for r in records:
        cells = [f"{_pct(r['sleeves'][s]['marked_2x'])} ({r['sleeves'][s]['trades']:,})"
                 if s in r["sleeves"] else "—" for s in names]
        lines.append(f"| {r['id']} | " + " | ".join(cells) + " |")
    return lines


def reasons(records: Sequence[Mapping[str, Any]]) -> list[str]:
    out = []
    for r in records:
        why = "; ".join(r["reasons"]) or "every check met"
        out.append(f"- **{r['id']}** {r['verdict']}: {why}")
        if r.get("holdout"):
            h = r["holdout"]
            out.append(f"  - holdout {h['oos_start']} → {h['oos_end']}: {h['verdict']} "
                       f"({'; '.join(h['reasons']) or 'every check met'})")
    return out


def page(records: Sequence[Mapping[str, Any]], universes: Mapping[str, str],
         intro: Sequence[str]) -> str:
    """The whole results page: the table, the reasons, the sleeves, the reports."""
    lines = [*intro, "", "## The 18 trials", "", *table(records, universes), "",
             "## Why each verdict", "", *reasons(records), "",
             "## Per sleeve (net after 2× costs and mark-down, compounded)", "",
             *sleeve_table(records), "", "## Appendix: each trial's firewall report", ""]
    lines += [str(r["report_md"]) for r in records]
    return "\n".join(lines) + "\n"
