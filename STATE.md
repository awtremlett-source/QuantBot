# STATE.md — resume in seconds (current only; ≤6k chars, tested)

Updated: 2026-11-09 (QT-30). History → docs/archive/STATE_2026-11-09_QT30.md (verbatim). Box done: QT-30 →
docs/reports/QT-30.md.

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
Never on the recorder (default OFF).

## The advisor and the bot pot, live
- **ADV-0 = hold VWRL**, stop 15% below the highest close (10% when unsettled), raise-only; crossed =
  URGENT-EXIT alert, never a sale. Fri 6 Nov: £6,749.24 at 1x, stop £118.23.
- **Bot pot** (P21) follows ADV-0 with VWRP as if, notional £3,000, its own 15% stop; a crossed stop =
  as-if SELL at the next open. Fri 6 Nov: £2,925.10 at 1x, stop £120.41. Paper only; NOT a trial.
- **Price check (P22, QT-30):** every stop-driving close gets a second price: Trading 212's (read after
  the close), else CNBC's. CONFIRMED within 0.5%; the stop rises only when CONFIRMED; a hit is never
  suppressed. Journal: data/qb2/price_check/journal.jsonl. **First real line: Tue 10 Nov 07:00.**
- **VWRL anchor: NOT SET UP** (no buying step exists; needs his words). VWRL is on the backup feed only.
  VWRP is anchored. £46.59 of the £100 anchor cap committed.
- **News, step 1 (QT-30 D):** US 8-K filings recorded once a UK day (data/raw/news/sec_8k.jsonl); nothing
  reads them. UK: no permitted free source. First trial is an unregistered DRAFT
  (docs/research/news_sources_2026-11-09_QT30.md).
- **Clock:** recorder runs 07:00–20:00 UK, pushes at :50. A session is final once London AND New York have
  closed, 21:00 UK, after the last run, so each day is processed at the next morning's 07:00 run.
- Brakes: advisor after an URGENT-EXIT — `python -m qb2.tools.clear_pause --pot advisor --words "..."`;
  bot pot's 15% pause — `--pot bot`.

## NEXT
1. **QT-31 Part A, by hand:** Tue 10 Nov 07:00 (or the first run after): Monday's close, the first real
   price-check lines, Trading 212 vs the store for VWRP.
2. OPERATOR: **keep the PC on or asleep, plugged in**. It has been sleeping about 03:00–18:00 and the 07:00
   wake is not working: 58 of 84 weekday runs missed since 30 Oct (QT-30 A1). Power settings are his.

## DECISION REQUESTED (open)
- **VWRL anchor.** Default: none. GO words: "GO on VWRL anchor: add VWRL to a separate pinned anchor list and
  buy one practice-account anchor of about £1 through the anchor buyer, inside the £100 cap."
- **SEC contact address.** Default: a plain name, no address.
- **D1 advisor risk rule.** Default: the 1% rule stays. GO words: "GO on D1: for the advisor,
  replace the 1% rule with a cap on how much the account can lose if the stop is hit, figure chosen
  by S5's crash tests."
- **Bot's brake.** Default: as built. GO words: "GO on the bot's brake: the 10% brake clears itself after 5
  sessions and restarts from there; the 15% pause stays measured from the true peak and only my words clear it."
- Holdout WAITING: none. v1's QuantBot-Daily/-Monthly run outside the cap (frozen): leave, report.

## Standing GOs (operator words, verbatim)
- 2026-11-08 (QT-30, accepted by reply): *"Alright give me QT-30, and tell me when to paste it"* (P22).
- 2026-11-08: *"GO with defaults"* = CLAUDE.md limit 4,100; any order still needs the operator's words; P10 stands until S10.
- 2026-10-29 (G3, chosen from a question): *"(c) Follow index (Recommended)"* = QT-28's (c), PLAN_V3 P21.
- 2026-10-23: *"Keep ADV-0's stop as the default for now; S-07 stays a shadow."* · *"GO on the
  advisor's 10% brake: after an urgent exit, my own words also clear the advisor's 10% brake and
  restart its peak from that day."*
- 2026-10-20, a FENCE: *"I stopped QT23 halfway through, there needs to be a limit on the amount of
  memory and CPU it takes up. like 80% limit for each. otherwise the PC cannot take it and will
  crash."*
- 2026-10-19: QT-23 advisor GO (verbatim in docs/archive/STATE_2026-10-29_QT28.md).
- 2026-10-07: *"STANDING GO: For routine settings and thresholds, go with the recommended default and
  log it. Three things always need my own words: switching the bot on to trade, real money, and
  removing any safety fence."*
- Live anchors 2026-10-05: "One GO until the £100 cap". Recorder: 14 hourly triggers, 07:00–20:00.

## CARRIED
- GOOG/GOOGL and VUAG/VUSA each count as ONE bet when the bot trades (bet_groups.json v1).
  FX 0.15% per leg on non-sterling lines. MTLN.L (EUR) skipped: no EUR rate.
- Parked: v1 revive-or-retire. 5m known-null to re-prove. QT-23 stash "QT-23-interrupted" kept.

## Open flags
- Thin London ETF quotes (SSLN.L, ACWI.L, SMEA.L). anchors.py 1,422 lines (pinned). At 250 lines:
  clean_step.py, ingest/daily.py, advisor/daily.py, guard/stops.py, s6_run.py, advisor_run.py,
  p19_run.py, status_push.py; bot_pot.py, price_check.py 198; cm_drills.py 247. 52 mypy errors silenced in 5
  inherited modules; 4 known Qt-stub errors.

## Fingerprints
v1 4add56ec…743b6. Advisor daily (a) 6883791f…97b1, (b) f7aae670…768e. Batch 2 trial data (a)
ad36150c…8781, (b) 14a454fb…90dc (QT-30, unchanged).
