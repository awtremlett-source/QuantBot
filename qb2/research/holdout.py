"""The holdout: data kept unseen until ONE final run (S4; fixed 2026-10-10).

Fixed under the STANDING GO of 2026-10-07, before any trial is run:

* daily bars -- the last 12 months to 2026-10-09 are sealed: from 2025-10-10 on;
* 5-minute bars -- the last 15 trading days to 2026-10-09 are sealed (both
  exchanges' calendars put the 15th session back on 2026-09-21), plus everything
  recorded after today: from 2026-09-21 on, for ever.

Research reads bars only through :func:`research_bars`, which returns the
unsealed part; asking for a date inside the seal is refused, and every scoring
path re-checks the bars it is handed (:func:`check_unsealed`), so sealed rows
cannot be slipped in from elsewhere. The one exception is :func:`open_final_run`:
once per candidate, logged, never twice. A holdout looked at twice is not a holdout.

Not research, so not sealed: the live shadow cross-check and the freshness meter
read recent bars to watch the feed, and score nothing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from qb2.data import access
from qb2.ingest import daily
from qb2.research import preregister, trial_log

REPO_ROOT = Path(__file__).resolve().parents[2]
SEALED_FROM = {"1d": date(2025, 10, 10), "5m": date(2026, 9, 21)}
EXCHANGE_TZ = {"US": "America/New_York", "LSE": "Europe/London"}
SPENT = REPO_ROOT / "data" / "qb2" / "holdout_spent.jsonl"


class Sealed(RuntimeError):
    """A read of sealed data outside the single final holdout run."""


_KEY = object()


@dataclass(frozen=True, slots=True)
class HoldoutPass:
    candidate_id: str
    opened_at: str
    key: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.key is not _KEY:
            raise Sealed("a HoldoutPass can only come from holdout.open_final_run()")


def local_index(index: pd.Index, market: str) -> pd.DatetimeIndex:
    """Any timestamps (mixed zones included) on the exchange's own clock."""
    return pd.DatetimeIndex(pd.to_datetime(index, utc=True)).tz_convert(EXCHANGE_TZ[market])


def check_unsealed(index: pd.Index, interval: str, market: str,
                   holdout: HoldoutPass | None = None) -> None:
    """Refuse bars inside the seal unless this is the final run's pass."""
    if holdout is not None:
        if holdout.key is not _KEY:
            raise Sealed("forged holdout pass")
        return
    if len(index) == 0:
        return
    newest = local_index(index, market).max().date()
    if newest >= SEALED_FROM[interval]:
        raise Sealed(f"{interval} bars reach {newest}, inside the holdout sealed from "
                     f"{SEALED_FROM[interval]} -- only the single final run may read it")


def _normalised(frame: pd.DataFrame, market: str) -> pd.DataFrame:
    out = frame.copy()
    out.index = local_index(frame.index, market)
    out = out.sort_index()
    return out[~out.index.duplicated(keep="first")]


def research_bars(symbol: str, interval: str, market: str, *,
                  through: date | None = None, clean_root: Path | None = None,
                  holdout: HoldoutPass | None = None) -> pd.DataFrame:
    """Unsealed bars for research, on the exchange clock (5m via the doorway)."""
    seal = SEALED_FROM[interval]
    if through is not None and through >= seal and holdout is None:
        raise Sealed(f"asked for {interval} bars through {through}; sealed from {seal}")
    if interval == "5m":
        frame = access.bars(symbol, "5m", clean_root=clean_root)
    elif interval == "1d":
        loaded = daily.load(symbol, clean_root)
        if loaded is None or loaded.empty:
            raise access.AccessRefused(f"no clean daily bars for {symbol}")
        frame = loaded
    else:
        raise ValueError(f"no research interval {interval!r}")
    frame = _normalised(frame, market)
    days = pd.Series(frame.index.date, index=frame.index)
    if holdout is not None:
        return frame[days >= seal]
    keep = days < seal if through is None else days <= through
    return frame[keep.to_numpy()]


def open_final_run(token: preregister.Registered, *, spent: Path | None = None,
                   log_path: Path | None = None) -> HoldoutPass:
    """The one look. Refused if this candidate has already had it."""
    registered = preregister.check(token)
    target = spent or SPENT
    used = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()
            if line.strip()] if target.is_file() else []
    if any(row.get("candidate_id") == registered.id for row in used):
        raise Sealed(f"{registered.id} has already had its final holdout run")
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"candidate_id": registered.id, "at_utc": stamp}) + "\n")
    trial_log.log_trial({
        "utc_time": stamp, "kind": trial_log.HOLDOUT, "candidate_id": registered.id,
        "register_commit": registered.commit, "strategy_name": str(registered.entry["rule"]),
        "params": {}, "metric_name": "holdout_opened", "metric_value": 1, "n_bars": 0},
        path=log_path)
    return HoldoutPass(registered.id, stamp, key=_KEY)
