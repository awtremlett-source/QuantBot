"""Brake replays: P12's 10% / 15% against 2008, 2020, 2022 and ordinary dips (QT-16 C1).

The brake under test is THE brake (qb2/guard/brakes.step), run day by day on a
long daily path as if it were a fully invested pot, from 2004 (or the path's
first date) to now. The paths, fetched once and kept OUTSIDE the trading store
(data/research/brake_replay/, each file's SHA-256 in manifest.json): ^GSPC, ^NDX,
^FTSE, URTH (from 2012) and GBPUSD=X. US paths are put in POUNDS (pounds.align:
the same rate rule as the firewall). Closes are price indices -- dividends are not
in them, so recoveries read a little slow. That is stated, not corrected.

* **Fires in a window:** the brake is ON on any day inside it -- 2007-10 to 2009-03,
  2020-02 to 2020-04, 2022-01 to 2022-10 (the trigger date is reported too).
* **False alarm:** a 10% trigger OUTSIDE the windows after which the path regained
  its peak without first falling a further 5% below the trigger day's value.
* **Return missed:** the path's return from the trigger to the day the brake
  cleared -- what new buys would have earned while none were allowed.

Description only. P12's 10% / 15% are NOT changed here, whatever this shows; a
change is a recommendation with exact GO words (docs/research/brake_replay_2026-10.md).

CLI (fetch once, replay, write the report): ``python -m qb2.research.brake_report``
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from qb2.execution.safety import ADVISOR
from qb2.guard import brakes
from qb2.research import pounds

REPO_ROOT = Path(__file__).resolve().parents[2]
FOLDER = REPO_ROOT / "data" / "research" / "brake_replay"
PATHS = {"^GSPC": "USD", "^NDX": "USD", "^FTSE": "GBP", "URTH": "USD"}
FX = pounds.FX_SYMBOL
START = "2004-01-01"
WINDOWS = {"2008": (date(2007, 10, 1), date(2009, 3, 31)),
           "2020": (date(2020, 2, 1), date(2020, 4, 30)),
           "2022": (date(2022, 1, 1), date(2022, 10, 31))}
FURTHER = 0.05
Fetch = Callable[[str], pd.Series]


@dataclass(frozen=True, slots=True)
class Episode:
    level: str                      # "10%" or "15%"
    start: date
    end: date | None                # cleared (back within 5% of peak); None = still on
    window: str | None
    false_alarm: bool | None        # 10% outside the windows only
    missed: float                   # path return from trigger to clear


def window_of(day: date) -> str | None:
    return next((k for k, (a, b) in WINDOWS.items() if a <= day <= b), None)


def _fetch(symbol: str) -> pd.Series:
    import yfinance as yf

    frame = yf.Ticker(symbol).history(start="2003-12-01", interval="1d", auto_adjust=False)
    return frame["Close"].dropna()


def store(fetch: Fetch = _fetch, folder: Path = FOLDER) -> dict[str, dict[str, str]]:
    """Fetch every path once, write CSVs and a manifest of their SHA-256."""
    folder.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict[str, str]] = {}
    for symbol in [*PATHS, FX]:
        series = fetch(symbol)
        days = pd.DatetimeIndex(series.index)
        target = folder / f"{symbol.replace('^', '').replace('=', '_')}.csv"
        pd.DataFrame({"date": [d.date().isoformat() for d in days],
                      "close": series.to_numpy(dtype=float)}).to_csv(target, index=False)
        manifest[symbol] = {"file": target.name, "rows": str(len(series)),
                            "first": str(days.min().date()), "last": str(days.max().date()),
                            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                            "fetched_at": datetime.now(timezone.utc).isoformat(
                                timespec="seconds")}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


def load(folder: Path = FOLDER) -> tuple[dict[str, pd.Series], dict[str, dict[str, str]]]:
    """The stored paths, refused if any file no longer matches its SHA."""
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    out = {}
    for symbol, row in manifest.items():
        raw = (folder / row["file"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError(f"{row['file']} no longer matches its manifest SHA-256")
        frame = pd.read_csv(folder / row["file"])
        out[symbol] = pd.Series(frame["close"].to_numpy(dtype=float),
                                index=pd.to_datetime(frame["date"]))
    return out, manifest


def in_pounds(path: pd.Series, gbpusd: pd.Series) -> tuple[pd.Series, int]:
    """Dollar closes / GBPUSD by date (pounds.align's rule); days with no rate dropped."""
    fx = pd.DataFrame({"open": gbpusd.to_numpy(), "close": gbpusd.to_numpy()},
                      index=pd.DatetimeIndex(gbpusd.index).tz_localize("Europe/London"))
    index = pd.DatetimeIndex(path.index).tz_localize("America/New_York")
    rates = pounds.align(index, fx, "1d")
    out = pd.Series(path.to_numpy(dtype=float) / rates.close, index=path.index)
    return out.dropna(), int(out.isna().sum())


def replay(path: pd.Series, start: str = START) -> list[Episode]:
    """THE brake, day by day; every 10% and 15% episode with its outcome."""
    path = path[path.index >= pd.Timestamp(start)]
    days = [pd.Timestamp(d).date() for d in path.index]
    values = path.to_numpy(dtype=float)
    state, open_at, out = None, {}, []
    for i, (day, value) in enumerate(zip(days, values, strict=True)):
        before = state.level if state else brakes.OK
        state = brakes.step(state, ADVISOR, float(value), day.isoformat())
        if before == brakes.OK and state.level != brakes.OK:
            open_at["10%"] = (i, state.peak)
        if state.level == brakes.HOLD_OFF and before != brakes.HOLD_OFF:
            open_at["15%"] = (i, state.peak)
        if state.level == brakes.OK and before != brakes.OK:
            out += [_episode(level, j, peak, i, days, values) for level, (j, peak)
                    in sorted(open_at.items())]
            open_at = {}
    out += [_episode(level, j, peak, None, days, values) for level, (j, peak)
            in sorted(open_at.items())]
    return sorted(out, key=lambda e: (e.start, e.level))


def _episode(level: str, i: int, peak: float, j: int | None, days: Sequence[date],
             values: Sequence[float]) -> Episode:
    window = window_of(days[i])
    false_alarm = None
    if level == "10%" and window is None:
        floor = values[i] * (1 - FURTHER)
        later = values[i + 1:]
        regained = next((k for k, v in enumerate(later) if v >= peak), None)
        fell = next((k for k, v in enumerate(later) if v <= floor), None)
        false_alarm = regained is not None and (fell is None or regained < fell)
    last = j if j is not None else len(values) - 1
    return Episode(level, days[i], days[j] if j is not None else None, window,
                   false_alarm, values[last] / values[i] - 1.0)


def on_in(episodes: Sequence[Episode], level: str, window: str) -> bool:
    """Was the brake at ``level`` on during any day of ``window``?"""
    a, b = WINDOWS[window]
    return any(e.level == level and e.start <= b and (e.end is None or e.end >= a)
               for e in episodes)


def required_misses(found: Mapping[str, Sequence[Episode]]) -> list[str]:
    """What the box requires and did not happen (STOP and report, never tune)."""
    misses = [f"10% never on in {w}" for w in WINDOWS
              if not any(on_in(e, "10%", w) for e in found.values())]
    misses += [f"15% never on in {w}" for w in ("2008", "2020")
               if not any(on_in(e, "15%", w) for e in found.values())]
    return misses
