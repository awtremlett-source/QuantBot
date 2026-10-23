"""The advisor's weekly review, and the one door every suggestion goes through (QT-23 C).

ADV-0 (registered 8fb2c49), the default: "hold the index fund" -- the WHOLE advisor pot in VWRL
(R1: Vanguard FTSE All-World, distributing, London, GBP, pinned by ISIN; R2: P8's 25% cap is for
picks, not a whole-market fund, by the GO of 2026-10-19).
* The first review: BUY. Each later review while held: HOLD, with its stop level. At 12 months
  (P13, R7): re-justified through age.rebuy -- a new record, no trade, a fresh stop no lower than
  the old one -- then HOLD. Out after an urgent exit, or with an order still to fill: nothing to
  suggest (re-entry only by the 10% re-buy: daily.py).
* :func:`issue` is the ONLY writer of suggestions.jsonl, and it runs every suggestion through
  guard.suggestion.check_suggestion first. A refused one is written with why, and not followed.
* Every suggestion carries a reason a beginner can read, and its stop level.
Nothing here can trade: qb2/advisor imports no order path (wall: tests/qb2/test_qt23_advisor.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from qb2.advisor import state
from qb2.advisor.scorecard import BUY, POT_GBP, SELL
from qb2.execution.safety import ADVISOR
from qb2.guard import age, brakes, pots, suggestion
from qb2.guard import stops as stop_ledger

TICKER, MARKET, KIND = "VWRL.L", "LSE", "ETF"
NAME = "Vanguard FTSE All-World (VWRL)"
HOLD = suggestion.HOLD


@dataclass(frozen=True, slots=True)
class Context:
    """What a review or a daily check sees: the newest FINAL session and the as-if state."""
    session: date                        # the newest final session (live.final_through)
    close: float                         # VWRL's close that session
    unsettled: bool                      # stops.unsettled(brake on, VIX before the day)
    brake: brakes.State | None
    value_gbp: float                     # the as-if pot at that close, 1x
    held: stop_ledger.Stop | None        # the ADVISOR's open stop record, if any


def pot_view(value_gbp: float) -> pots.View:
    """The as-if account: the advisor pot is 70% of it (P2), so a whole-pot buy sits at its limit."""
    return pots.View(account_total_gbp=value_gbp / pots.SHARE[ADVISOR])


def issue(paths: state.Paths, ctx: Context, *, action: str, kind: str, reason: str,
          stop: float | None, now: datetime, held: stop_ledger.Stop | None = None) -> dict[str, Any]:
    """THE way a suggestion leaves the advisor: checked first, then written -- refused or not."""
    s = suggestion.Suggestion(TICKER, action, KIND, MARKET,
                              spend_gbp=ctx.value_gbp if action == BUY else None,
                              held=held if held is not None else ctx.held)
    checked = suggestion.check_suggestion(s, brake=ctx.brake, pot=pot_view(ctx.value_gbp),
                                          earnings=None, now=now)
    row = {"at": now.astimezone(timezone.utc).isoformat(timespec="seconds"), "kind": kind,
           "action": action, "ticker": TICKER, "reason": reason, "stop": stop,
           "session": ctx.session.isoformat(), "close": ctx.close, "allowed": checked.allowed,
           "refusals": list(checked.refusals), "warnings": list(checked.warnings)}
    state.append(paths.log("suggestions"), row)
    return row


def preview(close: float, unsettled: bool) -> float:
    """The stop a buy would open with if it filled at this close (the fill sets the real one)."""
    return stop_ledger.fall_level(close, stop_ledger.FALLS[unsettled])


def _f(unsettled: bool) -> str:
    return f"{stop_ledger.FALLS[unsettled]:.0%}" + (" (markets are jumpy)" if unsettled else "")


def buy_reason(ctx: Context) -> str:
    return (f"Buy {NAME} with the whole advisor pot (about £{ctx.value_gbp:,.0f} of the notional "
            f"£{POT_GBP:,.0f}). This is the advisor's default: none of the 12 stock-picking rules "
            "tested so far beat simply holding the whole-world index fund once costs and luck are "
            f"counted. It carries a safety stop {_f(ctx.unsettled)} below the price paid -- at "
            f"{ctx.session}'s close of £{ctx.close:,.2f} that would be about "
            f"£{preview(ctx.close, ctx.unsettled):,.2f}.")


def hold_reason(ctx: Context, level: float) -> str:
    return (f"Keep holding {NAME}. Its safety stop is £{level:,.2f}, {1 - level / ctx.close:.1%} "
            f"below {ctx.session}'s close of £{ctx.close:,.2f}. If it ever closes at or below the "
            "stop, the advisor says SELL the next morning; the stop only ever moves up.")


def pending(paths: state.Paths) -> str | None:
    """An allowed BUY or SELL not yet followed by an opposite one: 'BUY' or 'SELL' (or None)."""
    sides = [str(r["action"]) for r in state.rows(paths.log("suggestions"))
             if r.get("allowed") and r.get("action") in (BUY, SELL)]
    return sides[-1] if sides else None


def after_exit(paths: state.Paths) -> bool:
    """The latest allowed BUY or SELL is an URGENT-EXIT: the pot is (or is about to be) cash after
    an exit -- when his words may also clear its 10% brake (QT-24, his GO of 2026-10-23)."""
    rows = [r for r in state.rows(paths.log("suggestions"))
            if r.get("allowed") and r.get("action") in (BUY, SELL)]
    return bool(rows) and rows[-1].get("kind") == "urgent-exit"


def weekly_review(paths: state.Paths, ctx: Context, ledger: stop_ledger.Ledger,
                  now: datetime) -> list[dict[str, Any]]:
    """The Friday review of ADV-0: what to do this week, in plain words, checked."""
    last = pending(paths)
    if ctx.held is None:
        if last is None:                                      # never bought: the first review
            return [issue(paths, ctx, action=BUY, kind="weekly", reason=buy_reason(ctx),
                          stop=preview(ctx.close, ctx.unsettled), now=now)]
        return []                    # a BUY still to fill, or out after an exit: the re-buy watch
    if last == SELL:
        return []                                             # an urgent exit still to fill
    held = ctx.held
    if age.status(held.opened_at, now) == age.LIMIT:          # P13, R7: re-justify, no trade
        held = age.rebuy(ledger, held.position_id, new_position_id=f"ADV-0-{ctx.session}-re", price=ctx.close,
                         atr=None, now=now, unsettled=ctx.unsettled,
                         reason="12 months held: still the default, re-justified (P13, R7)")
        return [issue(paths, ctx, action=HOLD, kind="re-justify", stop=held.level, now=now, held=held,
                      reason=(f"{NAME} has been held 12 months, the longest anything is held "
                              "without a fresh decision (P13). Decision: keep it -- it is still the "
                              f"default -- as a new record with a fresh stop at £{held.level:,.2f}, "
                              "never lower than before. Nothing to trade."))]
    return [issue(paths, ctx, action=HOLD, kind="weekly", reason=hold_reason(ctx, held.level),
                  stop=held.level, now=now)]
