# STATE.md — resume in seconds (current only; ≤6k chars, tested)

Updated: 2026-10-16. History → docs/archive/STATE_2026-10-16_QT18.md (QT-18 state,
verbatim). Box in hand: QT-19 → docs/reports/QT-19.md.

Phase: v2 BUILDING. **S0–S5 DONE; S6 OPEN (paused); S9 OPEN** (S3 close = QT-13 + QT-13b).
P19: none of 18 survived (QT-15). S6 batch 1: none of 24 (QT-18). S9 batch 1:
registered + built, NOT run (QT-19 STOP). Trial count N = 42. Sender disarmed (S10).

## QT-19 operator's words (verbatim, 2026-10-16 14:04)
- *"lets go with option 1."* — option 1 = "Build the advisor next. It manages the 70%
  pot and holds for weeks or months, so costs hardly matter. The bot's stage stays
  open and nothing is lost." S6 stays OPEN (paused, not closed).

## QT-19 in one screen — STOPPED at the known-null gate (box rule)
- A: earnings guard ignores dates outside the calendar (ULVR.L's 2004 rows); fixed.
- Step 0: daily store now from 2010-01-01 (routine fetch changed; median first date
  2023-10-16 → 2010-01-04; 108,840 old rows reconciled, 0 differ). Dividends re-checked
  for the advisor list (5,243 OK since 2013, 8 SUSPECT). ^VIX daily added (NY clock).
- B1: register 6332880 (alone): A-01..A-06, one arm (171 names), monthly book, OOS
  2014-03-31 → 2025-10-09; drills KN-A-RANDOM/GAP/PLANT; v2 plant (accc44b).
- B2: code 1adf545 (after the register; ancestry test). Bench extended, each
  fail-first: slot weights (1/k, not 1/n), dividends credited, D3 = VWRL+dividends
  before VWRP's first close, daily fingerprints. 24/24 mutants RED.
- **Known-null on this book: Gate 1 GREEN (red-first NOT shown), Gate 2 RED.** A
  planted +33,655% after 2× costs (D3 +265%) FAILED on the Deflated Sharpe only
  (0.000). Cause measured: the coin-flip null's per-bar Sharpe spread is 0.071 (1×) /
  0.151 (2×) vs ~0.013 sampling noise, so SR0 = 0.16 / 0.34 — above any edge. No
  trial run, no holdout opened, N stays 42.

## Decided while operator away (QT-19) — starting figures
- OOS from 2014-04 (D3 measurable: VWRP from 2019-07-25, VWRL's dividends from
  2014-03-19); D3 chained VWRL → VWRP. Dividends credited (P3), OK rows only, US 15%.
- Book rules (in the register's "book" field): month-end decision bar on the
  exchange's last session; coverage ≥ 90%; no month-end bar → sold next bar; P13
  re-justify = no trade, fresh stop; k_s = 2 when VIX (day before) > 30 or missing;
  1% ceiling bar by bar from the previous bar's 3×ATR; one-line bets only.
- Plant re-sized to v2 (0.3%/bar) before any gate run: the P10 stop closes about half
  of all buys within a month (turnover ~10×/yr on random picks).

## NEXT
1. **Mentor writes QT-20: fix the Deflated Sharpe's skill-free variance for the
   slot book** (why do coin books' Sharpes spread 5–10× the noise? measure, PROPOSE,
   test on the drills), re-prove the gate, THEN run A-01..A-06 as registered.
2. Flag for QT-20: the 3×ATR daily stop sells ~half of buys within a month (P10
   starting figure) — any change = PROPOSE→GO (loosens a fence? it is a stop).
3. OPERATOR: keep the PC on (or Sleep) 08:00–21:00 UK on weekdays.

## DECISION REQUESTED (open)
- **D1 advisor risk rule.** Default: the 1% rule stays the ceiling (stricter). GO
  words: "GO on D1: for the advisor, replace the 1% rule with a cap on how much the
  account can lose if the stop is hit, figure chosen by S5's crash tests." QT-19: the
  ceiling bound on 0.02% of held days (34 slots) — it barely matters at this size.
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
- Deflated Sharpe on the advisor slot book (above): DEFECT, not fixed.
- Survivorship: the advisor list was chosen in 2026 (today's big, liquid names);
  1%/yr mark-down is a starting figure — momentum will look better than real life.
- anchors.py 1,422 lines (pinned): splitting = PROPOSE→GO. 52 mypy errors silenced in
  5 inherited modules. No clock-sync task. Recorder missed 08:00 on 16 Oct.

## Fingerprints
v1 4add56ec…743b6 (unchanged). Advisor daily (a) 7d43bd09…16a1e, (b) 100065377…6e8d.
