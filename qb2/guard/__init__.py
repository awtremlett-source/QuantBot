"""The S5 safety layer: the checks that stand between a signal and an order (QT-16 B).

PLAN_V3 S5 -- built and tested together, ahead of any strategy, so that nothing
later gets to run without them:

* stops.py      P10  the stop ledger: one stop per open position, raised only;
* brakes.py     P12  each pot's brake from its own peak (10% / 15%);
* pots.py       P2   a pot may not be spent past its own limit;
* age.py        P13  nothing held past 12 months without a fresh decision;
* earnings_window.py  P15  no bot entry into a results announcement;
* suggestion.py      the advisor's one front door to all of the above.

The bot's order path is qb2/execution/sender.py: for a BUY it runs checks 6-9
(brake, pot limit, earnings window, a stop plan) after its first five. A SELL
skips all four -- getting out must always be possible.

Every check FAILS CLOSED: a missing figure is a refusal that names what was
missing, never a pass. Every threshold is a STARTING FIGURE, applied under the
STANDING GO of 2026-10-07 and listed in STATE.md.
"""
