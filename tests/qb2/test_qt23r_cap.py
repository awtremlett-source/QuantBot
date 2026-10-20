"""QT-23R: the operator's resource cap -- 80% of the CPU, 80% of the memory, for all of QuantBot.

Operator, 2026-10-20 (verbatim): "I stopped QT23 halfway through, there needs to be a limit on
the amount of memory and CPU it takes up. like 80% limit for each. otherwise the PC cannot take
it and will crash."  A fence: raising or removing it needs his words.

Offline: the cap's rule (job_object.problems), the worker count, the whole-PC memory rule, the
refusal, the one pool. Live, on this PC: the suite itself runs inside the cap; the launcher puts a
command and its grandchildren inside at below-normal priority; a process outside, or in a job
without the limits, is refused; raising the cap is refused and runs nothing; a memory hog is
stopped at a (lowered) cap in plain words; the suite refuses to start outside. Walls: no other
pool, no max_workers=len(jobs), no pytest -n; every heavy entry point refuses outside the cap
first -- each wall shown RED on a plant.
"""

from __future__ import annotations

import ast
import json
import math
import os
import re
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from qb2.tools import capped, governor
from qb2.tools import job_object as jo

ROOT = Path(__file__).resolve().parents[2]
GB = 2**30
RAM = 32 * GB
CORES = 16
GOOD = jo.Limits(jo.CPU_ENABLE | jo.CPU_HARD_CAP, 8000,
                 jo.LIMIT_AFFINITY | jo.LIMIT_PRIORITY | jo.LIMIT_JOB_MEMORY | jo.LIMIT_KILL_ON_CLOSE,
                 int(0.8 * RAM), jo.BELOW_NORMAL, (1 << 12) - 1)


# ------------------------------------------------------------------ offline ---

def test_the_operators_figures_are_pinned() -> None:
    """Changing any of these is raising or removing the fence: his words first."""
    assert (jo.CPU_SHARE, jo.MEM_SHARE, jo.CPU_RATE) == (0.80, 0.80, 8000)
    assert [jo.cores_allowed(n) for n in (1, 2, 4, 8, 16, 32)] == [1, 1, 3, 6, 12, 25]
    assert (governor.WAIT_AT, governor.STOP_AT, governor.STOP_AFTER_S) == (80.0, 90.0, 60.0)
    assert governor.STOP_NOW == 95.0 and governor.WORKER_SHARE == 0.8


def test_the_operators_limits_pass_and_lower_ones_too() -> None:
    assert jo.problems(GOOD, True, RAM, CORES) == []
    assert jo.problems(replace(GOOD, cpu_rate=5000, mem_bytes=GB, priority=jo.IDLE, affinity=0b11),
                       True, RAM, CORES) == []


@pytest.mark.parametrize(("weaker", "named"), [
    (replace(GOOD, cpu_flags=jo.CPU_ENABLE), "CPU"),                 # a soft cap
    (replace(GOOD, cpu_rate=8001), "CPU"),
    (replace(GOOD, cpu_rate=0), "CPU"),
    (replace(GOOD, affinity=(1 << 13) - 1), "processors"),               # 13 of 16 > 80%
    (replace(GOOD, affinity=0), "processors"),
    (replace(GOOD, limit_flags=GOOD.limit_flags & ~jo.LIMIT_AFFINITY), "processors"),
    (replace(GOOD, limit_flags=GOOD.limit_flags & ~jo.LIMIT_JOB_MEMORY), "memory"),
    (replace(GOOD, mem_bytes=int(0.81 * RAM)), "memory"),
    (replace(GOOD, limit_flags=GOOD.limit_flags | 0x800), "break out"),
    (replace(GOOD, limit_flags=GOOD.limit_flags | 0x1000), "break out"),
    (replace(GOOD, limit_flags=GOOD.limit_flags & ~jo.LIMIT_KILL_ON_CLOSE), "outlive"),
    (replace(GOOD, priority=0x20), "priority"),                          # NORMAL
    (replace(GOOD, limit_flags=GOOD.limit_flags & ~jo.LIMIT_PRIORITY), "priority"),
])
def test_each_weakening_is_named_in_plain_words(weaker: jo.Limits, named: str) -> None:
    found = jo.problems(weaker, True, RAM, CORES)
    assert len(found) == 1 and named in found[0], found


def test_outside_or_missing_is_refused() -> None:
    assert jo.problems(GOOD, False, RAM, CORES) == ["this process is not inside QuantBot's cap"]
    assert jo.problems(None, True, RAM, CORES) == ["no QuantBot cap was found"]


def test_workers_is_80_percent_of_the_cores_less_one() -> None:
    assert [governor.workers(n) for n in (1, 2, 4, 8, 16, 32)] == [1, 1, 2, 5, 11, 24]
    assert governor.workers() == max(1, math.floor(0.8 * (os.cpu_count() or 1)) - 1)


def test_the_whole_pc_memory_rule() -> None:
    rule = governor.Pressure()
    assert [rule.verdict(p, 0) for p in (79.9, 80.0, 89.9)] == ["go", "wait", "wait"]
    assert [rule.verdict(90.0, t) for t in (0, 59.9, 60)] == ["wait", "wait", "stop"]
    rule = governor.Pressure()
    assert [rule.verdict(p, t) for p, t in ((90, 0), (85, 30), (90, 40), (90, 99.9), (90, 100))] \
        == ["wait", "wait", "wait", "wait", "stop"]                     # a dip restarts the 60 s
    assert governor.Pressure().verdict(95.0, 0) == "stop"                # at once


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        self.t += 1.0
        return self.t


def test_the_gate_waits_says_so_once_and_goes_on() -> None:
    readings, slept, said = iter([85.0, 86.0, 70.0]), list[float](), list[str]()
    governor.gate(read=lambda: next(readings), sleep=slept.append, clock=Clock(), say=said.append)
    assert len(slept) == 2 and len(said) == 1 and "85%" in said[0] and "waiting" in said[0]


def test_the_gate_stops_cleanly_after_60_s_at_90() -> None:
    slept: list[float] = []
    with pytest.raises(governor.MemoryStop, match="STOPPED CLEANLY"):
        governor.gate(read=lambda: 92.0, sleep=slept.append, clock=Clock(), say=lambda _: None)
    assert 59 <= len(slept) <= 61


def test_the_watch_stops_the_main_thread_with_the_reason() -> None:
    readings, stops, said = iter([50.0, 96.0]), list[int](), list[str]()
    governor.watch(read=lambda: next(readings), sleep=lambda _: None, clock=Clock(),
                   say=said.append, stop=lambda: stops.append(1))
    assert stops == [1] and "STOPPED CLEANLY" in said[0]


def test_assert_capped_refuses_in_plain_words(monkeypatch: pytest.MonkeyPatch,
                                              tmp_path: Path) -> None:
    monkeypatch.setattr(capped, "LOG", tmp_path / "cap.log")
    with pytest.raises(governor.NotCapped) as refused:
        governor.assert_capped(verify=lambda: ["it was not started through qb2.tools.capped"])
    words = str(refused.value)
    assert isinstance(refused.value, SystemExit)
    assert words.startswith("REFUSED") and "python -m qb2.tools.capped --" in words
    assert "REFUSED" in (tmp_path / "cap.log").read_text(encoding="utf-8")
    governor.assert_capped(verify=lambda: [], start_watch=False)         # inside: no fuss


def test_run_pool_keeps_job_order_and_gates_each_worker() -> None:
    gates: list[int] = []
    assert governor.run_pool(abs, [-3, 2, -1], gate_fn=lambda: gates.append(1)) == [3, 2, 1]
    assert len(gates) == 3


def test_run_pool_stops_cleanly_and_passes_errors_on() -> None:
    calls: list[int] = []

    def short_of_memory() -> None:
        calls.append(1)
        if len(calls) == 2:
            raise governor.MemoryStop("STOPPED CLEANLY")
    with pytest.raises(governor.MemoryStop):
        governor.run_pool(abs, [1, 2, 3], gate_fn=short_of_memory)
    assert len(calls) == 2                                               # no third worker
    with pytest.raises(ValueError):
        governor.run_pool(math.sqrt, [4.0, -1.0], gate_fn=lambda: None)


# --------------------------------------------------------- live, this PC ---

PROBE = """
import json, os, subprocess, sys
import psutil
from qb2.tools import capped
me = {"verify": capped.verify(), "nice": psutil.Process().nice(), "job": os.environ.get(capped.ENV),
      "cpus": len(psutil.Process().cpu_affinity())}
if sys.argv[1:] == ["outer"]:
    run = subprocess.run([sys.executable, __file__, "inner"], capture_output=True, text=True)
    me["grandchild"] = json.loads(run.stdout)
print(json.dumps(me))
"""

UNLIMITED = """
import json, os, win32api, win32job
from qb2.tools import capped
name = f"Local\\\\QuantBot-test-unlimited-{os.getpid()}"
job = win32job.CreateJobObject(None, name)
win32job.AssignProcessToJobObject(job, win32api.GetCurrentProcess())
os.environ[capped.ENV] = name
print(json.dumps(capped.verify()))
"""

HOG = """
import sys
held, mb = [], 0
try:
    while mb < int(sys.argv[1]):              # bounded: a broken cap cannot run away
        held.append(bytearray(16 * 2**20))
        mb += 16
except MemoryError:
    print(f"hog: Windows refused more memory at {mb} MB")
    sys.exit(1)
print(f"hog: NOT STOPPED at {mb} MB")
"""


def run(args: list[str], tmp_path: Path, *, drop_cap: bool = False,
        extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(ROOT), "QB2_CAP_LOG": str(tmp_path / "cap.log"),
           **(extra or {})}
    if drop_cap:
        env.pop(capped.ENV, None)
    return subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)


def script(tmp_path: Path, name: str, text: str) -> str:
    (tmp_path / name).write_text(text, encoding="utf-8")
    return str(tmp_path / name)


def launcher(*opts: str) -> list[str]:
    return [sys.executable, "-m", "qb2.tools.capped", *opts, "--", sys.executable]


def test_this_suite_runs_inside_the_cap() -> None:
    assert capped.verify() == []
    if os.environ[capped.ENV] == capped.JOB_NAME:          # the shared job holds exactly 80%
        import psutil  # type: ignore[import-untyped]
        import win32job  # type: ignore[import-untyped]
        job = win32job.OpenJobObject(win32job.JOB_OBJECT_QUERY, False, capped.JOB_NAME)
        held = jo.read(job)
        eighty = int(0.8 * psutil.virtual_memory().total)
        assert eighty - 4096 < held.mem_bytes <= eighty          # Windows rounds to a 4 KB page
        assert (held.cpu_rate, held.priority) == (8000, jo.BELOW_NORMAL)
        assert held.affinity == (1 << jo.cores_allowed()) - 1    # 12 of 16 processors


def test_the_launcher_holds_the_command_and_its_grandchildren(tmp_path: Path) -> None:
    done = run([*launcher("--mem-share", "0.05"), script(tmp_path, "probe.py", PROBE), "outer"],
               tmp_path)
    assert done.returncode == 0, done.stderr
    me = json.loads(done.stdout.strip().splitlines()[-1])
    assert me["verify"] == [] and me["grandchild"]["verify"] == []
    assert me["nice"] == me["grandchild"]["nice"] == jo.BELOW_NORMAL
    assert me["cpus"] == me["grandchild"]["cpus"] == jo.cores_allowed()     # 12 of 16
    assert me["job"] == me["grandchild"]["job"] != capped.JOB_NAME       # less = a private job


def test_a_process_outside_the_cap_is_refused(tmp_path: Path) -> None:
    check = [sys.executable, "-c", "from qb2.tools import governor; governor.assert_capped()"]
    outside = run(check, tmp_path, drop_cap=True)
    assert outside.returncode == 1 and outside.stderr.strip().startswith("[cap] REFUSED")
    assert "not started through qb2.tools.capped" in outside.stderr
    fake = run(check, tmp_path, extra={capped.ENV:"Local\\QuantBot-cap-no-such-job"})
    assert fake.returncode == 1 and "could not be opened" in fake.stderr


def test_a_job_without_the_operators_limits_is_refused(tmp_path: Path) -> None:
    done = run([sys.executable, script(tmp_path, "unlimited.py", UNLIMITED)], tmp_path)
    found = " | ".join(json.loads(done.stdout))
    assert "not inside" not in found                                     # inside, but weak
    assert all(word in found for word in ("CPU", "memory", "outlive", "priority")), found


@pytest.mark.parametrize("raised", [("--mem-share", "0.81"), ("--cpu-share", "0.81"),
                                    ("--cpu-share", "0")])
def test_raising_the_cap_is_refused_and_runs_nothing(tmp_path: Path, raised: tuple[str, str]) -> None:
    marker = tmp_path / "ran"
    done = run([*launcher(*raised), "-c", f"open(r'{marker}', 'w')"], tmp_path)
    assert done.returncode == capped.REFUSED and not marker.exists()
    assert "never raised past 80%" in done.stderr


def test_a_memory_hog_is_stopped_at_the_cap_in_plain_words(tmp_path: Path) -> None:
    if governor.pc_memory() >= governor.WAIT_AT:
        pytest.skip("the whole PC is at >= 80% memory: no hog added, even a small one")
    import psutil
    limit_mb = int(0.02 * psutil.virtual_memory().total / 2**20)
    done = run([*launcher("--mem-share", "0.02"), script(tmp_path, "hog.py", HOG),
                str(2 * limit_mb)], tmp_path)
    assert done.returncode == 1, done.stdout + done.stderr
    refused = re.search(r"refused more memory at (\d+) MB", done.stdout)
    assert refused is not None and int(refused.group(1)) <= limit_mb
    assert "STOPPED AT THE MEMORY CAP" in done.stderr and "Nothing else on the PC" in done.stderr


def test_the_suite_refuses_to_start_outside_the_cap(tmp_path: Path) -> None:
    done = run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                "tests/qb2/test_lean_lines.py"], tmp_path, drop_cap=True)
    assert done.returncode == capped.REFUSED, done.stdout[-500:]
    assert "REFUSED" in done.stdout + done.stderr


# -------------------------------------------------------------------- walls ---

POOL = "a process pool outside governor.run_pool"
BANNED = {
    POOL: re.compile(r"ProcessPoolExecutor\s*\(|multiprocessing\.Pool\b|\bmp\.Pool\b|\bPool\s*\("),
    "max_workers=len(jobs)": re.compile(r"max_workers\s*=\s*len\("),
    "pytest -n": re.compile(r"pytest[^\n]*\s-n\s|\bxdist\b|-n\s+auto\b"),
}
ALLOWED = {"qb2/tools/governor.py": {POOL}}
PRE_CAP = {   # records of runs made BEFORE the cap; a copy run today is refused by firewall.load
    "docs/reports/QT-21_partD_driver.py.txt", "docs/reports/QT-22_drills_driver.py.txt"}
SKIP_TOP = {"archive", "data", "logs"}                  # top level only: qb2/data/ is code
SKIP_DIRS = {".git", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
SELF = "tests/qb2/test_qt23r_cap.py"


def scanned(root: Path) -> list[Path]:
    """Every script in the repo; the venvs, the data and the caches are pruned, not walked."""
    out = []
    for here, dirs, files in os.walk(root):
        top = Path(here) == root
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith(".venv")
                         and not (top and d in SKIP_TOP))
        out += [Path(here) / f for f in sorted(files) if f.endswith((".py", ".py.txt", ".bat", ".ps1"))]
    return out


def pool_breaches(root: Path) -> list[str]:
    out = []
    for path in scanned(root):
        rel = path.relative_to(root).as_posix()
        if rel in PRE_CAP or rel == SELF:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        out += [f"{rel}: {label}" for label, pattern in BANNED.items()
                if pattern.search(text) and label not in ALLOWED.get(rel, set())]
    return out


DOORS = {"qb2/research/firewall.py": {"load", "score"}}   # plus every main() below
DOOR_DIRS = ("qb2/research", "qb2/advisor")


def first_call_is_the_cap(fn: ast.FunctionDef) -> bool:
    body = fn.body[1:] if (isinstance(fn.body[0], ast.Expr) and isinstance(fn.body[0].value, ast.Constant)
                           and isinstance(fn.body[0].value.value, str)) else fn.body
    head = body[0] if body else None
    return (isinstance(head, ast.Expr) and isinstance(head.value, ast.Call)
            and getattr(head.value.func, "id", getattr(head.value.func, "attr", "")) == "assert_capped")


def door_breaches(root: Path) -> list[str]:
    out = []
    for folder in DOOR_DIRS:
        for path in sorted((root / folder).glob("*.py")) if (root / folder).is_dir() else []:
            rel = path.relative_to(root).as_posix()
            wanted = {"main"} | DOORS.get(rel, set())
            defs = {n.name: n for n in ast.parse(path.read_text(encoding="utf-8")).body
                    if isinstance(n, ast.FunctionDef)}
            out += [f"{rel}: {name}() missing" for name in sorted(DOORS.get(rel, set()) - set(defs))]
            out += [f"{rel}: {name}() does not refuse outside the cap first"
                    for name, fn in sorted(defs.items()) if name in wanted and not first_call_is_the_cap(fn)]
    for path in sorted((root / "docs" / "reports").glob("*driver*.py.txt")):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        if rel not in PRE_CAP and "assert_capped(" not in text and "run_pool(" not in text:
            out.append(f"{rel}: a driver that never asks for the cap")
    return out


def test_no_pool_outside_the_governor_and_no_pytest_n() -> None:
    assert pool_breaches(ROOT) == []


def test_every_heavy_entry_point_refuses_outside_the_cap_first() -> None:
    assert door_breaches(ROOT) == []


def test_the_pool_wall_goes_red_on_a_plant(tmp_path: Path) -> None:
    for folder in ("qb2/tools", "qb2/data", "data"):
        (tmp_path / folder).mkdir(parents=True)
    (tmp_path / "driver.py").write_text(
        "with ProcessPoolExecutor(max_workers=len(jobs)) as pool:\n    pass\n", encoding="utf-8")
    (tmp_path / "run.ps1").write_text("python -m pytest -n auto tests\n", encoding="utf-8")
    (tmp_path / "qb2" / "tools" / "governor.py").write_text(
        "ProcessPoolExecutor(max_workers=width)\n", encoding="utf-8")
    (tmp_path / "qb2" / "data" / "hidden.py").write_text("multiprocessing.Pool(4)\n", encoding="utf-8")
    (tmp_path / "data" / "store.py").write_text("multiprocessing.Pool(4)\n", encoding="utf-8")
    assert sorted(pool_breaches(tmp_path)) == sorted([      # top-level data/ is not code
        f"driver.py: {POOL}", "driver.py: max_workers=len(jobs)", f"qb2/data/hidden.py: {POOL}",
        "run.ps1: pytest -n"])


def test_the_door_wall_goes_red_on_a_plant(tmp_path: Path) -> None:
    (tmp_path / "qb2" / "research").mkdir(parents=True)
    (tmp_path / "docs" / "reports").mkdir(parents=True)
    (tmp_path / "qb2" / "research" / "late.py").write_text(
        'def main():\n    """Doc."""\n    work()\n    assert_capped()\n', encoding="utf-8")
    (tmp_path / "qb2" / "research" / "fine.py").write_text(
        'def main():\n    """Doc."""\n    assert_capped()\n    work()\n', encoding="utf-8")
    (tmp_path / "qb2" / "research" / "firewall.py").write_text(
        "def load():\n    assert_capped()\n", encoding="utf-8")
    (tmp_path / "docs" / "reports" / "QT-99_x_driver.py.txt").write_text("work()\n", encoding="utf-8")
    assert door_breaches(tmp_path) == [
        "qb2/research/firewall.py: score() missing",
        "qb2/research/late.py: main() does not refuse outside the cap first",
        "docs/reports/QT-99_x_driver.py.txt: a driver that never asks for the cap"]
