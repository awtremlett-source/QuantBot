# DEPLOY — the rubric-gated migration runbook

Moving QuantBot to the always-on PC (or any other machine) is a GOVERNANCE
action, not a chore. The installer is built and verified; EXECUTING it anywhere
but the current machine requires the gate below. Until then, this page is the
plan, not a to-do.

## Prerequisites (ALL required before migration day)

1. Every one of the 7 graduation-rubric conditions in docs/MANIFEST.md is met.
2. Operator (governance) sign-off, recorded in STATE.md as a settled decision.

## The order IS the safety (single-writer law in action)

1. **OLD machine — final run.** One last morning run:
   `powershell -ExecutionPolicy Bypass -File install.ps1 -Verify` must be green
   and the digest fresh; the run's backup must land on the VERIFIED REMOTE
   destination (QUANTBOT_BACKUP_DIR — off-laptop, rubric 7).
2. **OLD machine — decommission the writer.**
   `powershell -ExecutionPolicy Bypass -File install.ps1 -Uninstall`
   removes both scheduled tasks. From this moment NO machine writes; the
   single-writer law is preserved through the whole migration.
3. **NEW machine — install.** Clone the repo, then
   `powershell -ExecutionPolicy Bypass -File install.ps1`
   (Python 3.13 check → venv → pins → bat generated from the NEW root → DB
   init → tasks registered → verify report).
4. **NEW machine — restore the journal.** Replace `data\quantbot.db` (and
   `data\trials.jsonl`) with the NEWEST verified backup pair from the remote
   destination, then rerun `install.ps1 -Verify`: database integrity must be
   ok and the latest CLEAN bar age plausible for the gap.
5. **NEW machine — proof run.** One manual
   `python -m execution.paper_loop --db data\quantbot.db` (venv active): the
   digest must show a clean catch-up over the migration gap and the MONITORS
   block must be free of RED.
6. **OLD machine — stays at zero tasks.** Verify once more with
   `install.ps1 -Verify` on the old machine: both tasks must report
   "not registered". The old clone may be kept as a cold spare, but it never
   runs tasks again.

## Laws (non-negotiable)

- `data\quantbot.db` lives on LOCAL disk only — never a network share (SQLite
  over SMB risks silent corruption) and never synced live by a cloud client.
- At most ONE machine has QuantBot tasks registered, ever. Uninstall before
  install; when in doubt, verify BOTH machines.
- Killswitch: a file named `STOP_NEW_TRADES` at the repo root of the ACTIVE
  machine stops all new orders; it is the human's lever, on the human's disk.

## Pointers

Installer internals → tools/installer.py · rubric → docs/MANIFEST.md ·
build order → docs/FRAMEWORK.md (Phase 7).
