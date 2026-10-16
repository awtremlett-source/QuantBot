# STATE.md — resume in seconds (current only; ≤6k chars, tested)

Updated: 2026-10-16. History → docs/archive/STATE_2026-10-16_QT17.md (QT-17 state,
verbatim). Box in hand: QT-18 → docs/reports/QT-18.md.

Phase: v2 BUILDING. **S0–S5 DONE; S6 OPEN** (S3 close = QT-13 + QT-13b).
P19: none of 18 survived (QT-15). S6 batch 1: none of 24 survived (QT-18).
Trial count N = 42. Sender disarmed (S10).

## QT-18 operator's words (verbatim, 2026-10-16)
- *"GO on P15 history: in back-tests only, a results date counts as known from
  the results date before it, if that earlier date is before 2026-10-02; from
  2026-10-02 only knowable_time counts; a share with no date on record stays
  blocked."*
- 08:07: *"I'm away while QT-18 runs. Don't ask me anything else. For any choice,
  take your recommended option, log it ... as "decided while operator away"..."*

## QT-18 in one screen — done
- A1 qb2/research/p15_history.py (back-tests only; wall test_p15_history_wall.py):
  known from the CLOSE of the date before; cumulative snapshots; D1 never early;
  missing quarter = gap > 1.5 × median → blocked. p15.py uses it on 5m and 1h.
- A2 buy allowed on: US 95.1% (holdout 95.3%), London shares 47.8%, ETFs 100%,
  Mix 86.0%. Blocked throughout: RR.L, GLEN.L, RIO.L, AAL.L, ULVR.L (stale dates).
- A3 known-null 1h: Gate 1 + Gate 2 GREEN; both red-firsts RED (costs off → the
  below-cost drill PASSES +343% vs VWRP +50.7%: QT-17's gap closed).
- B: register c89f2fd → rule code 343cff3 → 24 run as registered, 111 min, no
  interruption, fingerprints (a)/(b) unchanged start to end. **24 FAIL**: best
  gross S6-08-US +9.2%, after 2× costs −13% … −95% vs VWRP +47–51%. No holdout run.

## Decided while operator away (QT-18) — starting figures
- Missing-quarter median capped at 182 days (AAL.L: one 17-year gap).
- Dates before 2006-10-16 dropped from the back-test copy (calendar starts there).
- Next date after 2026-10-02 = the earliest real snapshot's.
- S6 register clarifications: decisions at bar closes; S6-02/03/08 decide at bar
  1's close → in at bar 3; a day skipped if a bar/prior close is missing, entry
  would land at/after E, or P15 refuses the decision bar; XS = bets,
  round(0.2 n), ties by name; Mix S6-06/07 per market, S6-08 whole arm; stop
  k = 3 always, ATR from the bar before entry.
- Interrupted lines go in the S6 journal (docs/research/S6_batch1_runs), not a
  new trial-log kind. P19's runner now reads P19 ids only.

## Applied under standing GO — starting figures
- QT-14/15: holdout daily from 2025-10-10, 5m from 2026-09-21 + after
  2026-10-10; D3 = VWRP; survivorship 1%/yr; INSUFFICIENT < 30; stake GBP 300;
  walk-forward 252/63, 10/5 sessions; nulls 200 runs; P4 15 min.
- QT-16: stop k = 3 × Wilder ATR(14), 2 if unsettled; bot pot 30%; age flag 11
  months; earnings: bot blocked session before → after, unknown blocks, ETF N/A.
- QT-17: 1h sealed from 2026-07-13 for ever; 1h walk-forward 63/21; 1h FX ≤ 3 h;
  intraday benchmark = VWRP same bars.

## NEXT
1. **Mentor writes the next box.** S6 stays OPEN (no signal survived).
2. OPERATOR: keep the PC on (or Sleep) 08:00–21:00 UK on weekdays.

## DECISION REQUESTED (open)
- **Bot's brake** (the mentor's words, no GO yet). Default: as built. GO words:
  "GO on the bot's brake: the 10% brake clears itself after 5 sessions and
  restarts from there; the 15% pause stays measured from the true peak and only
  my words clear it."
- Backups on the university OneDrive? Default: keep (2026-10-06 archive).

## Standing GOs (operator words, verbatim)
- 2026-10-16: P15 history (above; PLAN_V3 P15).
- 2026-10-07: *"STANDING GO: For routine settings and thresholds, go with the
  recommended default and log it. Three things always need my own words: switching
  the bot on to trade, real money, and removing any safety fence."*
- 2026-10-07: *"From now on, every box ends by saving its report in the repo and
  pushing, so the mentor can read it from GitHub."* → docs/reports/<BOX>.md.
- Live anchors, 2026-10-05: "One GO until the £100 cap". 2026-10-09: *"GO on
  recorder triggers: 14 fixed hourly"* · *"GO on S4 delay: (c), measure T212
  freshness"*.

## CARRIED
- GOOG/GOOGL and VUAG/VUSA each count as ONE bet when the bot trades
  (bet_groups.json v1). FX 0.15% per leg on non-sterling lines; API order in USD?
  UNKNOWN.
- Parked: advisor trial counting (S9) · v1 revive-or-retire.

## Open flags
- **Live guard defect (found QT-18, not fixed — guard out of scope):**
  earnings_window.bot_verdict raises on a date before 2006-10-16 (ULVR.L's file
  holds 2004 dates). No buy can follow, but check 8 errors instead of answering.
- 5m back-tests carry P15 history: re-prove the 5m known-null before any 5m trial.
- Recorder missed 08:00 on 16 Oct (07:47 catch-up still running?).
- anchors.py 1,422 lines (pinned): splitting = PROPOSE→GO. 52 mypy errors
  silenced in 5 inherited modules. No clock-sync task.

## Fingerprints
v1 4add56ec…743b6 (unchanged 2026-10-16). qb2 see docs/reports/QT-18.md.
