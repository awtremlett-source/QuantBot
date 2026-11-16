# STATE.md — resume in seconds (current only; ≤6k chars, tested)

Updated: 2026-11-16 (QT-34). History → docs/archive/STATE_2026-11-16_QT34.md (verbatim). Box done: QT-34 →
docs/reports/QT-34.md (QT-33's report, left uncommitted on Fri 13, committed by QT-34).

Phase: v2 BUILDING. **S0–S5 DONE; S6 OPEN; S9 OPEN — the advisor is LIVE (armed 2026-10-20)**
(S3 close = QT-13 + QT-13b). No pick has survived (S6 0/30, S9 0/12, P19 0/18).
**Trial count N = 62.** Sender DISARMED. No holdout ever opened.

## Rule system (WI-0001 → docs/reports/WI-0001.md)
Every commit names an open work item: `python -m qb2.tools.work_door add item.json | close ID | list`.
18 rules ENFORCED, 88 OWED (may only fall). Baseline tag known-good-2026-11-08. NEXT job: requirement
checks, then the landing path. Run gates on a scratch copy: old app worktrees turn 2 tests red on main.

## The resource cap (operator's words below: a FENCE)
Every heavy run: `.venv-qb2/Scripts/python -m qb2.tools.capped -- <cmd>` (CPU 80%, 12 of 16
processors, 80% RAM, below-normal priority). Research runners: add `--clear-of-schedule` before `--`.
Fri 13 Nov 19:09 and 20:21: its memory guard stopped two recorder runs (the PC 98–99% full from other programs).

## The advisor and the bot pot, live
- **ADV-0 = hold VWRL**, stop 15% below the highest close (10% when unsettled), raise-only; crossed =
  URGENT-EXIT alert, never a sale. Fri 13 Nov: £6,914.82 at 1x, stop £118.23. Weekly HOLD issued Fri 13 10:05.
- **Bot pot** (P21) follows ADV-0 with VWRP as if, £3,000 notional, own 15% stop. Fri 13 Nov: £2,996.12 at 1x, stop £121.69.
  Paper only; NOT a trial.
- **Price check (P22):** every session so far CONFIRMED, 0.00% (Mon 9 to Fri 13 Nov); journal
  data/qb2/price_check/journal.jsonl.
- **Daily store:** a missing market or VWRL/VWRP close is BEHIND: RED, retried every run, both pots held
  (QT-32). **Arrival log** data/clean/arrival.jsonl (QT-33; people only): after a weeknight VWRL's and VWRP's
  closes came at ~10:05 every time (Wed–Fri), never by 09:05; after the weekend at 07:10 (Mon 16).
  CSH2.L (split; date unclear, QT-34 D) and SMEA.L (accepted) are named "short".
- **VWRL anchor: built, not bought.** `--live` halts at F13 on CSH2's split bookings; the fix
  (qb2/tools/record_split.py) is built and NOT used: needs his GO. £46.59 of the £100 cap committed.
- **News:** US 8-K filings recorded daily; nothing reads them. No trial.
- **Clock:** recorder 07:00–20:00 UK, **weekdays only**, pushes at :50. Unattended 07:00 wake: unproven (Fri 13
  NO; Mon 16 he woke the PC at 06:43).
- Brakes: advisor after an URGENT-EXIT — `python -m qb2.tools.clear_pause --pot advisor --words "..."`;
  bot pot's 15% pause — `--pot bot`.

## NEXT
1. **His words on QT-34 PROPOSE 1** (WAITING, not RED, before 10:00). No change before.
2. **CSH2 split, only after his GO words:** QT-32 DECISION 1 (ledger), command in docs/reports/QT-34.md.
   Then the VWRL buy (QT-31 Part D). Never run either twice. The daily store's CSH2: QT-34 DECISION 3.
3. The evening "Daily store" RED (PROPOSE 2); the morning wake (PROPOSE 3).

## DECISION REQUESTED (open; words in docs/reports/QT-34.md)
- **CSH2 split in the anchor ledger (blocks every --live).** Default: wait. GO words: "GO on the CSH2 split:
  record Trading 212's 27 Oct CSH2 split bookings in the anchor ledger from its order history, so the stale
  check passes and CSH2's anchor reads 0.2."
- **VWRL anchor.** Default: not bought. **CSH2.L in the daily store.** Default: wait (date unclear).
- **SEC contact address**, **D1 advisor risk rule**, **bot's brake**: defaults as built.
- **A close never delivered** (none yet): pots held, RED. **London WAITING before 10:00:** default no change.
- Holdout WAITING: none. v1's QuantBot-Daily/-Monthly run outside the cap (frozen): leave, report.

## Standing GOs (operator words, verbatim)
- 2026-11-16 (QT-34): *"Give me something for Monday 16th for 6am"* (no GO).
- 2026-11-13 (QT-33): *"Update this for Today (Friday) i ran out of useage. its currently 07:42"* (no GO).
- 2026-11-09 (QT-31): *"Do not ask for permission to do things, i will be gone after i paste it"*.
- 2026-11-08 (QT-30): *"GO with defaults"* = CLAUDE.md limit 4,100; any order still needs his words.
- 2026-10-29 (G3): *"(c) Follow index (Recommended)"* = PLAN_V3 P21.
- 2026-10-20, a FENCE: *"I stopped QT23 halfway through, there needs to be a limit on the amount of
  memory and CPU it takes up. like 80% limit for each. otherwise the PC cannot take it and will
  crash."*
- 2026-10-07: *"STANDING GO: For routine settings and thresholds, go with the recommended default and
  log it. Three things always need my own words: switching the bot on to trade, real money, and
  removing any safety fence."*
- Live anchors 2026-10-05: "One GO until the £100 cap". Older GOs: docs/archive/STATE_2026-11-16_QT34.md.

## CARRIED
- GOOG/GOOGL and VUAG/VUSA each count as ONE bet when the bot trades (bet_groups.json v1).
  FX 0.15% per leg on non-sterling lines. MTLN.L (EUR) skipped: no EUR rate.
- Parked: v1 revive-or-retire. 5m known-null to re-prove. QT-23 stash "QT-23-interrupted" kept.

## Open flags
- anchors.py 1,402 lines (pin 1,422); daily_step.py 239 of 250; cm_drills.py 247. At 250: advisor/daily,
  clean_step, ingest/daily, guard/stops, s6_run, advisor_run, p19_run, status_push. 52 mypy errors silenced
  in 5 inherited modules; 4 known Qt-stub errors. CSH2's anchor: broker 0.2, ledger 0.0008 (split).

## Fingerprints
v1 4add56ec…743b6. Advisor daily (a) 6883791f…97b1, (b) f7aae670…768e. Batch 2 trial data (a)
ad36150c…8781, (b) 14a454fb…90dc (QT-34, unchanged).
