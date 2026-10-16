# STATE.md — resume in seconds (current only; ≤6k chars, tested)

Updated: 2026-10-16. History → docs/archive/STATE_2026-10-16_QT19.md (QT-19 state,
verbatim). Box in hand: QT-20 → docs/reports/QT-20.md.

Phase: v2 BUILDING. **S0–S5 DONE; S6 OPEN (paused); S9 OPEN** (S3 close = QT-13 + QT-13b).
P19: none of 18 survived (QT-15). S6 batch 1: none of 24 (QT-18). S9 batch 1:
registered + built, NOT run (QT-19 STOP, QT-20 STOP). Trial count N = 42. Sender disarmed.

## Operator's words (verbatim)
- 2026-10-16 19:28: *"QT-19 done"*. 2026-10-16 14:04: *"lets go with option 1."* =
  the advisor next; S6 stays OPEN (paused, not closed).

## QT-20 in one screen — STOPPED in Part A: a DATA DEFECT (box rule)
- Step 0 green; the register untouched (10 entries hashed = their register commits).
- Why the luck bar was 5–10× too wide: NOT cost noise (cost bills < 1% of the spread).
  The coin-flip null ignores the book's eligibility, and SMEA.L's stored open on
  2023-11-27 is ×114.6 its previous close (a unit break). 102 of 200 coins held it into
  that open (+344% of the pot in one bar): that one fact = 99.9% of the spread. The book
  can never hold SMEA.L then (its 90% coverage fails at every 2023 month-end).
- The box's fix (i), random-rank books built by advisor_book (measured as a
  description): none touched SMEA.L; spread 0.005 (1× and 2×) on raw and patched data alike →
  SR0 ≈ 0.012 at N=48, far below the planted book (0.237 / 0.212). Coin on clean data:
  SR0 0.006 / 0.009. Analytic (ii) ≈ 0.031 / 0.036: differs > 2× as expected (one book's own luck,
  already in the PSR).
- STOP because the census found broken rows a real book CAN hold: EDV.L's 848 rows
  before its 2021-06-14 London listing (619 flat zero-volume, then a fake −41% day; three
  QT-19 drill books held it into that day). Also FWRG.L's first 7 rows (warm-up only),
  IITU.L's 2 launch rows. B–D not done: no code changed, nothing run or logged.

## Book rules in force (QT-19 register, unchanged)
Month-end decision bar on the exchange's last session; coverage ≥ 90%; no month-end bar
→ sold next bar; P13 re-justify = no trade, fresh stop; k_s = 2 when VIX (day before)
> 30 or missing; 1% ceiling bar by bar; OOS 2014-03-31 → 2025-10-09; D3 VWRL → VWRP.

## NEXT
1. **Mentor writes QT-21: data first**, then the box's fix (i) as QT-20 specified it,
   re-prove both gates both ways, THEN A-01..A-06 as registered. Proposed (QT-20 report):
   front-door daily check — a bar opening ≥ 3× or ≤ ⅓ its previous close = unit break; flat
   zero-volume rows before a line's first trade = filler; the wrong side quarantined,
   never corrected (starting figures, standing GO). Re-measure with
   docs/reports/QT-20_partA_scripts.py.txt. Bench guard: one bar carrying > 25% of a
   result's variance = INSUFFICIENT.
2. For the mentor: the Deflated Sharpe centres its luck bar on 0; long-only books earn
   the market's Sharpe without skill — centre on the null's mean? (firewall change).
3. Flag: the 3×ATR stop sells ~half of buys within a month — change = PROPOSE→GO.
4. OPERATOR: keep the PC on (or Sleep) 08:00–21:00 UK on weekdays.

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
- DATA DEFECT (above), not fixed. A line priced in the wrong currency throughout shows
  no jump (SMEA.L's later rows look like € on a GBX line): needs a scale check vs T212.
- Survivorship: the advisor list was chosen in 2026; 1%/yr mark-down is a starting figure.
- anchors.py 1,422 lines (pinned): splitting = PROPOSE→GO. 52 mypy errors silenced in
  5 inherited modules. No clock-sync task. Recorder missed 08:00 on 16 Oct.

## Fingerprints
v1 4add56ec…743b6 (unchanged). Advisor daily (a) 7d43bd09…16a1e, (b) 100065377…6e8d.
