# QB2 recorder status

- Updated at: 2026-11-20 20:50 (UK)
- Last recorder run: started 20:00, finished 20:41, exit 0
- Runs today (UK): 08:55, 10:00, 11:00, 12:00, 13:00, 14:00, 15:00, 16:00, 17:00, 18:00, 19:00, 20:00 -- 08:55 was the catch-up after switch-on (expected)
- Missed runs today: 07:00, 09:00 (PC off or asleep?)
- Status pushes today: 11
- Clean store: fresh to 2026-11-20 · 5m census 98.2% · OK
- Daily store: fresh to 2026-11-19 · OK · 2 names short of a session (named, retried, not holding the stops back): CSH2.L 2026-10-26, SMEA.L 2023-11-27 (accepted) · retried 2 names in 2.9s · 122 rows refused, their session not closed when fetched (fetched again once it has): AZN.L 2026-11-20, SHEL.L 2026-11-20, HSBA.L 2026-11-20, RR.L 2026-11-20, BP.L 2026-11-20, GLEN.L 2026-11-20 · 1 stored row kept, its re-fetch came back broken (set aside): GBPUSD=X 2026-11-09 · 2 closes corrected by the provider (the newer one kept): SNDK 2026-11-17 797.24 → 99.65, SNDK 2026-11-18 776.22 → 97.03
- Earnings: fresh to 2026-11-19 · coverage 96.5% · OK · no date for BAB.L, FCIT.L, HLMA.L, INVP.L, PCT.L, SGE.L
- T212 London freshness: 734 counted / 13 sessions · median 0 min (1546 not counted; target 20 over 3: MET)
- Cross-check (shadow): warn 134 · block 1 · stop 60 · no comparison 231 (of 6310 name checks in 251 market sweeps)
- Target: 20 counted samples per market over 3 full sessions. Counted = clock-checked, inside a full session, each bar once (qb2/tools/delay_count.py).

## London

- Counted today: 8 · since 2026-10-05: 134 of 20
- Per session: 2026-10-05: 2 · 2026-10-06: 1 · 2026-10-07: 1 · 2026-10-08: 10 · 2026-10-09: 8 · 2026-10-16: 8 · 2026-10-26: 8 · 2026-10-27: 8 · 2026-10-28: 8 · 2026-10-29: 8 · 2026-10-30: 8 · 2026-11-09: 8 · 2026-11-10: 8 · 2026-11-11: 8 · 2026-11-12: 8 · 2026-11-13: 8 · 2026-11-16: 8 · 2026-11-17: 8 · 2026-11-20: 8
- Meter: RED -- too few clock-checked samples on 2026-11-19 (0 of 3), 2026-11-18 (0 of 3) -- the sampler did not run for most of the session (PC off or asleep?)
- Expected by now today: 8 (09:00-16:00 runs)
- Missed hours today: 09:00
- Delay median: 17.0 min

## US

- Counted today: 6 · since 2026-10-05: 158 of 20
- Per session: 2026-10-05: 5 · 2026-10-06: 3 · 2026-10-07: 8 · 2026-10-08: 6 · 2026-10-09: 7 · 2026-10-12: 4 · 2026-10-13: 3 · 2026-10-14: 3 · 2026-10-15: 2 · 2026-10-16: 6 · 2026-10-19: 3 · 2026-10-20: 3 · 2026-10-21: 3 · 2026-10-22: 3 · 2026-10-23: 3 · 2026-10-26: 6 · 2026-10-27: 6 · 2026-10-28: 6 · 2026-10-29: 6 · 2026-10-30: 6 · 2026-11-02: 3 · 2026-11-03: 3 · 2026-11-04: 3 · 2026-11-05: 3 · 2026-11-06: 2 · 2026-11-09: 6 · 2026-11-10: 6 · 2026-11-11: 6 · 2026-11-12: 6 · 2026-11-13: 6 · 2026-11-16: 6 · 2026-11-17: 6 · 2026-11-18: 3 · 2026-11-19: 1 · 2026-11-20: 6
- Meter: RED -- too few clock-checked samples on 2026-11-19 (1 of 3) -- the sampler did not run for most of the session (PC off or asleep?)
- Expected by now today: 6 (15:00-20:00 runs)
- Missed hours today: none
- Delay median: 1.1 min
