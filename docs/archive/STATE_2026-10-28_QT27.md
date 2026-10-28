# STATE.md — resume in seconds (current only; ≤6k chars, tested)

Updated: 2026-10-28. History → docs/archive/STATE_2026-10-28_QT26.md (verbatim). Box done:
QT-27 → docs/reports/QT-27.md.

Phase: v2 BUILDING. **S0–S5 DONE; S6 OPEN; S9 OPEN — the advisor is LIVE (armed 2026-10-20)**
(S3 close = QT-13 + QT-13b). No pick has survived (S6 0/24, S9 0/12, P19 0/18).
**Trial count N = 56** (QT-27 ran no counted trial). Sender disarmed. No holdout ever opened.

## QT-27: S6 batch 2, the combined model — registered and built, NOT run
- Register **6be96dad** (alone, before code): CM-L/CM-G (ridge / gradient-boosted trees) × US/LON/MIX
  = 6 trials, + drills KN-CM-NULL/EDGE/BELOW. Code **ef4fcd0** (qb2/model/, research/cm_*.py).
- Known-null on LON: EDGE PASSED 4/4; NULL and BELOW rejected 8/8 by the firewall's own verdicts, but
  RED by the stricter gate words registered that morning → **STOP rule: the 6 trials were not run.**
  Red-firsts: the leaked fold boundary showed RED (gbt); costs off did NOT show. Details:
  docs/research/known_null_2026-10-28_QT27_cm.md. No defect in bench or code: the drills' gate words
  and the below-cost drill's size failed.
- Cost wall (docs/research/cost_wall_2026-10-28.md, description only): fill→E moves are mostly smaller
  than 2× costs; VWRL 2014–2025 made all its gain overnight (+797%), daytime −59%.
- London's 08:00 hourly bar has zero volume every winter (Yahoo): F7 missing on 29% of London rows.

## The resource cap (operator's words below: a FENCE)
Every heavy run: `.venv-qb2/Scripts/python -m qb2.tools.capped -- <cmd>` (CPU 80%, 12 of 16
processors, 80% RAM, below-normal priority). QT-27: `python -m qb2.tools.run_window` says whether a
recorder run is in the way (hh:57 → "finished"); cm_run/cm_drills wait by themselves.

## The advisor, live
- **ADV-0 = hold VWRL**, stop 15% below the highest close (10% when unsettled), raise-only; crossed =
  URGENT-EXIT alert, never a sale. **As-if BUY 21 Oct at £138.38. Tue 27 Oct £7,009.23 at 1x
  (£6,995.20 at 2x), stop raised to £118.01**, by hand (QT-27). S-07: +1.35% / +1.14% on 27 Oct.
- A session is final once London AND New York have closed: 20:00 UK this week, **21:00 UK from Mon
  2 Nov**. Daily door (QT-25/26): refuses unfinished rows, keeps a sane row a broken re-fetch would
  replace, names corrections (27 Oct: ^VIX 26 Oct 18.43 → 18.39, fetched before Cboe's 16:15 close).
- **Brake:** after an URGENT-EXIT his words also clear the advisor's 10% brake:
  `python -m qb2.tools.clear_pause --pot advisor --words "..."`.

## NEXT
1. **Mentor writes QT-28:** re-register the drills (v2) with gates = the firewall's own verdicts
   (Gate 1 = luck AND a positive net mean; rejected = not PASS) BEFORE running; re-run the known-null
   and red-firsts; then the 6 CM trials exactly as registered (N → 62). PROPOSE list: QT-27 report.
2. OPERATOR: keep the PC on or asleep (it wakes itself at 07:00) on weekdays.

## DECISION REQUESTED (open)
- **What the bot does next (G3)** — waits for the 6 trials; default (a) holds now: the bot stays off.
- **D1 advisor risk rule.** Default: the 1% rule stays. GO words: "GO on D1: for the advisor,
  replace the 1% rule with a cap on how much the account can lose if the stop is hit, figure chosen
  by S5's crash tests."
- **Bot's brake.** Default: as built. GO words: "GO on the bot's brake: the 10% brake clears itself
  after 5 sessions and restarts from there; the 15% pause stays measured from the true peak and only
  my words clear it."
- v1's QuantBot-Daily/-Monthly run outside the cap (frozen). Default: leave, report.

## Standing GOs (operator words, verbatim)
- 2026-10-23: *"Keep ADV-0's stop as the default for now; S-07 stays a shadow."* · *"GO on the
  advisor's 10% brake: after an urgent exit, my own words also clear the advisor's 10% brake and
  restart its peak from that day."*
- 2026-10-20, a FENCE: *"I stopped QT23 halfway through, there needs to be a limit on the amount of
  memory and CPU it takes up. like 80% limit for each. otherwise the PC cannot take it and will
  crash."*
- 2026-10-19: *"GO on QT-23: build the advisor with "hold the index fund" as its default, the 15%
  big-fall stop (10% when markets are jumpy) as its live stop, and the rules scored in the background
  on live prices only."*
- 2026-10-16: P15 history (verbatim in docs/archive/STATE_2026-10-20_QT22.md).
- 2026-10-07: *"STANDING GO: For routine settings and thresholds, go with the recommended default and
  log it. Three things always need my own words: switching the bot on to trade, real money, and
  removing any safety fence."*
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
v1 4add56ec…743b6. Advisor daily (a) 6883791f…97b1, (b) f7aae670…768e (QT-27 end checks).
