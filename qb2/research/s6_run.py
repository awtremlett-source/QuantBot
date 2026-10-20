"""S6 batch 1: the 24 registered trials, run exactly as registered -- resumable (QT-18 B2-B3).

The rules of the run, and where each is enforced:

* register order; each trial judged as registered by firewall.score at 2x costs
  (1x beside it), N = 18 + 24 = 42 for the Deflated Sharpe, nothing per arm;
* the rule is s6_rules.maker(entry, data), which refuses parameters it does not
  implement; the arm's names come from the entry's own ``sleeves``;
* SAVE AS IT GOES: a finished trial is written atomically (temp file, then rename)
  to docs/research/S6_batch1_runs/<id>.json with the code commit and fingerprint (a),
  THEN its trial-log line is appended (kind firewall, counted 1). A restart appends
  a line missing for a finished file, so each finished trial is counted exactly once;
* RESTART: finished trials whose code commit and fingerprint (a) match are skipped;
  one started and never finished is logged "interrupted, no result seen" (journal,
  counted 0) and run again from scratch. A code commit, fingerprint (a) or (b)
  different from the run's start is a DEFECT: stop and report;
* HOLDOUT: only a walk-forward PASS gets its single run, on the sealed bars to
  2026-10-09, fingerprint (b) checked first, saved atomically before anything else,
  never repeated (holdout.open_final_run refuses a second look).

CLI: ``python -m qb2.research.s6_run [--max N] [--new-run DEFECT] [--page-only]``
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from qb2.data import data_fingerprint, universe
from qb2.research import (firewall, holdout, p19_results, p19_run, preregister, s6_results,
                          trial_log)
from qb2.signals import s6_rules
from qb2.tools.governor import assert_capped

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_DIR = REPO_ROOT / "docs" / "research" / "S6_batch1_runs"
STRESS, N_TRIALS, N_NULL = 2.0, 42, 200
CODE_PATHS = ("qb2", "requirements-qb2.txt", "docs/research/preregistered.json",
              "docs/research/bet_groups.json", "docs/universe/bot-universe-v1-2026-10-01.json")


class Defect(RuntimeError):
    """The code or the data moved under a run: stop, fix with a test, re-run all 24."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def atomic_write(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(record, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


def journal(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "journal.ndjson"
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()
            if x.strip()] if path.is_file() else []


def note(run_dir: Path, **row: Any) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / "journal.ndjson").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"at": _now(), **row}, sort_keys=True) + "\n")


def code_commit(root: Path = REPO_ROOT, paths: Sequence[str] = CODE_PATHS) -> str:
    """The last commit touching the code and its inputs; refused if they are dirty."""
    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                              text=True, check=True).stdout.strip()
    dirty = git("status", "--porcelain", "--", *paths)
    if dirty:
        raise Defect(f"code paths have uncommitted changes:\n{dirty}")
    return git("log", "-1", "--format=%H", "--", *paths)


def fingerprints(clean_root: Path | None = None) -> dict[str, str]:
    entries = universe.bot_entries()
    names = [str(e["yfinance"]) for e in entries]
    shares = [str(e["yfinance"]) for e in entries if str(e["kind"]) != "ETF"]
    return {"a": data_fingerprint.trial_data(names, shares, clean_root),
            "b": data_fingerprint.holdout_data(names, clean_root)}


def trials(root: Path | None = None) -> list[dict[str, Any]]:
    return [e for e in preregister.entries(root).values()
            if e["kind"] == "trial" and str(e["id"]).startswith("S6-")]


def arm_entries(entry: Mapping[str, Any]) -> list[dict[str, Any]]:
    sleeves = set(entry["parameters"]["sleeves"])
    return [e for e in universe.for_register(entry) if e["sleeve"] in sleeves]


def start(run_dir: Path, new_run: str | None, commit: str, prints: dict[str, str]) -> int:
    """The run number; a moved commit or fingerprint since its start is a DEFECT."""
    starts = [r for r in journal(run_dir) if r["event"] == "start"]
    if starts and new_run is None:
        first = starts[-1]
        moved = [k for k, now, then in (("code commit", commit, first["code_commit"]),
                                        ("fingerprint (a)", prints["a"], first["fp_a"]),
                                        ("fingerprint (b)", prints["b"], first["fp_b"]))
                 if now != then]
        if moved:
            note(run_dir, event="defect", run=first["run"], moved=moved)
            raise Defect(f"{', '.join(moved)} differ(s) from run {first['run']}'s start")
        return int(first["run"])
    run = len(starts) + 1
    note(run_dir, event="start", run=run, code_commit=commit, fp_a=prints["a"],
         fp_b=prints["b"], reason=new_run or "first run",
         counted_before=trial_log.count_selection_trials()[0])
    return run


def _log_line(record: Mapping[str, Any], token: preregister.Registered, run: int) -> None:
    """The firewall's own trial-log line, written AFTER the result file exists."""
    trial_log.log_trial({
        "utc_time": _now(), "kind": trial_log.FIREWALL, "candidate_id": token.id,
        "register_commit": token.commit, "strategy_name": str(token.entry["rule"]),
        "params": {"stress": STRESS, "n_null": N_NULL, "seed": 0, "verdict": record["verdict"],
                   "p_value": record["p"], "null": "turnover-matched", "dsr": record["dsr"],
                   "trades": record["trades"], "benchmark": record["vwrp_symbol"],
                   "s6_run": run},
        "metric_name": "oos_sharpe_per_bar_marked", "metric_value": record["sharpe"],
        "n_bars": record["n_bars"]})


def _logged(cid: str, run: int) -> bool:
    return any(r.get("candidate_id") == cid and r.get("kind") == trial_log.FIREWALL
               and (r.get("params") or {}).get("s6_run") == run for r in trial_log.read_trials())


def _holdout(token: preregister.Registered, entry: Mapping[str, Any],
             data: Sequence[firewall.NameData], run_dir: Path, run: int,
             fp_b: str) -> dict[str, Any]:
    path = run_dir / f"run{run}" / f"{token.id}.holdout.json"
    if path.is_file():
        return dict(json.loads(path.read_text(encoding="utf-8")))
    if fingerprints()["b"] != fp_b:
        raise Defect("fingerprint (b) moved before the holdout run")
    try:
        final = holdout.open_final_run(token)
    except holdout.Sealed as why:              # opened before, no file: never repeated
        out = {"verdict": "NOT RUN", "reasons": [f"holdout already opened, no result saved "
                                                 f"({why}); never repeated"]}
        atomic_write(path, out)
        return out
    note(run_dir, event="holdout_opened", run=run, id=token.id)
    sealed = p19_run.sealed_names(data, "1h", final)
    result = firewall.score(token, s6_rules.maker(entry, sealed), sealed, interval="1h",
                            stress=STRESS, n_null=N_NULL, log_path=None, n_trials=N_TRIALS,
                            final=final)
    out = p19_results.summarise(result, [])
    atomic_write(path, out)                    # saved before anything else is done
    trial_log.log_trial({
        "utc_time": _now(), "kind": trial_log.HOLDOUT, "candidate_id": token.id,
        "register_commit": token.commit, "strategy_name": str(entry["rule"]),
        "params": {"stress": STRESS, "verdict": out["verdict"], "through": "2026-10-09",
                   "p_value": out["p"], "dsr": out["dsr"], "s6_run": run},
        "metric_name": "holdout_sharpe_per_bar_marked", "metric_value": out["sharpe"],
        "n_bars": out["bars"]})
    return out


def run(*, new_run: str | None = None, limit: int | None = None, run_dir: Path = RUN_DIR,
        say: Any = print) -> int:
    commit, prints = code_commit(), fingerprints()
    number = start(run_dir, new_run, commit, prints)
    folder = run_dir / f"run{number}"
    rows = [r for r in journal(run_dir) if r.get("run") == number]
    cache: dict[str, tuple[list[firewall.NameData], list[str], list[dict[str, Any]]]] = {}

    def arm(entry: Mapping[str, Any]) -> tuple[list[firewall.NameData], list[str],
                                               list[dict[str, Any]]]:
        key = ",".join(entry["parameters"]["sleeves"])
        if key not in cache:
            names = arm_entries(entry)
            cache[key] = (*firewall.load("1h", entries=names), names)
        return cache[key]

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
                say(f"  {cid}: interrupted last time -- run again from scratch")
            note(run_dir, event="started", run=number, id=cid)
            t0 = time.monotonic()
            data, skipped, names = arm(entry)
            result = firewall.score(token, s6_rules.maker(entry, data), data, interval="1h",
                                    stress=STRESS, skipped=skipped, n_null=N_NULL,
                                    log_path=None, n_trials=N_TRIALS)
            done = {**p19_results.summarise(result, names), "arm": entry["parameters"]["arm"],
                    "code_commit": commit, "fp_a": prints["a"], "register_commit": token.commit,
                    "run": number, "seconds": round(time.monotonic() - t0, 1)}
            atomic_write(path, done)           # the result exists BEFORE it is counted
            _log_line(done, token, number)
            note(run_dir, event="done", run=number, id=cid, verdict=done["verdict"],
                 seconds=done["seconds"])
            ran += 1
            say(f"  {cid}: {done['verdict']} ({done['seconds']:.0f}s)")
        if done["verdict"] == "PASS" and not done.get("holdout"):
            done["holdout"] = _holdout(token, entry, arm(entry)[0], run_dir, number, prints["b"])
            atomic_write(path, done)
            note(run_dir, event="holdout_done", run=number, id=cid, verdict=done["holdout"]["verdict"])
            say(f"  {cid}: holdout {done['holdout']['verdict']}")
    return number


def main(argv: Sequence[str] | None = None) -> int:
    assert_capped()                    # QT-23R: never outside the operator's cap
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
    print(s6_results.write_page(RUN_DIR, trials()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
