# STATE.md — resume in seconds (current only; ≤6k chars, tested)

Updated: 2026-11-13 (QT-33). History → docs/archive/STATE_2026-11-13_QT33.md (verbatim). Box done: QT-33 →
docs/reports/QT-33.md.

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

## The advisor and the bot pot, live
- **ADV-0 = hold VWRL**, stop 15% below the highest close (10% when unsettled), raise-only; crossed =
  URGENT-EXIT alert, never a sale. Thu 12 Nov: £6,985.00 at 1x, stop £118.23.
- **Bot pot** (P21) follows ADV-0 with VWRP as if, £3,000 notional, own 15% stop. Thu 12 Nov: £3,025.71 at 1x, stop £121.69.
  Paper only; NOT a trial.
- **Price check (P22):** every session so far CONFIRMED, 0.00% (Mon 9 to Thu 12 Nov); journal
  data/qb2/price_check/journal.jsonl.
- **Daily store:** a missing market or VWRL/VWRP close is BEHIND: RED, retried every run, both pots held
  (QT-32). Yahoo's pattern every weekday: London's newest day blank at ~07:04, absent ~08:00–09:05, VWRL
  and VWRP present by the ~10:05 fetch. **Arrival log (QT-33):** data/clean/arrival.jsonl, one line a run;
  people only. The advisor's RED names a held-back close. CSH2.L (split; no Yahoo record) and SMEA.L
  (2023, accepted) are named "short".
- **VWRL anchor: built, not bought.** `--live` halts at F13 on CSH2's split bookings; the fix
  (qb2/tools/record_split.py) is built and NOT used: needs his GO. £46.59 of the £100 cap committed.
- **News:** US 8-K filings recorded daily; nothing reads them. No trial.
- **Clock:** recorder 07:00–20:00 UK, pushes at :50. **Fri 13 Nov the PC slept through 07:00** (01:22–07:41
  UTC): the run went at 07:44 on his wake and Windows skipped 08:00 while it ran. Unattended wake: NOT working.
- Brakes: advisor after an URGENT-EXIT — `python -m qb2.tools.clear_pause --pot advisor --words "..."`;
  bot pot's 15% pause — `--pot bot`.

## NEXT
1. **After ~2 weeks of arrival lines:** the earliest hour London's closes are reliably present; if 07:00 is
   too early, PROPOSE a time for his words (QT-33 PROPOSE 1). No schedule change before.
2. **CSH2 split, only after his GO words:** QT-32 DECISION 1 (ledger), command in docs/reports/QT-32.md.
   Then the VWRL buy (QT-31 Part D). Never run either twice. The daily store's CSH2: QT-33 DECISION 7.
3. The evening "Daily store" RED (QT-33 PROPOSE 2); the morning wake (PROPOSE 3).

## DECISION REQUESTED (open)
- **CSH2 split in the anchor ledger (blocks every --live).** Default: wait. GO words: "GO on the CSH2 split:
  record Trading 212's 27 Oct CSH2 split bookings in the anchor ledger from its order history, so the stale
  check passes and CSH2's anchor reads 0.2." Command in docs/reports/QT-32.md.
- **VWRL anchor.** Default: not bought. GO words in docs/reports/QT-31.md (not yet typed).
- **CSH2.L in the daily store** (QT-33 D7). Default: wait for Yahoo's record; stays named "short".
- **SEC contact address.** Default: a plain name, no address.
- **D1 advisor risk rule** and **bot's brake.** Defaults as built. GO words in docs/reports/QT-32.md.
- **A close never delivered** (none yet): the pots stay held, RED, until he decides.
- Holdout WAITING: none. v1's QuantBot-Daily/-Monthly run outside the cap (frozen): leave, report.

## Standing GOs (operator words, verbatim)
- 2026-11-13 (QT-33): *"Update this for Today (Friday) i ran out of useage. its currently 07:42"* (no GO).
- 2026-11-10 (QT-32): *"QT-32, no GO"* · *"give me a time and day to paste QT-32, also make sure it
  doesnt ask anything during the day and is ready to be pasted at 6:00 am"*.
- 2026-11-09 (QT-31): *"Yes, write it"* · *"change this for 6am"* · *"Do not ask for permission to do
  things, i will be gone after i paste it"*.
- 2026-11-08 (QT-30): *"GO with defaults"* = CLAUDE.md limit 4,100; any order still needs his words.
- 2026-10-29 (G3): *"(c) Follow index (Recommended)"* = PLAN_V3 P21.
- 2026-10-20, a FENCE: *"I stopped QT23 halfway through, there needs to be a limit on the amount of
  memory and CPU it takes up. like 80% limit for each. otherwise the PC cannot take it and will
  crash."*
- 2026-10-07: *"STANDING GO: For routine settings and thresholds, go with the recommended default and
  log it. Three things always need my own words: switching the bot on to trade, real money, and
  removing any safety fence."*
- Live anchors 2026-10-05: "One GO until the £100 cap". Recorder: 14 hourly triggers, 07:00–20:00.
- Older GOs: docs/archive/STATE_2026-11-11_QT32.md.

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
ad36150c…8781, (b) 14a454fb…90dc (QT-33, unchanged).
