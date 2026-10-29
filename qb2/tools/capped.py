"""Run a command inside QuantBot's resource cap: 80% of the PC's CPU, 80% of its memory (QT-23R).

Operator, 2026-10-20 (verbatim): "I stopped QT23 halfway through, there needs to be a limit on
the amount of memory and CPU it takes up. like 80% limit for each. otherwise the PC cannot take
it and will crash."  Read as: everything QuantBot runs, all its processes TOGETHER, stays at or
under 80% of the CPU and 80% of the memory, always. A FENCE: raising or removing it needs his
words. A run may ask for LESS (a test, a demo), and then gets a private job, never the shared one.

    .venv-qb2\\Scripts\\python -m qb2.tools.capped -- <command ...>

ONE named Windows Job Object (qb2/tools/job_object.py: the limits, set and read back), shared by
every QuantBot run, holds all its processes; once the last launcher has gone (finished, or
stopped by you) nothing QuantBot started is left running. The command starts SUSPENDED, is placed
in the job, then resumed. (A process cannot join a job in another job tree -- the venv's
python.exe is a launcher with a job of its own -- but a child just made can be placed.) A job
made elsewhere (Task Scheduler vs a console) that will not take the child is waited for: never
two budgets at once. FAIL CLOSED: not Windows, a library missing or the job refused -> exit 3, in
plain words. The whole PC's memory, QuantBot's or not, is qb2.tools.governor's watch.

``--clear-of-schedule`` (QT-29 F, research runners): first wait until no recorder run is going and no
scheduled start is due within 15 minutes (run_window). Default OFF: the recorder itself runs through
this wrapper and must never wait for its own run.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path

from qb2.tools import job_object as jo
from qb2.tools.job_object import CPU_SHARE, MEM_SHARE, CapError

JOB_NAME = "Local\\QuantBot-cap"
ENV = "QB2_CAP_JOB"                   # tells a child which job to prove it is inside
REFUSED = 3                           # exit code: the cap could not be applied, nothing ran
CREATE_SUSPENDED = 0x4
PROCESS_PLACE, ACCESS_DENIED = 0x0100 | 0x0001, 5           # SET_QUOTA | TERMINATE; denied
LOG = Path(os.environ.get("QB2_CAP_LOG")           # tests point it at tmp: never real logs
           or Path(__file__).resolve().parents[2] / "logs" / "cap" / "cap.log")


def log(line: str) -> None:
    """Say it, and keep it in logs/cap/cap.log (a scheduled run has no window)."""
    print(f"[cap] {line}", file=sys.stderr, flush=True)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as out:
            out.write(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} pid {os.getpid()} {line}\n")
    except OSError as why:
        print(f"[cap] could not write {LOG}: {why}", file=sys.stderr, flush=True)


def verify() -> list[str]:
    """Is THIS process inside QuantBot's cap, with the operator's limits? Reasons if not."""
    try:
        psutil, pywintypes, win32api, win32job = jo.win()
    except CapError as why:
        return [str(why)]
    name = os.environ.get(ENV)
    if not name:
        return ["it was not started through qb2.tools.capped"]
    try:
        job = win32job.OpenJobObject(win32job.JOB_OBJECT_QUERY, False, name)
    except pywintypes.error as why:
        return [f"QuantBot's cap ({name}) could not be opened: {why.strerror}"]
    try:
        inside = bool(win32job.IsProcessInJob(win32api.GetCurrentProcess(), job))
        return jo.problems(jo.read(job), inside, psutil.virtual_memory().total, os.cpu_count() or 1)
    except CapError as why:
        return [str(why)]
    finally:
        win32api.CloseHandle(job)


def launch(command: Sequence[str], *, mem_share: float = MEM_SHARE, cpu_share: float = CPU_SHARE,
           retry_s: float = 10.0, say: Callable[[str], None] = log) -> int:
    """Run the command inside the cap and return its exit code."""
    if not command:
        raise CapError("nothing to run: python -m qb2.tools.capped -- <command>")
    if not (0 < mem_share <= MEM_SHARE and 0 < cpu_share <= CPU_SHARE):
        raise CapError(f"the cap may be lowered, never raised past {MEM_SHARE:.0%} "
                       "(that needs the operator's own words)")
    psutil, pywintypes, win32api, win32job = jo.win()
    ram, cores = psutil.virtual_memory().total, os.cpu_count() or 1
    less = (mem_share, cpu_share) != (MEM_SHARE, CPU_SHARE)
    name = f"{JOB_NAME}-{os.getpid()}" if less else JOB_NAME         # less: a private job
    while True:
        try:
            job = jo.make(name, int(mem_share * ram), round(cpu_share * 10_000))
        except pywintypes.error as why:
            raise CapError(f"Windows refused the job ({why.strerror})") from why
        if bad := jo.problems(jo.read(job), True, ram, cores):
            raise CapError("the cap did not take: " + "; ".join(bad))
        try:
            child = subprocess.Popen([shutil.which(command[0]) or command[0], *command[1:]],
                                     env={**os.environ, ENV: name},
                                     creationflags=CREATE_SUSPENDED | jo.BELOW_NORMAL)
        except OSError as why:
            raise CapError(f"the command could not be started ({why})") from why
        handle = win32api.OpenProcess(PROCESS_PLACE, False, child.pid)
        try:
            win32job.AssignProcessToJobObject(job, handle)
            break
        except pywintypes.error as why:
            child.kill()
            child.wait()
            win32api.CloseHandle(job)
            if why.winerror != ACCESS_DENIED:
                raise CapError(f"Windows would not put the run in the cap ({why.strerror})") from why
            say("another QuantBot run holds the cap from a different place: waiting for it")
            time.sleep(retry_s)
        finally:
            win32api.CloseHandle(handle)
    psutil.Process(child.pid).resume()
    say(f"capped ({name}): CPU <= {cpu_share:.0%} of the machine on <= {jo.cores_allowed(cores)} of "
        f"{cores} processors, memory <= {mem_share:.0%} of RAM ({mem_share * ram / 2**30:.1f} GB), "
        f"below-normal priority: {' '.join(command)[:160]}")
    try:
        code = child.wait()
    except KeyboardInterrupt:
        say("stopped by you: everything this run started closes with the cap")
        return 130
    ext = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
    peak, limit = ext["PeakJobMemoryUsed"] / 2**30, ext["JobMemoryLimit"] / 2**30
    if code != 0 and peak >= 0.9 * limit:      # a refused allocation never counts in the peak
        say(f"STOPPED AT THE MEMORY CAP: QuantBot used {peak:.2f} GB of its {limit:.2f} GB limit "
            f"({mem_share:.0%} of RAM) and the run failed: Windows refused it more memory, so it "
            "stopped. Nothing else on the PC was touched.")
    say(f"finished with exit code {code}; peak memory {peak:.2f} GB of {limit:.2f} GB")
    return int(code)


def main(argv: Sequence[str] | None = None, *, wait: Callable[..., float] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    cut = args.index("--") if "--" in args else len(args)     # no command: refused below
    parser = argparse.ArgumentParser(usage="python -m qb2.tools.capped [--mem-share 0.05] -- <command ...>",
                                     description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--mem-share", type=float, default=MEM_SHARE,
                        help="LOWER the memory cap (a test, a demo); never above 0.80")
    parser.add_argument("--cpu-share", type=float, default=CPU_SHARE, help="LOWER the CPU cap, likewise")
    parser.add_argument("--clear-of-schedule", action="store_true",
                        help="wait until no scheduled run is due within 15 minutes (research only)")
    opts = parser.parse_args(args[:cut])
    if opts.clear_of_schedule:
        from qb2.tools import run_window    # only then: the recorder's launcher never loads it
        waited = (wait or run_window.wait_clear)(margin=run_window.MARGIN, say=log)
        log(f"clear of the schedule (waited {waited / 60:.0f} min)")
    try:
        return launch(args[cut + 1:], mem_share=opts.mem_share, cpu_share=opts.cpu_share)
    except CapError as why:
        log(f"REFUSED -- QuantBot's cap could not be applied, so nothing was run: {why}")
        return REFUSED


if __name__ == "__main__":
    sys.exit(main())
