# STATE.md — resume in seconds (current only; ≤6k chars, tested)

Updated: 2026-10-12. History → docs/archive/STATE_2026-10-12_QT16.md (QT-16 state,
verbatim). Box in hand: QT-17 → docs/reports/QT-17.md.

Phase: v2 BUILDING. **S0–S5 DONE; S6 OPEN** (S3 close = QT-13 + QT-13b). P19:
none of 18 survived (QT-15).
Trial count N = 18. Bot sender still disarmed (S10).

## QT-17 operator's words (verbatim, 2026-10-12)
- *"write QT-17"*

## QT-17 in one screen — Part A done, Part B STOPPED before registering
- STOP (box step 0 rule): P15 asked exactly as the sender asks it blocks EVERY
  share on every unsealed hour — the store's earnings dates were first recorded
  2026-10-02. US arm = nothing; London/Mix = the same 9 ETFs. No trial added.
- A1 one door: holdout.research_bars / bars_through; wall
  tests/wall/test_sealed_doors.py. Two sealed reads logged (kind seal_viewed,
  SCARS #25): QT-16's stop description; the 5m benchmark (VWRP daily, QT-14–16).
  Stop re-run, unsealed: 85% stopped within 63 days. 5m VWRP via door +2.62%.
- A2 Gate 1 = matched p < 0.05 AND net mean per bar > 0. KN-INSTANT-5m: FAIL.
- A3 1h: sealed from 2026-07-13; fill 2 bars later; held only if a bar ends by
  the cut; P15 mask in every intraday back-test (p15.py); brakes not applied.
- A4 1h known-null, real store: Gate 1 GREEN (red, delay off); Gate 2 GREEN, but
  costs-off red-first did NOT show (39 of 47 bets in cash under P15).
- GEV 1h backfilled via the front door (2024-10-14 →; Yahoo refuses "730d").

## Applied under standing GO — starting figures
- QT-14/15: holdout daily from 2025-10-10, 5m from 2026-09-21 + after
  2026-10-10; D3 = VWRP; survivorship 1%/yr; INSUFFICIENT < 30; stake GBP 300;
  walk-forward 252/63, 10/5 sessions; nulls 200 runs; P4 15 min.
- QT-16: FX same bar else previous ≤ 10 min (5m) / 4 days (daily); stop k = 3 ×
  Wilder ATR(14), 2 if unsettled; brake clears within 5% of peak; bot pot 30%;
  age flag 11 months; earnings: bot blocked session before → after, unknown
  blocks, ETF N/A; advisor warns 5 sessions ahead; coverage RED < 90%.
- QT-17: 1h sealed from 2026-07-13 for ever; 1h walk-forward 63/21 sessions; 1h
  FX = open of the latest FX hour, ≤ 3 h; intraday benchmark = VWRP same bars.

## NEXT
1. **QT-18 in progress** (docs/reports/QT-18_progress.md): Part A, then S6
   batch 1 (8 rules × 3 arms) registered and run.
2. Tue 13 Oct 07:00: after-hours step cleans Mon 12 Oct; status page should show
   "Earnings: fresh to 2026-10-12 · … · OK" and no MISSED push.
3. OPERATOR: keep the PC on (or Sleep) 08:00–21:00 UK on weekdays.

## DECISION REQUESTED (open)
- **Bot's brake** (the mentor's words, no GO yet). Default: as built. GO words:
  "GO on the bot's brake: the 10% brake clears itself after 5 sessions and
  restarts from there; the 15% pause stays measured from the true peak and only
  my words clear it."
- Backups on the university OneDrive? Default: keep (2026-10-06 archive).

## Standing GOs (operator words, verbatim)
- 2026-10-16: *"GO on P15 history: in back-tests only, a results date counts as
  known from the results date before it, if that earlier date is before
  2026-10-02; from 2026-10-02 only knowable_time counts; a share with no date on
  record stays blocked."* (QT-18 A1, qb2/research/p15_history.py.)
- 2026-10-16 08:07 (QT-18, away): any choice → the recommended option, logged as
  "decided while operator away"; only the box's own STOPs stop the run.
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

## Recorder facts
QB2-Recorder (Mon–Fri, 14 triggers 07:00…20:00). After-hours: raw → clean,
censuses, labels; daily top-up; earnings refresh. Status page (QB2-StatusPush,
:50) on the status branch. The PC SLEEPS overnight, it does not shut down.

## Open flags
- 5m back-tests now carry P15 too: re-prove the 5m known-null before any 5m trial.
- Brake replays' index series (outside the store) run through 2026: description,
  P12 unchanged. Choosing stop k is an S9 trial on unsealed bars only.
- anchors.py 1,422 lines (pinned): splitting = PROPOSE→GO. 52 mypy errors
  silenced in 5 inherited modules. Recorder RED for 15m. No clock-sync task.

## Fingerprints
v1 4add56ec…743b6 (unchanged 2026-10-12). qb2 7474466a…8fdafe after QT-17.
