# STATE.md — resume in seconds (current only; ≤6k chars, tested)

Updated: 2026-10-12. History → docs/archive/STATE_2026-10-12.md (QT-15 state,
verbatim). Box in hand: QT-16 → docs/reports/QT-16.md.

Phase: v2 BUILDING. **S0–S5 DONE** (S3 close = QT-13 + QT-13b; S4 = QT-14; S5 =
QT-16). P19: none of 18 survived (QT-15). Bot sender still disarmed (S10).

## QT-16 operator's words (verbatim, 2026-10-12)
- *"write QT-16"*

## QT-16 in one screen
- A1 luck test = turnover-matched null (each rule's own trades at random times);
  coin-flip kept as description + DSR variance. KN-LAZY-5m: coin p 0.005 (RED),
  matched p 0.075 (GREEN). Known-null Gate 1 + Gate 2 GREEN, 7 drills.
- A2 US money in pounds (pounds.py): (1+r_usd)(1+r_fx)−1; held bar with no rate =
  INSUFFICIENT.
- B qb2/guard/: stops (raise-only ledger), brakes, pots, age, earnings_window,
  suggestion; sender BUY checks 6–9; sells skip them. Earnings refreshed after the
  daily top-up; status line "Earnings: …". FLAT_ON_SHUTDOWN.md (S10 builds).
- C replays: 10% fired in 2008/2020/2022, 15% in 2008 and 2020 (and 2022 on 3 of
  4 paths); false alarms 7/12 ^GSPC, 13/19 ^NDX, 5/9 ^FTSE, 4/8 URTH. 3×ATR daily
  trailing stop: 89% stopped within 63 days (description only).

## Applied under standing GO — starting figures
- QT-14/15 (unchanged): holdout daily from 2025-10-10, 5m from 2026-09-21 + after
  2026-10-10; D3 = VWRP; survivorship 1%/yr; INSUFFICIENT < 30; stake GBP 300;
  walk-forward 252/63, 10/5 sessions; nulls 200 runs; P4 15 min. P20 lines
  √-scaled; the 5% one-name stop UNSCALED.
- QT-16: FX same bar else previous within 10 min (5m) / 4 days (daily). Stop k = 3 ×
  Wilder ATR(14) (bot 5m, advisor/manual daily); k = 2 when brake on or VIX > 30
  (no VIX = unsettled). Brake clears within 5% of peak; his words clear the bot's
  15% pause and restart its peak. Bot pot = 30% of account value at the check
  ("not shrunk"), advisor 70%, anchors + manual in neither. Age flag 11 months.
  Earnings: bot blocked session before → after, unknown blocks, ETF N/A; advisor
  warns 5 sessions ahead; coverage RED < 90%. P12 10%/15% NOT changed.
- QB2-StatusPush: 14 fixed triggers Mon–Fri 08:50…21:50 UK (was one repeating).

## NEXT
1. **Mentor writes the next box (S6).** Inputs: QT-16 flags below.
2. Tue 13 Oct 07:00: after-hours step cleans Mon 12 Oct; status page should show
   "Earnings: fresh to 2026-10-12 · … · OK" and "Status pushes today" with no MISSED.
3. OPERATOR: keep the PC on (or Sleep) 08:00–21:00 UK on weekdays.
4. OPERATOR (optional, admin): `wevtutil set-log Microsoft-Windows-TaskScheduler/Operational /enabled:true`

## DECISION REQUESTED (open)
- Bot's 10% brake cannot clear by itself (a bot that may not buy holds cash).
  Default: as built (braked until you decide; nothing armed before S10). GO words:
  "GO on the bot's brake: my words also clear its 10% brake, and any clearance
  restarts its peak."
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
After-hours: raw → clean, censuses, labels; daily top-up; earnings refresh.
Status page (QB2-StatusPush, :50) on the status branch. Digest: logs/digest/.
The PC SLEEPS overnight (Kernel-Power 42), it does not shut down.

## Open flags
- A losing rule whose losses cluster can "beat" the luck test (negative Sharpe
  reads better when noisier): KN-INSTANT p 0.005 at −42.7%. Verdict holds (DSR).
- 3×ATR daily trailing stop exits most advisor holdings within a month: choosing
  k is a trial (S9, unsealed bars only). C2 read the sealed daily year (description).
- anchors.py 1,422 lines (pinned): splitting = PROPOSE→GO.
- v1 QuantBot-Daily not run since 28 Jul; revive-or-retire deferred.
- Recorder prints RED for 15m (never recorded). No clock-sync task. gh CLI absent.
- Typing debt: 52 mypy errors silenced in 5 inherited modules.

## Fingerprints
v1 4add56ec…743b6 (unchanged 2026-10-12). qb2 0aeeb5a2…a9691 after QT-16.
