"""How much QuantBot may run at once, and the refusal outside the cap (QT-23R).

Windows enforces the operator's cap (qb2.tools.capped: 80% of the CPU, 80% of the memory, for all
of QuantBot together). This is the polite half, which keeps a run well inside it:
* workers() = max(1, floor(0.8 x logical cores) - 1): 11 on a 16-core PC.
* gate(): before each new worker or unit of heavy work. The WHOLE PC (QuantBot's memory or not)
  at >= 80% -> wait, logged; >= 90% for 60 s -> MemoryStop, a clean stop (results are saved
  atomically, so the run resumes). >= 95% stops at once: past that, 60 s is too long to wait.
* assert_capped(): the first call of every heavy entry point. Outside the cap it refuses, in
  plain words (fail closed). Inside, a background watch applies the same stop rule while the
  run works: it interrupts the main thread, which unwinds as on Ctrl+C.
* run_pool(fn, jobs): THE process pool -- at most workers() processes, gated, results in job
  order. Any other process pool or parallel test runner is banned, and so is a pool as wide as
  its job list (wall: tests/qb2/test_qt23r_cap.py).
"""

from __future__ import annotations

import _thread
import math
import multiprocessing
import os
import threading
import time
from collections.abc import Callable, Iterable
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from dataclasses import dataclass
from typing import Literal, TypeVar

from qb2.tools import capped

J = TypeVar("J")
R = TypeVar("R")
WORKER_SHARE = 0.8
WAIT_AT, STOP_AT, STOP_NOW = 80.0, 90.0, 95.0    # the whole PC's memory in use, percent
STOP_AFTER_S, POLL_S, SAY_EVERY_S = 60.0, 1.0, 30.0
_watching = threading.Event()


class NotCapped(SystemExit):
    """The refusal: Python prints the words and exits with status 1, no traceback."""


class MemoryStop(RuntimeError):
    """The whole PC stayed short of memory: stop cleanly, carry on later."""


def workers(cores: int | None = None) -> int:
    """How many worker processes a pool may have."""
    n = cores if cores is not None else (os.cpu_count() or 1)
    return max(1, math.floor(WORKER_SHARE * n) - 1)


def pc_memory() -> float:
    """The whole PC's memory in use, percent."""
    import psutil  # type: ignore[import-untyped]
    return float(psutil.virtual_memory().percent)


@dataclass
class Pressure:
    """The whole-PC memory rule, fed one reading at a time."""
    since: float | None = None

    def verdict(self, percent: float, now: float) -> Literal["go", "wait", "stop"]:
        if percent >= STOP_NOW:
            return "stop"
        if percent < STOP_AT:
            self.since = None
        elif self.since is None:
            self.since = now
        if self.since is not None and now - self.since >= STOP_AFTER_S:
            return "stop"
        return "wait" if percent >= WAIT_AT else "go"


def stop_words(percent: float) -> str:
    return (f"STOPPED CLEANLY: the whole PC is short of memory ({percent:.0f}% in use; the rule is "
            f">= {STOP_AT:.0f}% for {STOP_AFTER_S:.0f} s, or >= {STOP_NOW:.0f}% at once). Finished "
            "results are saved; run it again later and it carries on.")


def gate(*, read: Callable[[], float] = pc_memory, sleep: Callable[[float], None] = time.sleep,
         clock: Callable[[], float] = time.monotonic, say: Callable[[str], None] = capped.log) -> None:
    """Return when there is room for more work; MemoryStop if the PC stays short."""
    rule, said = Pressure(), -math.inf
    while (verdict := rule.verdict(percent := read(), now := clock())) != "go":
        if verdict == "stop":
            say(stop_words(percent))
            raise MemoryStop(stop_words(percent))
        if now - said >= SAY_EVERY_S:
            say(f"the whole PC is at {percent:.0f}% memory (>= {WAIT_AT:.0f}%): waiting before "
                "starting more work")
            said = now
        sleep(POLL_S)


def watch(*, read: Callable[[], float] = pc_memory, sleep: Callable[[float], None] = time.sleep,
          clock: Callable[[], float] = time.monotonic, say: Callable[[str], None] = capped.log,
          stop: Callable[[], None] = _thread.interrupt_main) -> None:
    """While a run works: on the stop rule, say why and stop the main thread."""
    rule = Pressure()
    while rule.verdict(percent := read(), clock()) != "stop":
        sleep(POLL_S)
    say(stop_words(percent))
    stop()


def assert_capped(*, verify: Callable[[], list[str]] = capped.verify,
                  start_watch: bool = True) -> None:
    """Refuse, in plain words, unless this process is inside the operator's cap."""
    if reasons := verify():
        capped.log("REFUSED (not inside the cap): " + "; ".join(reasons))
        raise NotCapped(
            "REFUSED -- QuantBot runs heavy work only inside its cap (80% of the CPU, 80% of the "
            f"memory), and this process is not: {'; '.join(reasons)}. Start it as:\n"
            "  .venv-qb2\\Scripts\\python -m qb2.tools.capped -- <the same command>")
    if start_watch and multiprocessing.parent_process() is None and not _watching.is_set():
        _watching.set()                                  # one watch, in the main process only
        threading.Thread(target=watch, daemon=True, name="qb2-memory-watch").start()


def run_pool(fn: Callable[[J], R], jobs: Iterable[J], *,
             gate_fn: Callable[[], None] = gate) -> list[R]:
    """fn over jobs in at most workers() processes, gated before each; results in job order.

    fn must be a module-level function (Windows starts workers fresh). On MemoryStop no new
    worker starts, the running ones finish, and the stop is raised: fn should save its own
    result atomically if the run is to resume."""
    assert_capped()
    todo = list(jobs)
    width = min(workers(), len(todo)) or 1
    done: dict[int, R] = {}
    with ProcessPoolExecutor(max_workers=width) as pool:
        running: dict[Future[R], int] = {}
        for i, job in enumerate(todo):
            while len(running) >= width:
                for f in wait(running, return_when=FIRST_COMPLETED).done:
                    done[running.pop(f)] = f.result()
            gate_fn()
            running[pool.submit(fn, job)] = i
        for f in wait(running).done:
            done[running[f]] = f.result()
    return [done[i] for i in range(len(todo))]
