# P15 history: how much each arm may trade (QT-18 A2)

A BUY counts as allowed on a name-session when p15.py's mask allows it at EVERY hourly decision of that session (history rule, missing-quarter spans). Holdout counted from the exchange calendar and earnings rows only -- no sealed bar read. Skipped (no unsealed 1h bars): ['VALL.L: no unsealed 1h bars'].

| arm | unsealed | holdout 2026-07-13 → 2026-10-09 |
|---|---|---|
| US | 95.1% | 95.3% |
| London shares | 47.8% | 47.7% |
| London ETFs | 100.0% | 100.0% |
| Mix | 86.0% | 86.7% |

| name | sleeve | unsealed allowed | holdout allowed | missing-quarter gaps |
|---|---|---|---|---|
| MU | us_liquid | 641/674 (95%) | 61/64 (95%) | — |
| NVDA | us_liquid | 641/674 (95%) | 61/64 (95%) | — |
| SNDK | us_liquid | 281/346 (81%) | 61/64 (95%) | — |
| AAPL | us_liquid | 641/674 (95%) | 61/64 (95%) | — |
| TSLA | us_liquid | 644/674 (96%) | 61/64 (95%) | — |
| AMD | us_liquid | 642/674 (95%) | 61/64 (95%) | — |
| MSFT | us_liquid | 644/674 (96%) | 61/64 (95%) | — |
| META | us_liquid | 644/674 (96%) | 61/64 (95%) | — |
| INTC | us_liquid | 644/674 (96%) | 61/64 (95%) | — |
| GOOGL | us_liquid | 644/674 (96%) | 61/64 (95%) | — |
| AMZN | us_liquid | 644/674 (96%) | 61/64 (95%) | — |
| AVGO | us_liquid | 641/674 (95%) | 61/64 (95%) | — |
| GOOG | us_liquid | 641/671 (96%) | 61/64 (95%) | — |
| PLTR | us_liquid | 640/671 (95%) | 61/64 (95%) | — |
| MRVL | us_liquid | 638/671 (95%) | 61/64 (95%) | 2015-05-21→2015-12-07 (blocked 2015-08-20→2015-12-08); 2015-12-07→2016-07-19 (blocked 2016-03-07→2016-07-20) |
| ORCL | us_liquid | 638/671 (95%) | 61/64 (95%) | — |
| STX | us_liquid | 635/665 (95%) | 61/64 (95%) | — |
| LITE | us_liquid | 638/671 (95%) | 61/64 (95%) | — |
| AMAT | us_liquid | 638/671 (95%) | 61/64 (95%) | — |
| BE | us_liquid | 638/671 (95%) | 61/64 (95%) | — |
| WDC | us_liquid | 641/671 (96%) | 61/64 (95%) | — |
| DELL | us_liquid | 638/671 (95%) | 61/64 (95%) | — |
| LLY | us_liquid | 641/674 (95%) | 61/64 (95%) | — |
| LRCX | us_liquid | 641/671 (96%) | 61/64 (95%) | — |
| NFLX | us_liquid | 644/674 (96%) | 61/64 (95%) | — |
| WMT | us_liquid | 641/674 (95%) | 61/64 (95%) | — |
| CRM | us_liquid | 641/674 (95%) | 61/64 (95%) | — |
| JPM | us_liquid | 644/674 (96%) | 61/64 (95%) | — |
| V | us_liquid | 644/674 (96%) | 61/64 (95%) | — |
| GEV | us_liquid | 414/435 (95%) | 61/64 (95%) | — |
| ISF.L | uk_etf | 674/674 (100%) | 64/64 (100%) | — |
| VWRP.L | uk_etf | 671/671 (100%) | 64/64 (100%) | — |
| VALL.L | uk_etf | — | 64/64 (100%) | — |
| VUAG.L | uk_etf | 671/671 (100%) | 64/64 (100%) | — |
| VUSA.L | uk_etf | 674/674 (100%) | 64/64 (100%) | — |
| SGLN.L | uk_etf | 674/674 (100%) | 64/64 (100%) | — |
| SMGB.L | uk_etf | 671/671 (100%) | 64/64 (100%) | — |
| CSH2.L | uk_etf | 333/333 (100%) | 64/64 (100%) | — |
| VUKE.L | uk_etf | 672/672 (100%) | 64/64 (100%) | — |
| EQQQ.L | uk_etf | 674/674 (100%) | 64/64 (100%) | — |
| AZN.L | uk_share | 642/674 (95%) | 61/64 (95%) | — |
| SHEL.L | uk_share | 644/674 (96%) | 61/64 (95%) | — |
| HSBA.L | uk_share | 644/674 (96%) | 61/64 (95%) | — |
| RR.L | uk_share | 0/671 (0%) | 0/64 (0%) | 2016-07-28→2027-02-25 (blocked 2017-01-26→2027-02-26) |
| BP.L | uk_share | 644/674 (96%) | 61/64 (95%) | — |
| GLEN.L | uk_share | 0/674 (0%) | 0/64 (0%) | 2012-03-05→2027-02-17 (blocked 2012-09-03→2027-02-18) |
| BARC.L | uk_share | 644/674 (96%) | 61/64 (95%) | — |
| RIO.L | uk_share | 0/674 (0%) | 0/64 (0%) | 2009-08-20→2012-03-05 (blocked 2010-02-18→2012-03-06); 2012-03-05→2015-08-06 (blocked 2012-09-03→2015-08-07); 2016-03-03→2027-02-18 (blocked 2016-09-01→2027-02-19) |
| AAL.L | uk_share | 0/674 (0%) | 0/64 (0%) | 2010-03-01→2027-02-19 (blocked 2010-08-30→2027-02-22) |
| ULVR.L | uk_share | 0/674 (0%) | 0/64 (0%) | 2004-07-28→2005-05-06 (blocked 2004-10-27→2005-05-10); 2010-02-04→2010-08-05 (blocked 2010-05-06→2010-08-06); 2012-02-02→2012-07-26 (blocked 2012-05-03→2012-07-27); 2012-10-25→2013-04-25 (blocked 2013-01-24→2013-04-26); 2013-04-25→2014-01-21 (blocked 2013-07-25→2014-01-22); 2014-01-21→2015-04-16 (blocked 2014-04-22→2015-04-17); 2015-07-23→2017-01-26 (blocked 2015-10-22→2017-01-27); 2017-01-26→2027-02-09 (blocked 2017-04-27→2027-02-10) |

**No STOP:** the US arm is at or above 80% in both periods, and no share outside the stale five (RR.L, GLEN.L, RIO.L, AAL.L, ULVR.L) is blocked on more than half its sessions.
