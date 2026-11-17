# News trial — pre-registration DRAFT (QT-35 B3, 2026-11-17)

**Status: DRAFT. NOT registered, NOT run. The trial count N stays 62.** It becomes a registration only on the
operator's GO words (below); until then nothing is fetched for history and nothing is back-tested.
Source: docs/research/news_sources_2026-11-09_QT30.md (its PROPOSE section), turned into fixed terms.

## Plain words

When a US company files an "8-K" (a form it must send to the US regulator, the SEC, when something important
happens, such as results or a boss leaving), does it pay to **stay out of that share for a few days**? The
trial only ever avoids or leaves a share. It never shorts (bets on a fall).

## What is already checked (QT-35)

- **The time stamp is honest (B1).** VRT's 8-K 0001628280-26-073564 is stored as accepted
  2026-11-13T11:35:50Z; its EDGAR index page reads "Accepted 2026-11-13 06:35:50", New York time (EST, UTC−5):
  the same moment. The stored field is UTC.
- **Every name has its SEC id (B2).** data/ref/sec_cik.json: 98 US share lines (bot 30, advisor 68, none in
  both lists), from the SEC's company_tickers.json read 2026-11-17 06:36 UTC (sha256 29e8eee5a85a…); none
  missing. London names have no free source and are out of scope (100 of 198 stock lines).

## Fixed terms (frozen at registration; any change = a new variant counted in N)

| term | value |
| --- | --- |
| Question | Does avoiding a share after its own 8-K improve the book, after costs? |
| Names | the 98 in data/ref/sec_cik.json, as fixed on the registration date |
| Signal | a new 8-K whose items include any of 2.02, 1.01, 1.02, 2.01, 2.05, 2.06, 4.01, 4.02, 5.02, 8.01 |
| Action | avoid only: no new position in that name for H sessions; an open position is left at the next open |
| Variants | exactly 2: H = 1 and H = 5 sessions. N rises by 2 at registration |
| Timing | acts at the first open after the acceptance time (UTC), plus the delay we would really see (#16, #17) |
| Costs | qb2/execution/costs.py at 1× and 2×; gross AND net |
| Compared with | the same book without the filter, and D3 (do-nothing index fund) |
| History | SEC submissions history for the 98 names, ≤10 requests a second; read as-of acceptance time |
| Gates | the firewall's own: luck test, Deflated Sharpe over the full N, 2× costs, worst fold; holdout spent once, only on his words |
| Forward check | the daily recorder's own fetch times, at least 8 weeks, before trusting live timing |
| Stops | the trial stops on CORRECT or EXHAUSTED, never on PROFIT (#21) |

## Known limits (said before any result)

- US names only; a result says nothing about London.
- The item number does not say good or bad news, so "avoid" may also skip good moves.
- The bot is flat overnight (P4): filings after the close act only at the next open.

## DECISION REQUESTED

- **Register and run the news trial.** Default: not registered, nothing run. GO words: *"GO on the news trial:
  register the 8-K avoid-only trial in docs/research/news_trial_prereg_DRAFT.md with its two variants (N
  rises by 2), pull the SEC history for its 98 names and back-test it through the firewall; the holdout
  stays closed until my words."*
