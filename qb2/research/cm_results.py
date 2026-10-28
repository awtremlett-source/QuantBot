"""S6 batch 2's results page, rebuilt from the run files on disk (QT-27 F2).

Batch 1's shape (s6_results.table, p19_results.reasons and sleeve_table: one copy each): every
figure is the firewall's -- NET after 2x costs with the survivorship mark-down, compounded, 1x
beside it, VWRP 1h over the same dates, the luck test's p against the turnover-matched null, the
Deflated Sharpe over N. Plus, per trial, what the model did -- description only, never judged:
trades, days in cash, P15 refusals, and its calibration (mean forecast against mean realised gross
on the lines it bought).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from qb2.research import p19_results, s6_results, trial_log

REPO_ROOT = Path(__file__).resolve().parents[2]
PAGE = REPO_ROOT / "docs" / "research" / "S6_batch2_results_2026-10.md"
_pct, _num = p19_results._pct, p19_results._num


def _bp(x: float | None) -> str:
    return "—" if x is None else f"{float(x) * 100:+.3f}%"


def described(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    lines = ["| id | model | out-of-sample sessions | rows dropped (a feature missing) | lines picked | "
             "P15 refused | lines bought | days traded | days in cash | mean forecast (bought) | "
             "mean realised gross (bought) |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        d = r.get("describe") or {}
        lines.append(f"| {r['id']} | {r.get('model', '?')} | {d.get('oos_sessions', '—')} "
                     f"({d.get('oos_first')} → {d.get('oos_last')}) | {d.get('rows_dropped', '—'):,} | "
                     f"{d.get('picked_lines', 0):,} | {d.get('p15_refused', 0):,} | {d.get('bought_lines', 0):,} | "
                     f"{d.get('days_traded', 0):,} | {d.get('days_in_cash', 0):,} | "
                     f"{_bp(d.get('mean_prediction_bought'))} | {_bp(d.get('mean_realised_gross_bought'))} |")
    return lines


def write_page(run_dir: Path, listed: Sequence[Mapping[str, Any]], target: Path = PAGE) -> str:
    journal = [json.loads(x) for x in (run_dir / "journal.ndjson").read_text(encoding="utf-8").splitlines()
               if x.strip()] if (run_dir / "journal.ndjson").is_file() else []
    starts = [r for r in journal if r["event"] == "start"]
    run = int(starts[-1]["run"]) if starts else 1
    rows = s6_results.records(run_dir, listed, run)
    interrupted = [r["id"] for r in journal if r["event"] == "interrupted"]
    survivors = [r["id"] for r in rows if r["verdict"] == "PASS"
                 and (r.get("holdout") or {}).get("verdict") == "PASS"]
    total, seen = trial_log.count_selection_trials()
    minutes = sum(float(r.get("seconds", 0)) for r in rows) / 60
    start = starts[-1] if starts else {}
    lines = [
        "# S6 batch 2 results, 2026-10 (QT-27: the combined model — 2 models × 3 arms, 1-hour bars)", "",
        f"Run {run} of {len(starts)}; **{len(rows)} of {len(listed)} trials complete**; interrupted runs "
        f"logged (counted 0): {', '.join(interrupted) or 'none'}. Every trial run exactly as registered "
        "(docs/research/preregistered.json, commit 6be96dad, ids CM-L-US … CM-G-MIX). Code commit "
        f"`{str(start.get('code_commit', '?'))[:12]}`; data fingerprints (a) `{str(start.get('fp_a', '?'))[:12]}…`, "
        f"(b) `{str(start.get('fp_b', '?'))[:12]}…` (the agreed 50, GBPUSD and ^VIX).", "",
        "**Survived both gates (walk-forward PASS at 2× costs AND holdout PASS): "
        + (", ".join(survivors) if survivors else "none") + ".**", "",
        "How each trial is judged — exactly as batch 1: net after 2× costs with the survivorship mark-down, "
        "compounded; 1× beside it; against VWRP's own hourly closes over the same dates. PASS needs all of: the "
        "turnover-matched luck test (p < 0.05) AND a positive net mean per bar; Deflated Sharpe ≥ 0.95 over N; a "
        "higher return than VWRP. INSUFFICIENT (under 30 out-of-sample trades) is its own answer, never a PASS. "
        "Graded window: the model's own out-of-sample sessions only. Brakes (P12) are NOT applied in back-tests; "
        "the maximum drawdown is shown instead.", "",
        "**Read with care:** the P15 history rule lets the back-test always dodge the real results date (shares "
        "only). The model buys at most 3 bets a day per market, each holding 1/(the arm's bets) of the pot, the "
        "rest in cash (batch 1's equal weight per bet): even a real edge is diluted against a fully invested VWRP.", "",
        f"Trial count for deflation: **N = 62** (56 before + 6). qb2's trial log now counts {total} selection "
        f"trials ({seen['drills_excluded']} drill and {seen['holdout_excluded']} holdout lines excluded). Trial "
        f"runtime {minutes:.0f} minutes.", "",
        "## The 6 trials", "", *s6_results.table(rows), "",
        "## Why each verdict", "", *p19_results.reasons(rows), "",
        "## What the model did (description only, never judged)", "",
        "> Calibration is description only: a forecast that runs above what was realised is an over-confident "
        "model. It is not a verdict and choosing a model or an arm from it is a NEW trial.", "",
        *described(rows), "",
        "## Per sleeve (net after 2× costs and mark-down, compounded)", "",
        "> Per-sleeve figures are description only. **Picking a sleeve, an arm, a model or a year afterwards is a "
        "NEW trial** that must be registered first.", "",
        *p19_results.sleeve_table(rows), "", "## Appendix: each trial's firewall report", ""]
    lines += [str(r["report_md"]) for r in rows]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return f"written {target.name}: {len(rows)} trials, survivors {survivors or 'none'}"
