"""One arm of batch 2: rows built, the model walked forward, the picks scored by the firewall
(QT-27 D1/F; register commit 6be96dad, CM-*).

``assemble`` is pure -- bars in, rows out -- so the look-ahead test runs it offline; ``load`` and
``load_final`` add the store. Rows: every (name, session) with a bar 1 and a previous session ->
the 17 features -> rows missing any dropped (counted) -> ELIGIBLE (the entry lands before E, by
the calendar) -> the target (cm_book.targets). The arm's sessions are the dates with an eligible
row; the refit schedule is combined.blocks over them. ``score`` hands the chosen picks to the
UNCHANGED firewall (firewall.score), each name's bars cut so it grades from the first
out-of-sample bar (cm_book.graded), N floored at the batch's full count.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qb2.model import combined, features
from qb2.research import cm_book, fills, firewall, holdout, p19_run, preregister, s6_run
from qb2.research.names import NameData

N_TRIALS, N_NULL, STRESS = 62, 200, 2.0
VIX = "^VIX"
Extra = Callable[[pd.DataFrame], pd.DataFrame]


@dataclass(slots=True)
class Arm:
    cid: str
    data: list[NameData]
    skipped: list[str]
    rows: pd.DataFrame
    dropped: int
    sessions: list[date]
    blocks: list[combined.Block]
    cost: dict[str, float]


def build_rows(data: Sequence[NameData], vix_bars: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Complete, eligible rows of every name (no target yet), and how many were dropped."""
    vix = features.vix_closes(vix_bars)
    parts = [features.name_rows(d.symbol, d.market, d.bars, vix) for d in data]
    rows = features.cross_section(pd.concat([p for p in parts if not p.empty], ignore_index=True))
    rows, dropped = features.complete(rows)
    can = {key: cm_book.entry_possible(key[1], key[0])
           for key in set(zip(rows["market"], rows["day"]))}
    ok = np.array([can[(m, d)] for m, d in zip(rows["market"], rows["day"])], dtype=bool)
    return rows[ok].reset_index(drop=True), dropped


def with_targets(rows: pd.DataFrame, data: Sequence[NameData], cid: str) -> pd.DataFrame:
    """Each row's target: its trade's gross return (cm_book.targets); NaN when no trade was made."""
    target = pd.Series(np.nan, index=rows.index, dtype=float)
    for name in data:
        mine = rows["symbol"] == name.symbol
        got = cm_book.targets(cid, name, set(rows.loc[mine, "day"]))
        target[mine] = [got.get(d, np.nan) for d in rows.loc[mine, "day"]]
    return rows.assign(target=target)


def assemble(cid: str, data: Sequence[NameData], vix_bars: pd.DataFrame, *, skipped: Sequence[str] = (),
             oos_from: date = combined.OOS_FROM, oos_end: date = combined.OOS_END,
             extra: Extra | None = None) -> Arm:
    rows, dropped = build_rows(data, vix_bars)
    if extra is not None:                          # the drills: a planted feature, or the shuffle
        rows = extra(rows)
    rows = with_targets(rows, data, cid)
    sessions = sorted(set(rows["day"]))
    trained = set(rows.loc[rows["target"].notna(), "day"])
    plan = combined.blocks(sessions, [d in trained for d in sessions], oos_from=oos_from, oos_end=oos_end)
    return Arm(cid, list(data), list(skipped), rows, dropped, sessions, plan,
               {d.symbol: cm_book.round_trip(d) for d in data})


def predictions(arm: Arm, model: str, columns: Sequence[str] = features.FEATURES,
                ) -> tuple[pd.Series, list[dict[str, Any]]]:
    return combined.walk_forward(arm.rows, model, columns, arm.sessions, arm.blocks)


def picks(arm: Arm, preds: pd.Series) -> set[tuple[str, date]]:
    scored = preds.dropna()
    frame = arm.rows.loc[scored.index, ["symbol", "market", "day"]].assign(prediction=scored)
    return cm_book.choose(frame, arm.cost)


def _may_enter(plan: fills.Schedule, i: int) -> bool:
    mask = plan.may_enter
    return True if mask is None else bool(mask[i])


def describe(arm: Arm, preds: pd.Series, chosen: set[tuple[str, date]],
             log: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Description only, never judged: picks, P15 refusals, days in cash, calibration."""
    oos = arm.rows.loc[preds.dropna().index]
    plans = {d.symbol: d.plan for d in arm.data}
    key = list(zip(oos["symbol"], oos["day"]))
    pick = np.asarray([k in chosen for k in key], dtype=np.bool_)
    allowed = np.asarray([_may_enter(plans[s], int(i)) for s, i in zip(oos["symbol"], oos["s0"])],
                         dtype=np.bool_)
    bought = oos[pick & allowed]
    days = sorted(set(oos["day"]))
    traded = set(bought["day"])
    real = bought["target"].dropna()
    return {"oos_sessions": len(days), "oos_first": str(days[0]) if days else None,
            "oos_last": str(days[-1]) if days else None, "rows_oos": len(oos), "rows_dropped": arm.dropped,
            "picked_lines": int(pick.sum()), "p15_refused": int((pick & ~allowed).sum()),
            "bought_lines": len(bought), "days_traded": len(traded), "days_in_cash": len(days) - len(traded),
            "mean_prediction_bought": float(preds.loc[bought.index].mean()) if len(bought) else None,
            "mean_realised_gross_bought": float(real.mean()) if len(real) else None,
            "fits": len(log), "train_rows_last_fit": int(log[-1]["train_rows"]) if log else 0}


def score(token: preregister.Registered, arm: Arm, model: str, *, stress: float = STRESS,
          n_null: int = N_NULL, n_trials: int = N_TRIALS, log_path: Path | None = None,
          columns: Sequence[str] = features.FEATURES, final: holdout.HoldoutPass | None = None,
          ) -> tuple[firewall.FirewallResult, dict[str, Any]]:
    """One registered model on one arm through the unchanged firewall; the figures it describes."""
    registered = preregister.check(token)
    preds, log = predictions(arm, model, columns)
    chosen = picks(arm, preds)
    if not arm.blocks:
        raise ValueError(f"{registered.id}: no out-of-sample session (too few training sessions)")
    first = arm.sessions[arm.blocks[0].first]
    data = arm.data if final is not None else [cm_book.graded(d, first) for d in arm.data]
    result = firewall.score(registered, cm_book.maker(registered.id, chosen), data, interval="1h",
                            stress=stress, skipped=arm.skipped, n_null=n_null, log_path=log_path,
                            n_trials=n_trials, final=final)
    return result, describe(arm, preds, chosen, log)


def load(entry: Mapping[str, Any], *, extra: Extra | None = None) -> Arm:
    """The arm from the store: firewall.load's names, ^VIX's unsealed 1h bars (F15 only)."""
    data, skipped = firewall.load("1h", entries=s6_run.arm_entries(entry))
    return assemble(str(entry["id"]), data, holdout.research_bars(VIX, "1h", "US"), skipped=skipped,
                    extra=extra)


def load_final(entry: Mapping[str, Any], arm: Arm, final: holdout.HoldoutPass) -> Arm:
    """The ONE holdout pass: the same walk-forward continued into the sealed sessions."""
    sealed = p19_run.sealed_names(arm.data, "1h", final)
    vix = holdout.research_bars(VIX, "1h", "US", holdout=final)
    vix = vix[pd.Series(vix.index.date, index=vix.index).le(p19_run.HOLDOUT_END).to_numpy()]
    unsealed = holdout.research_bars(VIX, "1h", "US")
    return assemble(str(entry["id"]), sealed, pd.concat([unsealed, vix]), skipped=arm.skipped,
                    oos_end=p19_run.HOLDOUT_END)
