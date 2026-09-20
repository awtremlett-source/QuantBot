"""Nothing merged in may carry the banned legacy-project tokens.

A previous, abandoned project left its name scattered through older code. It
is not being revived, its files are not being imported, and nothing in this
merge may quietly re-introduce it -- not as a folder, not as a filename, not
as an identifier or a leftover string in a docstring. This is a naming
hygiene rule with teeth: a token that never appears cannot be grepped into
existence later by someone assuming it is still supported.

Both halves are checked: the PATHS of every merged file, and their CONTENTS.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MUSEUM = REPO_ROOT / "tests" / "museum" / "wall_violations"

# The banned tokens, matched case-insensitively.
FORBIDDEN: tuple[str, ...] = ("mtt", "mark_the_trend")

# Everything this merge created or moved in.
SCANNED_TREES: tuple[str, ...] = ("manual", "tests/manual", "tools_ui", "docs/merge")


def scanned_files() -> list[Path]:
    files: list[Path] = []
    for tree in SCANNED_TREES:
        root = REPO_ROOT / tree
        assert root.is_dir(), f"tree missing: {tree}"
        files += [p for p in sorted(root.rglob("*"))
                  if p.is_file() and "__pycache__" not in p.parts]
    return files


def path_violations(relative_paths: list[str]) -> list[str]:
    lowered = [(p, p.lower()) for p in relative_paths]
    return [f"path {path} contains {token!r}"
            for path, low in lowered for token in FORBIDDEN if token in low]


def content_violations(files: list[Path]) -> list[str]:
    found: list[str] = []
    for path in files:
        text = path.read_bytes().decode("utf-8", errors="replace").lower()
        for token in FORBIDDEN:
            if token in text:
                name = path.relative_to(REPO_ROOT).as_posix()
                found.append(f"{name} contains {token!r}")
    return found


def test_no_forbidden_token_in_any_merged_path() -> None:
    files = scanned_files()
    assert len(files) > 50, f"only {len(files)} files scanned -- scan broken"
    relative = [p.relative_to(REPO_ROOT).as_posix() for p in files]
    assert path_violations(relative) == []


def test_no_forbidden_token_in_any_merged_file() -> None:
    assert content_violations(scanned_files()) == []


def test_scanner_goes_red_on_a_planted_token() -> None:
    """Birth certificate: both halves of the scanner, deliberately tripped.

    The path half is checked against a STRING, never a real file: creating a
    path with the banned token in it is exactly what this rule forbids.
    """
    assert path_violations(["manual/mtt_helpers.py"]) != []
    assert path_violations(["manual/mark_the_trend/__init__.py"]) != []
    assert content_violations([MUSEUM / "forbidden_token.py.txt"]) != []
