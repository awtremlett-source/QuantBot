# QB2 recorder status

- Updated at: 2026-11-06 21:50 (UK)
- Last recorder run: started 20:00, finished 20:08, exit 0
- Runs today (UK): 18:36, 20:00 -- 18:36 was the catch-up after switch-on (expected)
- Missed runs today: 07:00, 08:00, 09:00, 10:00, 11:00, 12:00, 13:00, 14:00, 15:00, 16:00, 17:00, 19:00 (PC off or asleep?)
- Status pushes today: 3
- Clean store: fresh to 2026-11-05 · 5m census 98.2% · OK
- Daily store: fresh to 2026-11-05 · OK · 98 rows refused, their session not closed when fetched (fetched again once it has): MU 2026-11-06, NVDA 2026-11-06, SNDK 2026-11-06, AAPL 2026-11-06, TSLA 2026-11-06, AMD 2026-11-06
- Earnings: fresh to 2026-11-05 · coverage 98.5% · RED (2026-11-06 has finished) · no date for FCIT.L, PCT.L, SMT.L
- T212 London freshness: 327 counted / 6 sessions · median 0 min (713 not counted; target 20 over 3: MET)
- Cross-check (shadow): warn 63 · block 0 · stop 0 · no comparison 111 (of 3350 name checks in 129 market sweeps)
- Target: 20 counted samples per market over 3 full sessions. Counted = clock-checked, inside a full session, each bar once (qb2/tools/delay_count.py).

## London

- Counted today: 0 · since 2026-10-05: 70 of 20
- Per session: 2026-10-05: 2 · 2026-10-06: 1 · 2026-10-07: 1 · 2026-10-08: 10 · 2026-10-09: 8 · 2026-10-16: 8 · 2026-10-26: 8 · 2026-10-27: 8 · 2026-10-28: 8 · 2026-10-29: 8 · 2026-10-30: 8
- Meter: RED -- too few clock-checked samples on 2026-11-05 (0 of 3), 2026-11-04 (0 of 3), 2026-11-03 (0 of 3) -- the sampler did not run for most of the session (PC off or asleep?)
- Expected by now today: 8 (09:00-16:00 runs)
- Missed hours today: 09:00, 10:00, 11:00, 12:00, 13:00, 14:00, 15:00, 16:00
- Delay median: 16.9 min

## US

- Counted today: 2 · since 2026-10-05: 106 of 20
- Per session: 2026-10-05: 5 · 2026-10-06: 3 · 2026-10-07: 8 · 2026-10-08: 6 · 2026-10-09: 7 · 2026-10-12: 4 · 2026-10-13: 3 · 2026-10-14: 3 · 2026-10-15: 2 · 2026-10-16: 6 · 2026-10-19: 3 · 2026-10-20: 3 · 2026-10-21: 3 · 2026-10-22: 3 · 2026-10-23: 3 · 2026-10-26: 6 · 2026-10-27: 6 · 2026-10-28: 6 · 2026-10-29: 6 · 2026-10-30: 6 · 2026-11-02: 3 · 2026-11-03: 3 · 2026-11-04: 3 · 2026-11-05: 3 · 2026-11-06: 2
- Meter: OK -- every full session in the last 3 day(s) has at least 3 samples
- Expected by now today: 6 (15:00-20:00 runs)
- Missed hours today: 15:00, 16:00, 17:00, 19:00
- Delay median: 1.1 min
