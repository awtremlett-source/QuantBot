# QT-18 progress — resume from the last step marked done

Operator, 2026-10-16 08:07 (verbatim): *"I'm away while QT-18 runs. Don't ask me anything
else. For any choice, take your recommended option, log it in STATE and the report as
"decided while operator away", and carry on. Only the box's own STOP rules may stop the run
(a wrong known-null verdict, a DEFECT, A2 below its thresholds). If one fires, write the
report, push it, and end. Nothing that switches the bot on, uses real money or removes a
safety fence. If something would need one of those, stop and report."*

Resume: `git pull`, read this file, carry on from the last step marked **done**. Never redo
a finished step; never re-run a finished trial (docs/research/S6_batch1_runs/).

| step | status | commit | time (UK) | note |
|---|---|---|---|---|
| 0 ground truth | done | ba620a6 (base) | 08:08–08:12 | qb2 636 (1 desel.) · v1 440 · plan+wall 239 · ruff clean · mypy the 4 known · v1 4add56ec…743b6 · qb2 7474466a…8fdafe · disk 3.6 GB · N = 18 |
| A1 history rule | done | QT-18A | 08:12–08:24 | p15_history.py + p15.py wired; 14 tests + 3 wall tests; 12 mutants + 3 planted imports all RED |
| A2 arms tradeable | done | QT-18A | 08:24–08:29 | US 95.1% / holdout 95.3% · London shares 47.8% (stale five blocked) · ETFs 100% · Mix 86.0% — no STOP |
| A3 known-null 1h | done | QT-18A | 08:30–09:40 | honest Gate 1 GREEN · Gate 2 GREEN; red-first: delay removed → KN-INSTANT-1h PASS, costs off → KN-PLANT-SMALL-1h PASS (+343% vs VWRP +50.7%) — both RED as required |
| B1 register | done | QT-18 register | 09:45 | 24 entries S6-01-US … S6-08-MIX; clarifications in each entry (decided while operator away) |
| B1 rule code | done | QT-18 rule code | 10:20 | s6_rules.py (8 rules), s6_run.py (resumable runner), s6_results.py, data_fingerprint.py; 16 rule/fingerprint + 6 runner mutants all RED |
| B2 trials | running |  | 10:02– | 8 of 24 finished (FAIL 8) |
| B3 holdout | pending | | | |
| B4–B5 results, end | pending | | | |

Run 1 started 2026-10-16 09:02:27 UTC (10:02 UK), code commit 343cff3 (s6_run's code paths),
18 selection trials counted before. Data fingerprints taken at the start of B:
- (a) trial data: `bf58b2595eb5c62aa36738b6cfacb8e819bfbcad999fc121934eb80499c8b959`
- (b) holdout data: `b49e7dcb5b67765222e90017bc9ec136490d47c29d635c51b48ec163351cac87`

Resume B: `python -m qb2.research.s6_run --max 4` (it re-checks the commit and both
fingerprints first, skips finished trials, re-runs an interrupted one from scratch).
