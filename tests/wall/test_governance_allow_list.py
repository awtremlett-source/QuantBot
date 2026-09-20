"""The wall, fourth direction: the window launches ONLY what the panel launches.

The Bot tab can start the live paper loop. That is the most dangerous button in
this repo, so three things have to be true and stay true:

1. NOTHING under manual/ may launch a process except manual/bot_governance.py.
   One door, so there is one place to read when asking "what can this window
   actually do?".
2. That door's allow-list must equal the Tkinter control panel's command set
   EXACTLY -- same actions, same modules, same arguments, same "does it take
   the database" split. The window is a mirror of governance that already
   existed headlessly; it must not quietly grow a seventh command, and it must
   not silently lose one when the panel changes.
3. Each action must actually launch what it claims, with the ENGINE's
   interpreter, from the ENGINE's working directory.

Both files are PARSED, never imported: importing tools/gui.py would pull engine
packages into a test that must also run under the window's own environment,
which deliberately does not have them.

(3) runs against STUB modules in a temp directory. No test here ever invokes a
real engine command -- running the live paper loop from a test would write to
the real forward track record.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

from manual import bot_governance

REPO_ROOT = Path(__file__).resolve().parents[2]
MANUAL = REPO_ROOT / "manual"
MUSEUM = REPO_ROOT / "tests" / "museum" / "wall_violations"

PANEL = REPO_ROOT / "tools" / "gui.py"
LAUNCH_DOORWAY = "manual/bot_governance.py"

# Ways to start a process. None of these may appear outside the launch doorway.
LAUNCH_IMPORTS = frozenset({"subprocess"})
LAUNCH_CALLS = frozenset({
    "system", "popen", "spawn", "spawnl", "spawnv", "execv", "execvp",
    "Popen", "run", "call", "check_call", "check_output", "fork",
})

# A spec is (module, extra args, does it take --db).
Spec = tuple[str, tuple[str, ...], bool]


# ----------------------------------------------------------------- parsing ---

def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _string_tuple(node: ast.expr) -> tuple[str, ...]:
    if isinstance(node, (ast.Tuple, ast.List)):
        return tuple(element.value for element in node.elts
                     if isinstance(element, ast.Constant)
                     and isinstance(element.value, str))
    return ()


def action_dict(tree: ast.Module, name: str) -> dict[str, tuple[str, tuple[str, ...]]]:
    """Read a `{action: (module, extra)}` table, plain or annotated."""
    for node in ast.walk(tree):
        target: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
        elif isinstance(node, ast.AnnAssign):
            target = node.target
        else:
            continue
        if not (isinstance(target, ast.Name) and target.id == name):
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        found: dict[str, tuple[str, tuple[str, ...]]] = {}
        for key, value in zip(node.value.keys, node.value.values):
            if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                continue
            if not isinstance(value, (ast.Tuple, ast.List)) or not value.elts:
                continue
            module = value.elts[0]
            if not (isinstance(module, ast.Constant)
                    and isinstance(module.value, str)):
                continue
            extra = _string_tuple(value.elts[1]) if len(value.elts) > 1 else ()
            found[key.value] = (module.value, extra)
        return found
    return {}


def panel_specs(path: Path) -> dict[str, Spec]:
    """The Tkinter panel's command set, read out of its source.

    Two shapes: the `_DB_ACTIONS` table, and the one branch in `command()` that
    returns a literal argv (the telegram test, which takes no database).
    """
    tree = _tree(path)
    specs: dict[str, Spec] = {
        action: (module, extra, True)
        for action, (module, extra) in action_dict(tree, "_DB_ACTIONS").items()
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not (isinstance(test, ast.Compare) and len(test.comparators) == 1
                and isinstance(test.left, ast.Name) and test.left.id == "action"
                and isinstance(test.ops[0], ast.Eq)
                and isinstance(test.comparators[0], ast.Constant)):
            continue
        action = test.comparators[0].value
        if not isinstance(action, str):
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.Return) and isinstance(inner.value, ast.List):
                argv = _string_tuple(inner.value)
                if "-m" in argv:
                    index = argv.index("-m")
                    module = argv[index + 1]
                    specs[action] = (module, tuple(argv[index + 2:]), False)
    return specs


def doorway_specs(path: Path) -> dict[str, Spec]:
    tree = _tree(path)
    specs: dict[str, Spec] = {
        action: (module, extra, True)
        for action, (module, extra) in action_dict(tree, "DB_ACTIONS").items()
    }
    for action, (module, extra) in action_dict(tree, "PLAIN_ACTIONS").items():
        specs[action] = (module, extra, False)
    return specs


# ------------------------------------------------- 1. one door, no other ----

def manual_python_files() -> list[Path]:
    return [p for p in sorted(MANUAL.rglob("*.py"))
            if "__pycache__" not in p.parts]


def launch_violations(files: list[Path],
                      allowed: frozenset[str] = frozenset({LAUNCH_DOORWAY})
                      ) -> list[str]:
    """Any way of starting a process, found outside the launch doorway."""
    found: list[str] = []
    for path in files:
        name = (path.relative_to(REPO_ROOT).as_posix()
                if path.is_relative_to(REPO_ROOT) else path.name)
        if name in allowed:
            continue
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in LAUNCH_IMPORTS:
                        found.append(f"{name}: imports {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if not node.level and (node.module or "") in LAUNCH_IMPORTS:
                    found.append(f"{name}: imports from {node.module}")
            elif isinstance(node, ast.Call):
                called = ""
                if isinstance(node.func, ast.Attribute):
                    called = node.func.attr
                elif isinstance(node.func, ast.Name):
                    called = node.func.id
                if called in LAUNCH_CALLS and _looks_like_process_start(node):
                    found.append(f"{name}: calls {called}(...)")
    return found


def _looks_like_process_start(node: ast.Call) -> bool:
    """`subprocess.run` / `os.system` yes; a method called `run` on self, no."""
    if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
        return node.func.value.id in {"subprocess", "os"}
    return isinstance(node.func, ast.Name) and node.func.id == "Popen"


def test_only_the_launch_doorway_can_start_a_process() -> None:
    files = manual_python_files()
    assert len(files) > 20, f"only {len(files)} manual files scanned -- scan broken"
    assert launch_violations(files) == []


def test_scanner_goes_red_on_a_planted_launcher() -> None:
    planted = MUSEUM / "manual_launches_freely.py.txt"
    assert launch_violations([planted], allowed=frozenset()) != []


# --------------------------------------- 2. the allow-list is the panel's ----

def test_the_allow_list_equals_the_control_panels_command_set() -> None:
    panel = panel_specs(PANEL)
    doorway = doorway_specs(REPO_ROOT / LAUNCH_DOORWAY)
    assert panel, "parsed no commands out of tools/gui.py -- the parser is broken"
    assert len(panel) == 6, f"expected 6 panel commands, parsed {sorted(panel)}"
    assert doorway == panel


def test_the_doorway_builds_exactly_those_commands() -> None:
    """The parsed table and the real argv builder agree."""
    python = str(bot_governance.engine_python())
    database = str(bot_governance.engine_db())
    for action, (module, extra, takes_db) in panel_specs(PANEL).items():
        expected = [python, "-m", module]
        if takes_db:
            expected += ["--db", database]
        expected += list(extra)
        assert bot_governance.command(action) == expected


def test_an_action_outside_the_allow_list_is_refused() -> None:
    for attempt in ("", "rm", "loop; rm -rf", "execution.paper_loop", "LOOP"):
        with pytest.raises(bot_governance.UnknownAction):
            bot_governance.command(attempt)


def test_scanner_goes_red_when_the_panel_grows_a_command() -> None:
    """Birth certificate: a seventh command in the panel breaks equality."""
    planted = panel_specs(MUSEUM / "gui_with_extra_action.py.txt")
    doorway = doorway_specs(REPO_ROOT / LAUNCH_DOORWAY)
    assert "wipe" in planted, f"fixture not parsed: {sorted(planted)}"
    assert doorway != planted


# ------------------------------------------- 3. each button, against stubs ---

STUB = """import json, os, sys
from pathlib import Path
record = {"argv": sys.argv[1:], "cwd": os.getcwd(), "module": __name__}
Path(os.environ["WALL_STUB_OUT"]).write_text(json.dumps(record), encoding="utf-8")
sys.exit(int(os.environ.get("WALL_STUB_EXIT", "0")))
"""


@pytest.fixture
def stub_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fake repo root whose engine modules are stubs that record their argv."""
    for module in {spec[0] for spec in panel_specs(PANEL).values()}:
        package, _, name = module.rpartition(".")
        folder = tmp_path / package
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "__init__.py").write_text("", encoding="utf-8")
        (folder / f"{name}.py").write_text(STUB, encoding="utf-8")
    (tmp_path / "data").mkdir(exist_ok=True)
    monkeypatch.setattr(bot_governance, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(bot_governance, "engine_python", lambda: Path(sys.executable))
    monkeypatch.setenv("WALL_STUB_OUT", str(tmp_path / "seen.json"))
    return tmp_path


@pytest.mark.parametrize("action", sorted(bot_governance.ALLOWED_ACTIONS))
def test_each_button_launches_its_own_command(
        action: str, stub_engine: Path) -> None:
    module, extra, takes_db = panel_specs(PANEL)[action]
    outcome = bot_governance.run(action)

    assert outcome.returncode == 0, outcome.output
    seen = json.loads((stub_engine / "seen.json").read_text(encoding="utf-8"))
    assert seen["module"] == "__main__"           # it really ran as -m
    expected_argv = (["--db", str(stub_engine / "data" / "quantbot.db")]
                     if takes_db else [])
    assert seen["argv"] == expected_argv + list(extra)
    # Failure mode (b): the engine must run from the repo root, as the task does.
    assert Path(seen["cwd"]).resolve() == stub_engine.resolve()
    assert list(outcome.argv[1:3]) == ["-m", module]


def test_the_exit_code_is_captured_and_logged(
        stub_engine: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WALL_STUB_EXIT", "3")
    outcome = bot_governance.run("health")
    assert outcome.returncode == 3

    entries = bot_governance.read_log()
    assert [e["event"] for e in entries] == ["started", "finished"]
    assert entries[-1]["button"] == "health"
    assert entries[-1]["exit_code"] == 3
    assert all("time" in entry for entry in entries)
    # The log is the WINDOW's own book, under data/manual/ -- never the engine's.
    assert bot_governance.governance_log_path().parent.name == "manual"


def test_a_second_press_while_busy_is_refused(stub_engine: Path) -> None:
    """Failure mode (c): a double-click must not fire the loop twice."""
    assert bot_governance.begin("loop") is True
    try:
        with pytest.raises(bot_governance.Busy):
            bot_governance.run("loop")
    finally:
        bot_governance.finish()
    assert bot_governance.busy() is None
    # and the slot is reusable afterwards
    assert bot_governance.run("status").returncode == 0
    assert bot_governance.busy() is None


def test_the_killswitch_is_a_file_and_touches_nothing_else(
        stub_engine: Path) -> None:
    assert bot_governance.killswitch_armed() is False
    bot_governance.arm_killswitch()
    path = stub_engine / bot_governance.KILLSWITCH_FILENAME
    assert path.is_file()
    assert bot_governance.killswitch_armed() is True
    bot_governance.arm_killswitch()                      # idempotent
    bot_governance.disarm_killswitch()
    assert not path.exists()
    assert [e["button"] for e in bot_governance.read_log()] == [
        "killswitch_arm", "killswitch_arm", "killswitch_disarm"]
