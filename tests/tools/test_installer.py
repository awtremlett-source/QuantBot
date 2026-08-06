"""Offline tests for the installer: every system call goes through a fake
runner, so these assert the exact commands CONSTRUCTED without executing any
schtasks. The generated bat is asserted byte-exact from a temp root -- proving
no hardcoded machine paths survive."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from tools.installer import (
    LOGON_FALLBACK,
    TASK_DAILY,
    TASK_LOGON,
    RunResult,
    cmd_install,
    cmd_uninstall,
    cmd_verify,
    generate_bat,
)

_REAL_REQUIREMENTS = Path(__file__).resolve().parents[2] / "requirements.txt"


class FakeRunner:
    """Records every command; answers via an injectable responder."""

    def __init__(
        self, responder: Callable[[list[str]], RunResult] | None = None
    ) -> None:
        self.calls: list[list[str]] = []
        self._responder = responder if responder is not None else (
            lambda args: RunResult(0, "")
        )

    def run(self, args: Sequence[str]) -> RunResult:  # Runner protocol
        call = list(args)
        self.calls.append(call)
        return self._responder(call)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A minimal repo root: real pins, an env template, and a fake venv."""
    (tmp_path / "requirements.txt").write_text(_REAL_REQUIREMENTS.read_text())
    (tmp_path / ".env.example").write_text("T212_API_KEY=\n")
    venv_python = tmp_path / ".venv" / "Scripts" / "python.exe"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_bytes(b"")
    return tmp_path


# ------------------------------------------------------------ bat generation


def test_generated_bat_is_rendered_from_the_resolved_root(root: Path) -> None:
    bat = generate_bat(root)
    content = bat.read_text()
    assert content == (
        f"cd /d {root}\n"
        ".venv\\Scripts\\python.exe -m execution.paper_loop "
        "--db data\\quantbot.db >> data\\loop.log 2>&1\n"
    )
    # No machine path other than the resolved root itself survives generation.
    assert "C:\\Users\\mtrem\\TRADING" not in content
    # LF endings, byte-reproducible (the live byte-identical check depends on it).
    assert b"\r" not in bat.read_bytes()


# ------------------------------------------------------------ install


def test_install_is_idempotent_and_always_forces(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = FakeRunner()
    assert cmd_install(root, runner, env={}) == 0
    first_bat = (root / "tools" / "run_paper_loop.bat").read_bytes()
    first_out = capsys.readouterr().out
    assert "initialized fresh DB" in first_out

    assert cmd_install(root, runner, env={}) == 0
    second_out = capsys.readouterr().out
    # Second run REPAIRS, never duplicates: same bat bytes, DB kept + checked.
    assert (root / "tools" / "run_paper_loop.bat").read_bytes() == first_bat
    assert "existing DB integrity ok" in second_out
    creates = [c for c in runner.calls if c[1] == "/Create"]
    assert len(creates) == 4  # daily + logon, twice
    assert all("/F" in c for c in creates)


def test_install_refuses_wrong_python_before_any_side_effect(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = FakeRunner()
    assert cmd_install(root, runner, version_info=(3, 12), env={}) == 1
    assert runner.calls == []  # refused BEFORE touching the system
    assert not (root / "tools" / "run_paper_loop.bat").exists()
    assert "Python 3.13" in capsys.readouterr().out


def test_logon_denied_prints_gui_fallback_and_continues(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def deny_logon(args: list[str]) -> RunResult:
        if "/Create" in args and TASK_LOGON in args:
            return RunResult(1, "ERROR: Access is denied.")
        return RunResult(0, "")

    runner = FakeRunner(deny_logon)
    # NOT fatal: install completes and the verify report still runs (no RED --
    # the fresh-init DB and unset backup env are WARNs).
    assert cmd_install(root, runner, env={}) == 0
    out = capsys.readouterr().out
    assert LOGON_FALLBACK in out
    assert "VERIFY OVERALL:" in out


def test_install_creates_env_file_from_template(root: Path) -> None:
    cmd_install(root, FakeRunner(), env={})
    assert (root / ".env").read_text() == "T212_API_KEY=\n"


# ------------------------------------------------------------ verify


def test_verify_missing_db_is_red_and_exit_nonzero(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cmd_verify(root, FakeRunner(), env={}) == 1
    assert "database: RED" in capsys.readouterr().out


def test_verify_unset_backup_destination_warns(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cmd_verify(root, FakeRunner(), env={})
    assert "backup_destination: WARN" in capsys.readouterr().out
    cmd_verify(root, FakeRunner(), env={"QUANTBOT_BACKUP_DIR": "X:\\backups"})
    assert "backup_destination: OK - QUANTBOT_BACKUP_DIR=X:\\backups" in (
        capsys.readouterr().out
    )


def test_verify_task_aggregation(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cmd_install(root, FakeRunner(), env={})  # provision the DB
    capsys.readouterr()

    def absent_tasks(args: list[str]) -> RunResult:
        if "/Query" in args:
            return RunResult(1, "ERROR: The system cannot find the file specified.")
        return RunResult(0, "")

    # Missing logon task is only a WARN...
    def absent_logon(args: list[str]) -> RunResult:
        if "/Query" in args and TASK_LOGON in args:
            return RunResult(1, "not found")
        return RunResult(0, "")

    assert cmd_verify(root, FakeRunner(absent_logon), env={}) == 0
    out = capsys.readouterr().out
    assert f"task_{TASK_LOGON}: WARN" in out
    # ...but a missing DAILY task is RED and fails verify.
    assert cmd_verify(root, FakeRunner(absent_tasks), env={}) == 1
    assert f"task_{TASK_DAILY}: RED" in capsys.readouterr().out


# ------------------------------------------------------------ uninstall


def test_uninstall_removes_exactly_the_two_tasks(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = FakeRunner()
    assert cmd_uninstall(root, runner) == 0
    deletes = [c for c in runner.calls if "/Delete" in c]
    assert deletes == [
        ["schtasks", "/Delete", "/TN", TASK_DAILY, "/F"],
        ["schtasks", "/Delete", "/TN", TASK_LOGON, "/F"],
    ]
    out = capsys.readouterr().out
    assert f"task {TASK_DAILY}: removed" in out
    assert "data/ left untouched" in out


def test_uninstall_reports_never_registered_tasks(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = FakeRunner(lambda args: RunResult(1, "not found"))
    assert cmd_uninstall(root, runner) == 0
    assert all("/Delete" not in c for c in runner.calls)  # nothing to delete
    assert "was not registered" in capsys.readouterr().out
