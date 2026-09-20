"""The wall, direction 1 again: installing the ENGINE installs no UI.

The end goal is an installable app on an always-on PC, and the engine half of
it must stay headless. If requirements.txt or the one-command installer ever
learned about PySide6 -- or about requirements-ui.txt -- then a Qt wheel that
fails to build, or a GUI dependency that needs a display, could block the
install of a trading engine that does not draw anything.

The two pin sets also CONFLICT on purpose (pandas 3.x vs 2.x, yfinance 1.x vs
0.2.x). Installing the UI pins into the engine's .venv would silently swap the
libraries the live record is being produced with, so the installer must never
be able to do it by accident.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MUSEUM = REPO_ROOT / "tests" / "museum" / "wall_violations"

# The engine's install surface: what pip reads, and the one-command installer.
ENGINE_INSTALL_FILES: tuple[str, ...] = (
    "requirements.txt",
    "install.ps1",
    "tools/installer.py",
)

UI_TOKENS: tuple[str, ...] = (
    "pyside6", "shiboken6", "mplfinance", "requirements-ui", "tools_ui",
)


def ui_references(text: str, source: str) -> list[str]:
    lowered = text.lower()
    return [f"{source} mentions {token}" for token in UI_TOKENS if token in lowered]


def test_engine_install_surface_never_mentions_the_ui() -> None:
    found: list[str] = []
    for name in ENGINE_INSTALL_FILES:
        path = REPO_ROOT / name
        assert path.is_file(), f"engine install file missing: {name}"
        found += ui_references(path.read_text(encoding="utf-8"), name)
    assert found == []


def test_the_ui_pins_live_in_their_own_file() -> None:
    """They exist, they are separate, and they disagree -- deliberately."""
    engine = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    ui = (REPO_ROOT / "requirements-ui.txt").read_text(encoding="utf-8")
    assert "PySide6" in ui, "requirements-ui.txt should pin the UI toolkit"
    assert "PySide6" not in engine
    # Same library, different pin: proof the two environments are not shared.
    assert "pandas==3.0.2" in engine
    assert "pandas==2.3.3" in ui


def test_scanner_goes_red_on_a_planted_ui_dependency() -> None:
    """Birth certificate: the same scanner, a deliberate violation, red."""
    requirements = (MUSEUM / "requirements_with_ui.txt").read_text(encoding="utf-8")
    installer = (MUSEUM / "installer_with_ui.ps1.txt").read_text(encoding="utf-8")
    assert ui_references(requirements, "planted-requirements") != []
    assert ui_references(installer, "planted-installer") != []
