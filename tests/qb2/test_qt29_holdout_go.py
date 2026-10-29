"""QT-29 E (QT-28 PROPOSE 7): the sealed holdout opens only on the operator's GO words. Offline.

QT-28 found cm_run opening the seal by itself in the same run as a walk-forward PASS, and withheld it
with a thin wrapper. Now holdout.open_final_run -- the ONE entry every runner uses -- refuses unless the
trial's committed register entry holds ``holdout_go``: his words exactly "GO on holdout for <trial id>",
with when and where. A refusal opens nothing and logs nothing; each runner keeps the walk-forward
result, marks the holdout WAITING, and carries on; the next run asks again. Fixture seals only.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from qb2.research import advisor_data, advisor_run, cm_run, holdout, p19_run, preregister, s6_run, trial_log

ID = "QT29-T1"
GO = {"words": "GO on holdout for QT29-T1", "at": "2026-10-29 07:42 UK", "source": "chat, QT-29 test"}


def token(tmp: Path, go: dict[str, Any] | None) -> preregister.Registered:
    """A committed one-trial register in a tmp git repo, with or without a holdout_go record."""
    entry: dict[str, Any] = {"id": ID, "kind": "trial", "rule": "test", "bar_size": "1d", "universe": "test",
                             "exit_rule": "test", "parameters": {}, "holdout": "test", "date": "2026-10-29"}
    if go is not None:
        entry["holdout_go"] = go
    (tmp / "docs" / "research").mkdir(parents=True)
    (tmp / preregister.REGISTER_REL).write_text(json.dumps({"entries": [entry]}), encoding="utf-8")
    for args in (["init", "-q"], ["add", "."], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "r"]):
        subprocess.run(["git", "-C", str(tmp), *args], check=True, capture_output=True)
    return preregister.require(ID, root=tmp)


def opened(tmp: Path, go: dict[str, Any] | None) -> holdout.HoldoutPass:
    return holdout.open_final_run(token(tmp, go), spent=tmp / "spent.jsonl", log_path=tmp / "trials.jsonl")


@pytest.mark.parametrize("go", [
    None,                                                          # no GO at all
    {**GO, "words": "GO on holdout for QT29-T2"},                  # another trial's GO
    {**GO, "words": "GO on holdout for QT29-T"},                   # a prefix of the id
    {**GO, "words": "GO on holdout for QT29-T1."},                 # near misses: punctuation, case, space
    {**GO, "words": "go on holdout for QT29-T1"},
    {**GO, "words": "GO on holdout for QT29-T1 "},
    {**GO, "words": "GO on the holdout for QT29-T1"},
    {**GO, "at": ""},                                              # no when
    {"words": GO["words"], "at": GO["at"]},                        # no where
])
def test_without_his_exact_words_nothing_is_opened_or_logged(tmp_path: Path, go: dict[str, Any] | None) -> None:
    with pytest.raises(holdout.Waiting, match="WAITS for the operator's words"):
        opened(tmp_path, go)
    assert not (tmp_path / "spent.jsonl").exists() and not (tmp_path / "trials.jsonl").exists()   # no seal view


def test_his_exact_words_open_the_fixture_seal_once(tmp_path: Path) -> None:
    once = opened(tmp_path, GO)
    assert once.candidate_id == ID
    assert [json.loads(x)["kind"] for x in (tmp_path / "trials.jsonl").read_text(encoding="utf-8").splitlines()] \
        == ["holdout"]
    with pytest.raises(holdout.Sealed, match="already had"):
        holdout.open_final_run(preregister.require(ID, root=tmp_path), spent=tmp_path / "spent.jsonl",
                               log_path=tmp_path / "trials.jsonl")


def test_a_waiting_holdout_is_asked_again_and_a_done_one_never() -> None:
    assert holdout.due({"verdict": "PASS"}) and holdout.due({"holdout": {"verdict": holdout.WAITING}})
    assert not holdout.due({"holdout": {"verdict": "FAIL"}}) and not holdout.due({"holdout": {"verdict": "NOT RUN"}})


def test_every_runner_keeps_the_result_marks_waiting_and_carries_on(tmp_path: Path,
                                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    tok = token(tmp_path / "reg", None)
    monkeypatch.setattr(holdout, "SPENT", tmp_path / "spent.jsonl")              # never the real files,
    monkeypatch.setattr(trial_log, "DEFAULT_TRIAL_LOG", tmp_path / "trials.jsonl")   # even under a mutant
    for module in (s6_run, cm_run):
        monkeypatch.setattr(module, "fingerprints", lambda: {"b": "fp"})
    monkeypatch.setattr(advisor_data, "fingerprints", lambda: {"b": "fp"})
    calls: dict[str, Callable[[Path], dict[str, Any]]] = {
        "s6_run": lambda d: s6_run._holdout(tok, {}, [], d, 1, "fp"),
        "cm_run": lambda d: cm_run._holdout(tok, {}, None, "gbt", d, 1, "fp"),   # type: ignore[arg-type]
        "advisor_run": lambda d: advisor_run._holdout(tok, [], d, "fp", d, 1, 62),
        "p19_run": lambda d: p19_run._holdout(tok, lambda **_: None, [], "1d", 3, 18, holdout.open_final_run,
                                              None, d / "t.jsonl", None, lambda *a, **k: None),  # type: ignore[arg-type]
    }
    for name, call in calls.items():
        folder = tmp_path / name
        folder.mkdir()
        out = call(folder)
        assert out["verdict"] == holdout.WAITING and "GO on holdout for QT29-T1" in out["reasons"][0], name
        assert list(folder.rglob("*.json")) == [] and not (folder / "t.jsonl").exists(), name   # nothing saved
    assert not (tmp_path / "spent.jsonl").exists() and not (tmp_path / "trials.jsonl").exists()


def test_the_real_register_holds_no_holdout_go() -> None:
    """QT-29 adds the fence, never a GO: only his words, in a later box, may."""
    assert [e["id"] for e in preregister.entries().values() if "holdout_go" in e] == []
