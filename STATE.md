# STATE.md — resume in seconds (current only; ≤6k chars, tested)

Updated: 2026-10-26. History → docs/archive/STATE_2026-10-26_QT24.md (verbatim). Box done:
QT-25 → docs/reports/QT-25.md.

Phase: v2 BUILDING. **S0–S5 DONE; S6 OPEN (paused); S9 OPEN — the advisor is LIVE (armed
2026-10-20, first as-if fill 21 Oct)** (S3 close = QT-13 + QT-13b). No pick has survived (S6 0/24,
S9 0/12, P19 0/18). **Trial count N = 56** (S-07 described). Sender disarmed. No holdout ever opened.

## The resource cap (operator's words below: a FENCE)
Every heavy run: `.venv-qb2/Scripts/python -m qb2.tools.capped -- <cmd>` — one shared Job
Object: CPU 80% + 12 of 16 processors, 80% of RAM, below-normal priority; whole-PC memory ≥ 80%
waits, ≥ 90% for 60 s (or ≥ 95%) stops. Heavy entry points and the qb2 suite refuse outside it;
QB2-Recorder/QB2-StatusPush wrap themselves. Diary: logs/cap/cap.log.

## The advisor, live
- **ADV-0 = hold VWRL** (IE00B3RBWM25, GBP, London), stop 15% below the highest close (10% when
  unsettled), raise-only; crossed = URGENT-EXIT alert, never a sale; re-buy 10% above the low.
- **As-if BUY at Wed 21 Oct's open £138.38**, stop £117.91. Thu 22 Oct: £6,919.37 at 1x, £6,905.52
  at 2x (by hand, QT-25). **Friday's review (23 Oct 17:10 UTC): HOLD.**
- **Fri 23 Oct NOT processed yet:** Monday's provider bar for VWRL had no close (quarantined).
  The page says UNCHECKED, RED from Mon 10:00 UK (runs NOT CLEAN) until a sane close arrives.
- **Timing:** a session is final once London AND New York have closed (own clocks): 21:00 UK
  normally, **20:00 UK this week** (US clocks change Sun 1 Nov); figures come with the next run.
- **Daily door (QT-25 B):** a row fetched before its session closed is refused (manifest
  "refused", named in the "Daily store" line); the next top-up takes it.
- **5m bars (QT-25 C):** NOT YET DUE until their catch-up (20:00 UK or both markets shut); RED after.
- **^VIX** in the daily top-up; RED if it trails VWRL by > 1 London session.
- **Brake:** after an URGENT-EXIT his words also clear the advisor's 10% brake (GO below):
  `python -m qb2.tools.clear_pause --pot advisor --words "..."`.
- **Shadows:** S-01..S-06 from 20 Oct; **S-07** (registered cd3e863) day 0 = 23 Oct: first decision
  at Fri 23 Oct's close → as-if BUY at Mon 26 Oct's open. Both wait for VWRL's 23 Oct close.
- Described 2014–2025 at 2×: ADV-0 +173.3%, S-07 +145.0%, plain VWRL +268.7% (QT-24 report).
- Files: data/qb2/advisor/, stops.jsonl, brakes.jsonl; page `status/advisor.md` (status branch).

## NEXT
1. **Mentor writes the next box.** Check first: Mon 26 Oct's 20:00 UK run. VWRL's 23 Oct close back
   sane? Yes: days 23 + 26, S-07's first row and BUY at 26 Oct's open, RED gone. No: Monday done,
   Friday passed over silently (PROPOSE 2), S-07's first decision moves to Fri 30 Oct.
2. From Mon 2 Nov New York closes at 21:00 UK again.
3. PROPOSE: QT-25 report's list (first: the door keeps a sane stored row a re-fetch brings back
   broken; the advisor names a skipped session); MANUAL's re-justify (R4); scale check (SCARS #3).
4. OPERATOR: keep the PC on or asleep (it wakes itself at 07:00) on weekdays.

## DECISION REQUESTED (open)
- **D1 advisor risk rule.** Default: the 1% rule stays the ceiling. GO words: "GO on D1: for
  the advisor, replace the 1% rule with a cap on how much the account can lose if the stop is
  hit, figure chosen by S5's crash tests."
- **Bot's brake.** Default: as built. GO words: "GO on the bot's brake: the 10% brake clears
  itself after 5 sessions and restarts from there; the 15% pause stays measured from the true
  peak and only my words clear it."
- v1's QuantBot-Daily/-Monthly tasks run outside the cap (frozen; daily failing since 28 Jul).
  Default: leave, report. Backups on the university OneDrive? Default: keep.

## Standing GOs (operator words, verbatim)
- 2026-10-23, decision on QT-24's DECISION 1: *"Keep ADV-0's stop as the default for now; S-07
  stays a shadow."*
- 2026-10-23: *"GO on the advisor's 10% brake: after an urgent exit, my own words also clear the
  advisor's 10% brake and restart its peak from that day."*
- 2026-10-20, a FENCE (raising or removing it needs his words): *"I stopped QT23 halfway
  through, there needs to be a limit on the amount of memory and CPU it takes up. like 80%
  limit for each. otherwise the PC cannot take it and will crash."*
- 2026-10-19: *"GO on QT-23: build the advisor with "hold the index fund" as its default, the
  15% big-fall stop (10% when markets are jumpy) as its live stop, and the rules scored in the
  background on live prices only."* · *"GO on the advisor's brake: after an urgent exit, my own
  words clear the advisor's hold-off and restart its peak from that day, as for the bot's pause;
  no code clears it."*
- 2026-10-16: P15 history (verbatim in docs/archive/STATE_2026-10-20_QT22.md).
- 2026-10-07: *"STANDING GO: For routine settings and thresholds, go with the recommended
  default and log it. Three things always need my own words: switching the bot on to trade,
  real money, and removing any safety fence."* · reports saved in the repo and pushed.
- Live anchors 2026-10-05: "One GO until the £100 cap". Recorder: 14 hourly triggers, 07:00–20:00.

## CARRIED
- GOOG/GOOGL and VUAG/VUSA each count as ONE bet when the bot trades (bet_groups.json v1).
  FX 0.15% per leg on non-sterling lines. MTLN.L (EUR) skipped: no EUR rate.
- Parked: v1 revive-or-retire (its daily task fails since 28 Jul). 5m known-null to re-prove.
- QT-23 stash "QT-23-interrupted" kept (superseded by B; never deleted).

## Open flags
- Thin London ETF quotes (SSLN.L, ACWI.L, SMEA.L). anchors.py 1,422 lines (pinned); clean_step.py
  at 250. 52 mypy errors silenced in 5 inherited modules; 4 known Qt-stub errors.

## Fingerprints
v1 4add56ec…743b6 (unchanged). Advisor daily (a) 6883791f…97b1 since 26 Oct 06:17 UTC (BBY.L's
first earnings row; = 0f3a960c…f1f9 counted as before: no data in its window moved), (b)
f7aae670…768e (unchanged).
