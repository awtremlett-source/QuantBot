# Why the luck bar was too wide on the advisor's book — QT-20 Part A (2026-10-16)

**Description only.** Nothing was logged, nothing was written to the store, no drill and no
trial was run, the sealed year was not read. Trial count N stays 42. Evidence:
coin_spread_2026-10-16_QT20.json (every book measured). Scripts:
docs/reports/QT-20_partA_scripts.py.txt.

## Set-up

- **Data** exactly as the trials read it (advisor_data.load: 170 names, each from 253 of its
  own bars before 2014-04, dividends credited). Slot weights from KN-A-RANDOM-1d's book on
  the real bars. Graded 2014-03-31 → 2025-10-09: T = 5,815 bars (London and New York bars
  interleaved).
- **Coin books** = the QT-19 Deflated Sharpe input, unchanged: `firewall._coin` through
  `firewall.portfolio`, seeds `monte_carlo.trial_seeds(0, 200)`, at 1× and 2× costs.
- **Random-rank books** = the box's fix (i), as a description only: `advisor_book.build` on
  KN-A-RANDOM-1d's settings with a uniform rank per (seed, bet, month), 100 seeds.
- **raw** = the store as it is. **patched** = the same, with four broken stretches cut IN
  MEMORY only (census below): SMEA.L from 2023-11-27, FWRG.L before 2023-07-11, EDV.L before
  2021-06-14, IITU.L before 2015-11-24.
- **Analytic** = Bailey & López de Prado's noise of ONE book's per-bar Sharpe from its own
  moments, √((1 − skew·SR + (kurt − 1)/4·SR²)/(T − 1)), on 10 coin books.

## A1 — the books, measured

| data | books | cost | n | Sharpe/bar mean | **spread (sd)** | SR0 at N=48 | turnover/yr (× pot) | names held | exposure (× pot) | cost drag/yr (sd) | beta to D3 (sd) | kurtosis (median) | top bar's share of variance (median) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| raw | coin flip (QT-19 input) | 1× | 200 | -0.117 | **0.0723** | 0.163 | 322.4 | 77.6 | 2.56 | 182.1% (0.28%) | 1.86 (0.050) | 4,740 | 90% |
| raw | coin flip (QT-19 input) | 2× | 200 | -0.271 | **0.1534** | 0.347 | 322.4 | 77.6 | 2.56 | 361.8% (0.57%) | 1.85 (0.050) | 4,706 | 90% |
| raw | random-rank book (fix (i)) | 1× | 100 | +0.016 | **0.0052** | 0.012 | 10.0 | 24.4 | 0.80 | 6.4% (0.04%) | 0.54 (0.009) | 10 | 2% |
| raw | random-rank book (fix (i)) | 2× | 100 | -0.008 | **0.0052** | 0.012 | 10.0 | 24.4 | 0.80 | 12.1% (0.09%) | 0.53 (0.010) | 10 | 1% |
| patched | coin flip (QT-19 input) | 1× | 200 | -0.190 | **0.0028** | 0.006 | 323.2 | 77.3 | 2.56 | 182.5% (0.28%) | 1.91 (0.018) | 13 | 2% |
| patched | coin flip (QT-19 input) | 2× | 200 | -0.427 | **0.0039** | 0.009 | 323.2 | 77.3 | 2.56 | 362.6% (0.57%) | 1.90 (0.019) | 13 | 2% |
| patched | random-rank book (fix (i)) | 1× | 100 | +0.017 | **0.0052** | 0.012 | 10.0 | 24.3 | 0.80 | 6.4% (0.04%) | 0.54 (0.010) | 10 | 2% |
| patched | random-rank book (fix (i)) | 2× | 100 | -0.008 | **0.0052** | 0.012 | 10.0 | 24.3 | 0.80 | 12.1% (0.09%) | 0.53 (0.010) | 10 | 2% |

Turnover = share of the pot bought per year. Exposure = pot held, × pot (a coin holds about
half the names at 1/k each, so ≈ 2.6× the pot). Beta = Dimson beta of the daily return to D3
(same day + next day, since New York closes after London). Kurtosis and the top bar's share
of the variance: medians over the books.

## A1 — what explains the spread

| books | cost | (a) cost bill / turnover alone | (b) market exposure alone | (a)+(b) | (c) the rest | (c): "held SMEA.L into 2023-11-27" alone | (a)+(b) added after that fact |
|---|---|---|---|---|---|---|---|
| raw coin flip (QT-19 input) | 1× | 1.1% | 86.5% | 86.6% | 13.4% | **99.9%** (102 of 200 coins) | 0.01% |
| raw coin flip (QT-19 input) | 2× | 1.1% | 85.7% | 85.9% | 14.1% | **100.0%** (102 of 200 coins) | 0.01% |
| raw random-rank book (fix (i)) | 1× | 4.4% | 41.5% | 42.4% | 57.6% | — | — |
| raw random-rank book (fix (i)) | 2× | 3.5% | 42.2% | 43.5% | 56.5% | — | — |
| patched coin flip (QT-19 input) | 1× | 2.6% | 14.5% | 16.1% | 83.9% | — | — |
| patched coin flip (QT-19 input) | 2× | 4.7% | 22.2% | 25.2% | 74.8% | — | — |
| patched random-rank book (fix (i)) | 1× | 4.1% | 40.3% | 41.4% | 58.6% | — | — |
| patched random-rank book (fix (i)) | 2× | 3.2% | 41.1% | 42.5% | 57.5% | — | — |

The raw coins, split by that one fact:

| cost | held SMEA.L into 2023-11-27 | coins | Sharpe/bar | sd | std per bar | kurtosis | top bar's share | beta |
|---|---|---|---|---|---|---|---|---|
| 1× | yes | 102 | -0.0460 | 0.0007 | 0.0474 | 4,762 | 90% | 1.81 |
| 1× | no | 98 | -0.1902 | 0.0028 | 0.0146 | 14 | 2% | 1.90 |
| 2× | yes | 102 | -0.1211 | 0.0008 | 0.0474 | 4,730 | 90% | 1.80 |
| 2× | no | 98 | -0.4270 | 0.0041 | 0.0148 | 13 | 2% | 1.89 |

**Read with care:** on the raw data, "market exposure alone" looks large only because the
broken day bends each coin's own beta estimate (the coins that held SMEA.L show beta 1.81, the
rest 1.90). Once that one fact is in the regression, cost and exposure add almost nothing.

## A2 — diagnosis

**Hypothesis "cost noise" (each coin's cost bill differs a lot): rejected.** Every coin pays
nearly the same bill (182% of the pot a year at 1×, sd 0.3 points); it explains about 1% of
the spread. **The spread is one broken price that only the coin can reach.** SMEA.L's stored
open on 2023-11-27 is 114.6× its previous close. The coin ignores the book's eligibility,
so about half the coins held SMEA.L into that open and booked +344% of the pot in one bar —
their volatility triples and their Sharpe moves from −0.19 to −0.05. The book itself cannot
hold SMEA.L then (its 90% coverage test fails at every 2023 month-end, 0.81–0.87). **Costs
are the amplifier, not the cause:** daily churn (about 320× the pot a year) puts every coin's
Sharpe far below zero, the jump removes about three quarters of that distance, so the gap
between the two groups grows with the cost level — 0.071 at 1× became 0.151 at 2× in QT-19.

**Cross-check (ii), analytic** — each book's own Sharpe noise from its moments:

| data | cost | held the jump | coins | SR | skew | kurtosis | analytic sd of ONE book's Sharpe | SR0 at N=48 from it |
|---|---|---|---|---|---|---|---|---|
| patched | 1× | no | 10 | -0.189 | -0.2 | 14 | 0.0136 | 0.031 |
| patched | 2× | no | 10 | -0.425 | -0.2 | 13 | 0.0159 | 0.036 |
| raw | 1× | no | 6 | -0.190 | -0.2 | 14 | 0.0136 | 0.031 |
| raw | 1× | yes | 4 | -0.046 | +65.6 | 4,756 | 0.0333 | 0.075 |
| raw | 2× | no | 6 | -0.426 | -0.2 | 13 | 0.0158 | 0.036 |
| raw | 2× | yes | 4 | -0.121 | +65.2 | 4,724 | 0.0670 | 0.151 |

The same broken bar, seen from inside one book: skew 66 and kurtosis ≈ 4,750 when it holds
the jump.

## The broken rows (census of what the trials read)

Every unsealed daily bar of the 170 names checked for an open more than
1.5× or less than 0.67× the previous close, and for flat zero-volume rows
(open = high = low = close, volume 0):

| name | date | open ÷ previous close | what it is | does it reach a graded result? |
|---|---|---|---|---|
| **SMEA.L** (ETF) | 2023-11-27 | **×114.6** | a unit break: 0.54–0.61 before (live volume), 63–79 after (flat zero-volume rows and a ~5-month hole, live again from 2024-04-25) — consistent with the £ price ÷ 100 before and the € price after (114.6 ≈ 100 × EUR/GBP that day) | **only the coin** (+344% of the pot in one bar at a 1/33 slot): the book's 90% coverage test fails for SMEA.L at every 2023 month-end (0.81–0.87), so no book, and no random-rank book, can hold it then |
| FWRG.L (ETF) | 2023-07-11 | ×76.8 | its first 7 rows (from 2023-06-26) are flat, zero-volume, at 1/77 of the price | no — warm-up only (its first graded bar is a year later; its first 12-1 momentum reads the post-break close) |
| **EDV.L** (stock) | 2021-06-14 | ×0.59 | its 848 rows before its London listing that day: 619 flat zero-volume, the close unchanged on 73% of days (up to 85 sessions running), then the listing price | **yes** — the filler passes the coverage test, so a book can hold it on prices that never traded; the QT-19 GAP / PLANT-v2 / PLANT drill books held it into the fake −41% day (≈ −1.3% of the pot in one bar) |
| IITU.L (ETF) | 2015-11-24 | ×0.66 | two flat zero-volume launch rows | warm-up only |
| VRT | 2022-02-23 | ×0.62 | real (results day) | kept |
| AV.L, BLND.L, IAG.L, NWG.L, NXT.L | 2016-06-24 | ×0.65–0.66 | real (the Brexit vote) | kept |

D3 (VWRP, VWRL): no close-to-close move larger than their real March-2020 days; VIX's
largest is its real 2018-02-05 spike; GBPUSD (every dollar line's pound price): largest
daily move 7.9% after the Brexit vote, range 1.07–1.72 — clean. SMEA.L's 12-1
momentum reads about +11,800% at 11 month-ends (2024-05 → 2025-03), but the book's 90%
coverage check (0.71–0.74 there, because of the hole) keeps it out — the fake value never
becomes a buy. Not checked: a line priced in the wrong currency **throughout** shows no
jump (SMEA.L's later rows look like euros on a GBX line); only a per-ticker scale check
against Trading 212's own price finds that (SCARS #3).

## What the numbers say about the fix (for QT-21; description, not a re-proof)

- **The box's fix (i) is right in kind.** Random-rank books follow the book's own
  eligibility, slots, buffer, stops and costs, so they cannot catch a broken price the book
  cannot hold: none of the 100 did (their biggest bars are real 2020 days, at most 6.4%; kurtosis
  8–16), and their spread is 0.0052 at 1× and at 2×, on the raw and the patched data alike (SR0 ≈
  0.012). On clean data the coin gives a similar bar (SR0 0.006 / 0.009). All sit far
  below the QT-19 planted book's Sharpe (0.237 at 1×, 0.212 at 2×).
- **(i) and (ii) disagree by more than 2× (≈ 0.012 vs ≈ 0.031–0.036), as expected.** The nulls
  measure how far skill-free books sit from **each other** on the one price history they
  share — the market's luck is common to all of them. (ii) measures how far **one** book's
  Sharpe sits from its true value by the luck of that history, which the PSR already charges
  in its own denominator. SR0 is about the first.
- **For the mentor (not acted on):** the Deflated Sharpe centres its "best of N lucky tries"
  bar on zero. A long-only book earns the market's Sharpe without skill (random-rank books:
  +0.016 per bar at 1×, -0.008 at 2×). Centring on the skill-free books' own average
  would be stricter at 1× and looser at 2×; today the luck test and "beat D3" are what stop
  a market-riding book.
- The random-rank books trade like the book: turnover 10.0× the pot a year (the P10 stop
  closes many buys within a month), 24 names held, 0.80× the pot invested (the rest
  is cash from stops, the 1% ceiling and empty slots), beta 0.54.
