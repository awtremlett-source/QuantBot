"""The only way a strategy reads bars -- and the rule about minute data.

**Why this exists.** The 1-minute census is RED for London and GREEN for the US,
and that is not a data fault: a thinly-traded FTSE share simply does not trade in
every minute, so a minute with no trade has no bar and never will. US mega-caps
trade every minute of every session. Handing both to the same strategy as if they
were the same thing is how a back-test learns a pattern that only exists in the
gaps.

So every name carries a label — ``MINUTE_OK`` or ``FIVE_MIN_ONLY`` — and asking
for minute bars on a ``FIVE_MIN_ONLY`` name raises rather than returning a series
full of holes.

**What this is NOT.** It is a usage rule, not a change to any gate. PLAN_V3's 95%
bar and the way it is measured stay exactly as written: the census still counts
every name in the active universe, and the label is reported beside that figure,
never inside it. A label that shrank the denominator would be a back door around
the gate, which is why :func:`census_unchanged_by_labels` exists and why a test
pins it.

**The rules, and why each one is that way.**

* The default is ``FIVE_MIN_ONLY``. A new name, a name with too little history to
  judge, and anything we cannot find are all treated the same: cautious. Being
  wrong this way costs resolution; being wrong the other way costs a strategy
  built on holes.
* Demotion is **immediate** on one failed census — the data has already changed.
* Promotion needs **two consecutive** passing censuses, so a label does not flip
  back and forth on one quiet day -- and a pass counts only on NEW data: the
  name's newest bar must be newer than at its previous pass (QT-13b; on 5 Oct
  86 names were promoted by a second census over the same bars as 3 Oct).
* Recomputing on unchanged data leaves a label exactly as it was, so running
  the after-hours step twice changes nothing.
* Both are recomputed in the after-hours step, from the census that just ran.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from datetime import date
from pathlib import Path

import pandas as pd

from qb2.data.front_door import CLEAN

LABELS_PATH = CLEAN / "minute_labels.json"

MINUTE_OK = "MINUTE_OK"
FIVE_MIN_ONLY = "FIVE_MIN_ONLY"

# STARTING FIGURE, tested first. A name needs at least this many sessions of
# 1-minute history before the census can say anything useful about it: the
# provider only keeps about 30 days of minute bars, and two or three days of a
# quiet week would promote a name that trades thinly the rest of the month.
MIN_SESSIONS_TO_JUDGE = 10
# Promotion needs this many passing censuses in a row.
PASSES_TO_PROMOTE = 2


class AccessRefused(RuntimeError):
    """A strategy asked for data it is not allowed to use."""


@dataclass(frozen=True, slots=True)
class Label:
    """One name's label, and the census it came from."""

    symbol: str
    label: str
    reason: str
    census_taken: str          # the census run's own timestamp
    census_date: str           # the day it was taken
    consecutive_passes: int
    sessions_seen: int
    newest_bar: str = ""       # the name's last bar at this census ("" = unknown)


def load_labels(path: Path | None = None) -> dict[str, Label]:
    target = path or LABELS_PATH
    if not target.is_file():
        return {}
    raw = json.loads(target.read_text(encoding="utf-8"))
    return {k: Label(**v) for k, v in raw.get("labels", {}).items()}


def save_labels(labels: Mapping[str, Label], path: Path | None = None) -> Path:
    target = path or LABELS_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({
        "written": date.today().isoformat(),
        "rule": ("FIVE_MIN_ONLY is the default. Demotion is immediate on a failed "
                 "census; promotion needs "
                 f"{PASSES_TO_PROMOTE} consecutive passes. This is a usage rule "
                 "and changes no gate: the census still counts every name."),
        "labels": {k: asdict(v) for k, v in sorted(labels.items())},
    }, indent=1) + "\n", encoding="utf-8")
    return target


def label_for(symbol: str, labels: Mapping[str, Label] | None = None,
              path: Path | None = None) -> str:
    """The label, defaulting to the cautious one for anything we do not know."""
    known = labels if labels is not None else load_labels(path)
    found = known.get(symbol)
    return found.label if found else FIVE_MIN_ONLY


def update_labels(census: object, previous: Mapping[str, Label] | None = None,
                  ) -> dict[str, Label]:
    """Work out each name's label from a 1-minute census that has just run.

    ``census`` is a :class:`qb2.data.census.Census` taken on 1m bars.
    """
    was = dict(previous or {})
    out: dict[str, Label] = {}
    taken = str(getattr(census, "taken", ""))
    day = taken[:10]

    for name in getattr(census, "names", []):
        symbol = str(name.symbol)
        sessions = int(getattr(name, "sessions_present", 0))
        newest = str(getattr(name, "last_bar", None) or "")
        before = was.get(symbol)
        passes_before = before.consecutive_passes if before else 0
        label_before = before.label if before else FIVE_MIN_ONLY

        if sessions < MIN_SESSIONS_TO_JUDGE:
            label = Label(
                symbol, FIVE_MIN_ONLY,
                f"only {sessions} session(s) of minute history, fewer than the "
                f"{MIN_SESSIONS_TO_JUDGE} needed to judge",
                taken, day, 0, sessions, newest)
        elif not name.passes:
            # Immediate: the data has already changed.
            label = Label(
                symbol, FIVE_MIN_ONLY,
                "failed the minute census: " + "; ".join(name.reasons),
                taken, day, 0, sessions, newest)
        elif (before is not None and passes_before
              and (not newest or newest <= before.newest_bar)):
            # Same bars as the last pass: no new evidence, so nothing changes --
            # not the count, not the label, not the reason it was given.
            out[symbol] = before
            continue
        else:
            passes = passes_before + 1
            if passes >= PASSES_TO_PROMOTE or label_before == MINUTE_OK:
                label = Label(symbol, MINUTE_OK,
                              f"passed the minute census {passes} time(s) in a row",
                              taken, day, passes, sessions, newest)
            else:
                label = Label(
                    symbol, FIVE_MIN_ONLY,
                    f"passed {passes} of the {PASSES_TO_PROMOTE} consecutive "
                    "censuses needed for promotion",
                    taken, day, passes, sessions, newest)
        unchanged = before is not None and replace(
            label, census_taken=before.census_taken,
            census_date=before.census_date) == before
        out[symbol] = before if unchanged and before is not None else label
    return out


def census_unchanged_by_labels(census: object) -> bool:
    """The gate's denominator is every name, label or no label.

    If this ever returns False, a usage rule has become a way of making a gate
    pass, which is the one thing it must never be.
    """
    names = list(getattr(census, "names", []))
    return len(names) == len({str(n.symbol) for n in names})


# ------------------------------------------------------- the reading doorway

def bars(symbol: str, interval: str, *, clean_root: Path | None = None,
         labels: Mapping[str, Label] | None = None,
         labels_path: Path | None = None) -> pd.DataFrame:
    """Read clean bars for one name. THE way a strategy gets data.

    Reading the parquet files directly would skip the minute rule, so nothing
    else may do it -- a test scans for that.
    """
    if interval == "1m":
        label = label_for(symbol, labels, labels_path)
        if label != MINUTE_OK:
            known = labels if labels is not None else load_labels(labels_path)
            why = known[symbol].reason if symbol in known else \
                "no label on record, so the cautious default applies"
            raise AccessRefused(
                f"{symbol} is {label}: its minute bars have gaps that are real -- "
                f"the share simply did not trade in those minutes. {why}. Use 5m "
                "bars, or run the census again if you believe this has changed.")

    folder = (clean_root or CLEAN) / "bars" / interval / symbol
    files = sorted(folder.glob("*.parquet"))
    if not files:
        raise AccessRefused(
            f"no clean {interval} bars for {symbol} -- run the front door first")
    frame = pd.concat([pd.read_parquet(f) for f in files]).sort_index()
    return frame[~frame.index.duplicated(keep="first")]


def counts_by_sleeve(labels: Mapping[str, Label],
                     entries: Sequence[Mapping[str, object]],
                     ) -> dict[str, dict[str, int]]:
    """MINUTE_OK / FIVE_MIN_ONLY per sleeve, for the report."""
    out: dict[str, dict[str, int]] = {}
    for entry in entries:
        sleeve = str(entry.get("sleeve", "?"))
        symbol = str(entry["yfinance"])
        label = labels[symbol].label if symbol in labels else FIVE_MIN_ONLY
        bucket = out.setdefault(sleeve, {MINUTE_OK: 0, FIVE_MIN_ONLY: 0})
        bucket[label] = bucket.get(label, 0) + 1
    return out
