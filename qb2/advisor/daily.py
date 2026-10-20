"""The advisor's daily job and the weekly review's timing (QT-23 C, D). Catch-up safe.

Run by the after-hours step once the daily top-up has run (Part D), inside the cap:
1. ON WAKING (more than one new session): every open stop checked against the newest final
   close, logged (stops.catch_up).
2. Each final London session not yet processed, oldest first, from the arm date:
   a. fills: an allowed BUY or SELL fills at the open of the first session opening after it was
      issued -- a BUY opens the ADVISOR's stop at fill x (1 - f), a SELL closes it;
   b. the stop while held: a close at or below it -> URGENT-EXIT, a SELL suggestion and an alert,
      never a sale (P1); else raised to max(old, close x (1 - f));
   c. the record: the as-if value (scorecard), the brake measured on it, one line in days.jsonl;
   d. the re-buy (R6) while out after an exit: L = the lowest close from the exit's fill session
      on; a close >= L x 1.10 -> BUY again, re-checked daily while the signal holds; refused while
      the advisor pot's brake is on, and the page then says it waits behind the brake.
   f = 15%; 10% when unsettled = the brake on before the day, or VIX's latest close before the
   day above 30, or none within 5 days.
3. The shadows' new days (shadow.py). 4. The weekly review: the first run on a Friday once the
   store holds the session before it; a later run catches it up and says so; an older Friday with
   no review: MISSED. 5. The reconciliation (RED if any written day moved) and the page.
A newest final close older than the last finished session: the stop UNCHECKED, said so.
CLI: python -m qb2.advisor.daily [--arm]   (inside the cap: python -m qb2.tools.capped -- ...)
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from qb2.advisor import engine, live, page, scorecard, shadow, state
from qb2.data import universe
from qb2.execution.safety import ADVISOR, Blocked
from qb2.guard import brakes, stops
from qb2.research import adv0_describe, advisor_book, advisor_data, benchmark, firewall, preregister
from qb2.tools.governor import assert_capped

ISIN, HISTORY_DAYS = "IE00B3RBWM25", 730      # R1; the shadows' lookback window before the arm


def vwrl() -> dict[str, Any]:
    """R1: the GBP London line of IE00B3RBWM25 on the ADVISOR list, or STOP."""
    rows = [e for e in universe.advisor_entries() if e["yfinance"] == engine.TICKER]
    if len(rows) != 1 or (rows[0]["isin"], rows[0]["quote_currency"], universe.market_of(rows[0])) \
            != (ISIN, "GBP", "LSE"):
        raise Blocked(f"R1: {engine.TICKER} does not resolve to {ISIN}, GBP, London -- STOP")
    return rows[0]


def lse_sessions(first: date, last: date) -> list[date]:
    return [] if last < first else list(pd.DatetimeIndex(advisor_book.sessions("LSE", first, last)).date)


def last_finished(now: datetime) -> date:
    """The newest London session whose close has passed (the exchange's own calendar)."""
    days = lse_sessions(now.date() - timedelta(days=10), now.date())
    return next(d for d in reversed(days) if scorecard.xlon(d, "close") <= now)


def advisor_stop(ledger: stops.Ledger) -> stops.Stop | None:
    return next((s for s in ledger.stops().values() if s.pot == ADVISOR), None)


def unsettled_on(day: date, brake: brakes.State | None, through: date,
                 clean_root: Path | None) -> tuple[bool, float | None]:
    vix, _ = live.vix_before(day, through, clean_root)
    return stops.unsettled(brakes.tighten(brake), vix), vix


def run(now: datetime, paths: state.Paths, *, clean_root: Path | None = None,
        first_review: bool = False, shadows: bool = True) -> list[str]:
    """One run. Returns its plain-words lines (the page's today and any RED)."""
    arm, through = state.arm_date(paths), live.final_through(clean_root)
    if arm is None or through is None:
        return ["advisor not armed" if arm is None else "no final daily bars yet (the top-up never ran)"]
    entry, ledger, brake_log = vwrl(), stops.Ledger(paths.stops), brakes.Brakes(paths.brakes)
    instrument = firewall.instrument_of(entry)
    bars = live.bars(engine.TICKER, "LSE", through, since=arm, clean_root=clean_root)
    sessions = list(live.days_of(bars.index, "LSE"))
    if bars.empty:
        raise Blocked(f"no final {engine.TICKER} bars from the arm date {arm} -- nothing to follow")
    income, _ = advisor_data.income(engine.TICKER, "LSE", bars, clean_root)
    written = state.rows(paths.log("days"))
    done = {r["session"] for r in written}
    todo = [d for d in sessions if d.isoformat() not in done]
    lines: list[str] = []
    if len(todo) > 1:                                                  # 1. on waking
        acts = ledger.catch_up({engine.TICKER: float(bars["close"].iloc[-1])}) if advisor_stop(ledger) else []
        lines += [f"woke after {len(todo)} sessions: stops checked, {len(acts)} to act on (logged)"]
    for d in todo:
        k = sessions.index(d)
        brake = brake_log.state(ADVISOR)
        uns, vix = unsettled_on(d, brake, through, clean_root)
        suggested = state.rows(paths.log("suggestions"))
        fills = scorecard.as_if(suggested, sessions[:k + 1])
        for f in (f for f in fills if f.session == d):                    # a. fills at d's open
            held = advisor_stop(ledger)
            if f.side == scorecard.BUY and held is None:
                ledger.open(position_id=f"ADV-0-{d}", pot=ADVISOR, ticker=engine.TICKER, market="LSE",
                            opened_at=scorecard.xlon_open(d).isoformat(), entry=float(bars["open"].iloc[k]),
                            atr=None, unsettled=uns, reason=f"as-if BUY at the open (suggested {f.issued})")
            elif f.side == scorecard.SELL and held is not None:
                ledger.close(held.position_id, f"as-if SELL at the open (suggested {f.issued})")
        close, held = float(bars["close"].iloc[k]), advisor_stop(ledger)
        day = scorecard.day(bars, sessions, fills, income, instrument, k)
        brake = brake_log.update(ADVISOR, day.value[1.0], at=scorecard.xlon(d, "close"))
        ctx = engine.Context(d, close, uns, brake, day.value[1.0], held)
        low = None
        if held is not None and engine.pending(paths) != scorecard.SELL:   # b. the stop
            if close <= held.level:
                engine.issue(paths, ctx, action=scorecard.SELL, kind="urgent-exit", stop=held.level,
                             now=now, reason=(f"SELL VWRL at the next open: it closed at £{close:,.2f} on "
                                              f"{d}, at or below its safety stop of £{held.level:,.2f} -- "
                                              "the big-fall rule says get out. The advisor will suggest "
                                              "buying back once it closes 10% above its lowest close."))
            else:
                ledger.trail(held.position_id, close, None, unsettled=uns, reason=f"close of {d}")
        elif held is None and fills and fills[-1].side == scorecard.SELL:   # d. the re-buy watch
            since = sessions.index(fills[-1].session)
            low = float(bars["close"].iloc[since:k + 1].min())
            if adv0_describe.rebuy_signal(close, low) and engine.pending(paths) != scorecard.BUY:   # R6
                engine.issue(paths, ctx, action=scorecard.BUY, kind="re-buy", now=now,
                             stop=engine.preview(close, uns),
                             reason=(f"Buy VWRL back: since the exit on {fills[-1].session} its lowest "
                                     f"close was £{low:,.2f}; it closed at £{close:,.2f} on {d}, 10% or "
                                     "more above that -- the re-buy signal. New safety stop "
                                     f"{stops.FALLS[uns]:.0%} below the price paid."))
        stop = advisor_stop(ledger)
        state.append(paths.log("days"), {**scorecard.line(day), "stop": stop.level if stop else None,
                                         "unsettled": uns, "vix_before": vix, "brake": brake.level,
                                         "rebuy_low": low})
    if shadows:
        shadows_for(paths, todo, arm, through, clean_root)
    lines += weekly(paths, now, arm, through, ledger, brake_log, clean_root, first_review)
    fresh = scorecard.record(bars, sessions, scorecard.as_if(state.rows(paths.log("suggestions")), sessions),
                             income, instrument)
    red = scorecard.reconcile(written, fresh)
    lines += [f"RED: the scorecard does not reconcile -- {x}" for x in red]
    lines += today_line(now, paths, ledger, bars, through, red)
    write_page(now, paths, arm, lines)
    return lines


def shadows_for(paths: state.Paths, todo: Sequence[date], arm: date, through: date,
                clean_root: Path | None) -> None:
    if not todo:
        return
    names, _ = live.names(universe.advisor_entries(), through, since=arm - timedelta(days=HISTORY_DAYS),
                          clean_root=clean_root)
    vix, close = live.vix_series(through, clean_root), {
        s: live.bars(s, "LSE", through, clean_root=clean_root)["close"].astype(float)
        for s in (benchmark.D3, benchmark.D3_FALLBACK)}
    on = advisor_data.filter_of(close[benchmark.D3], close[benchmark.D3_FALLBACK])
    scored = {sid: shadow.score(preregister.require(sid).entry, names, vix, arm, on)
              for sid in shadow.SHADOWS}
    for d in todo:
        rules = {}
        for sid, by in scored.items():
            at = {s: v[live.days_of(v.index, "LSE") <= d] for s, v in by.items()}
            rules[sid] = {f"pct_{s:g}x": round((float(v.iloc[-1]) - 1) * 100, 4) if len(v) else 0.0
                          for s, v in at.items()}
        state.append(paths.log("shadows"), {"session": d.isoformat(), "rules": rules})


def weekly(paths: state.Paths, now: datetime, arm: date, through: date, ledger: stops.Ledger,
           brake_log: brakes.Brakes, clean_root: Path | None, first: bool) -> list[str]:
    runs = [r for r in state.rows(paths.log("runs")) if r.get("job") == "weekly"]
    fridays = [arm + timedelta(days=i) for i in range((now.date() - arm).days + 1)
               if (arm + timedelta(days=i)).weekday() == 4]
    ready = [f for f in fridays if lse_sessions(f - timedelta(days=10), f - timedelta(days=1))[-1] <= through]
    seen = {r.get("friday") for r in runs}
    open_ = [f for f in ready if f.isoformat() not in seen]
    out = []
    for f in open_[:-1]:
        state.append(paths.log("runs"), {"job": "weekly", "friday": f.isoformat(), "missed": True,
                                         "at": now.isoformat(timespec="seconds")})
        out.append(f"the weekly review for Friday {f} was MISSED (the PC was off or the store late)")
    due = open_[-1] if open_ else None
    if due is None and not (first and not runs):
        return out
    rows = state.rows(paths.log("days"))
    value = float(rows[-1]["value_1x"]) if rows else scorecard.POT_GBP
    close = float(live.bars(engine.TICKER, "LSE", through, clean_root=clean_root)["close"].iloc[-1])
    brake = brake_log.state(ADVISOR) or brake_log.update(ADVISOR, value, at=now)
    uns, _ = unsettled_on(through + timedelta(days=1), brake, through, clean_root)
    ctx = engine.Context(through, close, uns, brake, value, advisor_stop(ledger))
    made = engine.weekly_review(paths, ctx, ledger, now)
    late = due is not None and now.date() > due
    state.append(paths.log("runs"), {"job": "weekly", "friday": due.isoformat() if due else None,
                                     "first": due is None, "late": late, "suggestions": len(made),
                                     "at": now.isoformat(timespec="seconds")})
    return out + [f"weekly review {'caught up late for ' + str(due) if late else 'done'}: "
                  + (", ".join(f"{r['action']} ({'allowed' if r['allowed'] else 'REFUSED'})" for r in made)
                     or "nothing to suggest")]


def today_line(now: datetime, paths: state.Paths, ledger: stops.Ledger, bars: pd.DataFrame,
               through: date, red: Sequence[str]) -> list[str]:
    rows, stop = state.rows(paths.log("days")), advisor_stop(ledger)
    out = []
    if through < last_finished(now):
        out.append(f"UNCHECKED: the newest final close is from {through} -- the stop was NOT checked "
                   "against any later price. Look at VWRL yourself if markets moved.")
    if rows:
        r = rows[-1]
        held = (f"holding VWRL as if bought (stop £{stop.level:,.2f})" if stop else "in cash")
        out.append(f"{held}; VWRL closed £{float(r['close']):,.2f} on {r['session']}; as-if pot "
                   f"£{float(r['value_1x']):,.2f} ({float(r['pct_1x']):+.2f}%) at 1x costs, "
                   f"£{float(r['value_2x']):,.2f} at 2x; brake {r['brake']}")
    return out + (["reconciled: OK"] if not red else [])


def write_page(now: datetime, paths: state.Paths, arm: date, lines: Sequence[str]) -> None:
    status = {"line": next((x for x in reversed(lines) if x.startswith(("holding", "in cash"))), "no line"),
              "warnings": [x for x in lines if x.startswith(("UNCHECKED", "RED", "the weekly"))],
              "reconciled": "OK" if "reconciled: OK" in lines else "RED"}
    text = page.build(now, arm=arm, days=state.rows(paths.log("days")),
                      suggestions=state.rows(paths.log("suggestions")), runs=state.rows(paths.log("runs")),
                      shadows=state.rows(paths.log("shadows")), status=status)
    paths.page.parent.mkdir(parents=True, exist_ok=True)
    paths.page.write_text(text, encoding="utf-8", newline="\n")


def main(argv: Sequence[str] | None = None) -> int:
    assert_capped()                    # QT-23R: never outside the operator's cap
    parser = argparse.ArgumentParser(description="The advisor's daily job (and the weekly review).")
    parser.add_argument("--arm", action="store_true", help="arm the record today, then the first review")
    args, now, paths = parser.parse_args(argv), datetime.now(timezone.utc), state.Paths.default()
    try:
        if args.arm:
            state.arm(paths, now.astimezone(page.UK).date(), now, "QT-23 F")
            brakes.Brakes(paths.brakes).update(ADVISOR, scorecard.POT_GBP, at=now)
        lines = run(now, paths, first_review=args.arm)
    except Blocked as why:
        state.append(paths.log("runs"), {"job": "daily", "stop": str(why), "at": now.isoformat()})
        print(f"ADVISOR STOPPED: {why}")
        return 2
    state.append(paths.log("runs"), {"job": "daily", "lines": lines, "at": now.isoformat(timespec="seconds")})
    print("\n".join(lines))
    return 1 if any(x.startswith("RED") for x in lines) else 0


if __name__ == "__main__":
    sys.exit(main())
