# STATE.md — resume in seconds (current only; ≤6k chars, tested)

Updated: 2026-10-09. History → docs/archive/STATE_2026-10-08.md (QT-12R, QT-12S,
verbatim) and earlier archives. Last box: QT-13 (2026-10-09) → docs/reports/QT-13.md.

Phase: v2 BUILDING. S0–S3d DONE. **S3 NOT complete** (QT-13 exit check, PLAN_V3 S3).
S3 close = QT-13 ran 2026-10-09: quote delay now VERIFIED (FACTS row o: US median
1.25 min, London 16.66 min, 5 sessions each), but the census went RED: nothing on
the schedule runs the front door (raw → clean), so the clean store stopped on 2 Oct
and on 9 Oct all 221 names fail as stale (0.0%). A scratch rebuild from raw passes
217/221 (98.2%): the data is fine, the pipe is not wired. NOT S4.

## NEXT, in order
1. QT-13b (mentor writes it): run the front door + the 5-minute census in the
   recorder's after-hours step, RED when the clean store is stale; a label pass
   counts only on NEW data (today two runs on the same data promote). Then one
   fresh census on the real store ≥95% → S3 DONE. Earliest: the next weekday
   evening after QT-13b lands.
2. OPERATOR: two DECISIONS below. Keep the PC on (or Sleep) 08:00–21:00 UK on
   weekdays; Shut down at night shifts every next-day run (see QT-13 §2).

## DECISION REQUESTED (open)
- Recorder trigger (Windows, not touched): after a late catch-up the hourly runs
  move to that minute (9 Oct: all at :53, London's 16:00 slot after the close).
  Default: re-register QB2-Recorder with 14 fixed triggers 07:00…20:00 UK, no
  repetition, same settings. GO words: "GO on recorder triggers: 14 fixed hourly".
- S4 and London's 17-minute delay. Default (c): act only on bars seen complete,
  each market at its measured delay, and in S4 measure Trading 212's own price
  freshness for (a). GO words: "GO on S4 delay: (c), measure T212 freshness".
- Backups on the university OneDrive? Default: keep (2026-10-06 archive).

## Standing GOs (operator words, verbatim)
- 2026-10-07: *"STANDING GO: For routine settings and thresholds, go with the
  recommended default and log it. Three things always need my own words: switching
  the bot on to trade, real money, and removing any safety fence."*
- 2026-10-07: *"From now on, every box ends by saving its report in the repo and
  pushing, so the mentor can read it from GitHub."* → docs/reports/<BOX>.md.
- Live anchors, 2026-10-05, operator chose "One GO until the £100 cap" — one GO
  covers top-ups until the lifetime cap. Raising a cap (£3/order · £100 lifetime ·
  50/UTC day) still needs its own GO. QT-12 CLOSED 06/10: 50/50 priced, £46.59.
- Weekday anchor top-up TASK: not created — "that gets its own GO".

## CARRIED INTO S4 (from QT-13)
- GOOG/GOOGL and VUAG/VUSA each count as ONE bet when the bot trades (same
  company / same index fund); both still get an anchor.
- P20 cross-check thresholds are built in S4; their 1.6-min premise is now US
  1.25 / London 16.66 min (row o) — London's gap rule must allow for it.
- The S4 delay decision above. P19's 18 trials stay pre-registered as written.
- FX: costs.py already charges 0.15% per leg on US names. Trading 212 (page read
  2026-10-09): only the Invest account holds USD; the ISA does not, so in an ISA
  every US trade converts. Can an API order choose USD? UNKNOWN.
- Parked: which fund is D3 · the holdout period · advisor trial counting (S9) ·
  v1 revive-or-retire.

## Recorder facts
QB2-Recorder (Mon–Fri 07:00 +1h ×14h, wake, catch-up) writes RAW only; the hourly
status page (QB2-StatusPush, :50) now lists today's run times and flags runs 20+
min past the hour. Raw page: raw.githubusercontent.com/awtremlett-source/
QuantBot/status/status/recorder_status.md. Minute labels: 0 MINUTE_OK (86
promoted 5 Oct on the same data as 3 Oct, all demoted 7 Oct as stale).
Default test run is offline: the live smoke test runs only with -m network.

## Open flags
- anchors.py is 1,433 lines (pinned oversize): splitting = its own PROPOSE→GO;
  test_qt12* files fold in then.
- v1 QuantBot-Daily has not run since 28 Jul (0x800710E0); revive-or-retire deferred.
- Task Scheduler's history log is off on this PC; run evidence = logs/recorder.
- .env.example keeps the old T212 "to verify" note (inside the engine fingerprint).
- No daily clock-sync task (admin). gh CLI absent → plain git.
- Manual journal not migrated (MERGE_PLAN 3b). Two killswitch faces until stage 4.
- Typing debt: 52 mypy errors silenced in 5 inherited modules (docs/merge/TYPING_DEBT.md).
- Idea: a 15-minute sampler task (a new task = GO).

## Fingerprints
v1 4add56ec…743b6 (must never move; re-verified 2026-10-09) · qb2 a087ffbf…1580e
after QT-13 (normal CRLF checkout; delay_count.py, status_push.py changed).
