# STATE.md — resume in seconds (current only; ≤6k chars, tested)

Updated: 2026-10-28 (evening). History → docs/archive/STATE_2026-10-28_QT27.md (verbatim). Box done:
QT-28 → docs/reports/QT-28.md (read its "For Tuesday" first).

Phase: v2 BUILDING. **S0–S5 DONE; S6 OPEN; S9 OPEN — the advisor is LIVE (armed 2026-10-20)**
(S3 close = QT-13 + QT-13b). No pick has survived (S6 0/30, S9 0/12, P19 0/18).
**Trial count N = 62** (QT-28 ran the six CM trials). Sender disarmed. No holdout ever opened.

## QT-28: S6 batch 2 run — 0 of 6 PASS
- Drills v2 registered first, alone (**787d4a27**): gates = the firewall's own verdicts; BELOW sized by
  a written rule (k = 0.9). Code **bdd31fca** (cm_drills only). Birth certificate **PROVEN**
  (docs/research/known_null_2026-10-28_QT28_cm.md): null and below-cost never PASS, planted edge PASS
  4/4, both red-firsts seen.
- The six as registered (6be96dad; trial code = ef4fcd0's): ridge ×3 INSUFFICIENT (10–18 trades in two
  years); gbt ×3 FAIL (−2.82% / −1.99% / −2.15% at 2× costs; VWRP +36.8% to +38.5%).
  docs/research/S6_batch2_results_2026-10.md. Nothing survives → G3 default (a) holds: the bot stays off.
- Cost wall (QT-27, description only): fill→E moves mostly below 2× costs; VWRL 2014–2025 made all its
  gain overnight (+797%), daytime −59%.

## The resource cap (operator's words below: a FENCE)
Every heavy run: `.venv-qb2/Scripts/python -m qb2.tools.capped -- <cmd>` (CPU 80%, 12 of 16
processors, 80% RAM, below-normal priority). `python -m qb2.tools.run_window` says whether a recorder
run is in the way; cm_run/cm_drills wait by themselves (s6_run, advisor_run, known_null do not yet).

## The advisor, live
- **ADV-0 = hold VWRL**, stop 15% below the highest close (10% when unsettled), raise-only; crossed =
  URGENT-EXIT alert, never a sale. **As-if BUY 21 Oct at £138.38. Wed 28 Oct £7,021.85 at 1x
  (£7,007.80 at 2x), stop raised to £118.23**, by hand (QT-28). S-07: +1.53% / +1.33% on 28 Oct.
- A session is final once London AND New York have closed: 20:00 UK this week, **21:00 UK from Mon
  2 Nov**. Daily door (QT-25/26): refuses unfinished rows, keeps a sane row a broken re-fetch would
  replace, names corrections (26 and 27 Oct: ^VIX fetched before Cboe's 16:15 close, e.g. 17.54 → 17.52).
- **Brake:** after an URGENT-EXIT his words also clear the advisor's 10% brake:
  `python -m qb2.tools.clear_pause --pot advisor --words "..."`.

## NEXT
1. **OPERATOR (away Thu 29 Oct → Mon 2 Nov, his words 2026-10-28): on Tuesday read QT-28's "For
   Tuesday", then answer G3 below.** Nothing needs him before then.
2. **Mentor writes QT-29:** G3 as he answers it; then QT-27 PROPOSE 2–6, deferred while he was away
   (^VIX fetched after 16:20 New York first; run_window for the older runners). No new trial unless
   registered first.
3. OPERATOR: keep the PC on or asleep (it wakes itself at 07:00) on weekdays.

## DECISION REQUESTED (open)
- **G3 — what the bot does next (none of the six survived).** Default (a): the bot stays off and its
  30% is not traded; the search reopens only with a genuinely new kind of information. GO words:
  (b) "GO on bot holds: once the always-on PC (S13) runs, the bot may hold overnight with its stop
  placed at Trading 212." (reopens P4) · (c) "GO on bot to index: until a bot strategy survives, the
  bot's 30% follows ADV-0 with the big-fall stop."
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
  ingest/daily.py, advisor/daily.py at 250; cm_drills.py 247. 52 mypy errors silenced in 5 inherited
  modules; 4 known Qt-stub errors.

## Fingerprints
v1 4add56ec…743b6. Advisor daily (a) 6883791f…97b1, (b) f7aae670…768e. Batch 2 trial data (a)
ad36150c…8781, (b) 14a454fb…90dc (QT-28 end checks).
