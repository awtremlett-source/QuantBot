# STATE.md — resume in seconds (current only; ≤6k chars, tested)

Updated: 2026-11-11 (QT-32). History → docs/archive/STATE_2026-11-11_QT32.md (verbatim). Box done: QT-32 →
docs/reports/QT-32.md.

Phase: v2 BUILDING. **S0–S5 DONE; S6 OPEN; S9 OPEN — the advisor is LIVE (armed 2026-10-20)**
(S3 close = QT-13 + QT-13b). No pick has survived (S6 0/30, S9 0/12, P19 0/18).
**Trial count N = 62.** Sender DISARMED. No holdout ever opened.

## Rule system (WI-0001 → docs/reports/WI-0001.md)
Every commit names an open work item: `python -m qb2.tools.work_door add item.json | close ID | list`.
18 rules ENFORCED, 88 OWED (may only fall). Baseline tag known-good-2026-11-08. NEXT job: requirement
checks, then the landing path. Run gates on a scratch copy: old app worktrees turn 2 tests red on main.
S10 is not OPEN, so S10 work goes in as a named EXCEPTION (QT-32D).

## The resource cap (operator's words below: a FENCE)
Every heavy run: `.venv-qb2/Scripts/python -m qb2.tools.capped -- <cmd>` (CPU 80%, 12 of 16
processors, 80% RAM, below-normal priority). Research runners: add `--clear-of-schedule` before `--`.
Never on the recorder (default OFF).

## The advisor and the bot pot, live
- **ADV-0 = hold VWRL**, stop 15% below the highest close (10% when unsettled), raise-only; crossed =
  URGENT-EXIT alert, never a sale. Tue 10 Nov: £6,845.66 at 1x, stop £118.23.
- **Bot pot** (P21) follows ADV-0 with VWRP as if, notional £3,000, its own 15% stop. Tue 10 Nov:
  £2,966.53 at 1x, stop £120.41. Paper only; NOT a trial.
- **Price check (P22):** live since 11 Nov: Mon 9 and Tue 10 Nov, VWRL (backup) and VWRP (Trading 212),
  all CONFIRMED, 0.00%; no stop moved. Journal: data/qb2/price_check/journal.jsonl.
- **Daily store (QT-32, live 08:22 UK 11 Nov):** a market or VWRL.L/VWRP.L missing its last finished
  close is BEHIND: retried every run, RED, and both pots wait (fetched_through held). At 09:00 11 Nov
  VWRL's/VWRP's Tue closes were blank (held at Mon 9); 10:00 they came, Tue processed once.
  CSH2.L (split) and SMEA.L (2023) are named "short" every run: old holes, PROPOSE 2–3.
- **VWRL anchor: built, not bought.** `--live` halts at F13 on CSH2's split bookings. The fix is built
  (qb2/tools/record_split.py, dry run: CSH2 0.0008 → 0.2, F13 passes) and NOT used: needs his GO.
  £46.59 of the £100 cap committed.
- **News, step 1:** US 8-K filings recorded once a UK day; nothing reads them. No trial.
- **Clock:** recorder runs 07:00–20:00 UK, pushes at :50. Yahoo's London closes came blank at 07:00 two
  mornings running; the retries now catch them later in the day.
- Brakes: advisor after an URGENT-EXIT — `python -m qb2.tools.clear_pause --pot advisor --words "..."`;
  bot pot's 15% pause — `--pot bot`.

## NEXT
1. **QT-33, read-only:** each morning's London closes: blank at 07:00 again? Which run cleared them; each
   session processed once (days.jsonl, journal)? Retry times (marker `retry_s`; 143.4 s, 25.5 s so far).
2. **CSH2 split, only after his GO words:** his own command, dry run first (QT-32 DECISION 1). Then the
   VWRL buy, dry run first (QT-31 Part D). Never run either twice.
3. PROPOSE 1 (QT-32): measure when London's closes really arrive.

## DECISION REQUESTED (open)
- **CSH2 split (blocks every --live).** Default: wait. GO words: "GO on the CSH2 split: record Trading
  212's 27 Oct CSH2 split bookings in the anchor ledger from its order history, so the stale check passes
  and CSH2's anchor reads 0.2." Command in docs/reports/QT-32.md.
- **VWRL anchor.** Default: not bought. GO words in docs/reports/QT-31.md (not yet typed).
- **SEC contact address.** Default: a plain name, no address.
- **D1 advisor risk rule** and **bot's brake.** Defaults as built. GO words in docs/reports/QT-32.md.
- **A close never delivered** (none yet): the pots stay held, RED, until he decides.
- Holdout WAITING: none. v1's QuantBot-Daily/-Monthly run outside the cap (frozen): leave, report.

## Standing GOs (operator words, verbatim)
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
- Older GOs (QT-23 advisor, the 10% brake, ADV-0's stop): docs/archive/STATE_2026-11-11_QT32.md.

## CARRIED
- GOOG/GOOGL and VUAG/VUSA each count as ONE bet when the bot trades (bet_groups.json v1).
  FX 0.15% per leg on non-sterling lines. MTLN.L (EUR) skipped: no EUR rate.
- Parked: v1 revive-or-retire. 5m known-null to re-prove. QT-23 stash "QT-23-interrupted" kept.

## Open flags
- Thin London ETF quotes. anchors.py 1,402 lines (pin 1,422); daily_step.py 238 of 250; cm_drills.py 247.
  At 250: clean_step, ingest/daily, advisor/daily, guard/stops, s6_run, advisor_run, p19_run, status_push.
  52 mypy errors silenced in 5 inherited modules; 4 known Qt-stub errors. CSH2's anchor: broker 0.2,
  ledger 0.0008 (split).

## Fingerprints
v1 4add56ec…743b6. Advisor daily (a) 6883791f…97b1, (b) f7aae670…768e. Batch 2 trial data (a)
ad36150c…8781, (b) 14a454fb…90dc (QT-32, unchanged).
