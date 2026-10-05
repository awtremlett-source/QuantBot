# STATE.md — resume in seconds (current only; ≤6k chars, tested)

Updated: 2026-10-05. History before today → docs/archive/STATE_2026-10-05.md
(verbatim: settled decisions incl. v1 knobs, Done log, stage write-ups).
Last boxes: doc review (docs/sessions/2026-10-05-doc-review.md) · LEDGER GUARD (below).

Phase: v2 BUILDING. S0–S3d DONE. **S3 NOT complete**: only the quote delay is left
to measure (FACTS row o: 1 US session of 3, London 0). It resolves by the recorder
running; nothing to build. S3 close = QT-13. NOT S4.

## NEXT, in order
1. LEDGER GUARD (F13): DONE 2026-10-05 — section below.
2. QT-12 FINISH: `python -m qb2.execution.anchors --live --hold-above 1.10` on a NEW
   UTC day in London hours (08:10–16:15 London), earliest Tue 2026-10-06.
   **GATE: it may ONLY start if the ledger guard is merged on main and green** —
   first run `.venv-qb2/Scripts/python -m pytest tests/qb2/test_ledger_guard.py -q`;
   red, missing, or not on main = do not run.
   Closes when 50/50 names have a broker price → write the close-out here.
3. QT-13 = S3 close, once the delay has 3 US and 3 London sessions.

## LEDGER GUARD (F13) — DONE 2026-10-05
Operator verbatim: *"GO LEDGER-GUARD — fail-first tests, red then green: 1. If the
anchor ledger is missing, empty or unreadable, --live refuses to place any order
(dry run still allowed) and says why. Never recreate or reset it silently;
rebuilding it needs operator GO, from broker order history. 2. Prove it: tests for
missing, empty and corrupt ledger → zero orders sent. 3. Tomorrow's QT-12 run may
only start if this guard is merged and green; state that in STATE.md."*
BUILT: run_live checks AnchorLedger.unusable() FIRST — before the killswitch, the
broker and reconcile — and halts with the reason; the file is left byte-identical.
tests/qb2/test_ledger_guard.py: 8 tests (missing · empty · blank · corrupt JSON ·
non-record → 0 POSTs, 0 broker calls; dry run still plans; a real ledger passes).
Red on old code: a missing ledger SENT 3 orders. Live tests now start from a
seeded ledger. Pinned files did not grow (anchors.py 1,433 → 1,432).
NOT in this GO, still open: the ledger sits in gitignored data/ and DEPLOY's
backup+restore skip it.

## Standing GOs (operator words, verbatim)
- Live anchors, 2026-10-05, operator chose "One GO until the £100 cap" — one GO covers top-up runs
  until the lifetime cap. Raising a cap (£3/order · £100 lifetime · 50/UTC day)
  still needs its own GO.
- Weekday anchor top-up TASK: not created — "that gets its own GO".

## QT-12 anchors (P20) — where it stands, 2026-10-05
Ledger: 32 FILLED · 5 PRE_EXISTING · 18 REFUSED (all lifted once). Committed £32.93
of £100. Broker prices 37 of 50. Missing = 13 London names, still lifted: ISF VALL
SMGB VUKE SHEL HSBA RR BP GLEN BARC RIO AAL ULVR (est £1.01–1.08 each, none over
£1.10). Two runs on 10-05 bought 0: the 50/UTC-day fence counts refusals too (kept).
Read-only key proved unable to order (HTTP 403, nothing created).

## Carried flags
- CARRIED FLAG FOR THE S4 BOX: GOOG/GOOGL and VUAG/VUSA each count as ONE bet when
  the bot trades (same company / same index fund); both still get an anchor.
- Parked for their stage: which fund is D3 (S4) · which period is the holdout (S4) ·
  do advisor ideas face trial counting (S9) · v1 revive-or-retire.
- anchors.py is 1,433 lines (pinned oversize): splitting it = its own PROPOSE→GO.
- Test files named after boxes (test_qt12*) break "tests mirror the tree"; fold in
  when anchors.py is split.

## Open flags
- v1 QuantBot-Daily has not run since 28 Jul: Windows refuses start (0x800710E0,
  again 05/10 14:29); its bot is 31+ days behind. Revive-or-retire deferred.
- QB2-Recorder wakes the PC only on mains power (Balanced plan: DC wake timers off).
- Backups LOCAL-ONLY until QUANTBOT_BACKUP_DIR points off-laptop (rubric cond. 7).
- .env.example keeps the old T212 "to verify" note (inside the engine fingerprint).
- Daily auto clock-sync task not set up (admin). gh CLI absent → plain git.
- Manual app's journal not migrated (trades.shares INTEGER vs REAL; MERGE_PLAN 3b).
- Two killswitch faces (tools/gui.py + Bot tab) until stage 4.
- Typing debt: 52 mypy errors silenced in 5 inherited modules (docs/merge/TYPING_DEBT.md).
- Manual suite prints 2 Qt "access violation" lines and passes; pre-existing.
- CLAUDE.md budget 4,000 (QT-04 had 3,600): default kept, no operator reply yet.

## Fingerprints
v1 4add56ec…743b6 (must never move; re-verified 2026-10-05) · qb2 b96a3420…6546 after LEDGER GUARD (3ce2c634…d125 before).
