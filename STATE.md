# STATE.md — resume in seconds (current only; ≤6k chars, tested)

Updated: 2026-10-17. History → docs/archive/STATE_2026-10-17_QT21.md (QT-21 state,
verbatim). Box in hand: QT-22 → docs/reports/QT-22.md.

Phase: v2 BUILDING. **S0–S5 DONE; S6 OPEN (paused); S9 OPEN** (S3 close = QT-13 + QT-13b).
P19: none of 18 (QT-15). S6 batch 1: none of 24 (QT-18). S9 batch 1: none of 6 (QT-21).
**S9 batch 2: none of 6 (QT-22).** Trial count N = 54. Sender disarmed. No holdout ever opened.

## Operator's words (verbatim)
- 2026-10-17: *"QT-21 done"* · *"GO on QT-22: for advisor batch 2 only, the trailing stop is
  widened to a big-fall stop, figure chosen by S5's crash tests; the stop stays on every
  holding."* · batch 2's rules: *"Batch 1's six again (Recommended)"* (done: QT-22).
- 2026-10-16 14:04: *"lets go with option 1."* = the advisor next; S6 stays OPEN (paused).

## QT-22 in one screen
- **Stop (batch 2 only):** 15% below the highest price since the fill, 10% when VIX (day
  before) > 30 or missing — S5's crash-test figures (QT-16 brake replays). Raise-only; 1%
  ceiling at 15%. Live advisor stop (guard/stops.py) still 3 × ATR.
- **Register first:** A2-01..A2-06 = A-01..A-06 with only the stop changed, + KN-A2 drills,
  committed alone (196fd49) before the code (35a6e51). Batch 1's books identical bar for bar.
- **Gates re-proved** (ac4f367): random/gap FAIL, plant PASS 1× and 2×, both red-firsts shown.
  Random picks score DSR 0.970 on this book (M1).
- **Batch 2, net 2× vs D3 +265.1%:** A2-01 +256.8% · A2-02 +197.0% · A2-03 +284.6% (beat
  D3) · A2-04 +143.2% · A2-05 +152.1% · A2-06 +131.3%. All FAIL the luck test (p 0.74–1.00;
  0.6–3.0 sd below random timing of the same holdings). Stopped < 1 month 4–16% (was 40–43%);
  London halves now positive (description only).
- **The advisor's honest default stays "hold the index fund".**

## Book rules in force (QT-19 register; batch 2 = big-fall stop)
Month-end decision bar on the exchange's last session; coverage ≥ 90%; no month-end bar
→ sold next bar; P13 re-justify = no trade, fresh stop; batch 1 k_s = 2 when VIX (day before)
> 30 or missing; 1% ceiling bar by bar; OOS 2014-03-31 → 2025-10-09; D3 VWRL → VWRP.

## NEXT
1. **Mentor writes QT-23** (none survived). Leads (description, not results): in 12 rules the
   month-end timing never beat random timing of the same holdings — the luck test now binds;
   the wide stop turned London halves positive; the DSR's random-rank bar centred on 0 cannot
   separate this book from luck (random picks 0.970).
2. M1 idea for a FUTURE batch, registered before use: centre the DSR's luck bar on the
   skill-free books' mean.
3. If a big-fall rule ever survives, the live advisor stop must match it first: PROPOSE→GO.
4. PROPOSE: per-ticker scale check vs Trading 212's own price (SCARS #3). SMEA.L's kept
   2010–23 rows are £ ÷ 100 and its true-£ rows from 2024-04-25 sit quarantined.
5. OPERATOR: keep the PC on (or Sleep) 08:00–21:00 UK on weekdays.

## DECISION REQUESTED (open)
- **D1 advisor risk rule.** Default: the 1% rule stays the ceiling (stricter). GO
  words: "GO on D1: for the advisor, replace the 1% rule with a cap on how much the
  account can lose if the stop is hit, figure chosen by S5's crash tests." QT-22: the
  ceiling never bound with the 15% stop.
- **Bot's brake.** Default: as built. GO words: "GO on the bot's brake: the 10% brake
  clears itself after 5 sessions and restarts from there; the 15% pause stays
  measured from the true peak and only my words clear it."
- Backups on the university OneDrive? Default: keep (2026-10-06 archive).

## Standing GOs (operator words, verbatim)
- 2026-10-16: P15 history — *"GO on P15 history: in back-tests only, a results date
  counts as known from the results date before it, if that earlier date is before
  2026-10-02; from 2026-10-02 only knowable_time counts; a share with no date on
  record stays blocked."*
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
  UNKNOWN. MTLN.L (EUR line) skipped: no EUR rate in the store.
- Parked: v1 revive-or-retire. 5m known-null to re-prove before any 5m trial.

## Open flags
- Thin London ETF quotes left after each line's first trade (M3, description): SSLN.L
  99.8% flat untraded rows, ACWI.L 56%, SMEA.L 35%. Survivorship: the list was chosen in 2026.
- anchors.py 1,422 lines (pinned): splitting = PROPOSE→GO. 52 mypy errors silenced in
  5 inherited modules. No clock-sync task. Recorder missed 08:00 on 16 Oct.

## Fingerprints
v1 4add56ec…743b6 (unchanged). Advisor daily (a) 0f3a960c…f1f9, (b) f7aae670…768e
(unchanged since QT-21's clean-up).
