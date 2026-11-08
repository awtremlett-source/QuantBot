"""Gates 4 and 5 (operator's directive, 2026-11-08): the always-loaded rules cannot quietly rot.

Gate 4 fails if an always-loaded file is over its limit, if the import is missing, or if a name
on an ENFORCED line does not exist. Gate 5 is the count of rules with no gate, which may only fall.
Standard library only: tests/plan runs under both environments.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CLAUDE = REPO_ROOT / "CLAUDE.md"
LESSONS = REPO_ROOT / "docs" / "LESSONS_LEARNED.md"
STANDARDS = REPO_ROOT / "docs" / "DESK_STANDARDS.md"
THIS_FILE = "tests/plan/test_rule_files.py"
IMPORT_LINE = "@docs/LESSONS_LEARNED.md"
CLAUDE_LINES_UNDER = 120
LESSONS_MAX_LINES = 200

# Lower this when a rule gets a proven gate. Raising it is refused from git history below.
OWED_CEILING = 88
# Rules may be merged by hand, with this lowered in the same diff; none may quietly vanish.
RULES_FLOOR = 106
BULLET = re.compile(r"^\s*[-*+] ")
NAMES_ONLY = re.compile(r"`[^`]+`(?:, `[^`]+`)*")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def is_imported(text: str, line: str = IMPORT_LINE) -> bool:
    """A live import: at the start of its own line, outside code fences and HTML comments."""
    fenced = commented = False
    for raw in text.splitlines():
        stripped = raw.strip()
        if commented:
            commented = "-->" not in stripped
        elif stripped.startswith(("```", "~~~")):
            fenced = not fenced
        elif stripped.startswith("<!--"):
            commented = "-->" not in stripped
        elif not fenced and raw.rstrip() == line:
            return True
    return False


def rules_in(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("- ")]


def tag_of(rule: str) -> tuple[str, str] | None:
    """(ENFORCED or OWED, what it names), from the last tag on the line."""
    at, kind = max((rule.rfind(f" {k}: "), k) for k in ("ENFORCED", "OWED"))
    return None if at < 0 else (kind, rule[at + len(kind) + 3:].strip())


def gates_listed(text: str) -> set[str]:
    return set(re.findall(r"^\| ([a-z][a-z0-9-]*) \|", text, re.MULTILINE)) - {"gate"}


def name_exists(root: Path, spec: str) -> bool:
    """A python file, or file::name where the name is a function or class defined in that file."""
    name, _, symbol = spec.partition("::")
    path = root / name
    if not path.is_file() or path.suffix != ".py":
        return False
    return not symbol or re.search(rf"^\s*(?:def|class)\s+{re.escape(symbol)}\b", _read(path),
                                   re.MULTILINE) is not None


def tag_faults(text: str) -> list[str]:
    """A bullet of any other shape would escape the count, so it is a fault too."""
    return [line[:70] for line in text.splitlines()
            if BULLET.match(line) and (not line.startswith("- ") or tag_of(line) is None)]


def enforced_faults(text: str, root: Path) -> list[str]:
    said = []
    for rule in rules_in(text):
        tag = tag_of(rule)
        if tag is None or tag[0] != "ENFORCED":
            continue
        if not NAMES_ONLY.fullmatch(tag[1]):
            said.append(f"must end with backticked names only: {rule[:60]}")
            continue
        said += [f"does not exist: {n}" for n in re.findall(r"`([^`]+)`", tag[1])
                 if not name_exists(root, n)]
    return said


def owed_faults(text: str, gates: set[str]) -> list[str]:
    said = []
    for rule in rules_in(text):
        tag = tag_of(rule)
        if tag is not None and tag[0] == "OWED":
            names = [x.strip() for x in tag[1].split(",")]
            said += [f"no such gate {n!r}: {rule[:60]}" for n in names if n not in gates]
    return said


def owed_count(texts: Sequence[str]) -> int:
    return sum(1 for text in texts for rule in rules_in(text)
               if (tag := tag_of(rule)) is not None and tag[0] == "OWED")


def ratchet_faults(count: int, ceiling: int, history: Sequence[int]) -> list[str]:
    said = []
    if count > ceiling:
        said.append(f"{count} rules are OWED, over the ceiling of {ceiling}")
    if count < ceiling:
        said.append(f"{count} rules are OWED: lower OWED_CEILING to {count} so it cannot rise back")
    earlier = [*history, ceiling]
    if any(later > before for before, later in zip(earlier, earlier[1:], strict=False)):
        said.append(f"OWED_CEILING rose: {earlier}")
    return said


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                          encoding="utf-8", check=True).stdout


def ceilings_in_git(root: Path, path: str) -> list[int]:
    """Oldest first, following the file through renames."""
    words = _git(root, "log", "--follow", "--name-only", "--format=%H", "--", path).split()
    found = []
    for sha, name in reversed(list(zip(words[::2], words[1::2], strict=True))):
        match = re.search(r"^OWED_CEILING = (\d+)", _git(root, "show", f"{sha}:{name}"), re.MULTILINE)
        if match:
            found.append(int(match.group(1)))
    return found


# ------------------------------------------------------- gate 4, the real files

def test_claude_md_is_under_its_line_limit() -> None:
    assert len(_read(CLAUDE).splitlines()) < CLAUDE_LINES_UNDER


def test_lessons_is_within_its_line_limit() -> None:
    assert len(_read(LESSONS).splitlines()) <= LESSONS_MAX_LINES


def test_the_lessons_file_is_imported_live() -> None:
    assert is_imported(_read(CLAUDE))


def test_the_standards_file_is_pointed_to_but_not_imported() -> None:
    text = _read(CLAUDE)
    assert "docs/DESK_STANDARDS.md" in text
    assert not is_imported(text, "@docs/DESK_STANDARDS.md")


def test_every_rule_ends_with_its_tag() -> None:
    for path in (LESSONS, STANDARDS):
        assert rules_in(_read(path)), f"{path.name} holds no rules"
        assert tag_faults(_read(path)) == []


def test_every_name_on_an_enforced_line_exists() -> None:
    for path in (LESSONS, STANDARDS):
        assert enforced_faults(_read(path), REPO_ROOT) == []


def test_every_owed_rule_names_a_listed_gate() -> None:
    gates = gates_listed(_read(LESSONS))
    assert gates, "the list of owed gates is missing"
    for path in (LESSONS, STANDARDS):
        assert owed_faults(_read(path), gates) == []


# ------------------------------------------------------- gate 5, the real count

def test_the_owed_count_only_falls() -> None:
    count = owed_count([_read(LESSONS), _read(STANDARDS)])
    assert ratchet_faults(count, OWED_CEILING, ceilings_in_git(REPO_ROOT, THIS_FILE)) == []


def test_no_rule_has_quietly_gone() -> None:
    assert len(rules_in(_read(LESSONS))) + len(rules_in(_read(STANDARDS))) >= RULES_FLOOR


# ------------------------------------------------------- each check, seen to fail

def test_a_written_pointer_is_not_an_import() -> None:
    assert not is_imported("See docs/LESSONS_LEARNED.md for the rules.\n")


def test_an_import_in_backticks_is_not_an_import() -> None:
    assert not is_imported("`@docs/LESSONS_LEARNED.md`\n")


def test_an_import_in_a_code_fence_is_not_an_import() -> None:
    assert not is_imported("```\n@docs/LESSONS_LEARNED.md\n```\n")


def test_an_indented_import_is_not_an_import() -> None:
    assert not is_imported("    @docs/LESSONS_LEARNED.md\n")


def test_an_import_in_a_tilde_fence_is_not_an_import() -> None:
    assert not is_imported("~~~\n@docs/LESSONS_LEARNED.md\n~~~\n")


def test_an_import_in_an_html_comment_is_not_an_import() -> None:
    assert not is_imported("<!--\n@docs/LESSONS_LEARNED.md\n-->\n")


def test_a_bullet_of_another_shape_is_caught() -> None:
    assert tag_faults("* A star bullet. OWED: lint\n")
    assert tag_faults("  - An indented bullet. OWED: lint\n")


def test_words_after_a_tag_are_caught(tmp_path: Path) -> None:
    (tmp_path / "t.py").write_text("def test_a():\n    pass\n", encoding="utf-8")
    assert enforced_faults("- Rule. ENFORCED: `t.py::test_a` and also the audit\n", tmp_path)
    assert owed_faults("- Rule. OWED: lint, and then some\n", {"lint"})


def test_a_name_outside_backticks_is_caught(tmp_path: Path) -> None:
    (tmp_path / "t.py").write_text("def test_a():\n    pass\n", encoding="utf-8")
    assert enforced_faults("- Rule. ENFORCED: `t.py::test_a`, gone.py\n", tmp_path)


def test_a_name_only_in_a_comment_is_caught(tmp_path: Path) -> None:
    (tmp_path / "t.py").write_text("# test_gone\n", encoding="utf-8")
    assert enforced_faults("- Rule. ENFORCED: `t.py::test_gone`\n", tmp_path)


def test_a_document_is_not_code(tmp_path: Path) -> None:
    (tmp_path / "notes.md").write_text("words\n", encoding="utf-8")
    assert enforced_faults("- Rule. ENFORCED: `notes.md`\n", tmp_path)


def test_a_rename_does_not_reset_the_history(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.invalid")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.py").write_text("OWED_CEILING = 10\n" + "x = 1\n" * 40, encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "first")
    _git(tmp_path, "mv", "a.py", "b.py")
    _git(tmp_path, "commit", "-qm", "renamed")
    assert ceilings_in_git(tmp_path, "b.py") == [10, 10]


def test_a_live_import_is_seen() -> None:
    assert is_imported("# Title\n@docs/LESSONS_LEARNED.md\n")


def test_a_rule_with_no_tag_is_caught() -> None:
    assert tag_faults("- A rule with no tag at all.\n- Tagged. OWED: lint\n") == [
        "- A rule with no tag at all."]


def test_a_missing_path_on_an_enforced_line_is_caught(tmp_path: Path) -> None:
    assert enforced_faults("- Rule. ENFORCED: `no/such.py`\n", tmp_path) == [
        "does not exist: no/such.py"]


def test_a_missing_name_inside_a_real_file_is_caught(tmp_path: Path) -> None:
    (tmp_path / "t.py").write_text("def test_longer_name():\n    pass\n", encoding="utf-8")
    assert enforced_faults("- Rule. ENFORCED: `t.py::test_longer`\n", tmp_path) == [
        "does not exist: t.py::test_longer"]
    assert enforced_faults("- Rule. ENFORCED: `t.py::test_longer_name`\n", tmp_path) == []


def test_an_enforced_line_naming_nothing_is_caught(tmp_path: Path) -> None:
    assert enforced_faults("- Rule. ENFORCED: trust me\n", tmp_path)


def test_a_folder_is_not_a_named_file(tmp_path: Path) -> None:
    assert enforced_faults("- Rule. ENFORCED: `.`\n", tmp_path)


def test_an_owed_rule_with_an_unlisted_gate_is_caught() -> None:
    assert owed_faults("- Rule. OWED: someday\n", {"lint"})
    assert owed_faults("- Rule. OWED: lint\n", {"lint"}) == []


def test_the_gate_list_is_read_from_its_table() -> None:
    assert gates_listed("| gate | what |\n| --- | --- |\n| lint | a thing |\n") == {"lint"}


def test_a_rise_in_the_owed_count_is_caught() -> None:
    assert ratchet_faults(11, 10, [10])


def test_a_fall_must_lower_the_ceiling_so_it_cannot_rise_back() -> None:
    assert ratchet_faults(9, 10, [10])
    assert ratchet_faults(9, 9, [10]) == []


def test_raising_the_ceiling_to_fit_is_caught() -> None:
    assert ratchet_faults(11, 11, [10])
