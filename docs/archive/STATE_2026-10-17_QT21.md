# STATE.md — resume in seconds (current only; ≤6k chars, tested)

Updated: 2026-10-17. History → docs/archive/STATE_2026-10-17_QT20.md (QT-20 state,
verbatim). Box in hand: QT-21 → docs/reports/QT-21.md.

Phase: v2 BUILDING. **S0–S5 DONE; S6 OPEN (paused); S9 OPEN** (S3 close = QT-13 + QT-13b).
P19: none of 18 survived (QT-15). S6 batch 1: none of 24 (QT-18). **S9 batch 1: none of 6
(QT-21).** Trial count N = 48. Sender disarmed. No holdout has ever been opened.

## Operator's words (verbatim)
- 2026-10-16 23:42: *"QT-20 report read; proceed with QT-20's PROPOSE, in its order.
  Record in STATE."* (done: QT-21, in that order).
- 2026-10-16 14:04: *"lets go with option 1."* = the advisor next; S6 stays OPEN (paused).

## QT-21 in one screen
- **Data:** the daily front door now quarantines unit breaks (open ≥ 3× or ≤ ⅓ the previous
  close; the unit with the most rows is the line's own) and filler (rows before a line's
  first traded bar; a share: its first 20 sessions in a row with trades). qb2/data/
  cross_bar.py, on every daily write; sticky ledger quarantine/daily/<name>-crossbar.parquet
  (a re-fetch never brings a row back). Clean-up: 6,685 rows, 27 names, reconciled; real
  moves kept. D3's VWRL→VWRP chain now at 2019-08-13 (−0.16 points).
- **Bench:** one bar > 25% of a result's variance = INSUFFICIENT; the advisor's luck bar
  from 200 random-rank books built by each trial's own rules (rank_null.py); S6/P19 keep the
  coin; 42 old verdicts unchanged. Both gates proved both ways (QT-21 D). 17 of 17 mutants RED.
- **S9 batch 1, net 2× vs D3 +265.1% (2014-03 → 2025-10):** A-01 +24.7% · A-02 +12.4% ·
  A-03 +34.8% · A-04 +5.4% · A-05 +2.1% · A-06 +19.5%. All FAIL (luck p 1.000, DSR
  0.26–0.57, below D3). Each sits 3.6–5.1 sd BELOW random re-timings of its own holdings;
  US halves positive, London halves negative (description only).
- **The advisor's honest default stays "hold the index fund".**

## Book rules in force (QT-19 register, unchanged)
Month-end decision bar on the exchange's last session; coverage ≥ 90%; no month-end bar
→ sold next bar; P13 re-justify = no trade, fresh stop; k_s = 2 when VIX (day before)
> 30 or missing; 1% ceiling bar by bar; OOS 2014-03-31 → 2025-10-09; D3 VWRL → VWRP.

## NEXT
1. **Mentor writes QT-22 for S9 batch 2** (none survived; the QT-22 suggestion engine waits
   for a survivor). Leads (description, not results): the rules' timing loses to random
   timing of the same holdings; the P10 stop sells 40–43% of buys within a month (M2;
   change = PROPOSE→GO); London halves lost in all six.
2. M1 idea for a FUTURE batch, registered before use: centre the DSR's luck bar on the
   skill-free books' mean (random picks scored DSR 0.876 today; luck test + D3 stopped them).
3. PROPOSE: per-ticker scale check vs Trading 212's own price (SCARS #3). SMEA.L's kept
   2010–23 rows are £ ÷ 100 and its true-£ rows from 2024-04-25 sit quarantined.
4. OPERATOR: keep the PC on (or Sleep) 08:00–21:00 UK on weekdays.

## DECISION REQUESTED (open)
- **D1 advisor risk rule.** Default: the 1% rule stays the ceiling (stricter). GO
  words: "GO on D1: for the advisor, replace the 1% rule with a cap on how much the
  account can lose if the stop is hit, figure chosen by S5's crash tests." QT-21: the
  ceiling bound on ≤ 0.02% of held days — it barely matters at this size.
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
(after QT-21's clean-up; was 7d43bd09…16a1e / 10006537…6e8d).
