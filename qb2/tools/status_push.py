"""Hourly recorder status, pushed to GitHub so the mentor can read it (QT-12S).

Operator, 2026-10-08: "can the recorder automatically push every set interval
and then you can check it automatically?"

The recorder itself is not touched. A separate task (QB2-StatusPush, Mon-Fri at
:50 past each hour, 08:50-21:50 UK) runs this module, which:

1. reads the manifest READ-ONLY and counts with delay_count -- the one rule, no
   second copy. It never takes the recorder's lock and never writes data/;
2. writes a small plain-words file to logs/status_push/recorder_status.md;
3. scans it for anything secret-shaped and refuses to push if it finds one;
4. pushes ONLY that file to the orphan branch "status": one commit, rebuilt and
   force-pushed each time, made with git plumbing so main's history, index and
   working tree are never touched.

Every outcome is a line in logs/status_push/push.log; a failure exits non-zero.

CLI: ``python -m qb2.tools.status_push [--no-push]``
"""

from __future__ import annotations

import re
import statistics
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from qb2.tools import delay_count, sample_delay

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "logs" / "status_push"
STATUS_FILE = OUT_DIR / "recorder_status.md"
PUSH_LOG = OUT_DIR / "push.log"
RECORDER_LOGS = REPO_ROOT / "logs" / "recorder"

STATUS_REF = "refs/heads/status"           # never main: the only ref we push
STATUS_PATH = ("status", "recorder_status.md")
REMOTE = "origin"

UK = ZoneInfo("Europe/London")
SINCE = date(2026, 10, 5)                  # first day of clock-checked samples
MARKETS = (("LSE", "London"), ("US", "US"))
# Mirrors QB2-Recorder's trigger: 07:00 UK and every hour for 14 hours.
RECORDER_HOURS = range(7, 21)
GRACE = timedelta(minutes=20)              # a run's sample is on file by then

Git = Callable[..., object]


def _uk(moment: datetime) -> datetime:
    return moment.astimezone(UK)


def last_run(log_dir: Path) -> str:
    """Start, end and exit code of the newest recorder run, in UK time."""
    logs = sorted(log_dir.glob("run-*.log")) if log_dir.is_dir() else []
    if not logs:
        return "no recorder run logged"
    started = finished = exit_code = None
    for line in logs[-1].read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("==== run started "):
            started = datetime.fromisoformat(line.split()[-1])
        elif line.startswith("==== run finished exit="):
            exit_code = line.split("exit=")[1].split()[0]
            finished = datetime.fromisoformat(line.split()[-1])
    begin = f"started {_uk(started):%H:%M}" if started else "start not logged"
    if finished is None:
        return f"{begin}, no finish line yet (still running, or killed)"
    return f"{begin}, finished {_uk(finished):%H:%M}, exit {exit_code}"


def _market(market: str, name: str, rows: Sequence[dict[str, object]],
            meter: Mapping[str, object], now: datetime) -> list[str]:
    mine = [r for r in rows if r["market"] == market]
    at = [_uk(datetime.fromisoformat(str(r["at_utc"]))) for r in mine]
    today = _uk(now).date()
    per_day = Counter(moment.date() for moment in at)
    ages = [float(age) for r in mine
            if isinstance(age := r["age_seconds"], (int, float))]
    delay = timedelta(seconds=statistics.median(ages)) if ages else timedelta()
    lines = [f"## {name}", "",
             f"- Counted today: {per_day[today]} · since {SINCE.isoformat()}: "
             f"{len(mine)} of {sample_delay.MIN_SAMPLES_PER_MARKET}",
             "- Per session: " + (" · ".join(f"{d.isoformat()}: {n}" for d, n
                                             in sorted(per_day.items())) or "none"),
             f"- Meter: {meter.get('status', '?')} -- {meter.get('detail', '')}"]
    window = delay_count.full_session_hours(market, today)
    if window is None:
        lines.append("- Today is not a full session (weekend, holiday or half-day)")
    else:
        # An hour is expected when its run, minus the feed's delay, sees a bar
        # from inside today's session, and the run has had time to finish.
        runs = {hour: datetime.combine(today, time(hour), UK) for hour in RECORDER_HOURS}
        expected = [hour for hour, run in runs.items()
                    if window[0] + delay <= run <= window[1] and run + GRACE <= now]
        seen = {moment.hour for moment in at if moment.date() == today}
        missed = [f"{hour:02d}:00" for hour in expected if hour not in seen]
        span = (f" ({expected[0]:02d}:00-{expected[-1]:02d}:00 runs)"
                if expected else "")
        lines += [f"- Expected by now today: {len(expected)}{span}",
                  f"- Missed hours today: {', '.join(missed) or 'none'}"]
    lines.append(f"- Delay median: {delay.total_seconds() / 60:.1f} min"
                 if ages else "- Delay median: no samples yet")
    return lines + [""]


def build_status(manifest: Path, log_dir: Path, now: datetime) -> str:
    """The whole status file, in plain words. Reads; never writes."""
    raw, bad = delay_count.scan_samples(manifest)
    rows = [r for r in delay_count.countable(raw, verified_only=True)
            if str(r["at_utc"])[:10] >= SINCE.isoformat()]
    meters = {str(m["market"]): m for m in delay_count.session_meter(
        manifest, markets=[m for m, _ in MARKETS], today=now.date())}
    lines = ["# QB2 recorder status", "",
             f"- Updated at: {_uk(now):%Y-%m-%d %H:%M} (UK)",
             f"- Last recorder run: {last_run(log_dir)}",
             f"- Target: {sample_delay.MIN_SAMPLES_PER_MARKET} counted samples per "
             f"market over {sample_delay.MIN_SESSIONS} full sessions. Counted = "
             "clock-checked, inside a full session, each bar once "
             "(qb2/tools/delay_count.py).", ""]
    if bad:
        lines += [f"Note: {bad} unreadable manifest line skipped (half-written "
                  "while the recorder was saving?).", ""]
    for market, name in MARKETS:
        lines += _market(market, name, rows, meters.get(market, {}), now)
    return "\n".join(lines)


_KEY_SHAPED = re.compile(r"[A-Za-z0-9_\-+/=]{24,}")
_NAMED = re.compile(r"\b[A-Z][A-Z0-9_]*(KEY|SECRET|TOKEN|PASS|PASSWORD)\b\s*[:=]\s*\S")
_ABS_PATH = re.compile(r"[A-Za-z]:\\|/Users/|/home/")


def secret_hits(text: str, env_values: Mapping[str, str]) -> list[str]:
    """Why this text must not be pushed. Says WHAT was found, never the value."""
    hits = [f"a value from .env ({name})" for name, value in env_values.items()
            if len(value) >= 6 and value in text]
    hits += [f".env name with a value ({name})" for name in env_values
             if re.search(rf"\b{re.escape(name)}\s*[:=]\s*\S", text)]
    for n, line in enumerate(text.splitlines(), 1):
        if any(re.search(r"\d", t) and re.search(r"[A-Za-z]", t)
               for t in _KEY_SHAPED.findall(line)):
            hits.append(f"key-shaped string on line {n}")
        if _NAMED.search(line):
            hits.append(f"secret-named assignment on line {n}")
        if _ABS_PATH.search(line):
            hits.append(f"file path outside the repo on line {n}")
    return hits


def _log(log: Path, line: str) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"{stamp} {line}\n")
    try:
        print(line)
    except (OSError, ValueError, AttributeError):
        pass                        # pythonw has no stdout; the log is the record


def _run_git(args: list[str], *, cwd: Path, stdin: str | None = None) -> str:
    # Bytes, not text: text mode on Windows writes each newline as CR LF,
    # which put a carriage return inside every tree entry's name (seen in test).
    done = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          timeout=120, input=None if stdin is None else stdin.encode())
    return done.stdout.decode("utf-8", errors="replace").strip()


def publish(status: Path, log: Path, repo: Path, *,
            env_values: Mapping[str, str], git: Git = _run_git) -> int:
    """Scan, then push ``status`` alone to STATUS_REF. 0 = pushed."""
    hits = secret_hits(status.read_text(encoding="utf-8"), env_values)
    if hits:
        _log(log, "REFUSED to push: " + "; ".join(hits))
        return 2
    try:
        def out(*args: str, stdin: str | None = None) -> str:
            return str(git(list(args), cwd=repo, stdin=stdin))
        # Plumbing only: objects are written, but no index, no checkout, no
        # branch switch -- main's working tree cannot be disturbed.
        blob = out("hash-object", "--no-filters", "-w", str(status))  # exact bytes
        inner = out("mktree", stdin=f"100644 blob {blob}\t{STATUS_PATH[1]}\n")
        tree = out("mktree", stdin=f"040000 tree {inner}\t{STATUS_PATH[0]}\n")
        commit = out("commit-tree", tree, "-m", "recorder status")   # no parent
        out("push", "--force", REMOTE, f"{commit}:{STATUS_REF}")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        raw = getattr(exc, "stderr", None) or str(exc)
        detail = (raw.decode("utf-8", errors="replace") if isinstance(raw, bytes)
                  else str(raw)).strip().splitlines()
        _log(log, f"PUSH FAILED: {detail[-1] if detail else type(exc).__name__}")
        return 1
    _log(log, f"pushed {'/'.join(STATUS_PATH)} to {STATUS_REF}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    from qb2.execution.t212_client import read_env_file

    args = list(sys.argv[1:] if argv is None else argv)
    try:
        text = build_status(sample_delay.MANIFEST, RECORDER_LOGS,
                            datetime.now(timezone.utc))
        STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATUS_FILE.write_text(text, encoding="utf-8", newline="\n")
    except Exception as exc:        # logged, never silent (Scar #12)
        _log(PUSH_LOG, f"STATUS FAILED: {type(exc).__name__}: {exc}")
        return 1
    if "--no-push" in args:
        _log(PUSH_LOG, "status written, push skipped (--no-push)")
        return 0
    return publish(STATUS_FILE, PUSH_LOG, REPO_ROOT, env_values=read_env_file())


if __name__ == "__main__":
    sys.exit(main())
