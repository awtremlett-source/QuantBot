"""Offline tests for the control panel's Controller (no Tk event loop is ever
started -- the Tk layer is a thin shell over this object)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from tools.gui import Controller
from tools.installer import KILLSWITCH_FILE, RunResult


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def run(self, args: Sequence[str]) -> RunResult:
        self.calls.append(list(args))
        return RunResult(0, "ok")


def _controller(tmp_path: Path) -> tuple[Controller, FakeRunner]:
    runner = FakeRunner()
    return Controller(tmp_path, runner=runner), runner


# ------------------------------------------------------------ commands


def test_every_button_constructs_its_exact_command(tmp_path: Path) -> None:
    controller, runner = _controller(tmp_path)
    python = str(tmp_path / ".venv" / "Scripts" / "python.exe")
    db = str(tmp_path / "data" / "quantbot.db")

    expected = {
        "status": [python, "-m", "monitors.status", "--db", db],
        "drill": [python, "-m", "monitors.status", "--db", db, "--drill"],
        "loop": [python, "-m", "execution.paper_loop", "--db", db],
        "health": [python, "-m", "monitors.health", "--db", db],
        "backup": [python, "-m", "tools.backup", "--db", db],
        "telegram_test": [python, "-m", "monitors.notify", "--test"],
    }
    for action, argv in expected.items():
        assert controller.command(action) == argv

    controller.run_action("loop")
    assert runner.calls == [expected["loop"]]  # executed EXACTLY as constructed


# ------------------------------------------------------------ busy guard


def test_one_action_at_a_time(tmp_path: Path) -> None:
    controller, _ = _controller(tmp_path)
    assert controller.begin("loop") is True
    assert controller.busy == "loop"
    assert controller.begin("health") is False  # refused mid-run
    controller.finish()
    assert controller.begin("health") is True
    controller.finish()


# ------------------------------------------------------------ killswitch


def test_killswitch_arm_disarm_touches_exactly_one_file(tmp_path: Path) -> None:
    controller, _ = _controller(tmp_path)
    assert controller.killswitch_armed() is False

    message = controller.arm_killswitch()
    assert "ARMED" in message
    assert (tmp_path / KILLSWITCH_FILE).exists()
    # The ONLY file the controller may create is the killswitch itself.
    assert [p.name for p in tmp_path.iterdir()] == [KILLSWITCH_FILE]
    assert controller.killswitch_armed() is True
    controller.arm_killswitch()  # idempotent

    message = controller.disarm_killswitch()
    assert "DISARMED" in message
    assert not (tmp_path / KILLSWITCH_FILE).exists()
    assert controller.killswitch_armed() is False


# ------------------------------------------------------------ panels


def test_panels_read_gracefully_when_files_absent(tmp_path: Path) -> None:
    controller, _ = _controller(tmp_path)
    assert "no data" in controller.loop_log_tail()
    assert "no health report yet" in controller.latest_health_report()
    assert controller.telegram_configured() is False  # no .env in tmp root


def test_panels_read_newest_health_and_log_tail(tmp_path: Path) -> None:
    controller, _ = _controller(tmp_path)
    (tmp_path / "data" / "health").mkdir(parents=True)
    (tmp_path / "data" / "loop.log").write_text(
        "\n".join(f"line{i}" for i in range(100)), encoding="utf-8"
    )
    (tmp_path / "data" / "health" / "health-202607.txt").write_text("old")
    (tmp_path / "data" / "health" / "health-202608.txt").write_text("new")

    tail = controller.loop_log_tail(max_lines=40)
    assert tail.splitlines()[0] == "line60" and tail.splitlines()[-1] == "line99"
    assert controller.latest_health_report() == "new"
