"""P19's 18 trials, run exactly as registered -- resumable, every run counted (QT-15 B).

The rules of the run (QT-15 B1), and where each is enforced:

* register order, each trial judged as registered: net, survivorship mark-down
  applied, 2x costs (P17), 1x shown beside it (firewall.score, stress=2);
* no change to any rule, parameter, universe, bar size or threshold: the rule
  comes from p19_rules.build(entry), which refuses parameters it does not
  implement; the universe from universe.for_register(entry);
* the Deflated Sharpe's N is the FULL count -- every selection trial logged before
  this batch began plus the batch's 18 -- for every trial, first to last;
* resumable: each result is written as it completes (journal + one file per
  trial). A rerun skips completed trials; one that started and never finished is
  logged "interrupted" and run again. Every run is logged, every trial counted;
* a DEFECT found mid-run: stop, fix with a test, then ``--new-batch "<defect>"``
  re-runs all 18 from the start; the old batch's trials stay in the count;
* holdout (B2): only a trial that PASSES walk-forward gets its one final run, on
  the sealed bars through HOLDOUT_END (data after 2026-10-10 stays sealed for the
  forward run, S12). It is logged as kind "holdout", never as a selection trial.

CLI: ``python -m qb2.research.p19_run [--new-batch REASON]``; the results page is
written by qb2.research.p19_results.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable, Sequence
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from qb2.data import access, universe
from qb2.research import (benchmark, fills, firewall, holdout, monte_carlo, p19_results,
                          preregister, trial_log)
from qb2.signals import p19_rules

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_DIR = REPO_ROOT / "data" / "qb2" / "p19_run"
STRESS = 2.0                                  # judged at 2x (P17); 1x shown beside it
HOLDOUT_END = date(2026, 10, 9)               # S12: what came after stays sealed
Say = Callable[[str], None]
Loader = Callable[..., tuple[list[firewall.NameData], list[str]]]


def trials(root: Path | None = None) -> list[dict[str, Any]]:
    """The 18 registered trials, in register order."""
    return [e for e in preregister.entries(root).values() if e["kind"] == "trial"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _journal(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "journal.jsonl"
    if not path.is_file():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _note(run_dir: Path, **row: Any) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / "journal.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"at": _now(), **row}, sort_keys=True) + "\n")


def state(run_dir: Path) -> tuple[int, int, set[str], set[str]]:
    """(batch, counted before it, done ids, started-but-unfinished ids)."""
    rows = _journal(run_dir)
    batches = [r for r in rows if r["event"] == "batch"]
    if not batches:
        return 0, 0, set(), set()
    batch = int(batches[-1]["batch"])
    mine = [r for r in rows if r.get("batch") == batch]
    done = {str(r["id"]) for r in mine if r["event"] == "done"}
    started = {str(r["id"]) for r in mine if r["event"] == "started"} - done
    return batch, int(batches[-1]["counted_before"]), done, started


def sealed_names(data: Sequence[firewall.NameData], interval: str,
                 final: holdout.HoldoutPass,
                 clean_root: Path | None = None) -> list[firewall.NameData]:
    """Each name's unsealed bars (warm-up only) + its sealed bars to HOLDOUT_END."""
    out = []
    for name in data:
        try:
            sealed = holdout.research_bars(name.symbol, interval, name.market,
                                           holdout=final, clean_root=clean_root)
        except access.AccessRefused:
            continue
        sealed = sealed[pd.Series(sealed.index.date, index=sealed.index)
                        .le(HOLDOUT_END).to_numpy()]
        if len(sealed) < 2:
            continue
        bars = pd.concat([name.bars, sealed])
        out.append(firewall.NameData(name.symbol, name.market, name.instrument, bars,
                                     fills.schedule(bars.index, interval, name.market),
                                     name.bet))
    return out


def run(*, new_batch: str | None = None, run_dir: Path = RUN_DIR,
        log_path: Path = trial_log.DEFAULT_TRIAL_LOG,
        require: Callable[[str], preregister.Registered] = preregister.require,
        load: Loader = firewall.load, score: Callable[..., firewall.FirewallResult]
        = firewall.score, open_final: Callable[..., holdout.HoldoutPass]
        = holdout.open_final_run, bench: Callable[[date, date], benchmark.Benchmark]
        = benchmark.over, n_null: int = monte_carlo.DEFAULT_TRIALS,
        register_root: Path | None = None, clean_root: Path | None = None,
        say: Say = print) -> list[dict[str, Any]]:
    batch, counted_before, done, started = state(run_dir)
    listed = trials(register_root)
    if batch == 0 or new_batch is not None:
        batch, counted_before = batch + 1, trial_log.count_selection_trials(log_path)[0]
        done, started = set(), set()
        _note(run_dir, event="batch", batch=batch, counted_before=counted_before,
              reason=new_batch or "first run", trials=len(listed))
    n_full = counted_before + len(listed)
    say(f"P19 batch {batch}: {len(done)}/{len(listed)} done; Deflated Sharpe over "
        f"N = {n_full} ({counted_before} before this batch + {len(listed)})")
    cache: dict[str, tuple[list[firewall.NameData], list[str], list[dict[str, Any]]]] = {}
    out_dir = run_dir / f"batch{batch}"
    for entry in listed:
        cid, interval = str(entry["id"]), str(entry["bar_size"])
        if cid in done:
            continue
        if cid in started:
            _note(run_dir, event="interrupted", batch=batch, id=cid)
            say(f"  {cid}: interrupted last time -- run again, logged")
        _note(run_dir, event="started", batch=batch, id=cid)
        t0 = time.monotonic()
        token = require(cid)
        key = str(entry["universe"]).split(":", 1)[0] + "/" + interval
        if key not in cache:
            names = universe.for_register(token.entry)
            data, skipped = load(interval, entries=names, clean_root=clean_root)
            cache[key] = (data, skipped, names)
        data, skipped, names = cache[key]
        make = (lambda e: lambda name: p19_rules.build(e))(token.entry)
        result = score(token, make, data, interval=interval, stress=STRESS,
                       skipped=skipped, n_null=n_null, bench=bench, log_path=log_path,
                       n_trials=n_full)
        record = p19_results.summarise(result, names)
        if result.verdict.passed:
            record["holdout"] = _holdout(token, make, data, interval, n_null, n_full,
                                         open_final, bench, log_path, clean_root, score)
        record.update(batch=batch, seconds=round(time.monotonic() - t0, 1),
                      register_commit=token.commit)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{cid}.json").write_text(json.dumps(record, indent=1, default=str),
                                             encoding="utf-8")
        _note(run_dir, event="done", batch=batch, id=cid, verdict=record["verdict"],
              holdout=(record.get("holdout") or {}).get("verdict"),
              seconds=record["seconds"])
        say(f"  {cid}: {record['verdict']} ({record['seconds']:.0f}s)"
            + (f" · holdout {record['holdout']['verdict']}" if "holdout" in record else ""))
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(out_dir.glob("*.json"))]


def _holdout(token: preregister.Registered, make: Callable[..., Any],
             data: Sequence[firewall.NameData], interval: str, n_null: int, n_full: int,
             open_final: Callable[..., holdout.HoldoutPass],
             bench: Callable[[date, date], benchmark.Benchmark], log_path: Path,
             clean_root: Path | None,
             score: Callable[..., firewall.FirewallResult]) -> dict[str, Any]:
    """The ONE final run. Logged as kind "holdout" (never a selection trial)."""
    final = open_final(token, log_path=log_path)
    sealed = sealed_names(data, interval, final, clean_root)
    result = score(token, make, sealed, interval=interval, stress=STRESS, n_null=n_null,
                   bench=bench, log_path=None, n_trials=n_full, final=final)
    out = p19_results.summarise(result, [])
    trial_log.log_trial({
        "utc_time": _now(), "kind": trial_log.HOLDOUT, "candidate_id": token.id,
        "register_commit": token.commit, "strategy_name": str(token.entry["rule"]),
        "params": {"stress": STRESS, "verdict": out["verdict"], "through":
                   HOLDOUT_END.isoformat(), "p_value": out["p"], "dsr": out["dsr"]},
        "metric_name": "holdout_sharpe_per_bar_marked", "metric_value": out["sharpe"],
        "n_bars": out["bars"]}, path=log_path)
    return out


RESULTS_PAGE = REPO_ROOT / "docs" / "research" / "P19_results_2026-10.md"


def write_page(run_dir: Path = RUN_DIR, target: Path = RESULTS_PAGE,
               log_path: Path = trial_log.DEFAULT_TRIAL_LOG) -> str:
    """The results page for the newest batch, rebuilt from the files on disk."""
    batch, counted_before, done, _ = state(run_dir)
    listed = trials()
    folder = run_dir / f"batch{batch}"
    by_id = {p.stem: json.loads(p.read_text(encoding="utf-8"))
             for p in folder.glob("*.json")}
    records = [by_id[str(e["id"])] for e in listed if str(e["id"]) in by_id]
    universes = {str(e["id"]): str(e["universe"]).split(":", 1)[0] for e in listed}
    rows = _journal(run_dir)
    runs = [r for r in rows if r["event"] == "batch"]
    interrupted = sum(1 for r in rows if r["event"] == "interrupted")
    survivors = [r["id"] for r in records if r["verdict"] == "PASS"
                 and (r.get("holdout") or {}).get("verdict") == "PASS"]
    total, seen = trial_log.count_selection_trials(log_path)
    intro = [
        "# P19 results, 2026-10 (QT-15 B: the 18 pre-registered trials)", "",
        f"Batch {batch} of {len(runs)}; {len(records)} of {len(listed)} trials complete; "
        f"{interrupted} interrupted run(s) logged. Register commit "
        f"`{str(records[0]['register_commit'])[:7] if records else '?'}`; every trial "
        "run exactly as "
        "registered (docs/research/preregistered.json).", "",
        "**Survived (walk-forward PASS and holdout PASS): "
        + (", ".join(survivors) if survivors else "none") + ".**", "",
        "How each trial is judged: net after 2× costs with the survivorship mark-down, "
        "compounded (QT-15 A1), against VWRP over the same dates; 1× shown beside it. "
        "PASS needs all three: better than the coin-flip null (p < 0.05), Deflated "
        "Sharpe ≥ 0.95, and a higher return than VWRP. INSUFFICIENT (fewer than 30 "
        "out-of-sample trades or bars) is its own answer, never a PASS.", "",
        f"Trial count used for deflation: **N = {counted_before + len(listed)}** "
        f"({counted_before} selection trials before this batch + {len(listed)}). qb2's "
        f"trial log now counts {total} selection trials ({seen['drills_excluded']} "
        f"drills and {seen['holdout_excluded']} holdout lines excluded).", "",
        f"Runtime: {sum(float(r.get('seconds', 0)) for r in records) / 60:.1f} minutes "
        f"of trial time ({runs[-1]['at']} start).",
    ]
    text = p19_results.page(records, universes, intro)
    target.write_text(text, encoding="utf-8")
    return text


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--new-batch", metavar="DEFECT", default=None,
                        help="re-run all 18 from the start, naming the defect fixed")
    parser.add_argument("--page-only", action="store_true",
                        help="rewrite the results page from what is on disk")
    args = parser.parse_args(argv)
    t0 = time.monotonic()
    if not args.page_only:
        records = run(new_batch=args.new_batch)
        print(f"{len(records)} results this batch; wall {time.monotonic() - t0:.0f}s")
    write_page()
    print(f"written {RESULTS_PAGE.relative_to(REPO_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
