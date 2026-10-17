# Known-null gate on the advisor's monthly book, daily bars (QT-22, batch 2's book: the big-fall stop)

Cleaned store (QT-21 A); luck bar SR0 from 200 random-rank books built by each drill's own rules (QT-21 C); one bar > 25% of the variance = INSUFFICIENT (QT-21 B).

## gate1: GREEN · red-first shown

- KN-A2-RANDOM-1d at 1× honest: expected FAIL, got **FAIL** (net +165.9% vs D3 +265.1%, p 0.194, trades 3,082; DSR 0.97 (Sharpe/bar 0.0351 vs SR0 (i) 0.0103, (ii) 0.0304); biggest bar 1.3%; failed: luck, benchmark)
- KN-A2-GAP-1d at 1× honest: expected FAIL, got **FAIL** (net +159.0% vs D3 +265.1%, p 0.766, trades 2,509; DSR 0.965 (Sharpe/bar 0.0346 vs SR0 (i) 0.0108, (ii) 0.0304); biggest bar 1.5%; failed: luck, benchmark)
- KN-A2-GAP-1d at 1× BROKEN (same_bar_fill): expected PASS, got **PASS** (net +6510.2% vs D3 +265.1%, p 0.005, trades 2,509; DSR 1.0 (Sharpe/bar 0.1311 vs SR0 (i) 0.0103, (ii) 0.0302); biggest bar 1.7%; failed: none)

## gate2: GREEN · red-first shown

- KN-A2-PLANT-v2-1d at 1× honest: expected PASS, got **PASS** (net +62393.4% vs D3 +265.1%, p 0.005, trades 2,497; DSR 1.0 (Sharpe/bar 0.2153 vs SR0 (i) 0.0123, (ii) 0.0323); biggest bar 1.5%; failed: none)
- KN-A2-PLANT-v2-1d at 2× honest: expected PASS, got **PASS** (net +38725.3% vs D3 +265.1%, p 0.005, trades 2,497; DSR 1.0 (Sharpe/bar 0.1976 vs SR0 (i) 0.0122, (ii) 0.0321); biggest bar 1.4%; failed: none)
- KN-A2-PLANT-v2-1d at 1× BROKEN (no_slot_weights): expected FAIL, got **FAIL** (net +215.6% vs D3 +265.1%, p 0.005, trades 2,497; DSR 1.0 (Sharpe/bar 0.2141 vs SR0 (i) 0.0123, (ii) 0.0323); biggest bar 1.4%; failed: benchmark)

## KN-A2-RANDOM-1d 1× honest

### KN-A2-RANDOM-1d -- FAIL

- Registered in commit `196fd496f1c0`; bars: 1d; costs at 1x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +428.21% | 0.0581 | 0.92 | -20.36% |
| strategy, net at 1x costs | +195.87% | 0.0386 | 0.61 | -21.21% |
| strategy, net after survivorship mark-down | +165.85% | 0.0351 | 0.56 | -21.27% |
| **benchmark VWRP.L** (same period) | **+265.07%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-08-13 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +195.87%, after +165.85% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 3082; bars: 5815; net mean per bar +0.01816% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.1940 (null Sharpe/bar 0.0315 ± 0.0045)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.1642 (null Sharpe/bar 0.0300 ± 0.0045)
- Pounds: 867 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 0.970 over 54 trials (luck ceiling 0.0103 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 0.1940 < 0.05); failed: beats the benchmark (+165.85% vs +265.07%)

## KN-A2-GAP-1d 1× honest

### KN-A2-GAP-1d -- FAIL

- Registered in commit `196fd496f1c0`; bars: 1d; costs at 1x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +364.94% | 0.0545 | 0.87 | -23.02% |
| strategy, net at 1x costs | +188.56% | 0.0383 | 0.61 | -24.77% |
| strategy, net after survivorship mark-down | +158.98% | 0.0346 | 0.55 | -25.04% |
| **benchmark VWRP.L** (same period) | **+265.07%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-08-13 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +188.56%, after +158.98% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 2509; bars: 5815; net mean per bar +0.01767% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.7662 (null Sharpe/bar 0.0379 ± 0.0049)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.2139 (null Sharpe/bar 0.0306 ± 0.0047)
- Pounds: 970 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 0.965 over 54 trials (luck ceiling 0.0108 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 0.7662 < 0.05); failed: beats the benchmark (+158.98% vs +265.07%)

## KN-A2-PLANT-v2-1d 1× honest

### KN-A2-PLANT-v2-1d -- PASS

- Registered in commit `196fd496f1c0`; bars: 1d; costs at 1x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +111995.40% | 0.2356 | 3.74 | -21.09% |
| strategy, net at 1x costs | +69608.39% | 0.2189 | 3.47 | -21.81% |
| strategy, net after survivorship mark-down | +62393.44% | 0.2153 | 3.42 | -21.86% |
| **benchmark VWRP.L** (same period) | **+265.07%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-08-13 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +69608.39%, after +62393.44% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 2497; bars: 5815; net mean per bar +0.11212% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar 0.0390 ± 0.0049)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar 0.0309 ± 0.0053)
- Pounds: 969 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 1.000 over 54 trials (luck ceiling 0.0123 per bar)
- Verdict: PASS -- every check met

## KN-A2-PLANT-v2-1d 2× honest

### KN-A2-PLANT-v2-1d -- PASS

- Registered in commit `196fd496f1c0`; bars: 1d; costs at 2x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +111995.40% | 0.2356 | 3.74 | -21.09% |
| strategy, net at 2x costs | +43207.55% | 0.2012 | 3.19 | -22.53% |
| strategy, net after survivorship mark-down | +38725.31% | 0.1976 | 3.14 | -22.58% |
| strategy, net at 1x costs | +69608.39% | 0.2189 | 3.47 | -21.81% |
| **benchmark VWRP.L** (same period) | **+265.07%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-08-13 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +43207.55%, after +38725.31% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 2497; bars: 5815; net mean per bar +0.10396% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar 0.0250 ± 0.0048)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar 0.0114 ± 0.0053)
- Pounds: 969 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 1.000 over 54 trials (luck ceiling 0.0122 per bar)
- Verdict: PASS -- every check met

## KN-A2-GAP-1d 1× same_bar_fill

### KN-A2-GAP-1d -- PASS

- Registered in commit `196fd496f1c0`; bars: 1d; costs at 1x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +11730.77% | 0.1498 | 2.38 | -18.23% |
| strategy, net at 1x costs | +7265.84% | 0.1344 | 2.13 | -19.02% |
| strategy, net after survivorship mark-down | +6510.20% | 0.1311 | 2.08 | -19.07% |
| **benchmark VWRP.L** (same period) | **+265.07%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-08-13 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +7265.84%, after +6510.20% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 2509; bars: 5815; net mean per bar +0.07368% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar 0.0379 ± 0.0049)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar 0.0437 ± 0.0045)
- Pounds: 971 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 1.000 over 54 trials (luck ceiling 0.0103 per bar)
- Verdict: PASS -- every check met

## KN-A2-PLANT-v2-1d 1× no_slot_weights

### KN-A2-PLANT-v2-1d -- FAIL

- Registered in commit `196fd496f1c0`; bars: 1d; costs at 1x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +250.03% | 0.2343 | 3.72 | -4.05% |
| strategy, net at 1x costs | +221.77% | 0.2177 | 3.46 | -4.20% |
| strategy, net after survivorship mark-down | +215.61% | 0.2141 | 3.40 | -4.21% |
| **benchmark VWRP.L** (same period) | **+265.07%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-08-13 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +221.77%, after +215.61% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 2497; bars: 5815; net mean per bar +0.01981% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar 0.0387 ± 0.0049)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar 0.0309 ± 0.0053)
- Pounds: 969 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 1.000 over 54 trials (luck ceiling 0.0123 per bar)
- Verdict: FAIL -- failed: beats the benchmark (+215.61% vs +265.07%)
