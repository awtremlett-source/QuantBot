"""S6 batch 2: the 6 registered combined-model trials, run exactly as registered -- resumable
(QT-27 F; register commit 6be96dad).

The rules of the run are batch 1's, through s6_run's own helpers (journal, atomic write, code
commit, start/DEFECT), not copies:

* register order, CM-L-US ... CM-G-MIX; each trial = cm_arm.score at 2x costs (1x beside it),
  200 null runs, seed 0, the Deflated Sharpe's N floored at 56 + 6 = 62; an entry whose
  parameters are not exactly what this code implements is refused (``check_entry``);
* SAVE AS IT GOES: a finished trial is written atomically to docs/research/S6_batch2_runs/
  run<k>/<id>.json with the code commit and fingerprints, THEN its trial-log line (kind
  firewall, counted 1). A restart appends a line missing for a finished file;
* RESTART: finished trials under the same commit and fingerprint (a) are skipped; one started
  and never finished is logged "interrupted, no result seen" (journal, counted 0) and run again;
  a moved code commit or fingerprint is a DEFECT: stop and report;
* fingerprints: batch 1's (a) and (b) over the agreed 50, plus ^VIX's 1h bars (feature F15);
* HOLDOUT: only a walk-forward PASS, once, by holdout.open_final_run (cm_arm.load_final);
* box rule 0.3: before each trial it waits for the scheduled recorder runs (run_window).

CLI: ``python -m qb2.research.cm_run [--max N] [--new-run DEFECT] [--page-only]``
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from qb2.data import data_fingerprint, universe
from qb2.model import combined
from qb2.research import (cm_arm, cm_results, holdout, p19_results, preregister, s6_run,
                          trial_log)
from qb2.tools import run_window
from qb2.tools.governor import assert_capped

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_DIR = REPO_ROOT / "docs" / "research" / "S6_batch2_runs"
Defect = s6_run.Defect
WALK = {"window": "expanding", "min_train_sessions": combined.MIN_TRAIN_SESSIONS,
        "oos_not_before": combined.OOS_FROM.isoformat(), "refit_every_sessions": combined.REFIT_EVERY,
        "embargo_sessions": combined.EMBARGO, "oos_end": combined.OOS_END.isoformat()}
SETTINGS = {"ridge": {"scaler": "StandardScaler, fit on the training fold only", "Ridge": {"alpha": 1.0}},
            "gbt": {"HistGradientBoostingRegressor": combined.GBT, "scaler": None,
                    "other settings": "scikit-learn 1.8.0's defaults"}}


def check_entry(entry: Mapping[str, Any]) -> str:
    """The entry's model -- refused unless every parameter is what this code implements."""
    p, model = entry["parameters"], str(entry["parameters"].get("model"))
    want = {"walk_forward": WALK, "decide_at_bar": 1, "top": 3, "stop": True, "stop_k": 3.0,
            "atr_period": 14, "stake_gbp": 300.0, "model_settings": SETTINGS.get(model)}
    wrong = {k: p.get(k) for k, v in want.items() if p.get(k) != v}
    names = [str(f).split(" ", 1)[0] for f in p.get("features", [])]
    if wrong or model not in combined.MODELS or names != [f"F{i}" for i in range(1, 18)] or \
            entry["bar_size"] != "1h":
        raise ValueError(f"{entry['id']}: {wrong or 'model/features/bar size'} not as this code implements")
    return model


def require_trial(cid: str) -> preregister.Registered:
    """A batch-2 trial's token; an unregistered id, or a drill, is refused."""
    token = preregister.require(cid)
    if token.is_drill or token.entry["kind"] != "trial" or not cid.startswith("CM-"):
        raise preregister.NotRegistered(f"{cid!r} is not a registered S6 batch 2 trial")
    return token


def trials(root: Path | None = None) -> list[dict[str, Any]]:
    return [e for e in preregister.entries(root).values()
            if e["kind"] == "trial" and str(e["id"]).startswith("CM-")]


def fingerprints(clean_root: Path | None = None) -> dict[str, str]:
    entries = universe.bot_entries()
    names = [str(e["yfinance"]) for e in entries] + [cm_arm.VIX]
    shares = [str(e["yfinance"]) for e in entries if str(e["kind"]) != "ETF"]
    return {"a": data_fingerprint.trial_data(names, shares, clean_root),
            "b": data_fingerprint.holdout_data(names, clean_root)}


def _log_line(record: Mapping[str, Any], token: preregister.Registered, run: int) -> None:
    trial_log.log_trial({
        "utc_time": s6_run._now(), "kind": trial_log.FIREWALL, "candidate_id": token.id,
        "register_commit": token.commit, "strategy_name": str(token.entry["rule"]),
        "params": {"stress": cm_arm.STRESS, "n_null": cm_arm.N_NULL, "seed": 0, "verdict": record["verdict"],
                   "p_value": record["p"], "null": "turnover-matched", "dsr": record["dsr"],
                   "trades": record["trades"], "benchmark": record["vwrp_symbol"], "cm_run": run},
        "metric_name": "oos_sharpe_per_bar_marked", "metric_value": record["sharpe"],
        "n_bars": record["n_bars"]})


def _logged(cid: str, run: int) -> bool:
    return any(r.get("candidate_id") == cid and r.get("kind") == trial_log.FIREWALL
               and (r.get("params") or {}).get("cm_run") == run for r in trial_log.read_trials())


def _holdout(token: preregister.Registered, entry: Mapping[str, Any], arm: cm_arm.Arm, model: str,
             run_dir: Path, run: int, fp_b: str) -> dict[str, Any]:
    path = run_dir / f"run{run}" / f"{token.id}.holdout.json"
    if path.is_file():
        return dict(json.loads(path.read_text(encoding="utf-8")))
    if fingerprints()["b"] != fp_b:
        raise Defect("fingerprint (b) moved before the holdout run")
    try:
        final = holdout.open_final_run(token)
    except holdout.Sealed as why:              # opened before, no file: never repeated
        out: dict[str, Any] = {"verdict": "NOT RUN", "reasons": [f"holdout already opened, no result saved ({why}); "
                                                                 "never repeated"]}
        s6_run.atomic_write(path, out)
        return out
    s6_run.note(run_dir, event="holdout_opened", run=run, id=token.id)
    result, extras = cm_arm.score(token, cm_arm.load_final(entry, arm, final), model, final=final)
    out = {**p19_results.summarise(result, []), "describe": extras}   # same dict[str, Any]
    s6_run.atomic_write(path, out)             # saved before anything else is done
    trial_log.log_trial({
        "utc_time": s6_run._now(), "kind": trial_log.HOLDOUT, "candidate_id": token.id,
        "register_commit": token.commit, "strategy_name": str(entry["rule"]),
        "params": {"stress": cm_arm.STRESS, "verdict": out["verdict"], "through": "2026-10-09",
                   "p_value": out["p"], "dsr": out["dsr"], "cm_run": run},
        "metric_name": "holdout_sharpe_per_bar_marked", "metric_value": out["sharpe"], "n_bars": out["bars"]})
    return out


def run(*, new_run: str | None = None, limit: int | None = None, run_dir: Path = RUN_DIR,
        say: Any = print) -> int:
    commit, prints = s6_run.code_commit(), fingerprints()
    number = s6_run.start(run_dir, new_run, commit, prints)
    folder = run_dir / f"run{number}"
    rows = [r for r in s6_run.journal(run_dir) if r.get("run") == number]
    cache: dict[str, cm_arm.Arm] = {}
    ran = 0
    for entry in trials():
        cid, model = str(entry["id"]), check_entry(entry)
        token = require_trial(cid)
        path = folder / f"{cid}.json"
        key = ",".join(entry["parameters"]["sleeves"])
        if path.is_file():                     # finished: skipped, never re-run
            done = json.loads(path.read_text(encoding="utf-8"))
            if (done["code_commit"], done["fp_a"]) != (commit, prints["a"]):
                raise Defect(f"{cid}: finished under another commit or data")
            if not _logged(cid, number):
                _log_line(done, token, number)
        elif limit is not None and ran >= limit:
            break
        else:
            run_window.wait_clear(say=say)     # box rule 0.3: never in a scheduled run's way
            if any(r["event"] == "started" and r.get("id") == cid for r in rows):
                s6_run.note(run_dir, event="interrupted", run=number, id=cid,
                            note="interrupted, no result seen (counted 0)")
                say(f"  {cid}: interrupted last time -- run again from scratch")
            s6_run.note(run_dir, event="started", run=number, id=cid)
            t0 = time.monotonic()
            if key not in cache:
                cache[key] = cm_arm.load(entry)
            result, extras = cm_arm.score(token, cache[key], model)
            done = {**p19_results.summarise(result, s6_run.arm_entries(entry)), "describe": extras,
                    "arm": entry["parameters"]["arm"], "model": model, "code_commit": commit,
                    "fp_a": prints["a"], "register_commit": token.commit, "run": number,
                    "seconds": round(time.monotonic() - t0, 1)}
            s6_run.atomic_write(path, done)    # the result exists BEFORE it is counted
            _log_line(done, token, number)
            s6_run.note(run_dir, event="done", run=number, id=cid, verdict=done["verdict"],
                        seconds=done["seconds"])
            ran += 1
            say(f"  {cid}: {done['verdict']} ({done['seconds']:.0f}s)")
        if done["verdict"] == "PASS" and not done.get("holdout"):
            if key not in cache:
                cache[key] = cm_arm.load(entry)
            done["holdout"] = _holdout(token, entry, cache[key], model, run_dir, number, prints["b"])
            s6_run.atomic_write(path, done)
            s6_run.note(run_dir, event="holdout_done", run=number, id=cid, verdict=done["holdout"]["verdict"])
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
    print(cm_results.write_page(RUN_DIR, trials()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
