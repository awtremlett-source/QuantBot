# S9 advisor batch 2 (batch 1's six, the big-fall stop) — results, 2026-10 (QT-22)

Run 1; 6 of 6 trials complete; register commit `196fd49`. Every trial run exactly as registered (docs/research/preregistered.json).

**Survived (walk-forward PASS and holdout PASS): none.**

Judged on net after 2× costs with the survivorship mark-down and dividends credited, compounded, against D3 over the same dates (VWRP; VWRL with dividends before VWRP's first traded close, 2019-08-13 since QT-21). PASS needs the luck test (p < 0.05) and a positive net mean, Deflated Sharpe ≥ 0.95 at N = 54 (luck bar from random-rank books), and beating D3; one bar over 25% of the variance = INSUFFICIENT. Dividends: 4,751 payouts credited; 8 not credited (SUSPECT or UNCHECKED).

| id | rule | trades | gross | net 1× | **net 2×** | D3 same dates | max DD | p (matched) | DSR (N) | biggest bar | verdict | holdout | turnover/yr | avg hold | stopped < 1 month |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A2-01 | A-01 with the big-fall stop (advisor batch 2): Momentum 12-1: rank by the 12-month return skipping the latest month | 1,059 | +476.91% | +330.30% | **+256.82%** | +265.07% | -23.46% | 0.940 | 0.988 (54) | 0.9% | **FAIL** | not run | +303.34% | 110 days | 15.6% |
| A2-02 | A-02 with the big-fall stop (advisor batch 2): Momentum 6-1: rank by the 6-month return skipping the latest month | 1,412 | +448.95% | +283.05% | **+196.97%** | +265.07% | -27.99% | 0.896 | 0.972 (54) | 1.0% | **FAIL** | not run | +401.75% | 81 days | 14.7% |
| A2-03 | A-03 with the big-fall stop (advisor batch 2): Risk-adjusted momentum: A-01's return / its 12-month daily volatility | 957 | +499.15% | +355.41% | **+284.62%** | +265.07% | -20.93% | 0.741 | 0.996 (54) | 0.8% | **FAIL** | not run | +274.40% | 124 days | 11.8% |
| A2-04 | A-04 with the big-fall stop (advisor batch 2): Near the 52-week high: rank by close / the 52-week high | 1,388 | +346.29% | +212.43% | **+143.16%** | +265.07% | -19.57% | 0.896 | 0.963 (54) | 1.1% | **FAIL** | not run | +400.54% | 89 days | 4.1% |
| A2-05 | A-05 with the big-fall stop (advisor batch 2): Low volatility: rank by the LOWEST 1-year daily volatility | 393 | +219.86% | +170.31% | **+152.14%** | +265.07% | -16.32% | 0.826 | 0.987 (54) | 1.4% | **FAIL** | not run | +113.16% | 311 days | 3.6% |
| A2-06 | A-06 with the big-fall stop (advisor batch 2): Momentum 12-1 with a market filter: A-01, but only when VWRP closes above its 200-day average | 956 | +251.99% | +173.67% | **+131.33%** | +265.07% | -28.00% | 1.000 | 0.943 (54) | 0.9% | **FAIL** | not run | +273.05% | 97 days | 11.7% |

## US / London split (net 2×)

> Description only. Choosing the US or London half because it looks better here would be a NEW trial: registered, and counted, before it is run.

| id | US net 2× (trades) | London net 2× (trades) |
|---|---|---|
| A2-01 | +138.05% (580) | +49.89% (479) |
| A2-02 | +93.64% (729) | +53.36% (683) |
| A2-03 | +129.06% (507) | +67.91% (450) |
| A2-04 | +70.51% (669) | +42.61% (719) |
| A2-05 | +48.95% (154) | +69.28% (239) |
| A2-06 | +94.13% (532) | +19.16% (424) |

## The book, per trial

| id | stopped | P13 re-justified | 1% ceiling binds (held name-days) | months in cash (A-06) | buys | P15 warning: results within 5 days | date unknown |
|---|---|---|---|---|---|---|---|
| A2-01 | 631 | 31 | 0.00% | 0 | 1,059 | 52 | 356 |
| A2-02 | 630 | 8 | 0.00% | 0 | 1,431 | 70 | 478 |
| A2-03 | 528 | 37 | 0.00% | 0 | 957 | 39 | 344 |
| A2-04 | 238 | 16 | 0.00% | 0 | 1,388 | 52 | 546 |
| A2-05 | 286 | 149 | 0.00% | 0 | 393 | 11 | 172 |
| A2-06 | 416 | 10 | 0.00% | 43 | 956 | 40 | 317 |

## The luck bar, two ways (SR0 at N; DSR uses (i))

(i) random-rank books built by the trial's own rules: how far skill-free books sit from each other on the one shared history. (ii) DESCRIPTION ONLY, one book's own Sharpe noise from its moments: the noise the PSR already charges in its denominator, so (ii) is expected to be the larger.

| id | Sharpe/bar (2×) | SR0 (i) random-rank | SR0 (ii) analytic |
|---|---|---|---|
| A2-01 | 0.0404 | 0.0103 | 0.0306 |
| A2-02 | 0.0356 | 0.0102 | 0.0306 |
| A2-03 | 0.0455 | 0.0103 | 0.0306 |
| A2-04 | 0.0339 | 0.0103 | 0.0305 |
| A2-05 | 0.0404 | 0.0108 | 0.0304 |
| A2-06 | 0.0312 | 0.0103 | 0.0305 |

## Why each did not pass

- **A2-01**: failed: beats the turnover-matched luck test (p 0.9403 < 0.05); failed: beats the benchmark (+256.82% vs +265.07%)
- **A2-02**: failed: beats the turnover-matched luck test (p 0.8955 < 0.05); failed: beats the benchmark (+196.97% vs +265.07%)
- **A2-03**: failed: beats the turnover-matched luck test (p 0.7413 < 0.05)
- **A2-04**: failed: beats the turnover-matched luck test (p 0.8955 < 0.05); failed: beats the benchmark (+143.16% vs +265.07%)
- **A2-05**: failed: beats the turnover-matched luck test (p 0.8259 < 0.05); failed: beats the benchmark (+152.14% vs +265.07%)
- **A2-06**: failed: beats the turnover-matched luck test (p 1.0000 < 0.05); failed: Deflated Sharpe 0.943 >= 0.95; failed: beats the benchmark (+131.33% vs +265.07%)

## A2-01 — firewall report

### A2-01 -- FAIL

- Registered in commit `196fd496f1c0`; bars: 1d; costs at 2x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +476.91% | 0.0546 | 0.87 | -21.59% |
| strategy, net at 2x costs | +296.76% | 0.0435 | 0.69 | -23.09% |
| strategy, net after survivorship mark-down | +256.82% | 0.0404 | 0.64 | -23.46% |
| strategy, net at 1x costs | +378.46% | 0.0491 | 0.78 | -22.14% |
| **benchmark VWRP.L** (same period) | **+265.07%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-08-13 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +296.76%, after +256.82% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 1059; bars: 5815; net mean per bar +0.02359% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.9403 (null Sharpe/bar 0.0475 ± 0.0044)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar 0.0106 ± 0.0045)
- Pounds: 1138 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 0.988 over 54 trials (luck ceiling 0.0103 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 0.9403 < 0.05); failed: beats the benchmark (+256.82% vs +265.07%)


## A2-02 — firewall report

### A2-02 -- FAIL

- Registered in commit `196fd496f1c0`; bars: 1d; costs at 2x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +448.95% | 0.0541 | 0.86 | -24.23% |
| strategy, net at 2x costs | +230.04% | 0.0387 | 0.61 | -26.94% |
| strategy, net after survivorship mark-down | +196.97% | 0.0356 | 0.56 | -27.99% |
| strategy, net at 1x costs | +325.71% | 0.0464 | 0.74 | -24.70% |
| **benchmark VWRP.L** (same period) | **+265.07%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-08-13 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +230.04%, after +196.97% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 1412; bars: 5815; net mean per bar +0.02036% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.8955 (null Sharpe/bar 0.0415 ± 0.0050)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar 0.0112 ± 0.0044)
- Pounds: 1033 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 0.972 over 54 trials (luck ceiling 0.0102 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 0.8955 < 0.05); failed: beats the benchmark (+196.97% vs +265.07%)


## A2-03 — firewall report

### A2-03 -- FAIL

- Registered in commit `196fd496f1c0`; bars: 1d; costs at 2x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +499.15% | 0.0596 | 0.95 | -19.53% |
| strategy, net at 2x costs | +327.42% | 0.0488 | 0.78 | -20.88% |
| strategy, net after survivorship mark-down | +284.62% | 0.0455 | 0.72 | -20.93% |
| strategy, net at 1x costs | +406.08% | 0.0542 | 0.86 | -20.20% |
| **benchmark VWRP.L** (same period) | **+265.07%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-08-13 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +327.42%, after +284.62% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 957; bars: 5815; net mean per bar +0.02464% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.7413 (null Sharpe/bar 0.0481 ± 0.0046)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar 0.0106 ± 0.0045)
- Pounds: 1064 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 0.996 over 54 trials (luck ceiling 0.0103 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 0.7413 < 0.05)


## A2-04 — firewall report

### A2-04 -- FAIL

- Registered in commit `196fd496f1c0`; bars: 1d; costs at 2x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +346.29% | 0.0556 | 0.88 | -17.11% |
| strategy, net at 2x costs | +170.39% | 0.0377 | 0.60 | -19.10% |
| strategy, net after survivorship mark-down | +143.16% | 0.0339 | 0.54 | -19.57% |
| strategy, net at 1x costs | +247.43% | 0.0467 | 0.74 | -17.60% |
| **benchmark VWRP.L** (same period) | **+265.07%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-08-13 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +170.39%, after +143.16% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 1388; bars: 5815; net mean per bar +0.01646% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.8955 (null Sharpe/bar 0.0392 ± 0.0043)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar 0.0106 ± 0.0045)
- Pounds: 1060 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 0.963 over 54 trials (luck ceiling 0.0103 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 0.8955 < 0.05); failed: beats the benchmark (+143.16% vs +265.07%)


## A2-05 — firewall report

### A2-05 -- FAIL

- Registered in commit `196fd496f1c0`; bars: 1d; costs at 2x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +219.86% | 0.0503 | 0.80 | -15.53% |
| strategy, net at 2x costs | +178.31% | 0.0445 | 0.71 | -16.27% |
| strategy, net after survivorship mark-down | +152.14% | 0.0404 | 0.64 | -16.32% |
| strategy, net at 1x costs | +198.37% | 0.0474 | 0.75 | -15.73% |
| **benchmark VWRP.L** (same period) | **+265.07%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-08-13 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +178.31%, after +152.14% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 393; bars: 5815; net mean per bar +0.01677% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.8259 (null Sharpe/bar 0.0433 ± 0.0033)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar 0.0111 ± 0.0047)
- Pounds: 915 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 0.987 over 54 trials (luck ceiling 0.0108 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 0.8259 < 0.05); failed: beats the benchmark (+152.14% vs +265.07%)


## A2-06 — firewall report

### A2-06 -- FAIL

- Registered in commit `196fd496f1c0`; bars: 1d; costs at 2x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +251.99% | 0.0456 | 0.72 | -23.17% |
| strategy, net at 2x costs | +151.55% | 0.0341 | 0.54 | -27.56% |
| strategy, net after survivorship mark-down | +131.33% | 0.0312 | 0.50 | -28.00% |
| strategy, net at 1x costs | +197.59% | 0.0398 | 0.63 | -25.39% |
| **benchmark VWRP.L** (same period) | **+265.07%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-08-13 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +151.55%, after +131.33% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 956; bars: 5815; net mean per bar +0.01569% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 1.0000 (null Sharpe/bar 0.0453 ± 0.0047)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar 0.0106 ± 0.0045)
- Pounds: 938 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 0.943 over 54 trials (luck ceiling 0.0103 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 1.0000 < 0.05); failed: Deflated Sharpe 0.943 >= 0.95; failed: beats the benchmark (+131.33% vs +265.07%)

