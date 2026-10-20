"""The Windows Job Object behind QuantBot's resource cap: the operator's limits, set and read back.

qb2/tools/capped.py launches runs inside one of these; :func:`problems` is THE rule a job must
meet (governor.assert_capped refuses a process whose job does not). The operator's figures,
2026-10-20, a fence -- raising or removing them needs his words, lowering does not:
* CPU, two fences. (1) Hard CPU rate cap at 80% of the machine (ENABLE | HARD_CAP, CpuRate 8000).
  Windows enforces it on AVERAGE: in single seconds the job ran up to ~6 points over it (QT-23R
  proof (a): 85.1% under 80%, 36.7% under a 30% test cap). (2) So the job may also use at most
  floor(80% x logical cores) of the processors (affinity: 12 of 16 = 75%), which holds at every
  instant.
* Memory: 80% of physical RAM for the whole job (JOB_MEMORY), Windows rounding to a 4 KB page.
* No breakaway; KILL_ON_JOB_CLOSE; priority BELOW_NORMAL.
FAIL CLOSED: not Windows or a library missing -> CapError, in plain words. pywin32 has no call for
CPU rate control, so that one structure goes through ctypes.
"""

from __future__ import annotations

import ctypes
import math
import os
import sys
from dataclasses import dataclass
from typing import Any

CPU_SHARE = 0.80                      # the operator's figures: a fence (see above)
MEM_SHARE = 0.80
CPU_RATE = round(CPU_SHARE * 10_000)  # Windows counts CPU rate in 1/10,000ths of the machine
CPU_ENABLE, CPU_HARD_CAP, CPU_RATE_INFO = 0x1, 0x4, 15                       # winnt.h
LIMIT_AFFINITY, LIMIT_PRIORITY, LIMIT_JOB_MEMORY, LIMIT_KILL_ON_CLOSE = 0x10, 0x20, 0x200, 0x2000
LIMIT_BREAKAWAY = 0x800 | 0x1000                            # BREAKAWAY_OK | SILENT_BREAKAWAY_OK
BELOW_NORMAL, IDLE = 0x4000, 0x40


class CapError(RuntimeError):
    """The cap could not be applied or proved; the text is for the operator."""


@dataclass(frozen=True, slots=True)
class Limits:
    """What a job really enforces, read back from Windows."""
    cpu_flags: int
    cpu_rate: int
    limit_flags: int
    mem_bytes: int
    priority: int
    affinity: int


def cores_allowed(cores: int | None = None) -> int:
    """How many logical processors the job may use: floor(80% x cores), at least 1."""
    return max(1, math.floor(CPU_SHARE * (cores or os.cpu_count() or 1)))


def problems(limits: Limits | None, inside: bool, ram_bytes: int, cores: int) -> list[str]:
    """Why a process is NOT safely inside the operator's cap, in plain words ([] = it is)."""
    if limits is None:
        return ["no QuantBot cap was found"]
    flags, out = limits.limit_flags, [] if inside else ["this process is not inside QuantBot's cap"]
    if (limits.cpu_flags & (CPU_ENABLE | CPU_HARD_CAP) != CPU_ENABLE | CPU_HARD_CAP
            or not 0 < limits.cpu_rate <= CPU_RATE):
        out.append(f"the CPU is not hard-capped at {CPU_SHARE:.0%} or less")
    if not flags & LIMIT_AFFINITY or not 0 < limits.affinity.bit_count() <= cores_allowed(cores):
        out.append(f"more than {cores_allowed(cores)} of the {cores} processors are open to it")
    if not flags & LIMIT_JOB_MEMORY or not 0 < limits.mem_bytes <= MEM_SHARE * ram_bytes:
        out.append(f"memory is not capped at {MEM_SHARE:.0%} of RAM or less")
    if flags & LIMIT_BREAKAWAY:
        out.append("child processes could break out of the cap")
    if not flags & LIMIT_KILL_ON_CLOSE:
        out.append("processes could outlive the cap")
    if not flags & LIMIT_PRIORITY or limits.priority not in (BELOW_NORMAL, IDLE):
        out.append("priority is not below normal")
    return out


def win() -> tuple[Any, Any, Any, Any]:
    """psutil and pywin32, or a plain refusal (fail closed)."""
    if sys.platform != "win32":
        raise CapError("this PC is not Windows, so QuantBot's cap cannot be applied")
    try:
        import psutil  # type: ignore[import-untyped]
        import pywintypes  # type: ignore[import-untyped]
        import win32api  # type: ignore[import-untyped]
        import win32job  # type: ignore[import-untyped]
    except ImportError as why:
        raise CapError(f"a library the cap needs is missing ({why.name}): install "
                       "requirements-qb2.txt into .venv-qb2") from why
    return psutil, pywintypes, win32api, win32job


class _CpuRate(ctypes.Structure):
    _fields_ = [("flags", ctypes.c_uint32), ("rate", ctypes.c_uint32)]


def _cpu(job: Any, rate: _CpuRate | None = None) -> _CpuRate:
    """Set (rate given) or read a job's CPU rate control -- ctypes, as pywin32 lacks it."""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    info = rate if rate is not None else _CpuRate()
    head = (ctypes.c_void_p(int(job)), CPU_RATE_INFO, ctypes.byref(info), ctypes.sizeof(info))
    ok = (k32.SetInformationJobObject(*head) if rate is not None
          else k32.QueryInformationJobObject(*head, None))
    if not ok:
        raise CapError(f"Windows refused the CPU cap (error {ctypes.get_last_error()})")
    return info


def read(job: Any) -> Limits:
    """The limits a job really holds."""
    win32job = win()[3]
    ext = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
    basic, cpu = ext["BasicLimitInformation"], _cpu(job)
    return Limits(cpu.flags, cpu.rate, basic["LimitFlags"], ext["JobMemoryLimit"],
                  basic["PriorityClass"], basic["Affinity"])


def make(name: str, mem_bytes: int, cpu_rate: int = CPU_RATE) -> Any:
    """Create the named job -- or open it, if another QuantBot run made it -- and state the limits."""
    win32job = win()[3]
    job = win32job.CreateJobObject(None, name)
    ext = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
    basic = ext["BasicLimitInformation"]
    basic["LimitFlags"] = LIMIT_AFFINITY | LIMIT_PRIORITY | LIMIT_JOB_MEMORY | LIMIT_KILL_ON_CLOSE
    basic["Affinity"] = (1 << cores_allowed()) - 1          # the lowest floor(80%) processors
    basic["PriorityClass"] = BELOW_NORMAL
    ext["JobMemoryLimit"] = mem_bytes
    win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, ext)
    _cpu(job, _CpuRate(CPU_ENABLE | CPU_HARD_CAP, cpu_rate))
    return job
