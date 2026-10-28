# STATE.md — resume in seconds (current only; ≤6k chars, tested)

Updated: 2026-10-27. History → docs/archive/STATE_2026-10-27_QT25.md (verbatim). Box done:
QT-26 → docs/reports/QT-26.md.

Phase: v2 BUILDING. **S0–S5 DONE; S6 OPEN (paused); S9 OPEN — the advisor is LIVE (armed
2026-10-20, first as-if fill 21 Oct)** (S3 close = QT-13 + QT-13b). No pick has survived (S6 0/24, S9 0/12, P19 0/18).
**Trial count N = 56**. Sender disarmed. No holdout ever opened.

## The resource cap (operator's words below: a FENCE)
Every heavy run: `.venv-qb2/Scripts/python -m qb2.tools.capped -- <cmd>` — one shared Job
Object: CPU 80% + 12 of 16 processors, 80% of RAM, below-normal priority; whole-PC memory ≥ 80%
waits, ≥ 90% for 60 s (or ≥ 95%) stops. QB2-Recorder/QB2-StatusPush wrap themselves.
Diary: logs/cap/cap.log.

## The advisor, live
- **ADV-0 = hold VWRL** (IE00B3RBWM25, GBP, London), stop 15% below the highest close (10% when
  unsettled), raise-only; crossed = URGENT-EXIT alert, never a sale; re-buy 10% above the low.
- **As-if BUY at Wed 21 Oct's open £138.38**, stop £117.91. Fri 23 Oct £6,916.34, Mon 26 Oct
  **£6,945.11** at 1x (£6,931.22 at 2x), by hand (QT-26). Friday's review: HOLD.
- **S-07** first decision Fri 23 Oct's close (Sep 140.29 > 10-month avg 131.66): as-if BUY at Mon
  26 Oct's open £136.72; +0.42% at 1x on 26 Oct. S-01..S-06 in cash since 20 Oct.
- **Timing:** a session is final once London AND New York have closed: **20:00 UK this week**,
  21:00 UK from Mon 2 Nov (US clocks change Sun 1 Nov); figures come with the next run.
- **Daily door:** refuses a row fetched before its session closed (QT-25 B). **QT-26 B:** a sane
  stored row whose re-fetch comes back broken is KEPT; a changed close is taken and named with both
  figures; the quarantine only grows (refetch.py). All named in the "Daily store" line.
- **QT-26 C:** a London session VWRL lacks between good days = a SKIPPED row in days.jsonl, named
  "UNCHECKED: <date> has no sane VWRL close" every run and on the page; a late close is final
  (never re-processed). skips.py.
- 5m bars NOT YET DUE until their catch-up; ^VIX RED if it trails VWRL by > 1 London session.
- **Brake:** after an URGENT-EXIT his words also clear the advisor's 10% brake:
  `python -m qb2.tools.clear_pause --pot advisor --words "..."`.
- Files: data/qb2/advisor/, stops.jsonl, brakes.jsonl; page `status/advisor.md` (status branch).

## NEXT
1. **Mentor writes the next box.** Check: tonight's 20:00 UK run is the first top-up on QT-26's
   door — read its "Daily store" line (any "kept" or "corrected" names, and why).
2. PROPOSE (QT-26 report): fingerprint (a)'s "no file" counting; GBPUSD cut-off; ^VIX Cboe
   calendar; MANUAL's re-justify (R4); scale check (SCARS #3); Windows task-history log; a row the
   provider leaves out altogether.
3. OPERATOR: keep the PC on or asleep (it wakes itself at 07:00) on weekdays.

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
- Parked: v1 revive-or-retire. 5m known-null to re-prove. QT-23 stash "QT-23-interrupted" kept.

## Open flags
- Thin London ETF quotes (SSLN.L, ACWI.L, SMEA.L). anchors.py 1,422 lines (pinned); clean_step.py,
  ingest/daily.py, advisor/daily.py at 250. 52 mypy errors silenced in 5 inherited modules; 4 known
  Qt-stub errors.

## Fingerprints
v1 4add56ec…743b6 (unchanged). Advisor daily (a) 6883791f…97b1, (b) f7aae670…768e (both
unchanged, QT-26).
