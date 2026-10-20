"""The S5 safety layer: the checks that stand between a signal and an order (QT-16 B).

PLAN_V3 S5 -- built and tested together, ahead of any strategy, so that nothing
later gets to run without them:

* stops.py      P10  the stop ledger: one stop per open position, raised only.
  OUR code holds every stop (Trading 212 has no trailing stop and no amend: FACTS d1, d2).
  BOT and MANUAL (QT-16, unchanged by QT-23 R4; MANUAL flagged for a later PROPOSE): entry -
  k x Wilder ATR(14) on the position's own bars (bot 5m, manual daily), k = 3, tightened to
  max(old, price - 2 x ATR) when unsettled. ADVISOR (QT-23 R3, operator GO 2026-10-19): the
  big-fall stop -- fill x (1 - f), raised at each close to max(old, close x (1 - f)), f = 15%,
  10% when unsettled: S5's crash-test figures (docs/research/brake_replay_2026-10.md); a
  re-justified buy (age.rebuy, P13) opens no lower than the record it replaces. Unsettled =
  the pot's 10% brake on, VIX's previous close above 30, or no VIX figure. Crossed: BOT -> a
  SELL through the sender (disarmed today); ADVISOR or MANUAL -> an URGENT-EXIT alert, never a
  sale (P1: the one automatic act on his holdings is raising their stop). No price ->
  UNCHECKED, said in plain words. The catch-up on waking checks every open stop, logged; the
  daily sync lists any held position with no stop -- above all his own;
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
