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
import sys
from pathlib import Path

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
