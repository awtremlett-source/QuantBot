# 2026-10-05 — desk review of the operating docs (CLAUDE.md, STATE.md and friends)

## Operator words (verbatim)
1. *"i need an elite quant desk review of the claude.md to optimise its contants as
   well as be trim enough not to waste tokens."*
2. *"GO PROPOSE . yes to all. given we are developing a small quant desk using a small
   code base can you 10x the claude.md file and any other relevant md files tro
   optionise the whole setup. we need to build this desk to be best in class as well
   as reduce bloat and sprawl typically associated with vibe ai coding practices. ask
   any quiestions"*
3. Answers to the four questions (chosen options):
   - CLAUDE.md: "Apply draft (Recommended)"
   - STATE.md: "Yes, ≤6k (Recommended)"
   - Live orders: "One GO until the £100 cap"
   - Ledger gap: "Own box, before next --live (Recommended)"

"10x" was read as ten times better, not bigger (stated before the questions).

## How it was reviewed
Three independent read-only reviewers (risk · research validity · token cost),
each citing file:line; the five weightiest claims re-verified by hand.

## What was wrong (verified)
- CLAUDE.md said the bot "holds days"; P4 (2026-09-27) made it same-day, flat
  overnight. It slipped past the old wording check because it spans a line break.
- No order-safety rule (caps, never-resend, STOP_NEW_TRADES) in the always-loaded file.
- "v1 keeps running" was false: Windows refuses QuantBot-Daily since 28 Jul.
- A resume cost ~116k chars: STATE.md 58k plus a memory note that also pulled in
  the 38k founding directive and SCARS.
- v1's frozen list named 8 folders; the fingerprint covers 9 (reconcile/).
- Code gap (not fixed here, own box): a missing anchor ledger reads as empty.

## What changed
- CLAUDE.md rebuilt in FOUNDING §3 order (mission+phase · commands · map · laws ·
  token rules · pointers) — the approved draft's content; the draft had put
  money first as its own section, the constitution's order puts it first INSIDE
  the laws. 3,994 → 3,983 chars, with 4 order-safety rules added.
- STATE.md 57,817 chars → 3,552, current-only (≤6k, tested). The old file is archived verbatim
  at docs/archive/STATE_2026-10-05.md (STATE.md's own git log still holds every earlier version).
- tests/plan/test_plan_v3.py: budgets STATE 6k, MANIFEST 8k; CLAUDE.md and STATE.md
  may never state the old horizon (red on the old files, green after).
- SCARS/MANIFEST/README count 24 laws; FRAMEWORK's law index gained #24 (kept,
  not cut: it is the only one-line index of all 24); MANIFEST's live-strategy,
  daily-run and rubric-clock lines corrected; README's £100/day north star and
  "Phase 1" replaced; qb2/README says what is built.
- Auto-memory: the project note is now a resume pointer; the £100/day line retired.

## Parked (own boxes or their stage)
Ledger guard (next) · anchors.py split (PROPOSE) · test files named after boxes ·
D3 fund · holdout period · advisor trial counting · v1 revive-or-retire.
