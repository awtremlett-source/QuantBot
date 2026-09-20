"""The wall, third direction: two environments that never mix.

LOCKED DECISION (merge stage 3a): the engine keeps `.venv`, the window keeps
`.venv-ui`, permanently. Their pins CONFLICT on purpose -- pandas 3.0.2 vs
2.3.3, yfinance 1.4.1 vs 0.2.66 -- and a library version is part of what
produced the live forward record. `pip install -r requirements-ui.txt` typed
with the wrong environment activated would silently swap those libraries
underneath a running track record, and no test of trading logic would notice.

So this checks both the DECLARATION and the INSTALLATION:

* no requirement line from requirements-ui.txt appears in requirements.txt;
* the engine's `.venv`, as actually installed on this machine, contains none of
  the UI-only distributions.

Version alignment is deferred to the July 2027 refit, where it can ride a full
firewall re-run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MUSEUM = REPO_ROOT / "tests" / "museum" / "wall_violations"

ENGINE_REQUIREMENTS = REPO_ROOT / "requirements.txt"
UI_REQUIREMENTS = REPO_ROOT / "requirements-ui.txt"
ENGINE_VENV = REPO_ROOT / ".venv"


def requirement_lines(text: str) -> set[str]:
    """Pinned requirement lines, comments and blanks stripped."""
    lines = set()
    for raw in text.splitlines():
        line = raw.split("#")[0].strip()
        if line:
            lines.add(line.lower())
    return lines


def distribution_name(requirement: str) -> str:
    for separator in ("==", ">=", "<=", "~=", ">", "<"):
        if separator in requirement:
            return requirement.split(separator)[0].strip().lower()
    return requirement.strip().lower()


def installed_distributions(venv: Path) -> set[str]:
    """Distribution names actually installed in a venv, from its dist-info."""
    found: set[str] = set()
    for pattern in ("Lib/site-packages", "lib/site-packages",
                    "lib/python*/site-packages"):
        for site in venv.glob(pattern):
            for info in site.glob("*.dist-info"):
                found.add(info.name.split("-")[0].lower().replace("_", "-"))
    return found


def shared_requirement_lines() -> set[str]:
    return (requirement_lines(ENGINE_REQUIREMENTS.read_text(encoding="utf-8"))
            & requirement_lines(UI_REQUIREMENTS.read_text(encoding="utf-8")))


def ui_only_distributions() -> set[str]:
    engine = {distribution_name(r) for r
              in requirement_lines(ENGINE_REQUIREMENTS.read_text(encoding="utf-8"))}
    ui = {distribution_name(r) for r
          in requirement_lines(UI_REQUIREMENTS.read_text(encoding="utf-8"))}
    # PySide6 pulls these in; neither belongs in the engine either.
    return (ui - engine) | {"pyside6-essentials", "pyside6-addons", "shiboken6"}


def environment_violations(installed: set[str], forbidden: set[str]) -> list[str]:
    return [f".venv has UI-only distribution {name!r}"
            for name in sorted(installed & forbidden)]


# ------------------------------------------------------------- declaration ---

def test_the_engine_requirements_share_no_line_with_the_ui_requirements() -> None:
    assert shared_requirement_lines() == set()


def test_the_two_files_pin_the_same_libraries_differently() -> None:
    """Proof the conflict is real, so the two-venv rule is not ceremony."""
    engine = ENGINE_REQUIREMENTS.read_text(encoding="utf-8").lower()
    ui = UI_REQUIREMENTS.read_text(encoding="utf-8").lower()
    for engine_pin, ui_pin in (("pandas==3.0.2", "pandas==2.3.3"),
                               ("yfinance==1.4.1", "yfinance==0.2.66")):
        assert engine_pin in engine
        assert ui_pin in ui


# ------------------------------------------------------------ installation ---

@pytest.mark.skipif(not ENGINE_VENV.is_dir(),
                    reason="no .venv on this machine (fresh clone)")
def test_the_engine_venv_has_no_ui_distribution_installed() -> None:
    installed = installed_distributions(ENGINE_VENV)
    assert installed, "read no distributions from .venv -- the scan is broken"
    assert environment_violations(installed, ui_only_distributions()) == []


# ------------------------------------------------------- birth certificate ---

def test_scanner_goes_red_on_a_ui_pin_in_the_engine_requirements() -> None:
    planted = requirement_lines(
        (MUSEUM / "requirements_with_ui.txt").read_text(encoding="utf-8"))
    ui = requirement_lines(UI_REQUIREMENTS.read_text(encoding="utf-8"))
    assert planted & ui, "planted engine requirements should share a UI pin"


def test_scanner_goes_red_on_a_ui_package_installed_in_the_engine_venv() -> None:
    planted = installed_distributions(MUSEUM / "fake_engine_venv")
    assert planted == {"pyside6"}, f"fixture not read correctly: {planted}"
    assert environment_violations(planted, ui_only_distributions()) != []
