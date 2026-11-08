"""Gates 1-3: the work-item front door (operator's directive, 2026-11-08).

Every test builds its own world under tmp_path; only the last section reads the real repo.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pytest

from qb2.tools import work_door as door
from qb2.tools import work_items as wi

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "qb2" / "tools" / "hooks" / "commit-msg"
GATE_START = "80feba2"             # the known-good commit: every commit after it names an item


@pytest.fixture
def world(tmp_path: Path) -> wi.World:
    (tmp_path / "evidence.txt").write_text("measured\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    defs = "".join(f"def test_y{n}():\n    pass\n\n" for n in (*range(10), 100))
    (tmp_path / "tests" / "test_x.py").write_text(defs, encoding="utf-8")
    return wi.World(root=tmp_path, requirements=frozenset({"S6", "S9"}))


@pytest.fixture
def ledger(tmp_path: Path) -> Path:
    return tmp_path / "work" / "items.jsonl"


def item(number: int = 100, **changes: Any) -> wi.WorkItem:
    good = wi.WorkItem(
        id=f"WI-{number:04d}", behaviour=f"behaviour-{number}", requirement="S6",
        files=("qb2/data/census.py",),
        assumption="the census only counts the days it already holds",
        evidence="1 of 3 fixture days vanished and completeness stayed at 100%",
        evidence_source="evidence.txt",
        premortem="the new count could mark a real market holiday as missing and turn the meter red",
        check=f"tests/test_x.py::test_y{number}")
    return replace(good, **changes)


def note(behaviour: str, world: wi.World, name: str = "note.md") -> str:
    words = "the first two attempts both moved the level after the check had already read it, so"
    (world.root / name).write_text(f"Why {behaviour} failed: {words} the design must change.\n",
                                   encoding="utf-8")
    return name


# ------------------------------------------------------- gate 1, at write

def test_a_complete_item_is_accepted_and_read_back(ledger: Path, world: wi.World) -> None:
    door.add(item(), ledger, world)
    assert door.load(ledger, world) == [item()]


@pytest.mark.parametrize("field", ["behaviour", "requirement", "assumption", "evidence",
                                   "evidence_source", "premortem", "check"])
def test_an_item_missing_any_required_field_is_refused(field: str, ledger: Path,
                                                       world: wi.World) -> None:
    with pytest.raises(wi.Refused, match=field):
        door.add(item(100, **{field: "  "}), ledger, world)
    assert not ledger.exists()


@pytest.mark.parametrize("files", [(), ("",), ("  ",)])
def test_a_brief_with_no_files_is_refused(files: tuple[str, ...], ledger: Path,
                                          world: wi.World) -> None:
    with pytest.raises(wi.Refused, match="files"):
        door.add(item(files=files), ledger, world)


@pytest.mark.parametrize("field", ["assumption", "premortem"])
def test_a_token_answer_is_refused(field: str, ledger: Path, world: wi.World) -> None:
    with pytest.raises(wi.Refused, match=field):
        door.add(item(100, **{field: "tbd"}), ledger, world)


def test_evidence_without_a_measured_figure_is_refused(ledger: Path, world: wi.World) -> None:
    with pytest.raises(wi.Refused, match="measured"):
        door.add(item(evidence="it looked wrong to me when I read the census"), ledger, world)


def test_one_digit_is_not_evidence(ledger: Path, world: wi.World) -> None:
    with pytest.raises(wi.Refused, match="evidence"):
        door.add(item(evidence="1"), ledger, world)


def test_evidence_must_come_from_a_file_that_exists(ledger: Path, world: wi.World) -> None:
    with pytest.raises(wi.Refused, match="evidence_source"):
        door.add(item(evidence_source="no/such/file.txt"), ledger, world)


def test_a_folder_is_not_an_evidence_source(ledger: Path, world: wi.World) -> None:
    with pytest.raises(wi.Refused, match="evidence_source"):
        door.add(item(evidence_source="."), ledger, world)


def test_a_requirement_outside_the_current_phase_is_refused(ledger: Path,
                                                            world: wi.World) -> None:
    with pytest.raises(wi.Refused, match="S7"):
        door.add(item(requirement="S7"), ledger, world)


def test_an_urgent_exception_is_accepted_named_and_counted(ledger: Path, world: wi.World) -> None:
    urgent = item(requirement="EXCEPTION: the operator's directive of 2026-11-08 names this work")
    door.add(urgent, ledger, world)
    assert wi.exceptions(door.load(ledger, world)) == [urgent]


def test_a_nameless_exception_is_refused(ledger: Path, world: wi.World) -> None:
    with pytest.raises(wi.Refused, match="EXCEPTION"):
        door.add(item(requirement="EXCEPTION: because"), ledger, world)


def test_a_check_that_names_no_test_is_refused(ledger: Path, world: wi.World) -> None:
    with pytest.raises(wi.Refused, match="check"):
        door.add(item(check="I will look at it"), ledger, world)


def test_the_queue_is_capped(ledger: Path, world: wi.World) -> None:
    for n in range(wi.MAX_OPEN):
        door.add(item(n), ledger, world)
    with pytest.raises(wi.Refused, match="open"):
        door.add(item(wi.MAX_OPEN), ledger, world)


def test_the_limits_are_pinned() -> None:
    assert (wi.MAX_OPEN, wi.MIN_WORDS, wi.THIRD_ATTEMPT) == (5, 5, 3)


def test_one_id_cannot_be_used_twice(ledger: Path, world: wi.World) -> None:
    door.add(item(), ledger, world)
    with pytest.raises(wi.Refused, match="already"):
        door.add(item(), ledger, world)


# -------------------------------------------------- gate 2, the third attempt

def test_the_third_attempt_is_refused_without_a_design_note(ledger: Path, world: wi.World) -> None:
    door.add(item(1, behaviour="the-stop-fires"), ledger, world)
    door.add(item(2, behaviour="the-stop-fires"), ledger, world)
    with pytest.raises(wi.Refused, match="design note"):
        door.add(item(3, behaviour="the-stop-fires"), ledger, world)


def test_the_third_attempt_passes_with_a_note_about_that_behaviour(ledger: Path,
                                                                   world: wi.World) -> None:
    door.add(item(1, behaviour="the-stop-fires"), ledger, world)
    door.add(item(2, behaviour="the-stop-fires"), ledger, world)
    door.add(item(3, behaviour="the-stop-fires", design_note=note("the-stop-fires", world)),
           ledger, world)
    assert len(door.load(ledger, world)) == 3


def test_the_same_check_counts_as_the_same_behaviour(ledger: Path, world: wi.World) -> None:
    same = "tests/test_x.py::test_y1"
    door.add(item(1, behaviour="stop-fires", check=same), ledger, world)
    door.add(item(2, behaviour="stop-fires-again", check=same), ledger, world)
    with pytest.raises(wi.Refused, match="design note"):
        door.add(item(3, behaviour="stop-fires-for-real", check=same), ledger, world)


def test_a_note_about_something_else_does_not_count(ledger: Path, world: wi.World) -> None:
    door.add(item(1, behaviour="the-stop-fires"), ledger, world)
    door.add(item(2, behaviour="the-stop-fires"), ledger, world)
    with pytest.raises(wi.Refused, match="design note"):
        door.add(item(3, behaviour="the-stop-fires", design_note=note("another-thing", world)),
               ledger, world)


@pytest.mark.parametrize(("name", "text"), [
    ("note.md", "the-stop-fires failed.\n"),
    ("note.txt", "the-stop-fires " * 30)])
def test_a_note_must_be_a_real_markdown_note(name: str, text: str, ledger: Path,
                                             world: wi.World) -> None:
    (world.root / name).write_text(text, encoding="utf-8")
    door.add(item(1, behaviour="the-stop-fires"), ledger, world)
    door.add(item(2, behaviour="the-stop-fires"), ledger, world)
    with pytest.raises(wi.Refused, match="design note"):
        door.add(item(3, behaviour="the-stop-fires", design_note=name), ledger, world)


def test_a_fourth_attempt_needs_its_own_note(ledger: Path, world: wi.World) -> None:
    door.add(item(1, behaviour="the-stop-fires"), ledger, world)
    door.add(item(2, behaviour="the-stop-fires"), ledger, world)
    door.add(item(3, behaviour="the-stop-fires", design_note=note("the-stop-fires", world)),
           ledger, world)
    with pytest.raises(wi.Refused, match="design note"):
        door.add(item(4, behaviour="the-stop-fires", design_note="note.md"), ledger, world)


# ----------------------------------------------- gate 3, a seam deletes its path

def test_a_seam_change_must_name_what_it_deletes(ledger: Path, world: wi.World) -> None:
    with pytest.raises(wi.Refused, match="delete"):
        door.add(item(seam="prices"), ledger, world)


def test_an_unknown_seam_is_refused(ledger: Path, world: wi.World) -> None:
    with pytest.raises(wi.Refused, match="seam"):
        door.add(item(seam="vibes"), ledger, world)


def test_a_seam_change_must_name_a_path_that_exists_today(ledger: Path, world: wi.World) -> None:
    with pytest.raises(wi.Refused, match="delete"):
        door.add(item(seam="prices", deletes=("no/such.py",)), ledger, world)


def test_a_seam_change_cannot_close_while_the_old_path_survives(ledger: Path,
                                                                world: wi.World) -> None:
    old = world.root / "old.py"
    old.write_text("x = 1\n", encoding="utf-8")
    door.add(item(seam="prices", deletes=("old.py",)), ledger, world)
    with pytest.raises(wi.Refused, match="old.py"):
        door.close("WI-0100", ledger, world)
    old.unlink()
    door.close("WI-0100", ledger, world)
    assert door.load(ledger, world)[0].status == wi.DONE


def test_a_seam_can_delete_one_function_from_a_file(ledger: Path, world: wi.World) -> None:
    old = world.root / "old.py"
    old.write_text("def stale():\n    pass\n\ndef kept():\n    pass\n", encoding="utf-8")
    door.add(item(seam="exits", deletes=("old.py::stale",)), ledger, world)
    with pytest.raises(wi.Refused, match="stale"):
        door.close("WI-0100", ledger, world)
    old.write_text("def kept():\n    pass\n", encoding="utf-8")
    door.close("WI-0100", ledger, world)


def test_an_item_cannot_close_until_its_check_exists(ledger: Path, world: wi.World) -> None:
    door.add(item(check="tests/test_x.py::test_not_written_yet"), ledger, world)
    with pytest.raises(wi.Refused, match="test_not_written_yet"):
        door.close("WI-0100", ledger, world)


def test_a_check_named_only_in_a_comment_cannot_close(ledger: Path, world: wi.World) -> None:
    (world.root / "tests" / "test_c.py").write_text("# test_ghost\n", encoding="utf-8")
    door.add(item(check="tests/test_c.py::test_ghost"), ledger, world)
    with pytest.raises(wi.Refused, match="test_ghost"):
        door.close("WI-0100", ledger, world)


# ----------------------------------------------------- gates 1-3, at read

def _rows(ledger: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in ledger.read_text(encoding="utf-8").splitlines()]


def _save(ledger: Path, rows: list[dict[str, Any]]) -> None:
    ledger.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


@pytest.mark.parametrize(("field", "value", "said"), [
    ("premortem", "", "premortem"), ("evidence", "no figure here at all", "measured"),
    ("requirement", "S1", "S1"), ("check", "nothing", "check"), ("seam", "prices", "delete")])
def test_a_hand_edited_ledger_is_refused_at_read(field: str, value: str, said: str, ledger: Path,
                                                 world: wi.World) -> None:
    door.add(item(), ledger, world)
    rows = _rows(ledger)
    rows[0][field] = value
    _save(ledger, rows)
    with pytest.raises(wi.Refused, match=said):
        door.load(ledger, world)


def test_a_third_attempt_hand_written_without_a_note_is_refused_at_read(ledger: Path,
                                                                        world: wi.World) -> None:
    door.add(item(1, behaviour="same"), ledger, world)
    door.add(item(2, behaviour="same"), ledger, world)
    rows = _rows(ledger)
    rows.append({**rows[1], "id": "WI-0003", "check": "tests/test_x.py::test_y3"})
    _save(ledger, rows)
    with pytest.raises(wi.Refused, match="design note"):
        door.load(ledger, world)


def test_a_later_row_may_only_change_the_status(ledger: Path, world: wi.World) -> None:
    door.add(item(), ledger, world)
    rows = _rows(ledger)
    rows.append({**rows[0], "premortem": "a different premortem written after the event, by hand"})
    _save(ledger, rows)
    with pytest.raises(wi.Refused, match="only the status"):
        door.load(ledger, world)


def test_a_first_row_cannot_already_be_done(ledger: Path, world: wi.World) -> None:
    ledger.parent.mkdir(parents=True)
    _save(ledger, [{**asdict(item()), "status": wi.DONE}])
    with pytest.raises(wi.Refused, match="starts open"):
        door.load(ledger, world)


def test_a_row_without_a_seam_answer_is_refused(ledger: Path, world: wi.World) -> None:
    door.add(item(), ledger, world)
    rows = _rows(ledger)
    del rows[0]["seam"]
    _save(ledger, rows)
    with pytest.raises(wi.Refused, match="line 1"):
        door.load(ledger, world)


def test_a_queue_stretched_by_hand_is_refused_at_read(ledger: Path, world: wi.World) -> None:
    for n in range(wi.MAX_OPEN):
        door.add(item(n), ledger, world)
    rows = _rows(ledger)
    rows.append({**rows[0], "id": "WI-0999", "behaviour": "another", "check": "tests/test_x.py::t"})
    _save(ledger, rows)
    with pytest.raises(wi.Refused, match="open"):
        door.load(ledger, world)


def test_a_broken_line_is_refused_at_read(ledger: Path, world: wi.World) -> None:
    ledger.parent.mkdir(parents=True)
    ledger.write_text("this is not json\n", encoding="utf-8")
    with pytest.raises(wi.Refused, match="line 1"):
        door.load(ledger, world)


def test_an_unknown_field_is_refused_at_read(ledger: Path, world: wi.World) -> None:
    door.add(item(), ledger, world)
    rows = _rows(ledger)
    rows[0]["surprise"] = 1
    _save(ledger, rows)
    with pytest.raises(wi.Refused, match="line 1"):
        door.load(ledger, world)


def test_an_old_closed_item_is_not_rechecked_so_a_revert_cannot_jam_the_ledger(
        ledger: Path, world: wi.World) -> None:
    old = world.root / "old.py"
    old.write_text("x = 1\n", encoding="utf-8")
    door.add(item(seam="prices", deletes=("old.py",)), ledger, world)
    old.unlink()
    door.close("WI-0100", ledger, world)
    old.write_text("x = 1\n", encoding="utf-8")       # a revert brought it back
    assert door.load(ledger, world)[0].status == wi.DONE


# ------------------------------------------------------- the commit door

def _text(ledger: Path) -> str:
    return ledger.read_text(encoding="utf-8") if ledger.exists() else ""


def _everywhere(name: str) -> str | None:
    return "x = 1\n"


def _nowhere(name: str) -> str | None:
    return None


def land(message: str, head: str, work: str, files: tuple[str, ...] = ("qb2/data/census.py",),
         in_head: wi.Tree = _everywhere, in_index: wi.Tree = _nowhere) -> door.Landing:
    return door.Landing(message, head, work, files, in_head, in_index)


def test_a_commit_naming_no_item_is_refused(ledger: Path, world: wi.World) -> None:
    door.add(item(), ledger, world)
    assert door.commit_refusals(land("fix the census", "", _text(ledger)), world)


def test_a_commit_naming_an_unknown_item_is_refused(ledger: Path, world: wi.World) -> None:
    door.add(item(), ledger, world)
    assert door.commit_refusals(land("WI-9999: fix", "", _text(ledger)), world)


def test_a_commit_naming_an_open_item_passes(ledger: Path, world: wi.World) -> None:
    door.add(item(), ledger, world)
    assert door.commit_refusals(land("WI-0100: fix", "", _text(ledger)), world) == []


def test_an_id_only_in_a_comment_line_does_not_count(ledger: Path, world: wi.World) -> None:
    door.add(item(), ledger, world)
    assert door.commit_refusals(land("fix\n# WI-0100\n", "", _text(ledger)), world)


def test_a_commit_outside_the_named_files_is_refused(ledger: Path, world: wi.World) -> None:
    door.add(item(), ledger, world)
    said = door.commit_refusals(land("WI-0100: fix", "", _text(ledger),
                                     files=("qb2/guard/stops.py",)), world)
    assert said and "qb2/guard/stops.py" in said[0]


def test_the_ledger_and_state_are_always_allowed(ledger: Path, world: wi.World) -> None:
    door.add(item(), ledger, world)
    files = (wi.LEDGER_NAME, "STATE.md", "qb2/data/census.py")
    assert door.commit_refusals(land("WI-0100: fix", "", _text(ledger), files=files), world) == []


def test_a_folder_entry_covers_what_is_under_it(ledger: Path, world: wi.World) -> None:
    door.add(item(files=("docs/reports/",)), ledger, world)
    files = ("docs/reports/x.md",)
    assert door.commit_refusals(land("WI-0100: fix", "", _text(ledger), files=files), world) == []


def test_the_closing_commit_may_name_its_item_but_the_next_may_not(ledger: Path,
                                                                   world: wi.World) -> None:
    door.add(item(), ledger, world)
    before = _text(ledger)
    door.close("WI-0100", ledger, world)
    after = _text(ledger)
    tree = wi.disk(world.root)
    assert door.commit_refusals(land("WI-0100: last", before, after, in_index=tree), world) == []
    assert door.commit_refusals(land("WI-0100: more", after, after, in_index=tree), world)


def test_a_seam_commit_is_refused_while_the_old_path_is_staged(ledger: Path,
                                                               world: wi.World) -> None:
    (world.root / "old.py").write_text("x = 1\n", encoding="utf-8")
    door.add(item(seam="prices", deletes=("old.py",)), ledger, world)
    said = door.commit_refusals(land("WI-0100: new path", "", _text(ledger),
                                     in_index=_everywhere), world)
    assert said and "old.py" in said[0]


def test_a_seam_commit_that_stages_the_deletion_passes(ledger: Path, world: wi.World) -> None:
    (world.root / "old.py").write_text("x = 1\n", encoding="utf-8")
    door.add(item(seam="prices", deletes=("old.py",)), ledger, world)
    assert door.commit_refusals(land("WI-0100: new path", "", _text(ledger)), world) == []


def test_a_hand_written_close_cannot_skip_the_deletion(ledger: Path, world: wi.World) -> None:
    (world.root / "old.py").write_text("x = 1\n", encoding="utf-8")
    door.add(item(seam="prices", deletes=("old.py",)), ledger, world)
    head = _text(ledger)
    rows = _rows(ledger)
    rows.append({**rows[0], "status": wi.DONE})
    _save(ledger, rows)
    said = door.commit_refusals(land("WI-0100: done", head, _text(ledger), in_index=_everywhere),
                                world)
    assert said and "old.py" in said[0]


def test_a_hand_written_close_needs_its_check_to_exist(ledger: Path, world: wi.World) -> None:
    door.add(item(), ledger, world)
    head = _text(ledger)
    rows = _rows(ledger)
    rows.append({**rows[0], "status": wi.DONE})
    _save(ledger, rows)
    assert door.commit_refusals(land("WI-0100: done", head, _text(ledger)), world)


def test_a_new_row_outside_the_phase_is_refused_at_the_door(ledger: Path, world: wi.World) -> None:
    door.add(item(), ledger, world)
    rows = _rows(ledger)
    rows = [{**rows[0], "requirement": "S999"}, {**rows[0], "requirement": "S999", "status": wi.DONE}]
    _save(ledger, rows)
    said = door.commit_refusals(land("WI-0100: x", "", _text(ledger), in_index=wi.disk(world.root)),
                                world)
    assert said and "S999" in said[0]


def test_a_new_seam_row_must_name_a_path_in_head(ledger: Path, world: wi.World) -> None:
    (world.root / "old.py").write_text("x = 1\n", encoding="utf-8")
    door.add(item(seam="prices", deletes=("old.py",)), ledger, world)
    said = door.commit_refusals(land("WI-0100: x", "", _text(ledger), in_head=_nowhere), world)
    assert said and "old.py" in said[0]


def test_a_real_revert_is_never_blocked(ledger: Path, world: wi.World) -> None:
    door.add(item(), ledger, world)
    message = 'Revert "QT-29 G: tonight"\n\nThis reverts commit 80feba2abc.\n'
    assert door.commit_refusals(land(message, "", "this ledger is broken\n"), world) == []


def test_a_fake_revert_is_refused(ledger: Path, world: wi.World) -> None:
    door.add(item(), ledger, world)
    assert door.commit_refusals(land('Revert "something else"\n', "", _text(ledger)), world)


def test_a_rewritten_ledger_refuses_the_commit(ledger: Path, world: wi.World) -> None:
    door.add(item(1), ledger, world)
    first = _text(ledger)
    door.add(item(2), ledger, world)
    second = _text(ledger)
    said = door.commit_refusals(land("WI-0002: x", second, first), world)
    assert said and "append-only" in said[0]


def test_a_broken_ledger_refuses_the_commit(ledger: Path, world: wi.World) -> None:
    door.add(item(), ledger, world)
    bad = _text(ledger).replace('"premortem": "the new', '"premortem": "x", "was": "the new')
    assert door.commit_refusals(land("WI-0100: x", "", bad), world)


def test_a_windows_checkout_of_the_ledger_is_not_a_rewrite(ledger: Path, world: wi.World) -> None:
    door.add(item(), ledger, world)
    text = _text(ledger)
    assert door.commit_refusals(land("WI-0100: x", text, text.replace("\n", "\r\n")), world) == []


# ------------------------------------------------------- where requirements come from

def test_requirements_come_from_the_phase_line() -> None:
    line = "Phase: v2 BUILDING. **S0–S5 DONE; S6 OPEN; S9 OPEN — the advisor is LIVE**\n"
    assert wi.phase_requirements("# STATE\n" + line) == frozenset({"S6", "S9"})


def test_no_phase_line_refuses_everything() -> None:
    with pytest.raises(wi.Refused, match="Phase"):
        wi.phase_requirements("# STATE\nnothing here\n")


# ------------------------------------------------------- the real commit path, in a scratch repo

def _in(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True,
                          encoding="utf-8", check=True).stdout


@pytest.fixture
def repo(tmp_path: Path, world: wi.World, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "STATE.md").write_text("Phase: v2. S6 OPEN\n", encoding="utf-8")
    (tmp_path / "qb2" / "data").mkdir(parents=True)
    (tmp_path / "qb2" / "data" / "census.py").write_text("x = 1\n", encoding="utf-8")
    _in(tmp_path, "init", "-q")
    _in(tmp_path, "config", "user.email", "t@example.invalid")
    _in(tmp_path, "config", "user.name", "t")
    _in(tmp_path, "add", "-A")
    _in(tmp_path, "commit", "-qm", "base")
    monkeypatch.setattr(wi, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(wi, "LEDGER", tmp_path / wi.LEDGER_NAME)
    door.add(item(), wi.LEDGER, wi.current_world(tmp_path))
    return tmp_path


def _message(repo: Path, text: str) -> list[str]:
    (repo / "MSG").write_text(text, encoding="utf-8")
    return ["commit-msg", str(repo / "MSG")]


def test_the_door_reads_the_staged_ledger(repo: Path) -> None:
    (repo / "qb2" / "data" / "census.py").write_text("x = 2\n", encoding="utf-8")
    _in(repo, "add", "qb2/data/census.py")
    assert door.main(_message(repo, "WI-0100: fix")) == 1      # the item is on disk, not staged
    _in(repo, "add", "-f", wi.LEDGER_NAME)
    assert door.main(_message(repo, "WI-0100: fix")) == 0


def test_the_door_reads_the_staged_files(repo: Path) -> None:
    (repo / "other.py").write_text("y = 1\n", encoding="utf-8")
    _in(repo, "add", "other.py")
    _in(repo, "add", "-f", wi.LEDGER_NAME)
    assert door.main(_message(repo, "WI-0100: fix")) == 1


def test_list_shows_each_exception_by_name(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    urgent = item(7, requirement="EXCEPTION: a broker outage needs this before the phase allows")
    door.add(urgent, wi.LEDGER, wi.current_world(repo))
    assert door.main(["list"]) == 0
    shown = capsys.readouterr().out
    assert "exceptions so far: 1" in shown and "WI-0007" in shown and "broker outage" in shown


# ------------------------------------------------------- the real thing

def test_the_real_ledger_reads_clean() -> None:
    assert door.load(wi.LEDGER, wi.current_world()) != []


def _git(*args: str) -> str:
    return _in(REPO_ROOT, *args)


def test_the_commit_hook_is_wired() -> None:
    """Absolute or relative: the app rewrites the setting when it makes a worktree."""
    assert _git("config", "--get", "core.hooksPath").strip().replace("\\", "/").endswith(
        "qb2/tools/hooks")


def test_the_hook_ends_by_running_the_door() -> None:
    assert HOOK.read_text(encoding="utf-8").rstrip().endswith(
        'python.exe" -m qb2.tools.work_door commit-msg "$1"')


def _sh() -> str:
    found = shutil.which("sh")
    return found or str(Path(_git("--exec-path").strip()).parents[2] / "bin" / "sh.exe")


def test_the_real_hook_refuses_a_message_naming_no_item(tmp_path: Path) -> None:
    message = tmp_path / "MSG"
    message.write_text("tidy up the docs\n", encoding="utf-8")
    run = subprocess.run([_sh(), str(HOOK), str(message)], cwd=REPO_ROOT, capture_output=True,
                         text=True, encoding="utf-8")
    assert run.returncode == 1 and "REFUSED" in run.stderr


def test_the_commit_hook_keeps_unix_line_endings() -> None:
    """A carriage return in the hook stops the shell running it, so every commit would fail."""
    assert b"\r" not in HOOK.read_bytes()
    assert _git("check-attr", "eol", "--", "qb2/tools/hooks/commit-msg").strip().endswith("eol: lf")


def test_the_real_ledger_is_tracked_by_git() -> None:
    """*.jsonl is gitignored for data logs; a ledger left out would vanish with the checkout."""
    assert _git("ls-files", "--", wi.LEDGER_NAME).strip() == wi.LEDGER_NAME


def _open_at(ref: str) -> set[str]:
    found = subprocess.run(["git", "show", f"{ref}:{wi.LEDGER_NAME}"], cwd=REPO_ROOT,
                           capture_output=True, text=True, encoding="utf-8")
    if found.returncode:
        return set()
    return {x.id for x in wi.current(wi.parse(found.stdout)) if x.status == wi.OPEN}


def test_every_commit_since_the_gate_named_an_open_item() -> None:
    """The read side of the commit door: --no-verify cannot hide here."""
    bad = []
    for sha in _git("log", "--format=%H", f"{GATE_START}..HEAD").split():
        message = _git("log", "-1", "--format=%B", sha)
        named = set(door.ID_NAMED.findall(message))
        if not door.is_revert(message) and not named & (_open_at(sha) | _open_at(f"{sha}^")):
            bad.append(sha)
    assert bad == []
