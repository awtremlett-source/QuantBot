# STATE.md — resume in seconds (current only; ≤6k chars, tested)

Updated: 2026-10-23. History → docs/archive/STATE_2026-10-23_QT23.md (verbatim). Box done:
QT-24 → docs/reports/QT-24.md.

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
- **First fill: as-if BUY at Wed 21 Oct's open £138.38**, written by Thu 22 Oct's 18:14 UK run.
  Stop £117.91. Day 1: £7,003.17 at 1x, £6,989.16 at 2x (reconciled to the penny by hand).
- **Timing:** a session is final once London AND New York have closed (21:00 UK); its figures
  (fills, stop checks) arrive with the NEXT morning's first run. The price door STOPs if the store
  claims a session London has not closed by the run's clock (QT-24 A).
- **^VIX** rides the daily top-up (New York clock); the "Daily store" line is RED if ^VIX trails
  VWRL by more than one London session. Caught up to 22 Oct (19.03). The 21 Oct day line keeps its
  recorded 15.88 (a pre-open snapshot; the real 20 Oct close was 17.31: settled either way).
- **Brake:** after an URGENT-EXIT his words also clear the advisor's 10% brake (GO below):
  `python -m qb2.tools.clear_pause --pot advisor --words "..."`.
- **Shadows:** S-01..S-06 from 20 Oct; **S-07** (trend filter, registered cd3e863) from 23 Oct,
  its own day 0 — first decision Fri 23 Oct's close → as-if BUY at Mon 26 Oct's open.
- **Described 2014–2025, 2× costs:** ADV-0 +173.3% (worst fall −25.5%); S-07 +145.0% (−18.6%, out
  9 times); plain VWRL +268.7% (−24.9%). 2020: +12.1 / +7.0 / +10.8%. 2022: −16.1 / −9.0 / −7.0%.
- Files: data/qb2/advisor/, stops.jsonl, brakes.jsonl; page `status/advisor.md` (status branch).

## NEXT
1. **Mentor writes the next box.** Check first: the 07:00 UK run of Fri 23 Oct processed 22 Oct
   with VIX 16.68 (stop stays £117.91), did Friday's review (HOLD), and S-07's first decision.
2. The DECISION below (ADV-0's stop, S-07's figures beside it).
3. PROPOSE: the daily front door drops a row whose session had not closed when fetched (the
   cause of the 16 Oct pre-open ^VIX row; a lost name can otherwise keep one).
4. PROPOSE: MANUAL's re-justify can open lower (R4); per-ticker scale check vs T212 (SCARS #3).
5. OPERATOR: keep the PC on or asleep (it wakes itself at 07:00) on weekdays — both mornings this
   week were missed, so each session's figures came a day late.

## DECISION REQUESTED (open)
- **ADV-0's stop.** Default: kept (his GO; P10). GO words: "GO on ADV-0: hold VWRL with no big-fall
  stop and no re-buy; the shadows keep theirs." S-07 cannot replace it except by the promotion rule.
- **D1 advisor risk rule.** Default: the 1% rule stays the ceiling. GO words: "GO on D1: for
  the advisor, replace the 1% rule with a cap on how much the account can lose if the stop is
  hit, figure chosen by S5's crash tests."
- **Bot's brake.** Default: as built. GO words: "GO on the bot's brake: the 10% brake clears
  itself after 5 sessions and restarts from there; the 15% pause stays measured from the true
  peak and only my words clear it."
- v1's QuantBot-Daily/-Monthly tasks run outside the cap (frozen; daily failing since 28 Jul).
  Default: leave, report. Backups on the university OneDrive? Default: keep.

## Standing GOs (operator words, verbatim)
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
- Thin London ETF quotes (SSLN.L, ACWI.L, SMEA.L). anchors.py 1,422 lines (pinned). 52 mypy
  errors silenced in 5 inherited modules; mypy's 4 known Qt-stub errors in manual/ui.

## Fingerprints
v1 4add56ec…743b6 (unchanged). Advisor daily (a) 0f3a960c…f1f9, (b) f7aae670…768e (unchanged by
the ^VIX catch-up).
