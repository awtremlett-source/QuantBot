"""QT-21 B3 wall test: every saved S6 / P19 verdict, re-judged WITH the bench guard, is unchanged.

docs/research/guard_wall_2026-10-17_QT21.json (made by docs/reports/QT-21_scripts.py.txt,
guard_wall.py) re-ran each saved result's judged series -- net 2x, marked down -- and measured
its biggest bar's share of the variance. S6 reproduced exactly (trades, bars, net 2x: 24 of
24, on fingerprint (a) bf58b259...). P19's inputs have moved since QT-15 (the daily store
re-fetched, P15's history rule), so its 18 re-runs are a proxy, not a copy. The guard only
ever turns a judged result into INSUFFICIENT; at <= 18.8% none comes near 25%.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from qb2.research import verdict

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE: list[dict[str, Any]] = json.loads((ROOT / "docs" / "research" / "guard_wall_2026-10-17_QT21.json")
                      .read_text(encoding="utf-8"))


def saved(cid: str) -> dict[str, Any]:
    folder = "docs/research/S6_batch1_runs/run1" if cid.startswith("S6-") else "data/qb2/p19_run/batch1"
    path = ROOT / folder / f"{cid}.json"
    if not path.is_file():
        pytest.skip(f"{path} is local data (not in git)")
    return dict(json.loads(path.read_text(encoding="utf-8")))


def rejudge(r: dict[str, Any], e: dict[str, Any], guard: bool) -> verdict.Verdict:
    mean = e["mean_per_bar"] if e["reproduced"] else r["sharpe"]   # P19 proxy: the saved sign
    return verdict.judge(
        oos_trades=int(r["trades"]), oos_bars=int(r["n_bars"]), p_value=r["p"],
        mean_per_bar=float(mean), dsr=r["dsr"], strategy_return=float(r["marked_2x"]),
        benchmark_return=float(r["vwrp"]) if r["vwrp"] is not None else np.inf,
        top_share=float(e["top_bar_share"]) if guard else None)


def test_all_42_saved_verdicts_are_unchanged_by_the_guard() -> None:
    assert len(EVIDENCE) == 42 and sum(e["id"].startswith("S6-") for e in EVIDENCE) == 24
    for e in EVIDENCE:
        r = saved(str(e["id"]))
        assert rejudge(r, e, guard=False).outcome == r["verdict"], e["id"]
        assert rejudge(r, e, guard=True).outcome == r["verdict"], e["id"]
        assert float(e["top_bar_share"]) < verdict.BIGGEST_BAR


def test_s6_reproduced_exactly_and_its_reasons_are_unchanged() -> None:
    for e in (x for x in EVIDENCE if str(x["id"]).startswith("S6-")):
        assert e["reproduced"], e["id"]
        r = saved(str(e["id"]))
        assert rejudge(r, e, guard=True).reasons == r["reasons"], e["id"]
