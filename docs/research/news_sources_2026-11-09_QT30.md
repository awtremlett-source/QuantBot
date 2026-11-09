# News data for the universe names: what exists (QT-30 D, 2026-11-09)

Research note, read-only survey. **No trial, no model.** Nothing scores, trades or advises on this
data, and the draft at the end is not registered and has not been run. N stays 62.

## Verdict in plain words

- **US names: a fair back-test is possible.** The SEC publishes every company filing free, with the
  moment it accepted each one, to the second, and years of history.
- **UK names: no.** There is no free feed we may use. The official one costs £6,500 a year. UK
  company news would have to come from a paid feed, or wait until a permitted free source is found.
- **"News" here means company filings** (the SEC's form 8-K: results, deals, management changes). It
  does not mean press articles. No free source of timestamped articles was found that we may store.

## Sources checked (9 Nov 2026)

| source | covers | how far back | timestamps | terms | cost | usable? |
|---|---|---|---|---|---|---|
| SEC EDGAR submissions | US filings (8-K) | years (Apple: 1,006 recent filings, plus 1 older file) | `acceptanceDateTime`, to the second | "Anyone can access and download this information for free"; at most 10 requests a second | free | **yes, recording built** |
| LSEG RNS Data Feed | UK announcements (RNS) | licensed | exact | licence holders only | £6,500 a year | not free |
| Investegate | UK announcements | site archive | shown on each page | one copy "for your personal reference"; no reproducing third-party content without written consent; automated access not mentioned | free to read | **not for a stored dataset** |
| FCA National Storage Mechanism | UK regulated announcements | archive | not established | the website terms found allow "any lawful purpose", but that page looks early, and no API terms were found | free | **not established**: its data service is undocumented; my one test of it was refused (HTTP 400) |
| CNBC, Yahoo news | articles | short | loose | not checked: article text is not ours to store | free | no |

Figures from: sec.gov "Accessing EDGAR Data"; lseg.com RNS pricing and policy guidelines 2026;
investegate.co.uk/terms-of-use, clauses 3.3, 3.4, 4.2 and 4.3; a live read of Apple's submissions file.

## What can be tested honestly

- **Timestamps.** The SEC's acceptance time is the moment a filing became public on EDGAR, so a
  back-test can act only on filings it could have seen. One check is owed first: the field ends in
  `Z`, meaning UTC. Apple's 2 Nov filing reads 21:30:23Z, which is 16:30 New York and looks right, but
  **one filing must be compared with its own EDGAR index page before any back-test** relies on it.
- **A filing is not its effect.** Companies often file after the market closes, and the first possible
  trade is the next open. The bot is flat overnight (P4), so it could only act on filings that land
  during the session.
- **UK names cannot be tested from free data.** That is 100 of the 198 stock lines across the bot and
  advisor lists (bot 10 of 40, advisor 90 of 158, before overlaps), so any result would cover US
  names only.

## What was built (D2)

`qb2/ingest/news_record.py`, riding the existing recorder (no new scheduled task): once a UK day, the
8-K filings of the universe's US shares, saved append-only to `data/raw/news/sec_8k.jsonl`. It reads
at 4 requests a second, inside the SEC's limit of 10. Nothing reads the file yet.

The SEC asks automated clients to declare a name and contact address. The recorder sends a plain name
and **no contact address**, because giving one is the operator's decision (see QT-30's DECISION
REQUESTED). It was accepted without one on 9 Nov; the SEC may limit that at any time.

## PROPOSE: the first news trial, a DRAFT (not registered, not run; he decides later)

- **Question.** Does a company's own 8-K tell us to avoid or leave a holding, after costs?
- **Signal.** A new 8-K carrying item 2.02 (results), 1.01, 1.02, 2.01, 2.05, 2.06, 4.01, 4.02, 5.02
  or 8.01. Direction cannot be read from the item number alone, so the first test is **avoid only**:
  do not open a new position in that name for N sessions after the filing.
- **Long-only.** It never shorts. It can only keep the bot or advisor out of a name, or exit early.
- **Holding time.** Two variants at most, 1 and 5 sessions, fixed before running: each counts towards N.
- **Timing.** Acts at the first open after the acceptance time, plus the delay we would really see.
- **Costs.** costs.py, at 1× and 2×, net result vs the same book without the filter and vs D3.
- **Data needed.** History is available from the SEC now, so a back-test needs no waiting. Recording
  forward gives the check on real fetch times: **at least 8 weeks** before trusting those.
- **Gates.** The firewall's own: the luck test, Deflated Sharpe over the full count N, 2× costs,
  worst fold, the holdout spent once and only on his words.
- **Before it is registered:** the timestamp check above, a list of names with a known SEC id, and
  his GO.
