"""When London's closes really arrive (QT-33 C; PLAN_V3 S9, note 2026-11-13). A measurement only.

**Why.** Three mornings running (Tue 10, Wed 11, Thu 12 Nov 2026) Yahoo sent London's newest session
with no close at 07:04 UTC and filled it later in the morning (QT-31 A2, QT-32 A2, QT-33 A2). The daily
step retries every run until it comes (behind.py), but nothing recorded WHEN it comes, so whether the
07:00 run is simply too early could not be judged (QT-32 PROPOSE 1).

**What.** Every recorder run, after the top-up, appends ONE line to data/clean/arrival.jsonl: for each
market (London, US: a session counts once any of its names holds it, as behind.py) and each
stop-driving name (VWRL.L, VWRP.L), the newest finished session the daily step wants
(behind.last_session of its target) and its state:
* present     -- the store holds its close;
* blank       -- not stored, and this run's fetch sent the session with no close;
* refused     -- not stored, though this run's fetch sent it with a close (the door refused it);
* absent      -- not stored, and this run's fetch did not send the session at all;
* not fetched -- not stored, and this run fetched nothing for it.
A market not present also counts its fetched names by what each sent. Lines carrying a "source" were
back-filled once (Tue 10 to Fri 13 Nov 2026) from the run logs and the manifest: there "blank" is a row
the fetch set aside as broken whose session the name's blank-row quarantine holds. Nothing reads this file but
people: no rule, no stop, no schedule. Noting what a fetch sent never changes what the fetch returns,
and a failure here is said in the "Daily store:" line, never raised into the recorder.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from qb2.data import behind, universe
from qb2.ingest import daily

LOG = "arrival.jsonl"
TAIL = 5                                  # a fetch's last rows noted: the newest sessions only
PRESENT, BLANK, REFUSED, ABSENT, UNFETCHED = "present", "blank", "refused", "absent", "not fetched"
Fetch = Callable[[str], pd.DataFrame | None]


@dataclass(slots=True)
class Watch:
    """What this run's fetches sent: per name, its newest sessions and whether each close was blank."""

    sent: dict[str, dict[str, bool]] = field(default_factory=dict)
    trouble: list[str] = field(default_factory=list)

    def wrap(self, fetch: Fetch) -> Fetch:
        """The same fetch, returning exactly what it returns; it only notes the tail on the way past."""
        def noted(symbol: str) -> pd.DataFrame | None:
            frame = fetch(symbol)
            try:
                if frame is not None and not frame.empty and "close" in frame.columns:
                    tail = frame.tail(TAIL)
                    self.sent[symbol] = {d.isoformat(): bool(pd.isna(c)) for d, c in
                                         zip(pd.DatetimeIndex(tail.index).date, tail["close"].to_numpy())}
                else:
                    self.sent[symbol] = {}
            except Exception as exc:          # noqa: BLE001 - said in the line; the fetch is untouched
                self.trouble.append(f"{symbol}: {type(exc).__name__}: {exc}")
            return frame
        return noted


def _state(session: str, held: bool, sends: Sequence[dict[str, bool]]) -> str:
    if held:
        return PRESENT
    if not sends:
        return UNFETCHED
    if any(s.get(session) for s in sends):
        return BLANK
    return REFUSED if any(session in s for s in sends) else ABSENT


def states(target: date, newest: Mapping[str, str | None], held: Mapping[str, set[date]],
           markets: Mapping[str, str], watch: Watch) -> dict[str, dict[str, Any]]:
    """Each market's and stop-driving name's wanted session and its state. Pure.

    ``newest``: the marker's newest session per market; ``held``: each stop name's stored sessions;
    ``markets``: every name of the run -> its market."""
    out: dict[str, dict[str, Any]] = {}
    for market in behind.MARKETS:
        want = behind.last_session(market, target).isoformat()
        mine = [watch.sent[s] for s, m in markets.items() if m == market and s in watch.sent
                and s not in behind.OWN_RULES]
        have = str(newest.get(market) or "") >= want
        entry: dict[str, Any] = {"session": want, "state": _state(want, have, mine)}
        if not have and mine:
            entry["names"] = dict(Counter(_state(want, False, [s]) for s in mine))
        out[market] = entry
    for name in behind.STOP_DRIVING:
        day = behind.last_session(markets.get(name, universe.LONDON), target)
        sends = [watch.sent[name]] if name in watch.sent else []
        out[name] = {"session": day.isoformat(),
                     "state": _state(day.isoformat(), day in held.get(name, set()), sends)}
    return out


def note(now: datetime, target: date | None, names: Sequence[Mapping[str, Any]], watch: Watch,
         marker: Path) -> str:
    """Append this run's line beside the daily step's ``marker``; return "" when written, else what went
    wrong (for the line). Never raises."""
    try:
        if target is None:
            return ""
        root = marker.parent
        newest = dict(json.loads(marker.read_text(encoding="utf-8")).get("newest") or {}) \
            if marker.is_file() else {}
        held = {n: set() if (f := daily.load(n, root)) is None else set(pd.DatetimeIndex(f.index).date)
                for n in behind.STOP_DRIVING}
        markets = {str(e["yfinance"]): universe.market_of(e) for e in names}
        row: dict[str, Any] = {"at": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
                               "fetched": len(watch.sent), **states(target, newest, held, markets, watch)}
        if watch.trouble:
            row["trouble"] = watch.trouble[:5]
        append(row, root)
        return ""
    except Exception as exc:                  # noqa: BLE001 - a measurement: said, never fatal
        return f" · arrival log not written ({type(exc).__name__}: {exc})"


def append(row: Mapping[str, Any], root: Path) -> None:
    """The log's one writer: one line added, nothing rewritten (the live runs and QT-33's back-fill)."""
    with (root / LOG).open("a", encoding="utf-8") as out:
        out.write(json.dumps(row) + "\n")
