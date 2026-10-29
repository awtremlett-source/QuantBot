"""The bot pot (P21, QT-29): until a bot strategy survives, the bot's 30% follows the index, AS IF.

His G3 choice, 2026-10-29: "(c) Follow index (Recommended)" -- QT-28's option (c) (PLAN_V3 P21).
PAPER ONLY: nothing here can trade (the qb2/advisor wall: no order path); the sender stays DISARMED.
NOT a trial and NOT a strategy: the trial count is unchanged and S6 stays OPEN.
* VWRP (the bot's own line and D3 itself; the advisor holds VWRL: no overlap), pinned by ISIN.
* In when ADV-0 is in, out when it is out: on each session processed, in the run right after the
  advisor's, a BUY or SELL is issued whenever the pot's state differs from ADV-0's, so it fills at
  the same open (P9's rule, scorecard.as_if). Armed on the first session processed after the deploy.
* Its own stop on VWRP's closes: 15% below the highest close since the fill (10% unsettled), only
  up (stops.fall_level, the one copy; its own ledger file). A close at or below it: SELL at the next
  open -- the bot is automatic, a sale and not an alert. Out after its own stop while ADV-0 still
  holds: back in by ADV-0's re-buy rule (R6) on VWRP's closes, or on ADV-0's next buy.
* The bot's brake, as built (P12): 10% no new buys and the 10% stop; 15% PAUSED until his words.
* The record: P9's arithmetic (scorecard) on a notional GBP 3,000, 1x and 2x, reconciled every run.
Run by earnings_step.advise after the advisor's job; :func:`step` never raises (a fault is a RED line).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from qb2.advisor import daily, live, page, scorecard, skips, state
from qb2.data import clean_step, universe
from qb2.execution.safety import BOT, Blocked
from qb2.guard import brakes, stops
from qb2.research import advisor_rules, names

TICKER, MARKET, ISIN, NAME = "VWRP.L", "LSE", "IE00BK5BQT80", "VWRP"
POT_GBP = 3_000.0                 # 30% of the notional GBP 10,000 account (P21); the advisor's is 7,000
BUY, SELL = scorecard.BUY, scorecard.SELL
FOLLOW, STOP, REBUY = "follow", "stop", "re-buy"
Row = Mapping[str, Any]


def beside(advisor: state.Paths) -> state.Paths:
    """Its record next to the advisor's (data/qb2/bot_pot/), with its OWN stop ledger there; its brake
    in the shared brakes file as pot "bot" (clear_pause --pot bot); its page block beside advisor.md."""
    root = advisor.root.parent / "bot_pot"
    return state.Paths(root, root / "stops.jsonl", advisor.brakes, advisor.page.parent / "bot_pot.md")


def vwrp() -> dict[str, Any]:
    """VWRP on the BOT list, pinned by ISIN as R1 pins VWRL, or STOP."""
    rows = [e for e in universe.bot_entries() if e["yfinance"] == TICKER]
    if len(rows) != 1 or (rows[0]["isin"], rows[0]["quote_currency"], universe.market_of(rows[0])) \
            != (ISIN, "GBP", MARKET):
        raise Blocked(f"{TICKER} does not resolve to {ISIN}, GBP, London -- STOP")
    return rows[0]


def held_stop(ledger: stops.Ledger) -> stops.Stop | None:
    return next((s for s in ledger.stops().values() if s.pot == BOT), None)


def last(rows: Sequence[Row]) -> Row | None:
    """The latest allowed BUY or SELL: the pot's own signals, or ADV-0's suggestions."""
    return next((r for r in reversed(rows) if r.get("allowed") and r.get("action") in (BUY, SELL)), None)


def bought_since(adv0: Sequence[Row], at: str) -> bool:
    """Has ADV-0 issued an allowed BUY after ``at`` (the pot's own stop exit)?"""
    since = datetime.fromisoformat(at)
    return any(r.get("allowed") and r.get("action") == BUY and datetime.fromisoformat(str(r["at"])) > since
               for r in adv0)


def issue(paths: state.Paths, *, action: str, kind: str, d: date, close: float, brake: brakes.State,
          now: datetime, reason: str) -> None:
    """The ONE writer of signals.jsonl. A BUY is checked against the bot's brake first (P12)."""
    refusals = []
    if action == BUY:
        try:
            brakes.check_buy(brake, BOT)
        except Blocked as why:
            refusals.append(str(why))
    state.append(paths.log("signals"), {
        "at": now.astimezone(timezone.utc).isoformat(timespec="seconds"), "kind": kind, "action": action,
        "ticker": TICKER, "session": d.isoformat(), "close": close, "allowed": not refusals,
        "refusals": refusals, "reason": reason})


def run(now: datetime, paths: state.Paths, advisor: state.Paths, *, clean_root: Path | None = None) -> list[str]:
    """One run, after the advisor's. Returns its plain-words lines (the page's today and any RED)."""
    through = live.final_through(clean_root, now)
    if through is None:
        return ["no final daily bars yet (the top-up never ran)"]
    arm = state.arm_date(paths) or state.arm(        # the first session processed after the deploy
        paths, daily.lse_sessions(through + timedelta(days=1), through + timedelta(days=10))[0], now, "QT-29 B")
    instrument, ledger, brake_log = names.instrument_of(vwrp()), stops.Ledger(paths.stops), brakes.Brakes(paths.brakes)
    written = state.rows(paths.log("days"))
    bars, late = skips.split(live.bars(TICKER, MARKET, through, since=arm, clean_root=clean_root), written)
    sessions = list(live.days_of(bars.index, MARKET))
    income, _ = advisor_rules.income(TICKER, MARKET, bars, clean_root)
    todo = [d for d in sessions if d.isoformat() not in {r["session"] for r in written}]
    holes = skips.holes(daily.lse_sessions(arm, through), sessions, written)
    adv0 = state.rows(advisor.log("suggestions"))
    follow = (a := last(adv0)) is not None and a["action"] == BUY      # ADV-0 in, or its BUY waiting
    for d in sorted([*todo, *holes]):
        if d in holes:                                                  # a skipped row, in its place
            state.append(paths.log("days"), skips.row(d, held_stop(ledger), NAME))
            continue
        k, brake = sessions.index(d), brake_log.state(BOT)
        vix, _ = live.vix_before(d, through, clean_root)
        uns = stops.unsettled(brakes.tighten(brake), vix)
        fills = scorecard.as_if(state.rows(paths.log("signals")), sessions[:k + 1])
        for f in (f for f in fills if f.session == d):                    # fills at d's open
            held = held_stop(ledger)
            if f.side == BUY and held is None:
                ledger.open(position_id=f"BOT-POT-{d}", pot=BOT, ticker=TICKER, market=MARKET,
                            opened_at=scorecard.xlon_open(d).isoformat(), entry=float(bars["open"].iloc[k]),
                            atr=None, unsettled=uns, rule=stops.FALL_RULE,
                            reason=f"as-if BUY at the open (issued {f.issued})")
            elif f.side == SELL and held is not None:
                ledger.close(held.position_id, f"as-if SELL at the open (issued {f.issued})")
        close, held = float(bars["close"].iloc[k]), held_stop(ledger)
        day = scorecard.day(bars, sessions, fills, income, instrument, k, POT_GBP)
        brake = brake_log.update(BOT, day.value[1.0], at=scorecard.xlon(d, "close"))
        mine, low = last(state.rows(paths.log("signals"))), None
        side, say = mine["action"] if mine else None, {"paths": paths, "d": d, "close": close, "brake": brake, "now": now}
        if held is not None and side != SELL:
            if not follow:
                issue(**say, action=SELL, kind=FOLLOW, reason="the advisor is out of VWRL: the bot pot sells "
                      "VWRP at the next open, as if")
            elif close <= held.level:
                issue(**say, action=SELL, kind=STOP, reason=f"VWRP closed at £{close:,.2f} on {d}, at or below "
                      f"its stop of £{held.level:,.2f}: the bot sells at the next open, as if")
            else:
                ledger.trail(held.position_id, close, None, unsettled=uns, reason=f"close of {d}")
        elif held is None and side != BUY and follow:
            if mine is not None and mine["kind"] == STOP and not bought_since(adv0, str(mine["at"])):
                low = float(bars["close"].iloc[sessions.index(fills[-1].session):k + 1].min())
                if advisor_rules.rebuy_signal(close, low):                   # R6, on VWRP's own closes
                    issue(**say, action=BUY, kind=REBUY, reason=f"since its own stop VWRP's lowest close was "
                          f"£{low:,.2f}; it closed at £{close:,.2f} on {d}, 10% or more above: buy back")
            else:
                issue(**say, action=BUY, kind=FOLLOW, reason="the advisor holds the index fund: the bot pot "
                      "buys VWRP at the next open, as if")
        stop = held_stop(ledger)
        state.append(paths.log("days"), {**scorecard.line(day), "stop": stop.level if stop else None,
                                         "unsettled": uns, "vix_before": vix, "brake": brake.level,
                                         "adv0": "in" if follow else "out", "rebuy_low": low})
    fresh = scorecard.record(bars, sessions, scorecard.as_if(state.rows(paths.log("signals")), sessions),
                             income, instrument, POT_GBP)
    red = scorecard.reconcile([r for r in written if not skips.is_skip(r)], fresh)
    lines = [f"RED: the bot pot does not reconcile -- {x}" for x in red]
    lines += skips.lines(state.rows(paths.log("days")), late, NAME) + today(now, paths, ledger, bars, through, red, arm)
    write_page(now, paths, arm, lines)
    return lines


def today(now: datetime, paths: state.Paths, ledger: stops.Ledger, bars: pd.DataFrame, through: date,
          red: Sequence[str], arm: date) -> list[str]:
    rows, stop = [r for r in state.rows(paths.log("days")) if not skips.is_skip(r)], held_stop(ledger)
    out = []
    if len(bars) and (have := min(through, live.days_of(bars.index, MARKET)[-1])) < (gone := daily.last_finished(now)):
        out.append(f"UNCHECKED: VWRP's newest final close is from {have} -- the bot pot's stop was NOT checked "
                   f"against {gone}'s close")
        if now > (due := clean_step.due_by(daily.lse_sessions(have + timedelta(days=1), gone)[0])):
            out.append(f"RED: VWRP's daily close is overdue (due {due:%a %d %b %H:%M} UK): the bot pot's stop "
                       f"has been unchecked since {have}")
    side = mine["action"] if (mine := last(state.rows(paths.log("signals")))) else None
    if rows:
        r, wait = rows[-1], f", a {side} waiting for the next London open" if side else ""
        held = f"holding VWRP as if bought (stop £{stop.level:,.2f}){wait if side == SELL else ''}" if stop \
            else f"in cash{wait if side == BUY else ''}"
        out.append(f"{held}; VWRP closed £{float(r['close']):,.2f} on {r['session']}; as-if pot "
                   f"£{float(r['value_1x']):,.2f} ({float(r['pct_1x']):+.2f}%) at 1x costs, "
                   f"£{float(r['value_2x']):,.2f} ({float(r['pct_2x']):+.2f}%) at 2x; brake {r['brake']}")
    else:
        out.append(f"armed from {arm}: nothing processed yet -- its first session comes with the next daily top-up")
    return out + (["reconciled: OK"] if not red else [])


def write_page(now: datetime, paths: state.Paths, arm: date | None, lines: Sequence[str]) -> None:
    paths.page.parent.mkdir(parents=True, exist_ok=True)
    days = state.rows(paths.log("days")) if arm else []
    paths.page.write_text(page.bot_block(arm, days, lines), encoding="utf-8", newline="\n")


def step(now: datetime, clean_root: Path | None, advisor: state.Paths) -> str:
    """earnings_step's call after the advisor's job. Never raises: paper only, so a fault is a RED line
    in the run's log and on the page -- it must never hide the advisor's line or the store's."""
    mine = beside(advisor)
    try:
        lines = run(now, mine, advisor, clean_root=clean_root)
    except Exception as why:                      # noqa: BLE001 - said in the line and on the page
        lines = [f"RED: the bot pot STOPPED ({type(why).__name__}: {why})"]
        try:
            write_page(now, mine, None, lines)
        except OSError as also:
            lines.append(f"(its page was not written either: {also})")
    return "Bot pot: " + " · ".join(lines)
