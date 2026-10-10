"""How many minutes behind is Trading 212's ``currentPrice`` for London? (QT-14A, S4.)

Decided 2026-10-09 (operator: *"GO on S4 delay: (c), measure T212 freshness"*):
read-only, on the anchored London names, so London can be reopened on evidence.
Same bar as FACTS row o: 20 counted samples over 3 full sessions.

**Sampling** (in recorder runs, London's regular session only, AFTER the live
sampling): poll positions every 30 s, 10 times (4.5 min; capped at 5). The
positions endpoint allows 1 request a second (FACTS), so 30 s is well inside it.
Raw polls go to data/raw/t212_fresh/<day>.jsonl. A failed poll is logged and
skipped; it never stops the recorder.

**Measuring** (after that day's London minute bars are clean): for each name and
run, try every lag from 0 to 30 minutes and take the median absolute gap between
each poll and the yfinance minute close that had finished ``lag`` minutes before
it. The lag with the lowest gap wins -- and the sample COUNTS only if it beats the
next-best lag by a clear margin (starting figure: 25% lower) and the name is
MINUTE_OK. Anything else is written down as "not counted", with the reason, and is
never rounded up.
"""

from __future__ import annotations

import json
import statistics
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qb2.data import access, universe
from qb2.execution import xcheck
from qb2.ingest.xcheck_shadow import broker_prices
from qb2.tools import delay_count

REPO_ROOT = Path(__file__).resolve().parents[2]
FOLDER = REPO_ROOT / "data" / "raw" / "t212_fresh"
SAMPLES = REPO_ROOT / "data" / "qb2" / "t212_fresh_samples.jsonl"

# STARTING FIGURES (STANDING GO 2026-10-07), tested first.
POLLS = 10
SPACING_SECONDS = 30.0
CAP_SECONDS = 300.0
MAX_LAG_MINUTES = 30
MARGIN = 0.25                    # best lag's gap must be 25% below the next-best
MIN_COVER = 0.8                  # share of polls that need a bar at a lag
MIN_COUNTED = 20                 # row o's bar
MIN_SESSIONS = 3

Prices = dict[str, tuple[float, str]]
MINUTE_NS = 60_000_000_000


@dataclass(frozen=True, slots=True)
class Poll:
    at: datetime
    prices: Prices


def poll_once(read: Callable[[], Sequence[Mapping[str, Any]]], now: datetime,
              say: Callable[[str], None]) -> Poll | None:
    try:
        return Poll(now, broker_prices(read()))
    except Exception as exc:              # noqa: BLE001 - logged and skipped, never fatal
        say(f"  T212 freshness: a poll failed ({type(exc).__name__}) -- skipped")
        return None


def poll_series(read: Callable[[], Sequence[Mapping[str, Any]]], *,
                still_open: Callable[[datetime], bool], say: Callable[[str], None],
                first: Poll | None = None, sleep: Callable[[float], None] = time.sleep,
                now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
                ) -> list[Poll]:
    """Up to POLLS polls, SPACING_SECONDS apart, never past CAP_SECONDS."""
    polls = [first] if first else []
    start = first.at if first else now()
    for i in range(1 if first else 0, POLLS):
        due = start + timedelta(seconds=i * SPACING_SECONDS)
        if (due - start).total_seconds() > CAP_SECONDS:
            break
        wait = (due - now()).total_seconds()
        if wait > 0:
            sleep(wait)
        moment = now()
        if not still_open(moment):
            say("  T212 freshness: London closed during the polls -- stopped early")
            break
        poll = poll_once(read, moment, say)
        if poll is not None:
            polls.append(poll)
    return polls


def save_polls(polls: Sequence[Poll], run: str, folder: Path | None = None) -> Path | None:
    if not polls:
        return None
    target = (folder or FOLDER) / f"{polls[0].at.astimezone(timezone.utc):%Y-%m-%d}.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        for i, poll in enumerate(polls):
            handle.write(json.dumps({
                "run": run, "poll": i + 1,
                "at_utc": poll.at.astimezone(timezone.utc).isoformat(timespec="seconds"),
                "prices": {k: list(v) for k, v in sorted(poll.prices.items())}}) + "\n")
    return target


# ------------------------------------------------------------- measuring --

@dataclass(frozen=True, slots=True)
class LagFit:
    best_lag: int | None
    best_err: float | None
    next_err: float | None
    counted: bool
    reason: str


def lag_errors(polls: Sequence[tuple[datetime, float]], closes: pd.Series,
               ) -> dict[int, float | None]:
    """Lag (minutes) -> median |poll - close| / close, over the polls with a bar.

    ``closes`` is indexed by one-minute bar START; a bar is known once it ends.
    A lag is only judged if at least MIN_COVER of the polls have a bar that ended
    within the minute before ``poll time - lag``.
    """
    index = pd.DatetimeIndex(closes.index).tz_convert("UTC").as_unit("ns")
    ends = (index + pd.Timedelta(minutes=1)).asi8            # nanoseconds, always
    values = closes.to_numpy(dtype=float)
    out: dict[int, float | None] = {}
    for lag in range(MAX_LAG_MINUTES + 1):
        gaps: list[float] = []
        for at, price in polls:
            cutoff = pd.Timestamp(at - timedelta(minutes=lag)).as_unit("ns").value
            k = int(np.searchsorted(ends, cutoff, side="right")) - 1
            if k >= 0 and cutoff - ends[k] < MINUTE_NS:
                gaps.append(abs(price - values[k]) / values[k])
        out[lag] = statistics.median(gaps) if len(gaps) >= MIN_COVER * len(polls) else None
    return out


def fit(polls: Sequence[tuple[datetime, float]], closes: pd.Series) -> LagFit:
    """The best lag, and whether it is clear enough to count."""
    if len(polls) < 2 or len({round(p, 10) for _, p in polls}) == 1:
        return LagFit(None, None, None, False, "flat: the polled price never changed")
    errors = lag_errors(polls, closes)
    missing = [lag for lag, err in errors.items() if err is None]
    if missing:
        return LagFit(None, None, None, False,
                      f"no bars to judge lags {missing[0]}..{missing[-1]} "
                      "(too near the open, or gaps)")
    ranked = sorted(errors.items(), key=lambda kv: (kv[1], kv[0]))
    (best, best_err), (_, next_err) = ranked[0], ranked[1]
    assert best_err is not None and next_err is not None
    if not best_err < (1.0 - MARGIN) * next_err:
        return LagFit(best, best_err, next_err, False,
                      f"no clear best lag: {best_err:.5f} vs next {next_err:.5f}")
    return LagFit(best, best_err, next_err, True, "counted")


BarsOf = Callable[[str, date], pd.DataFrame]


def clean_minutes(symbol: str, day: date) -> pd.DataFrame:
    """That day's clean 1m bars, through the doorway -- refused unless MINUTE_OK."""
    bars = access.bars(symbol, "1m", since=day)
    local = pd.DatetimeIndex(bars.index).tz_convert("Europe/London")
    return bars[local.date == day]


def measure_day(day: date, folder: Path | None = None, *,
                entries: Sequence[Mapping[str, Any]] | None = None,
                bars_of: BarsOf = clean_minutes) -> list[dict[str, Any]]:
    """One sample per (run, anchored London name) polled that day."""
    path = (folder or FOLDER) / f"{day.isoformat()}.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()] if path.is_file() else []
    full = delay_count.full_session_hours("LSE", day) is not None
    london = [e for e in (entries or universe.bot_entries())
              if universe.market_of(e) == universe.LONDON]
    samples: list[dict[str, Any]] = []
    for run in sorted({str(r["run"]) for r in rows}):
        polls = [r for r in rows if r["run"] == run]
        for entry in london:
            ticker, symbol = str(entry["t212_ticker"]), str(entry["yfinance"])
            base = {"day": day.isoformat(), "run": run, "ticker": ticker, "yfinance": symbol}
            try:
                bars = bars_of(symbol, day)
            except access.AccessRefused as refused:
                why = "name is not MINUTE_OK" if "FIVE_MIN_ONLY" in str(refused) \
                    else f"no clean bars: {str(refused)[:80]}"
                samples.append({**base, **asdict(LagFit(None, None, None, False, why))})
                continue
            currency = str(bars["currency"].iloc[-1]) if len(bars) else ""
            series = [(datetime.fromisoformat(r["at_utc"]),
                       xcheck.to_quote(r["prices"][ticker][0], r["prices"][ticker][1],
                                       currency))
                      for r in polls if ticker in r.get("prices", {})]
            pairs = [(at, p) for at, p in series if p is not None]
            result = fit(pairs, bars["close"]) if len(bars) else \
                LagFit(None, None, None, False, "no clean bars that day")
            if result.counted and not full:
                result = LagFit(result.best_lag, result.best_err, result.next_err,
                                False, "not a full London session")
            samples.append({**base, "polls": len(pairs), **asdict(result)})
    return samples


def measure_pending(cleaned_through: date, folder: Path | None = None,
                    samples_path: Path | None = None, **kw: Any) -> int:
    """Measure every polled day the clean store now covers, once. Append-only."""
    out = samples_path or SAMPLES
    done = {str(r.get("day")) for r in read_samples(out) if r.get("kind") == "day_done"}
    added = 0
    for path in sorted((folder or FOLDER).glob("*.jsonl")):
        day = date.fromisoformat(path.stem)
        if day > cleaned_through or day.isoformat() in done:
            continue
        rows = measure_day(day, folder, **kw)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a", encoding="utf-8") as handle:
            for row in [*rows, {"kind": "day_done", "day": day.isoformat()}]:
                handle.write(json.dumps(row) + "\n")
        added += len(rows)
    return added


def read_samples(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or SAMPLES
    if not target.is_file():
        return []
    return [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def status_line(path: Path | None = None) -> str:
    rows = [r for r in read_samples(path) if r.get("kind") != "day_done"]
    counted = [r for r in rows if r.get("counted")]
    sessions = len({r["day"] for r in counted})
    lag = f"{statistics.median(r['best_lag'] for r in counted):g}" if counted else "—"
    met = len(counted) >= MIN_COUNTED and sessions >= MIN_SESSIONS
    return (f"T212 London freshness: {len(counted)} counted / {sessions} sessions · "
            f"median {lag} min ({len(rows) - len(counted)} not counted; target "
            f"{MIN_COUNTED} over {MIN_SESSIONS}: {'MET' if met else 'UNVERIFIED'})")
