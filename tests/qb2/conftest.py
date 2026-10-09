"""Keep qb2's tests on qb2's interpreter, without breaking v1's test run.

Two things have to be true at once:

* ``python -m pytest -q`` in v1's ``.venv`` must stay exactly as green as it was.
  qb2's environment is not installed there and never will be, so collecting
  these tests by default would turn v1's daily gate red for a reason that has
  nothing to do with v1.
* Running them AT v1's interpreter on purpose must FAIL, loudly. A smoke test
  that shrugs when pointed at the wrong environment is not a smoke test.

So: skipped when nobody asked for them, run when somebody did.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest

QB2_ONLY = ("PySide6",)   # present in .venv-qb2, absent from v1's .venv


def _explicitly_requested(config: pytest.Config) -> bool:
    """True when the command line actually named qb2's tests."""
    return any("qb2" in str(argument) for argument in config.args)


def pytest_ignore_collect(collection_path: Path,
                          config: pytest.Config) -> bool | None:
    if _explicitly_requested(config):
        return None            # asked for -> run, and fail if the env is wrong
    missing = [name for name in QB2_ONLY
               if importlib.util.find_spec(name) is None]
    if missing:
        print(f"tests/qb2 NOT COLLECTED: this interpreter is missing "
              f"{', '.join(missing)}. Run them with .venv-qb2:\n"
              f"  .venv-qb2\\Scripts\\python.exe -m pytest tests/qb2 -q",
              file=sys.stderr)
        return True
    return None


# ------------------------------------------- the default run stays offline ---
#
# QT-13: the practice-account smoke test was gated only on keys existing, and
# the keys exist on the operator's PC, so every default run called Trading 212.
# A test marked `network` now runs only when asked: pytest -m network tests/qb2
# (Here, not in pyproject.toml: that file is inside v1's frozen fingerprint.)

def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "network: reaches a real server; off unless -m network")


def pytest_collection_modifyitems(config: pytest.Config,
                                  items: list[pytest.Item]) -> None:
    if config.getoption("markexpr"):
        return                 # an explicit -m chooses for itself
    offline = [item for item in items if "network" not in item.keywords]
    if len(offline) != len(items):
        config.hook.pytest_deselected(
            items=[item for item in items if "network" in item.keywords])
        items[:] = offline


# ------------------------------------------- tests never write real data -----
#
# test_recorder.py once called the recorder without a manifest of its own, and
# every test run appended "AAPL 1m lost" to the REAL manifest -- 19 lines between
# 2 and 5 October before anyone noticed. Passing tmp_path everywhere is a rule
# people forget, so this makes forgetting impossible: while a qb2 test is
# running, any WRITE under the repository's data/, logs/ or reports/ is refused.
# Reads are untouched. Python-level writes are caught by an audit hook; parquet
# goes through pyarrow's own file code, so DataFrame.to_parquet is guarded too.

_REPO = Path(__file__).resolve().parents[2]
PROTECTED = tuple(os.path.normcase(str(_REPO / name)) + os.sep
                  for name in ("data", "logs", "reports"))
_WRITE_EVENTS = {"os.remove", "os.rename", "os.replace", "os.mkdir",
                 "os.rmdir", "shutil.rmtree", "shutil.move", "shutil.copyfile"}
_guard_on = False


def _is_protected(target: object) -> bool:
    if isinstance(target, bytes):
        target = target.decode(errors="replace")
    if not isinstance(target, (str, os.PathLike)):
        return False                      # a file descriptor, not a path
    full = os.path.normcase(os.path.abspath(os.fspath(target))) + os.sep
    return full.startswith(PROTECTED)


def _refuse(target: object) -> None:
    raise PermissionError(f"a test tried to write real data: {target!s} -- "
                          f"pass it a tmp_path instead")


def _audit(event: str, args: tuple[object, ...]) -> None:
    if not _guard_on:
        return
    if event == "open":
        path, mode, flags = args
        writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
            mode is None and isinstance(flags, int)
            and flags & (os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT))
        if writing and _is_protected(path):
            _refuse(path)
    elif event in _WRITE_EVENTS and args and any(
            _is_protected(a) for a in args[:2]):
        _refuse(args[0])


sys.addaudithook(_audit)       # hooks cannot be removed; _guard_on gates it


@pytest.fixture(autouse=True)
def _no_real_data_writes(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    global _guard_on
    original = pd.DataFrame.to_parquet

    def guarded(self: pd.DataFrame, path: object = None,
                *args: object, **kwargs: object) -> object:
        if _is_protected(path):
            _refuse(path)
        return original(self, path, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "to_parquet", guarded)
    _guard_on = True
    try:
        yield
    finally:
        _guard_on = False
