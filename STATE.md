# STATE.md — resume in seconds (current only; ≤6k chars, tested)

Updated: 2026-10-29. History → docs/archive/STATE_2026-10-29_QT28.md (verbatim). Box done: QT-29 →
docs/reports/QT-29.md (its Part G addendum = tonight's 20:00 run, checked by hand).

Phase: v2 BUILDING. **S0–S5 DONE; S6 OPEN; S9 OPEN — the advisor is LIVE (armed 2026-10-20)**
(S3 close = QT-13 + QT-13b). No pick has survived (S6 0/30, S9 0/12, P19 0/18).
**Trial count N = 62.** Sender DISARMED. No holdout ever opened.

## QT-29 (code 84e3eee, deployed 09:11 UTC 29 Oct)
- **G3 answered: option (c), P21** (2046702). His words, 07:42: "(c) Follow index (Recommended)" — chosen from the
  mentor's question, recorded as QT-28's (c). **The bot pot**: the bot's 30% follows the index AS IF — VWRP,
  in/out with ADV-0 (same open), its own 15% big-fall stop (10% unsettled, raise-only), the bot's brake as
  built, notional £3,000 (qb2/advisor/bot_pot.py; data/qb2/bot_pot/; block under the advisor's on the status
  page). **Armed from Thu 29 Oct 2026**; first BUY fills at Fri 30 Oct's open. Paper only; NOT a trial.
- ^VIX's daily row now waits for Cboe's settle (16:20 New York). Holdout opens only on "GO on holdout for
  <trial id>" in the register (else WAITING). `capped --clear-of-schedule` for research runners.

## The resource cap (operator's words below: a FENCE)
Every heavy run: `.venv-qb2/Scripts/python -m qb2.tools.capped -- <cmd>` (CPU 80%, 12 of 16
processors, 80% RAM, below-normal priority). Research runners: add `--clear-of-schedule` before `--`
(waits until no scheduled run is due within 15 minutes). Never on the recorder (default OFF).

## The advisor and the bot pot, live
- **ADV-0 = hold VWRL**, stop 15% below the highest close (10% when unsettled), raise-only; crossed =
  URGENT-EXIT alert, never a sale. As-if BUY 21 Oct at £138.38; Wed 28 Oct £7,021.85 at 1x, stop £118.23.
- **Bot pot** follows ADV-0 with VWRP; its crossed stop = as-if SELL at the next open (automatic).
- **Clock change:** a session is final once London AND New York have closed: 20:00 UK this week; **from
  Mon 2 Nov, 21:00 UK — after the last run, so each day is processed at the next morning's 07:00 run**
  (replayed in tests/qb2/test_qt29_clock_change.py). No run time changes.
- Brakes: advisor after an URGENT-EXIT — `python -m qb2.tools.clear_pause --pot advisor --words "..."`;
  bot pot's 15% pause — `--pot bot`.

## NEXT
1. **Mentor: QT-29 Part G** — check tonight's 20:00 run (the bot pot's first line, ^VIX 29 Oct refused,
   the 28 Oct correction 16.81 → 16.91) unless already in the report's addendum.
2. **Fri 30 Oct 20:00**: the ^VIX 29 Oct row arrives; the bot pot's VWRP fill at Friday's open shows.
3. **Tue 3 Nov 07:00**: Monday 2 Nov processed (first morning after the clock change) — check by hand.
4. OPERATOR: **keep the PC on or asleep, plugged in** (it should wake itself at 07:00; on Thu 29 Oct it
   did not — QT-29 A1, cause UNKNOWN).

## DECISION REQUESTED (open)
- **D1 advisor risk rule.** Default: the 1% rule stays. GO words: "GO on D1: for the advisor,
  replace the 1% rule with a cap on how much the account can lose if the stop is hit, figure chosen
  by S5's crash tests."
- **Bot's brake** (now live in the bot pot). Default: as built. GO words: "GO on the bot's brake: the 10%
  brake clears itself after 5 sessions and restarts from there; the 15% pause stays measured from the
  true peak and only my words clear it."
- Holdout WAITING: none. v1's QuantBot-Daily/-Monthly run outside the cap (frozen): leave, report.

## Standing GOs (operator words, verbatim)
- 2026-10-29 (G3, chosen from a question): *"(c) Follow index (Recommended)"* = QT-28's (c), PLAN_V3 P21.
- 2026-10-23: *"Keep ADV-0's stop as the default for now; S-07 stays a shadow."* · *"GO on the
  advisor's 10% brake: after an urgent exit, my own words also clear the advisor's 10% brake and
  restart its peak from that day."*
- 2026-10-20, a FENCE: *"I stopped QT23 halfway through, there needs to be a limit on the amount of
  memory and CPU it takes up. like 80% limit for each. otherwise the PC cannot take it and will
  crash."*
- 2026-10-19: QT-23 advisor GO (verbatim in docs/archive/STATE_2026-10-29_QT28.md).
- 2026-10-07: *"STANDING GO: For routine settings and thresholds, go with the recommended default and
  log it. Three things always need my own words: switching the bot on to trade, real money, and
  removing any safety fence."*
- Live anchors 2026-10-05: "One GO until the £100 cap". Recorder: 14 hourly triggers, 07:00–20:00.

## CARRIED
- GOOG/GOOGL and VUAG/VUSA each count as ONE bet when the bot trades (bet_groups.json v1).
  FX 0.15% per leg on non-sterling lines. MTLN.L (EUR) skipped: no EUR rate.
- Parked: v1 revive-or-retire. 5m known-null to re-prove. QT-23 stash "QT-23-interrupted" kept.

## Open flags
- Thin London ETF quotes (SSLN.L, ACWI.L, SMEA.L). anchors.py 1,422 lines (pinned). At 250 lines:
  clean_step.py, ingest/daily.py, advisor/daily.py, guard/stops.py, s6_run.py, advisor_run.py,
  p19_run.py, status_push.py; bot_pot.py 198; cm_drills.py 247. 52 mypy errors silenced in 5 inherited
  modules; 4 known Qt-stub errors.

## Fingerprints
v1 4add56ec…743b6. Advisor daily (a) 6883791f…97b1, (b) f7aae670…768e. Batch 2 trial data (a)
ad36150c…8781, (b) 14a454fb…90dc (QT-29, 09:18 UTC, after the deploy).
