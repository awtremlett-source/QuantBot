"""S9 batch 1: the six advisor rules, run exactly as registered -- resumable (QT-19 B3-B4).

Same rules of the run as S6 batch 1 (qb2/research/s6_run.py, whose helpers this uses):

* register order (A-01..A-06); each judged by firewall.score at 2x costs (1x beside
  it), N = 42 + 6 = 48 for the Deflated Sharpe; one arm, the whole advisor list; the
  luck bar from random-rank books built by the trial's own rules (rank_null.py, QT-21 C);
* the rule is a_rules.of(entry) and the book advisor_book.build -- each refuses what
  it does not implement; the book is rebuilt on data cut at three mid-month dates and
  refused if its past changed (advisor_book.causal);
* SAVE AS IT GOES: a finished trial is written atomically to
  docs/research/A_batch1_runs/run<N>/<id>.json with the code commit and fingerprint
  (a), THEN its trial-log line (kind firewall, counted 1). A restart skips finished
  trials; one started and never finished is logged "interrupted" (counted 0) and run
  again. A code commit or fingerprint different from the run's start is a DEFECT;
* HOLDOUT: only a walk-forward PASS gets its single run (sealed daily year to
  2026-10-09, the book carried on from the unsealed years), fingerprint (b) first.

CLI: ``python -m qb2.research.advisor_run [--max N] [--new-run DEFECT] [--page-only]``
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from qb2.research import (advisor_book, advisor_data, advisor_results, firewall, holdout,
                          p19_results, preregister, rank_null, trial_log)
from qb2.research.advisor_book import Held as Held      # re-exported: advisor_run.Held
from qb2.research.s6_run import Defect, atomic_write, code_commit, journal, note, start
from qb2.signals import a_rules

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_DIR = REPO_ROOT / "docs" / "research" / "A_batch1_runs"
PAGE = REPO_ROOT / "docs" / "research" / "A_batch1_results_2026-10.md"
STRESS, N_TRIALS, N_NULL = 2.0, 48, 200
CODE_PATHS = ("qb2", "requirements-qb2.txt", "docs/research/preregistered.json",
              "docs/research/bet_groups.json", "docs/universe/advisor-universe-v1-2026-10-01.json")


def trials(root: Path | None = None) -> list[dict[str, Any]]:
    return [e for e in preregister.entries(root).values()
            if e["kind"] == "trial" and str(e["id"]).startswith("A-")]


def cuts(data: Sequence[firewall.NameData]) -> list[date]:
    lo = min(pd.Timestamp(d.bars.index[0]).tz_localize(None) for d in data)
    hi = max(pd.Timestamp(d.bars.index[-1]).tz_localize(None) for d in data)
    return [(lo + (hi - lo) * q).date().replace(day=15) for q in (0.25, 0.5, 0.75)]


def book_for(entry: Mapping[str, Any], data: Sequence[firewall.NameData], *,
             final: holdout.HoldoutPass | None = None, clean_root: Path | None = None,
             ) -> tuple[advisor_book.Book, list[firewall.NameData]]:
    """The registered rule's book on these names (checked causal), and the names with
    their slot weights."""
    rule = a_rules.of(entry)
    s = advisor_book.Settings.of(entry["parameters"], rule.lookback, rule.ascending)
    vix = advisor_data.vix(final, clean_root)
    on = advisor_data.market_filter(final, clean_root) if rule.market_filter else None

    def make(names: Sequence[firewall.NameData]) -> advisor_book.Book:
        return advisor_book.build(s, names, rank_null.rule_values(rule, names), vix=vix, market_on=on)

    book = make(data)
    advisor_book.causal(make, data, book, cuts(data))
    return book, [replace(n, weight=book.weights[n.symbol]) for n in data]


def score(token: preregister.Registered, data: Sequence[firewall.NameData],
          book: advisor_book.Book, *, stress: float = STRESS, skipped: Sequence[str] = (),
          final: holdout.HoldoutPass | None = None, log_path: Path | None = None,
          n_null: int = N_NULL) -> firewall.FirewallResult:
    index = {d.symbol: pd.DatetimeIndex(d.bars.index) for d in data}

    def make(name: firewall.NameData) -> Held:
        return Held(name.symbol, index[name.symbol], book.decisions[name.symbol])
    nulls = rank_null.Nulls(token.entry, data, vix=advisor_data.vix(final), cuts=cuts(data))
    return firewall.score(token, make, data, interval="1d", stress=stress, skipped=skipped,
                          n_null=n_null, log_path=log_path, n_trials=N_TRIALS, final=final,
                          skill_free=nulls.draw)


def summary(token: preregister.Registered, result: firewall.FirewallResult,
            data: Sequence[firewall.NameData], book: advisor_book.Book) -> dict[str, Any]:
    return {**p19_results.summarise(result, []), **advisor_results.extras(result, data, book),
            "rule_name": str(token.entry["name"]), "register_commit": token.commit}


def _log_line(record: Mapping[str, Any], token: preregister.Registered, run: int) -> None:
    trial_log.log_trial({
        "utc_time": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"),
        "kind": trial_log.FIREWALL, "candidate_id": token.id, "register_commit": token.commit,
        "strategy_name": str(token.entry["rule"]),
        "params": {"stress": STRESS, "n_null": N_NULL, "seed": 0, "verdict": record["verdict"],
                   "p_value": record["p"], "null": "turnover-matched", "dsr": record["dsr"],
                   "trades": record["trades"], "benchmark": record["vwrp_symbol"],
                   "advisor_run": run},
        "metric_name": "oos_sharpe_per_bar_marked", "metric_value": record["sharpe"],
        "n_bars": record["n_bars"]})


def _logged(cid: str, run: int) -> bool:
    return any(r.get("candidate_id") == cid and r.get("kind") == trial_log.FIREWALL and
               (r.get("params") or {}).get("advisor_run") == run for r in trial_log.read_trials())


def _holdout(token: preregister.Registered, data: Sequence[firewall.NameData], folder: Path,
             fp_b: str, run_dir: Path, run: int) -> dict[str, Any]:
    path = folder / f"{token.id}.holdout.json"
    if path.is_file():
        return dict(json.loads(path.read_text(encoding="utf-8")))
    if advisor_data.fingerprints()["b"] != fp_b:
        raise Defect("fingerprint (b) moved before the holdout run")
    try:
        final = holdout.open_final_run(token)
    except holdout.Sealed as why:              # opened before, no file: never repeated
        out = {"verdict": "NOT RUN", "reasons": [f"holdout already opened ({why})"]}
        atomic_write(path, out)
        return out
    note(run_dir, event="holdout_opened", run=run, id=token.id)
    sealed = advisor_data.sealed(data, final)
    book, sealed = book_for(token.entry, sealed, final=final)
    result = score(token, sealed, book, final=final)
    out = summary(token, result, sealed, book)
    atomic_write(path, out)                    # saved before anything else is done
    trial_log.log_trial({
        "utc_time": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"),
        "kind": trial_log.HOLDOUT, "candidate_id": token.id, "register_commit": token.commit,
        "strategy_name": str(token.entry["rule"]),
        "params": {"stress": STRESS, "verdict": out["verdict"], "through": "2026-10-09",
                   "p_value": out["p"], "dsr": out["dsr"], "advisor_run": run},
        "metric_name": "holdout_sharpe_per_bar_marked", "metric_value": out["sharpe"],
        "n_bars": out["n_bars"]})
    return out


def run(*, new_run: str | None = None, limit: int | None = None, run_dir: Path = RUN_DIR,
        say: Callable[[str], None] = print) -> int:
    commit, prints = code_commit(REPO_ROOT, CODE_PATHS), advisor_data.fingerprints()
    number = start(run_dir, new_run, commit, prints)
    folder, rows = run_dir / f"run{number}", [r for r in journal(run_dir) if r.get("run") == number]
    data, skipped, counts = advisor_data.load()
    say(f"run {number}: {len(data)} names, {advisor_data.counts_text(counts)}")
    ran = 0
    for entry in trials():
        cid, token = str(entry["id"]), preregister.require(str(entry["id"]))
        path = folder / f"{cid}.json"
        if path.is_file():                     # finished: skipped, never re-run
            done = json.loads(path.read_text(encoding="utf-8"))
            if (done["code_commit"], done["fp_a"]) != (commit, prints["a"]):
                raise Defect(f"{cid}: finished under another commit or data")
            if not _logged(cid, number):
                _log_line(done, token, number)
        elif limit is not None and ran >= limit:
            break
        else:
            if any(r["event"] == "started" and r.get("id") == cid for r in rows):
                note(run_dir, event="interrupted", run=number, id=cid,
                     note="interrupted, no result seen (counted 0)")
            note(run_dir, event="started", run=number, id=cid)
            t0 = time.monotonic()
            book, weighted = book_for(token.entry, data)
            result = score(token, weighted, book, skipped=skipped)
            done = {**summary(token, result, weighted, book), "code_commit": commit,
                    "fp_a": prints["a"], "dividends": counts, "run": number,
                    "seconds": round(time.monotonic() - t0, 1)}
            atomic_write(path, done)           # the result exists BEFORE it is counted
            _log_line(done, token, number)
            note(run_dir, event="done", run=number, id=cid, verdict=done["verdict"],
                 seconds=done["seconds"])
            ran += 1
            say(f"  {cid}: {done['verdict']} ({done['seconds']:.0f}s)")
        if done["verdict"] == "PASS" and not done.get("holdout"):
            done["holdout"] = _holdout(token, data, folder, prints["b"], run_dir, number)
            atomic_write(path, done)
            note(run_dir, event="holdout_done", run=number, id=cid,
                 verdict=done["holdout"]["verdict"])
    if advisor_data.fingerprints() != prints:
        note(run_dir, event="defect", run=number, moved=["fingerprint at the end"])
        raise Defect("a data fingerprint moved during the run")
    note(run_dir, event="fingerprints_end", run=number, fp_a=prints["a"], fp_b=prints["b"])
    return number


def write_page(run_dir: Path = RUN_DIR, target: Path = PAGE) -> str:
    starts = [r for r in journal(run_dir) if r["event"] == "start"]
    number = int(starts[-1]["run"]) if starts else 0
    records = advisor_results.load(run_dir / f"run{number}", [str(e["id"]) for e in trials()])
    passed = [r["id"] for r in records if r["verdict"] == "PASS"
              and (r.get("holdout") or {}).get("verdict") == "PASS"]
    intro = ["# S9 advisor batch 1 — results, 2026-10 (built QT-19, run QT-21)", "",
             f"Run {number}; {len(records)} of {len(trials())} trials complete; register commit "
             f"`{str(records[0]['register_commit'])[:7] if records else '?'}`. Every trial run "
             "exactly as registered (docs/research/preregistered.json).", "",
             f"**Survived (walk-forward PASS and holdout PASS): {', '.join(passed) or 'none'}.**",
             "", "Judged on net after 2× costs with the survivorship mark-down and dividends "
             "credited, compounded, against D3 over the same dates (VWRP; VWRL with dividends "
             "before VWRP's first traded close, 2019-08-13 since QT-21). PASS needs the luck test "
             "(p < 0.05) and a positive net mean, Deflated Sharpe ≥ 0.95 at N = 48 (luck bar from "
             "random-rank books), and beating D3; one bar over 25% of the variance = "
             "INSUFFICIENT. Dividends: "
             + (advisor_data.counts_text(records[0]["dividends"]) if records else "—") + "."]
    text = advisor_results.page(records, intro)
    target.write_text(text, encoding="utf-8")
    return text


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--new-run", metavar="DEFECT", default=None)
    parser.add_argument("--max", type=int, default=None, help="run at most N new trials")
    parser.add_argument("--page-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not args.page_only:
            run(new_run=args.new_run, limit=args.max)
    except Defect as why:
        print(f"DEFECT -- STOP: {why}")
        return 2
    write_page()
    print(f"written {PAGE.relative_to(REPO_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
