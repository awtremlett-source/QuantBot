"""logs/advisor/advisor.md: the week's suggestion and today's line, each figure with its age (QT-23 D).

Plain words for a beginner, first; figures after, each saying how old it is. Pushed on the status
branch by status_push, through its secret scan -- so no file paths and no long codes here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from qb2.advisor.engine import NAME
from qb2.advisor.scorecard import POT_GBP

UK = ZoneInfo("Europe/London")


def age(of: date | str | None, today: date) -> str:
    if of is None:
        return "no figure"
    days = (today - (of if isinstance(of, date) else date.fromisoformat(str(of)))).days
    return "today" if days <= 0 else "1 day old" if days == 1 else f"{days} days old"


def _money(row: Mapping[str, Any], s: str) -> str:
    return f"£{float(row[f'value_{s}x']):,.2f} ({float(row[f'pct_{s}x']):+.2f}%)"


def build(now: datetime, *, arm: date | None, days: Sequence[Mapping[str, Any]],
          suggestions: Sequence[Mapping[str, Any]], runs: Sequence[Mapping[str, Any]],
          shadows: Sequence[Mapping[str, Any]], status: Mapping[str, Any]) -> str:
    """The whole page from the record; ``status`` = today's line's figures (daily.py)."""
    today = now.astimezone(UK).date()
    out = [f"# QuantBot advisor — {now.astimezone(UK):%A %d %B %Y, %H:%M} UK", ""]
    if arm is None:
        return "\n".join(out + ["Not armed yet: nothing is suggested or scored until it is.", ""])
    out += ["**What this is.** The advisor only ever SUGGESTS; you decide and trade by hand. Its "
            f"default is to hold the whole-world index fund, {NAME}. Below, every suggestion is "
            f"followed *as if* you had (P9), on a notional pot of £{POT_GBP:,.0f}, so you can see "
            "whether it is any good.", ""]
    told = status.get("line", "no line")
    out += ["## Today", "", "- " + (told if days or told != "no line" else
                                    "No session since the arm date yet: the first one arrives with the "
                                    "next daily top-up (after London and New York have both closed).")]
    out += [f"- {x}" for x in status.get("warnings", [])] + [""]
    weekly = [s for s in suggestions if s.get("kind") in ("weekly", "re-justify")]
    out += ["## This week's suggestion", ""]
    if weekly:
        s = weekly[-1]
        verdict = "allowed" if s.get("allowed") else "REFUSED: " + "; ".join(s.get("refusals", []))
        out += [f"**{s['action']} VWRL** (issued {s['at'][:16].replace('T', ' ')} UTC, from the close "
                f"of {s['session']}, {age(s['session'], today)}; checked: {verdict})", "",
                str(s["reason"]), ""]
    else:
        out += ["No weekly review yet.", ""]
    urgent = [s for s in suggestions if s.get("kind") in ("urgent-exit", "re-buy")][-3:]
    if urgent:
        out += ["## Alerts", ""] + [f"- {s['at'][:10]}: **{s['action']}** — {s['reason']}"
                                    + ("" if s.get("allowed") else " (REFUSED: "
                                       + "; ".join(s.get("refusals", [])) + ")") for s in urgent] + [""]
    out += [f"## The as-if record (P9), from the arm date {arm}", ""]
    if days:
        out += ["| session | held | VWRL close | value 1x costs | value 2x costs |", "|---|---|---|---|---|"]
        out += [f"| {d['session']} | {'yes' if d['held'] else 'cash'} | £{float(d['close']):,.2f} | "
                f"{_money(d, '1')} | {_money(d, '2')} |" for d in days[-10:]]
        out += ["", f"Reconciled today: {status.get('reconciled', 'not checked')}.", ""]
    else:
        out += ["No session processed yet.", ""]
    if shadows:
        last, since = shadows[-1], dict[str, str]()
        for r in shadows:
            for k in r.get("rules", {}):
                since.setdefault(k, str(r["session"]))      # each rule's own first day (S-07: later)
        out += [f"## The {len(last.get('rules', {}))} rules scored in the background", "",
                "Not advice: each would have to beat the default above for 12 months, pass the luck "
                "test, and then still wait for your words.", "",
                "| rule | from | 1x | 2x |", "|---|---|---|---|"]
        out += [f"| {k} | {since[k]} | {float(v['pct_1x']):+.2f}% | {float(v['pct_2x']):+.2f}% |"
                for k, v in sorted(last.get("rules", {}).items())]
        out += ["", f"As of the close of {last['session']} ({age(last['session'], today)}).", ""]
    out += ["## The brake", "",
            "If the as-if pot falls 10% below its best value, the brake goes on: no new buys, and the "
            "safety stop tightens to 10%. While VWRL is held it clears by itself once the pot is back "
            "within 5% of its best. After an URGENT-EXIT the pot is cash, which never climbs back, so "
            "the buy-back would wait for ever: then only your own words clear it (the clear-pause "
            "tool, pot advisor), and the pot's best value restarts from that day. A 15% fall is a "
            "hold-off, and only your words clear that either.", ""]
    reviews = [r for r in runs if r.get("job") == "weekly"][-6:]
    if reviews:
        out += ["## Weekly reviews", ""] + [
            f"- {r.get('friday') or 'first review'}: " + ("**MISSED**" if r.get("missed") else
            "caught up late" if r.get("late") else "done") for r in reviews] + [""]
    return "\n".join(out)
