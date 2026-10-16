"""S6 batch 1's results page, rebuilt from the run files on disk (QT-18 B4).

One row per trial, in register order. Every figure is the firewall's: NET after 2x
costs with the survivorship mark-down (compounded), 1x beside it, VWRP 1h over the
same dates, the luck test's p against the TURNOVER-MATCHED null, the Deflated Sharpe
over N. Per-sleeve figures are description only (p19_results.SLEEVE_WARNING).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from qb2.research import p19_results, trial_log

REPO_ROOT = Path(__file__).resolve().parents[2]
PAGE = REPO_ROOT / "docs" / "research" / "S6_batch1_results_2026-10.md"
_pct, _num = p19_results._pct, p19_results._num


def records(run_dir: Path, listed: Sequence[Mapping[str, Any]], run: int) -> list[dict[str, Any]]:
    folder = run_dir / f"run{run}"
    out = []
    for e in listed:
        path = folder / f"{e['id']}.json"
        if path.is_file():
            out.append(json.loads(path.read_text(encoding="utf-8")))
    return out


def table(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    lines = ["| id | arm | OOS dates | trades | net 1× | **net 2×** | VWRP same dates | "
             "max DD (2×) | p vs matched null | DSR (N) | verdict | holdout |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        hold = r.get("holdout")
        lines.append(
            f"| {r['id']} | {r['arm']} | {r['oos_start']} → {r['oos_end']} | {r['trades']:,} | "
            f"{_pct(r['marked_1x'])} | **{_pct(r['marked_2x'])}** | {_pct(r['vwrp'])} | "
            f"{_pct(r['max_dd_2x'])} | {_num(r['p'])} | {_num(r['dsr'])} "
            f"({_num(r['n_trials'], 0)}) | **{r['verdict']}** | "
            f"{hold['verdict'] if hold else 'not run (no walk-forward PASS)'} |")
    return lines


def write_page(run_dir: Path, listed: Sequence[Mapping[str, Any]],
               target: Path = PAGE) -> str:
    rows_j = [json.loads(x) for x in (run_dir / "journal.ndjson").read_text(
        encoding="utf-8").splitlines() if x.strip()] if (run_dir / "journal.ndjson").is_file() else []
    starts = [r for r in rows_j if r["event"] == "start"]
    run = int(starts[-1]["run"]) if starts else 1
    rows = records(run_dir, listed, run)
    interrupted = [r["id"] for r in rows_j if r["event"] == "interrupted"]
    survivors = [r["id"] for r in rows if r["verdict"] == "PASS"
                 and (r.get("holdout") or {}).get("verdict") == "PASS"]
    total, seen = trial_log.count_selection_trials()
    minutes = sum(float(r.get("seconds", 0)) for r in rows) / 60
    lines = [
        "# S6 batch 1 results, 2026-10 (QT-18: 8 same-day rules × 3 arms, 1-hour bars)", "",
        f"Run {run} of {len(starts)}; **{len(rows)} of {len(listed)} trials complete**; "
        f"interrupted runs logged (counted 0): {', '.join(interrupted) or 'none'}. Every trial "
        "run exactly as registered (docs/research/preregistered.json, ids S6-01-US … "
        "S6-08-MIX); code commit and data fingerprints in docs/reports/QT-18_progress.md.", "",
        "**Survived both gates (walk-forward PASS at 2× costs AND holdout PASS): "
        + (", ".join(survivors) if survivors else "none") + ".**", "",
        "How each trial is judged: net after 2× costs with the survivorship mark-down, "
        "compounded; 1× beside it; against VWRP's own hourly closes over the same dates. PASS "
        "needs all of: the turnover-matched luck test (p < 0.05) AND a positive net mean per "
        "bar; Deflated Sharpe ≥ 0.95 over N; a higher return than VWRP. INSUFFICIENT (under 30 "
        "out-of-sample trades) is its own answer, never a PASS. Brakes (P12) are NOT applied "
        "in back-tests; the maximum drawdown is shown instead.", "",
        "**Read with care:** the P15 history rule lets the back-test always dodge the real "
        "results date. Live, a date can move, so share results are slightly optimistic (ETFs "
        "are not affected) -- most of all in the holdout, where each share's next date is the "
        "one first recorded on 2026-10-02, treated as known from its July/August results.", "",
        f"Trial count for deflation: **N = 42** (18 before + 24). qb2's trial log now counts "
        f"{total} selection trials ({seen['drills_excluded']} drill and "
        f"{seen['holdout_excluded']} holdout lines excluded). Trial runtime "
        f"{minutes:.0f} minutes.", "",
        "## The 24 trials", "", *table(rows), "",
        "## Why each verdict", "", *p19_results.reasons(rows), "",
        "## Per sleeve (net after 2× costs and mark-down, compounded)", "",
        "> Per-year figures are not shown; per-sleeve figures are description only. Picking "
        "a sleeve, an arm or a year afterwards is a NEW trial that must be registered first.", "",
        *p19_results.sleeve_table(rows), "", "## Appendix: each trial's firewall report", ""]
    lines += [str(r["report_md"]) for r in rows]
    text = "\n".join(lines) + "\n"
    target.write_text(text, encoding="utf-8")
    return f"written {target.name}: {len(rows)} trials, survivors {survivors or 'none'}"
