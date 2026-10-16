# Daily history top-up, 2026-10-16 (QT-19 Step 0.2)

Advisor list advisor-universe-v1 (171 names). Unsealed bars only (before the daily seal,
2025-10-10); the sealed year was rewritten only by the front door's own daily write
(qb2/ingest/daily.py, the same write the after-hours step makes every day) and was not read.

| | before (3-year fetch) | after (fetch from 2010-01-01) |
|---|---|---|
| first date: earliest | 2023-10-16 | 2010-01-04 |
| first date: median | 2023-10-16 | 2010-01-04 |
| first date: latest | 2025-08-04 | 2025-08-04 |
| last unsealed date | 2025-10-09 | 2025-10-09 |
| names with < 5 years | 171 | 8: APP, COIN, HOOD, HLN.L, ITH.L, MTLN.L, SEMI.L, FWRG.L |
| unsealed rows (all 221 daily names) | 108,840 | 772,603 |

**Reconciled:** every one of the 108,840 rows held before is still there with the same
close (0 differ by more than 1e-6; 0 dates lost). VALL.L (bot list) has no unsealed daily bar.

**Missing sessions (advisor):** 6,143 of 610,811 exchange sessions (1.0%), almost all of them rows the front door's OHLC check quarantined (7,365 unsealed rows, all names): thin London days whose close sits outside that day's
high-low range (a closing-auction print). Kept in data/clean/quarantine/daily/, excluded from the series, by the
existing rule. Names missing more than 5% of their sessions:

| name | first | rows | sessions | missing |
|---|---|---|---|---|
| FLRK.L | 2019-06-04 | 998 | 1606 | 608 (38%) |
| SMEA.L | 2010-01-04 | 2638 | 3984 | 1347 (34%) |
| ACWI.L | 2011-05-16 | 2486 | 3641 | 1155 (32%) |
| CCEP.L | 2019-03-28 | 1227 | 1650 | 423 (26%) |
| VHVG.L | 2019-09-24 | 1269 | 1527 | 258 (17%) |
| IITU.L | 2015-11-20 | 2127 | 2497 | 370 (15%) |
| VWRL.L | 2012-05-22 | 3048 | 3383 | 335 (10%) |
| VHYL.L | 2013-05-21 | 2857 | 3132 | 275 (9%) |
| VUKG.L | 2019-05-14 | 1495 | 1620 | 125 (8%) |
| BGEO.L | 2010-01-04 | 3706 | 3984 | 278 (7%) |
| EMIM.L | 2014-06-09 | 2668 | 2867 | 199 (7%) |
| SEMI.L | 2021-08-05 | 996 | 1055 | 59 (6%) |
| GAW.L | 2010-01-04 | 3784 | 3984 | 201 (5%) |

Census per name: rows, expected sessions (XNYS/XLON calendars), missing, quarantined, overlap
checks — rebuilt by the QT-19 census script; the old 3-year files are kept at data/qb2/daily_before_QT19/.
