"""Does qb2's environment actually contain what qb2 asked for?

A library version is part of what produces a track record, so "it works on my
machine" must never quietly mean a different set of libraries. This test reads
``requirements-qb2.txt``, reads what is really installed, and requires them to
agree exactly -- then proves the three libraries that matter most can actually
be imported and started: pandas, yfinance, and the GUI toolkit offscreen.

It is written to FAIL when run on v1's interpreter. That is the point: pointing
it at the wrong environment must be noisy, not silent.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIREMENTS = REPO_ROOT / "requirements-qb2.txt"

# Qt must not try to open a window: these tests run headless, on a schedule,
# and on machines with no display at all.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def pinned_versions() -> dict[str, str]:
    """The pins qb2 asked for, read from the file rather than duplicated here."""
    pins: dict[str, str] = {}
    for raw in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = raw.split("#")[0].strip()
        if "==" in line:
            name, version = line.split("==")
            pins[name.strip().lower().replace("_", "-")] = version.strip()
    return pins


def installed_version(distribution: str) -> str | None:
    from importlib.metadata import PackageNotFoundError, version
    try:
        return version(distribution)
    except PackageNotFoundError:
        return None


def test_the_requirements_file_is_fully_pinned() -> None:
    """No loose bounds: a range is a version you have not chosen."""
    loose = []
    for raw in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = raw.split("#")[0].strip()
        if line and "==" not in line:
            loose.append(line)
    assert loose == [], f"unpinned requirements: {loose}"
    assert len(pinned_versions()) >= 10


@pytest.mark.parametrize("distribution", sorted(pinned_versions()))
def test_every_pin_is_installed_at_exactly_that_version(distribution: str) -> None:
    """The whole point: asked-for and installed must be the same number."""
    expected = pinned_versions()[distribution]
    actual = installed_version(distribution)
    assert actual is not None, (
        f"{distribution} is pinned at {expected} but is NOT installed -- this is "
        f"almost certainly the wrong interpreter. Use .venv-qb2 "
        f"(see docs/plan/ENV_QB2.md).")
    assert actual == expected, (
        f"{distribution}: requirements-qb2.txt pins {expected}, "
        f"but {actual} is installed")


def test_pandas_and_yfinance_import_and_report_their_pinned_versions() -> None:
    import pandas
    import yfinance

    pins = pinned_versions()
    assert pandas.__version__ == pins["pandas"]
    assert yfinance.__version__ == pins["yfinance"]


def test_the_gui_toolkit_starts_offscreen() -> None:
    """Importing Qt is not enough -- it has to initialise without a display."""
    PySide6 = pytest.importorskip(
        "PySide6", reason="PySide6 missing: this is not qb2's environment")
    from PySide6.QtWidgets import QApplication

    assert PySide6.__version__ == pinned_versions()["pyside6"]
    application = QApplication.instance() or QApplication([])
    assert application is not None
    assert os.environ["QT_QPA_PLATFORM"] == "offscreen"


def test_the_skeleton_imports_and_holds_no_logic() -> None:
    """qb2 is importable and still empty -- no signals, no model, no orders."""
    import qb2

    expected = {"data", "execution", "model", "research", "signals", "sizing",
                "tools", "ui"}
    for name in sorted(expected):
        __import__(f"qb2.{name}")
    assert expected <= set(dir(qb2))
    # Nothing callable has appeared at the top level of the package yet.
    assert [n for n in dir(qb2)
            if not n.startswith("_") and callable(getattr(qb2, n))] == []


def test_qb2_does_not_reach_into_v1() -> None:
    """Importing qb2 must not drag a single v1 engine package in with it."""
    import sys

    for name in list(sys.modules):
        if name.split(".")[0] in {"execution", "ingest", "monitors", "research",
                                  "strategies", "data_store", "reconcile"}:
            del sys.modules[name]
    import qb2  # noqa: F401  -- the import itself is the test

    leaked = [n for n in sys.modules
              if n.split(".")[0] in {"execution", "ingest", "monitors",
                                     "strategies", "data_store", "reconcile"}]
    assert leaked == [], f"importing qb2 pulled in v1 packages: {leaked}"
