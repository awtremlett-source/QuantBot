"""S4's read-only measurements, inside each recorder run (QT-14A).

One hook in qb2/tools/record_now.py wraps the after-hours step, so the order of a
run is fixed and tested:

1. the live sampling (quote delay, then the hourly top-up) -- untouched;
2. :func:`before_clean` -- in a market's session: a fresh yfinance quote and one
   Trading 212 positions read for the shadow P20 cross-check; in London's session,
   the rest of the freshness polls (every 30 s, at most 5 minutes);
3. the after-hours step (raw -> clean, censuses, labels);
4. :func:`after_clean` -- measure every polled day the clean store now covers,
   and print the two status lines.

Nothing here may stop or fail the recorder: every error is said in the run log
and skipped. Both measurements are shadow and read-only -- they guard no trade.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, timezone
from typing import Any

from qb2.data import clean_step, universe
from qb2.data.front_door import CLEAN
from qb2.ingest import recorder, t212_fresh, xcheck_shadow

Say = Callable[[str], None]
Read = Callable[[], Sequence[Mapping[str, Any]]]
Clock = Callable[[], datetime]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _positions() -> Sequence[Mapping[str, Any]]:
    """The read-only practice client (GET only; the read key, never the order key)."""
    from qb2.execution.t212_client import T212DemoClient

    return T212DemoClient().positions()


def before_clean(say: Say, *, now: Clock | None = None, read: Read | None = None,
                 fetch: xcheck_shadow.Fetch | None = None,
                 sleep: Callable[[float], None] | None = None) -> None:
    now = now or _utcnow                         # all resolved at call time, so
    read = read or _positions                    # a test can plant any of them
    fetch = fetch or recorder.batched_yfinance_fetch
    moment = now()
    open_markets = [m for m in (universe.LONDON, universe.US)
                    if recorder.market_is_open(m, moment)]
    if universe.LONDON not in open_markets:
        say("  T212 freshness: market closed, freshness skipped")
    if not open_markets:
        say("  Cross-check (shadow): markets closed, skipped")
        return
    names = xcheck_shadow.names_in(open_markets, universe.bot_entries())
    try:
        quotes = xcheck_shadow.quotes_for(names, fetch)
    except Exception as exc:              # noqa: BLE001 - said, never fatal
        say(f"  Cross-check (shadow): yfinance quote failed ({type(exc).__name__})")
        quotes = {}
    first = t212_fresh.poll_once(read, now(), say)
    ratings = xcheck_shadow.run_sweep(now(), first.prices if first else {}, names, quotes)
    xcheck_shadow.log(ratings, now())
    tally = {r.level: 0 for r in ratings}
    for rating in ratings:
        tally[rating.level] += 1
    say(f"  Cross-check (shadow) {'+'.join(open_markets)}: "
        + ", ".join(f"{k} {v}" for k, v in sorted(tally.items())))
    if universe.LONDON in open_markets:
        polls = t212_fresh.poll_series(
            read, still_open=lambda m: recorder.market_is_open(universe.LONDON, m),
            say=say, first=first, sleep=sleep or time.sleep, now=now)
        t212_fresh.save_polls(polls, run=f"{moment.astimezone(timezone.utc):%Y%m%dT%H%MZ}")
        say(f"  T212 freshness: {len(polls)} polls saved for London")


def after_clean(say: Say) -> None:
    marker = CLEAN / clean_step.MARKER
    seen = json.loads(marker.read_text(encoding="utf-8")) if marker.is_file() else {}
    through = str(seen.get("cleaned_through") or "")
    if through:
        added = t212_fresh.measure_pending(date.fromisoformat(through))
        if added:
            say(f"  T212 freshness: measured {added} new samples")
    say(f"  {t212_fresh.status_line()}")
    say(f"  {xcheck_shadow.status_line()}")


def around_clean(clean: Callable[..., list[str]], *, after_hours: bool,
                 say: Say) -> list[str]:
    """record_now's one hook: measurements before and after the after-hours step."""
    try:
        before_clean(say)
    except Exception as exc:              # noqa: BLE001 - said, never fatal
        say(f"  S4 measurements (before) failed: {type(exc).__name__}: {exc}")
    complaints = clean(after_hours=after_hours)
    try:
        after_clean(say)
    except Exception as exc:              # noqa: BLE001 - said, never fatal
        say(f"  S4 measurements (after) failed: {type(exc).__name__}: {exc}")
    return complaints
