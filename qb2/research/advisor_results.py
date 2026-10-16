"""S9 batch 1's results: each trial summarised, and the one page (QT-19 B5).

The headline figures are P19's (p19_results.summarise: compounded, net after 2x costs
with the survivorship mark-down, D3 over the same dates, 1x beside it). Added for a
slow monthly book: turnover per year (share of the pot bought), average holding
length, the US / London split (DESCRIPTION ONLY -- picking one afterwards would be a
new trial), stops, P13 re-qualifications, how often the 1% ceiling bound, the advisor's
P15 warnings on its buys, and the dividends credited.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qb2.guard import earnings_window
from qb2.research import (advisor_book, bet_groups, fills, firewall, matched_null, p15_history,
                          rank_null, stats, verdict)
from qb2.research.p19_results import _num, _pct

WARNING = ("Description only. Choosing the US or London half because it looks better here "
           "would be a NEW trial: registered, and counted, before it is run.")


def extras(result: firewall.FirewallResult, data: Sequence[firewall.NameData],
           book: advisor_book.Book) -> dict[str, Any]:
    seen, by = result.observed, {d.symbol: d for d in data}
    years = max((pd.Timestamp(str(result.end)) - pd.Timestamp(str(result.start))).days / 365.25,
                1e-9) if result.start else float("nan")
    bought, days, held_bars, capped = 0.0, [], 0, 0
    for sym, g in seen.graded.items():
        part, w = seen.parts[sym], by[sym].weight
        if w is not None:
            bought += float((w.reindex(part.index).fillna(0.0) * part["entries"]).sum())
        on = g.full.held[g.lo:g.hi] > 0
        a, b = matched_null.runs_of(g.full.held[g.lo:g.hi])
        index = pd.DatetimeIndex(g.full.index[g.lo:g.hi]).date
        days += [(index[min(e, len(index) - 1)] - index[s]).days for s, e in zip(a, b, strict=True)]
        held_bars += int(on.sum())
        capped += int((on & book.capped[sym][g.lo:g.hi]).sum())
    split = {}
    for market in ("US", "LSE"):
        part = {s: f for s, f in seen.parts.items() if by[s].market == market}
        if part:
            line = bet_groups.combine({s: f["marked"].astype(float) for s, f in part.items()}, None,
                                      {s: w for s in part if (w := by[s].weight) is not None})
            split[market] = {"marked_2x": stats.compute(line, "1d").total_return,
                             "trades": int(sum(int(f["entries"].sum()) for f in part.values()))}
    marked = seen.marked.to_numpy(dtype=float)
    sr0_ii = rank_null.analytic_sr0(marked, int(result.deflated.get("n_trials", 48)))
    return {"turnover_per_year": bought / years, "avg_hold_days": float(np.mean(days)) if days
            else None, "split": split, "stopped": book.stopped, "requalified": book.requalified,
            "filter_off_months": book.filter_off_months,
            "ceiling_binds": capped / held_bars if held_bars else 0.0,
            "warnings": warnings(book, data, result.start),
            "top_bar_share": verdict.top_bar_share(marked), "stopped_in_a_month":
            stopped_within(book, data, result.start), "sr0_rank": result.deflated.get("sr0"),
            "sr0_analytic": sr0_ii}


def stopped_within(book: advisor_book.Book, data: Sequence[firewall.NameData], start: object,
                   bars: int = 21) -> float | None:
    """Of the buys decided on/after ``start``: the share whose holding ended at a P10 stop
    within ``bars`` sessions (a month) of the decision."""
    by, stops = {d.symbol: d for d in data}, set(book.stops)
    hit = n = 0
    for sym, t in book.buys:
        if start is None or pd.DatetimeIndex(by[sym].bars.index).date[t] < start:
            continue
        n += 1
        rest = np.flatnonzero(book.decisions[sym][t + 1:] == 0.0)
        end = t + 1 + int(rest[0]) if len(rest) else None
        hit += end is not None and (sym, end) in stops and end - t <= bars
    return hit / n if n else None


def warnings(book: advisor_book.Book, data: Sequence[firewall.NameData],
             start: object) -> dict[str, int]:
    """P15 as the advisor uses it: what earnings_window.advisor_warning said at each buy."""
    by, frames = {d.symbol: d for d in data}, {}
    out = {"buys": 0, "within_5_days": 0, "date_unknown": 0}
    for sym, t in book.buys:
        name = by[sym]
        day = pd.DatetimeIndex(name.bars.index).date[t]
        if start is None or day < start:
            continue
        out["buys"] += 1
        if name.instrument.kind == earnings_window.ETF:
            continue
        if sym not in frames:
            frames[sym] = p15_history.load(sym, name.market).frame
        moment = datetime.fromtimestamp(fills._close_ns(day, name.market) / 1e9, tz=timezone.utc)  # noqa: SLF001
        said = earnings_window.advisor_warning(sym, name.instrument.kind, name.market, moment,
                                               frames[sym]) or ""
        out["within_5_days"] += "within" in said
        out["date_unknown"] += "unknown" in said
    return out


def table(records: Sequence[Mapping[str, Any]]) -> list[str]:
    lines = ["| id | rule | trades | gross | net 1× | **net 2×** | D3 same dates | max DD | "
             "p (matched) | DSR (N) | biggest bar | verdict | holdout | turnover/yr | avg hold | "
             "stopped < 1 month |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in records:
        hold = r.get("holdout")
        held = "—" if r["avg_hold_days"] is None else f"{r['avg_hold_days']:.0f} days"
        lines.append(
            f"| {r['id']} | {r['rule_name']} | {r['trades']:,} | {_pct(r['gross'])} | "
            f"{_pct(r['marked_1x'])} | **{_pct(r['marked_2x'])}** | {_pct(r['vwrp'])} | "
            f"{_pct(r['max_dd_2x'])} | {_num(r['p'])} | {_num(r['dsr'])} ({_num(r['n_trials'], 0)})"
            f" | {_share(r.get('top_bar_share'))} | **{r['verdict']}** | "
            f"{hold['verdict'] if hold else 'not run'} | {_pct(r['turnover_per_year'])} | {held} | "
            f"{_share(r.get('stopped_in_a_month'))} |")
    return lines


def _share(x: float | None) -> str:
    return "—" if x is None else f"{float(x):.1%}"


def page(records: Sequence[Mapping[str, Any]], intro: Sequence[str]) -> str:
    lines = [*intro, "", *table(records), "", "## US / London split (net 2×)", "", f"> {WARNING}",
             "", "| id | US net 2× (trades) | London net 2× (trades) |", "|---|---|---|"]
    for r in records:
        cell = {m: f"{_pct(v['marked_2x'])} ({v['trades']:,})" for m, v in r["split"].items()}
        lines.append(f"| {r['id']} | {cell.get('US', '—')} | {cell.get('LSE', '—')} |")
    lines += ["", "## The book, per trial", "", "| id | stopped | P13 re-justified | 1% ceiling "
              "binds (held name-days) | months in cash (A-06) | buys | P15 warning: results within "
              "5 days | date unknown |", "|---|---|---|---|---|---|---|---|"]
    for r in records:
        w = r["warnings"]
        lines.append(f"| {r['id']} | {r['stopped']:,} | {r['requalified']:,} | "
                     f"{r['ceiling_binds']:.2%} | {r['filter_off_months']} | {w['buys']:,} | "
                     f"{w['within_5_days']:,} | {w['date_unknown']:,} |")
    lines += ["", "## The luck bar, two ways (SR0 at N; DSR uses (i))", "",
              "(i) random-rank books built by the trial's own rules: how far skill-free books sit "
              "from each other on the one shared history. (ii) DESCRIPTION ONLY, one book's own "
              "Sharpe noise from its moments: the noise the PSR already charges in its "
              "denominator, so (ii) is expected to be the larger.", "",
              "| id | Sharpe/bar (2×) | SR0 (i) random-rank | SR0 (ii) analytic |", "|---|---|---|---|"]
    lines += [f"| {r['id']} | {_num(r['sharpe'], 4)} | {_num(r.get('sr0_rank'), 4)} | "
              f"{_num(r.get('sr0_analytic'), 4)} |" for r in records]
    lines += ["", "## Why each did not pass", ""]
    lines += [f"- **{r['id']}**: " + ("; ".join(r["reasons"]) or "every check met") for r in records]
    for r in records:
        lines += ["", f"## {r['id']} — firewall report", "", r["report_md"]]
    return "\n".join(lines) + "\n"


def load(folder: Path, order: Sequence[str]) -> list[dict[str, Any]]:
    found = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in folder.glob("A-*.json")
             if not p.stem.endswith(".holdout")}
    return [found[c] for c in order if c in found]

