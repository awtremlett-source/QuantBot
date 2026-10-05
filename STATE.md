# STATE.md — resume in seconds (current only; ≤6k chars, tested)

Updated: 2026-10-05. History before today → docs/archive/STATE_2026-10-05.md
(verbatim: settled decisions incl. v1 knobs, Done log, stage write-ups).
Last boxes: doc review (docs/sessions/2026-10-05-doc-review.md) · LEDGER GUARD+BACKUP ·
BACKUP-OFFSITE.

Phase: v2 BUILDING. S0–S3d DONE. **S3 NOT complete**: only the quote delay is left
to measure (FACTS row o: 1 US session of 3, London 0). It resolves by the recorder
running; nothing to build. S3 close = QT-13. NOT S4.

## NEXT, in order
1. LEDGER GUARD + BACKUP (F13): DONE 2026-10-05 — section below.
2. QT-12 FINISH: `python -m qb2.execution.anchors --live --hold-above 1.10` on a NEW
   UTC day in London hours (08:10–16:15 London), earliest Tue 2026-10-06.
   **GATE: it may ONLY start if the ledger guard is merged on main and green** —
   first run `.venv-qb2/Scripts/python -m pytest tests/qb2/test_ledger_guard.py
   tests/qb2/test_ledger_backup.py -q`;
   red, missing, or not on main = do not run.
   Closes when 50/50 names have a broker price → write the close-out here.
3. QT-13 = S3 close, once the delay has 3 US and 3 London sessions.

## LEDGER GUARD + BACKUP (F13) — DONE 2026-10-05
Operator verbatim: *"GO LEDGER-GUARD ... If the anchor ledger is missing, empty or
unreadable, --live refuses to place any order (dry run still allowed) and says why.
Never recreate or reset it silently; rebuilding it needs operator GO, from broker
order history ... Tomorrow's QT-12 run may only start if this guard is merged and
green"* and *"GO LEDGER-BACKUP ... Add the anchor ledger to DEPLOY's backup and
restore steps. After any restore, --live refuses until the ledger is reconciled
against broker order history (every broker anchor order present in the ledger). A
mismatch stops, reports, and changes nothing."*
BUILT: run_live refuses a missing/empty/unreadable ledger before any broker call,
and a STALE one (a broker API order no ledger intent matches; checked on EVERY run,
so any restore is covered) before reconcile writes. qb2/execution/ledger_backup.py:
verified dated copy after every live run (also `python -m qb2.execution.ledger_backup`);
DEPLOY steps 1 and 4 carry it. Red first: missing ledger SENT 3 orders; stale SENT 3.
Real account 2026-10-05: 32 API orders, all in the ledger; hand orders are WEB/IOS.
First backup verified but LOCAL-ONLY (QUANTBOT_BACKUP_DIR unset) → fixed below.

## BACKUP-OFFSITE — DONE 2026-10-05
Operator verbatim: *"GO BACKUP-OFFSITE — set QUANTBOT_BACKUP_DIR to a OneDrive
folder (create QuantBot_Backups under the user's OneDrive; name-only in output)
... Restore never writes to the live file without operator GO."*
QUANTBOT_BACKUP_DIR = user env var → QuantBot_Backups in the ONLY signed-in
OneDrive (the university work account; the old C: OneDrive folder is not linked).
Backups 22:44 BST, all hash-checked by hand, 0 of 4 .env values in any copy:
ledger-20261005T224412+0100.jsonl c9adeab6…7343 (= live) · quantbot-20261005.db
5b0760cd…8e72 (integrity ok, 82,670 rows) · trials-20261005.jsonl a14a7858…4fca (= live).
No restore code exists; DEPLOY step 4 says restore = operator GO.
DECISION REQUESTED: keep backups on the university OneDrive (lost if the account
closes; university admins can read it)? Default: keep; move if you prefer a personal one.

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
- .env.example keeps the old T212 "to verify" note (inside the engine fingerprint).
- Daily auto clock-sync task not set up (admin). gh CLI absent → plain git.
- Manual app's journal not migrated (trades.shares INTEGER vs REAL; MERGE_PLAN 3b).
- Two killswitch faces (tools/gui.py + Bot tab) until stage 4.
- Typing debt: 52 mypy errors silenced in 5 inherited modules (docs/merge/TYPING_DEBT.md).
- Manual suite prints 2 Qt "access violation" lines and passes; pre-existing.
- CLAUDE.md budget 4,000 (QT-04 had 3,600): default kept, no operator reply yet.

## Fingerprints
v1 4add56ec…743b6 (must never move; re-verified 2026-10-05) · qb2 d4dc0942…f269 after LEDGER BACKUP (b96a3420…6546 after GUARD).
