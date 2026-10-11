# STATE.md — resume in seconds (current only; ≤6k chars, tested)

Updated: 2026-10-11. History → docs/archive/STATE_2026-10-11.md (QT-14 state,
verbatim). Box in hand: QT-15 → docs/reports/QT-15.md.

Phase: v2 BUILDING. **S0–S4 DONE** (S3 close = QT-13 + QT-13b; S4 = QT-14). QT-15 ran P19's 18 registered trials.
**Result: none survived** — all 18 FAIL walk-forward at 2× costs; no holdout opened.
No EMA/Keltner rule feeds the confidence score (PLAN_V3 P19 records it).

## QT-15 operator's words (verbatim, 2026-10-10)
- *"write QT-15"*

## QT-15 in one screen
- A1 returns now COMPOUND (slot re-sized each bar; equity = cumprod; drawdown on
  it; benchmark compared compounded vs compounded). Coin-flip 5m −369% → −97.5%;
  planted 5m 2× +108% → +187.9%. Known-null gate re-proved: each half RED on
  broken code, then GREEN.
- A2 front door stamps every clean file on its exchange's clock (cause: batched
  US+London yfinance requests labelled US bars London). 721 files re-cleaned
  through the door; census fails a wrong-zone file. 5m census 98.2% GREEN.
- A3 daily store top-up after the front door, once per finished day (qb2/data/
  daily_step.py). "Daily store: fresh to … · OK/RED" on digest + status page.
  Fresh to 2026-10-09, 222/222.
- A4 advisor loader: universe.advisor_entries / for_register (171 names).
- B: rules qb2/signals/p19_rules.py, runner qb2/research/p19_run.py (resumable).
  5m: −23% to −95% net vs VWRP +2.65%. Daily: best +9.83% vs VWRP +17.39%, best
  DSR 0.872. Trial count N = 18 (data/qb2/trials.jsonl: 18 trials, 16 drills).
  Results: docs/research/P19_results_2026-10.md.

## Applied under standing GO — each a starting figure (QT-14, unchanged)
- Holdout: daily sealed from 2025-10-10; 5m from 2026-09-21 + all after 2026-10-10.
  None spent (no PASS). D3 = VWRP. Survivorship 1.0%/yr single shares. INSUFFICIENT
  < 30 OOS trades or bars. Stake GBP 300 (costs only). Walk-forward 252/63 daily,
  10/5 sessions 5m. Coin-flip null 200 runs. P4 flat 15 min before the close.
- P20 lines √-scaled as QT-14; the 5% one-name stop stays UNSCALED (no GO).
- QT-15 readings fixed before the run (commit e6eb241): Keltner reversion = the
  bar's low touches the lower band, close back inside; 5m sessions start flat.

## NEXT
1. **Mentor writes the next box.** Inputs: P19 none survived; flags below.
2. Mon 12 Oct: status page should show runs on :00, "Clean store: … · OK",
   "Daily store: fresh to … · OK", freshness and cross-check lines.
3. OPERATOR: keep the PC on (or Sleep) 08:00–21:00 UK on weekdays.
4. OPERATOR (optional, admin): `wevtutil set-log Microsoft-Windows-TaskScheduler/Operational /enabled:true`

## DECISION REQUESTED (open)
- Backups on the university OneDrive? Default: keep (2026-10-06 archive).

## Standing GOs (operator words, verbatim)
- 2026-10-07: *"STANDING GO: For routine settings and thresholds, go with the
  recommended default and log it. Three things always need my own words: switching
  the bot on to trade, real money, and removing any safety fence."*
- 2026-10-07: *"From now on, every box ends by saving its report in the repo and
  pushing, so the mentor can read it from GitHub."* → docs/reports/<BOX>.md.
- Live anchors, 2026-10-05: "One GO until the £100 cap". Raising a cap needs its
  own GO. 2026-10-09: *"GO on recorder triggers: 14 fixed hourly"* · *"GO on S4
  delay: (c), measure T212 freshness"*.

## CARRIED
- GOOG/GOOGL and VUAG/VUSA each count as ONE bet when the bot trades (bet_groups.json v1). Within the advisor
  list no same-fund pair (VWRL/VWRP, VUKG/VUKE split across bot/advisor).
- FX: 0.15% per leg on non-sterling lines. Can an API order choose USD? UNKNOWN.
- Parked: advisor trial counting (S9) · v1 revive-or-retire.

## Recorder facts
QB2-Recorder (Mon–Fri, 14 triggers 07:00…20:00, wake, catch-up, IgnoreNew, 3h).
Order: delay sample → hourly top-up → S4 measurements → after-hours step (raw →
clean, censuses, labels; then daily top-up) → freshness measuring. Status page
(QB2-StatusPush, :50) on the status branch. Daily digest: logs/digest/.

## Open flags
- Coin-flip null is weak on costs: a 50% coin churns, so every P19 rule "beat" it
  (p 0.005) while losing to VWRP. The verdict still needs DSR + benchmark.
- Daily trials score US names in dollars (FX per leg charged, FX moves not marked).
- anchors.py 1,422 lines (pinned): splitting = PROPOSE→GO.
- v1 QuantBot-Daily not run since 28 Jul; revive-or-retire deferred.
- Recorder prints RED for 15m (never recorded). No clock-sync task. gh CLI absent.
- Typing debt: 52 mypy errors silenced in 5 inherited modules.

## Fingerprints
v1 4add56ec…743b6 (unchanged 2026-10-11). qb2 32ec9a4b…7864fea after QT-15.
