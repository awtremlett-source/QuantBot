# STATE.md — resume in seconds (current only; ≤6k chars, tested)

Updated: 2026-10-20. History → docs/archive/STATE_2026-10-20_QT22.md (verbatim). Box done:
QT-23R + QT-23 → docs/reports/QT-23R.md, docs/reports/QT-23.md.

Phase: v2 BUILDING. **S0–S5 DONE; S6 OPEN (paused); S9 OPEN — the advisor is BUILT and ARMED
(2026-10-20)** (S3 close = QT-13 + QT-13b). No pick has survived (S6 0/24, S9 0/12, P19 0/18).
**Trial count N = 55** (ADV-0 described). Sender disarmed. No holdout ever opened.

## The resource cap (operator's words below: a FENCE)
Every heavy run: `.venv-qb2/Scripts/python -m qb2.tools.capped -- <cmd>` — one shared Job
Object: CPU rate cap 80% + 12 of 16 processors, 80% of RAM, below-normal priority; whole-PC
memory ≥ 80% waits, ≥ 90% for 60 s (or ≥ 95%) stops cleanly. Heavy entry points and the qb2
suite refuse outside it; QB2-Recorder/QB2-StatusPush wrap themselves. Diary: logs/cap/cap.log.

## The advisor, live (QT-23)
- **ADV-0 = hold VWRL** (IE00B3RBWM25, GBP, London), the whole advisor pot; stop 15% below the
  highest close (10% when unsettled), raise-only; crossed = URGENT-EXIT alert, never a sale;
  re-buy at a close 10% above the low since the exit. Weekly review Friday (first recorder run
  with Thursday's session); daily job every weekday — both ride the after-hours step.
- **First review 2026-10-20: BUY VWRL, allowed** (close £139.02 on 19 Oct; stop ≈ £118.17); as
  if filled at Wed 21 Oct's open. Notional pot £7,000. Page: status branch `status/advisor.md`.
- **S-01..S-06** (= A2-01..A2-06) scored from 2026-10-20, counted 0; promotion only after 12
  months + luck test + DSR, then only a PROPOSE.
- **ADV-0 described (2014–2025, 2× costs):** +173.3% vs plain VWRL +268.7% (the stop −95 pts;
  worst fall −25.5% vs −24.9%); 2020 +1.3 pts; 2022 −9.1 pts.
- Files: data/qb2/advisor/ (arm.json, suggestions, days, shadows, runs), stops.jsonl,
  brakes.jsonl. Clear the advisor's hold-off: `python -m qb2.tools.clear_pause --pot advisor
  --words "..."` (his words only).

## NEXT
1. **Mentor writes the next box.** Check first: tomorrow's ~07:00 UK recorder run (in the cap:
   logs/cap/cap.log) fills the BUY at Wed's open, opens the stop, writes day 0 and day 1.
2. The two DECISIONS below (the stop's cost; the 10% brake after an exit).
3. PROPOSE: MANUAL's re-justify can still open lower (R4: unchanged, flagged).
4. Watch ^VIX: the store's newest close is 16 Oct (older than 5 days = unsettled = 10% stop).
5. PROPOSE: per-ticker scale check vs Trading 212's own price (SMEA.L, SCARS #3).
6. OPERATOR: keep the PC on (or Sleep) 08:00–21:00 UK on weekdays.

## DECISION REQUESTED (open)
- **ADV-0's stop.** Default: kept (his GO; P10). GO words: "GO on ADV-0: hold VWRL with no
  big-fall stop and no re-buy; the shadows keep theirs."
- **The advisor's 10% brake after an exit** (cash never climbs back within 5%: the re-buy
  waits for ever). Default: as registered. GO words: "GO on the advisor's 10% brake: after an
  urgent exit, my own words also clear the advisor's 10% brake and restart its peak from that day."
- **D1 advisor risk rule.** Default: the 1% rule stays the ceiling. GO words: "GO on D1: for
  the advisor, replace the 1% rule with a cap on how much the account can lose if the stop is
  hit, figure chosen by S5's crash tests."
- **Bot's brake.** Default: as built. GO words: "GO on the bot's brake: the 10% brake clears
  itself after 5 sessions and restarts from there; the 15% pause stays measured from the true
  peak and only my words clear it."
- v1's QuantBot-Daily/-Monthly tasks run outside the cap (frozen; daily failing since 28 Jul).
  Default: leave, report. Backups on the university OneDrive? Default: keep.

## Standing GOs (operator words, verbatim)
- 2026-10-20, a FENCE (raising or removing it needs his words): *"I stopped QT23 halfway
  through, there needs to be a limit on the amount of memory and CPU it takes up. like 80%
  limit for each. otherwise the PC cannot take it and will crash."*
- 2026-10-19: *"GO on QT-23: build the advisor with "hold the index fund" as its default, the
  15% big-fall stop (10% when markets are jumpy) as its live stop, and the rules scored in the
  background on live prices only."* · *"GO on the advisor's brake: after an urgent exit, my own
  words clear the advisor's hold-off and restart its peak from that day, as for the bot's
  pause; no code clears it."*
- 2026-10-16: P15 history (verbatim in docs/archive/STATE_2026-10-20_QT22.md).
- 2026-10-07: *"STANDING GO: For routine settings and thresholds, go with the recommended
  default and log it. Three things always need my own words: switching the bot on to trade,
  real money, and removing any safety fence."* · reports saved in the repo and pushed.
- Live anchors 2026-10-05: "One GO until the £100 cap". Recorder: 14 fixed hourly triggers.

## CARRIED
- GOOG/GOOGL and VUAG/VUSA each count as ONE bet when the bot trades (bet_groups.json v1).
  FX 0.15% per leg on non-sterling lines. MTLN.L (EUR) skipped: no EUR rate.
- Parked: v1 revive-or-retire (its daily task fails since 28 Jul). 5m known-null to re-prove.
- QT-23 stash "QT-23-interrupted" kept (superseded by B; never deleted).

## Open flags
- Thin London ETF quotes (SSLN.L, ACWI.L, SMEA.L). anchors.py 1,422 lines (pinned). 52 mypy
  errors silenced in 5 inherited modules; mypy's 4 known Qt-stub errors in manual/ui.

## Fingerprints
v1 4add56ec…743b6 (unchanged). Advisor daily (a) 0f3a960c…f1f9, (b) f7aae670…768e.
