# Known-null gate on the advisor's monthly book, daily bars (QT-21 D, re-proved)

Cleaned store (QT-21 A); luck bar SR0 from 200 random-rank books built by each drill's own rules (QT-21 C); one bar > 25% of the variance = INSUFFICIENT (QT-21 B).

## gate1: GREEN · red-first shown

- KN-A-RANDOM-1d at 1× honest: expected FAIL, got **FAIL** (net +87.7% vs D3 +265.1%, p 0.403, trades 3,467; DSR 0.876 (Sharpe/bar 0.0261 vs SR0 (i) 0.0109, (ii) 0.0297); biggest bar 1.5%; failed: luck, dsr, benchmark)
- KN-A-GAP-1d at 1× honest: expected FAIL, got **FAIL** (net +55.6% vs D3 +265.1%, p 0.975, trades 3,250; DSR 0.731 (Sharpe/bar 0.0192 vs SR0 (i) 0.0111, (ii) 0.0297); biggest bar 2.2%; failed: luck, dsr, benchmark)
- KN-A-GAP-1d at 1× BROKEN (same_bar_fill): expected PASS, got **PASS** (net +15121.3% vs D3 +265.1%, p 0.005, trades 3,250; DSR 1.0 (Sharpe/bar 0.1702 vs SR0 (i) 0.0110, (ii) 0.0276); biggest bar 1.6%; failed: none)

## gate2: GREEN · red-first shown

- KN-A-PLANT-v2-1d at 1× honest: expected PASS, got **PASS** (net +60381.2% vs D3 +265.1%, p 0.005, trades 3,077; DSR 1.0 (Sharpe/bar 0.2352 vs SR0 (i) 0.0126, (ii) 0.0315); biggest bar 1.9%; failed: none)
- KN-A-PLANT-v2-1d at 2× honest: expected PASS, got **PASS** (net +33685.2% vs D3 +265.1%, p 0.005, trades 3,077; DSR 1.0 (Sharpe/bar 0.2106 vs SR0 (i) 0.0126, (ii) 0.0314); biggest bar 1.9%; failed: none)
- KN-A-PLANT-v2-1d at 1× BROKEN (no_slot_weights): expected FAIL, got **FAIL** (net +213.1% vs D3 +265.1%, p 0.005, trades 3,077; DSR 1.0 (Sharpe/bar 0.2333 vs SR0 (i) 0.0126, (ii) 0.0316); biggest bar 1.9%; failed: benchmark)

## KN-A-PLANT-1d (0.1%/bar, superseded as Gate 2's instrument; reported)

- KN-A-PLANT-1d at 1× honest: expected PASS, got **PASS** (net +893.8% vs D3 +265.1%, p 0.005, trades 3,202; DSR 1.0 (Sharpe/bar 0.0889 vs SR0 (i) 0.0113, (ii) 0.0300); biggest bar 2.1%; failed: none)
- KN-A-PLANT-1d at 2× honest: expected PASS, got **PASS** (net +442.2% vs D3 +265.1%, p 0.005, trades 3,202; DSR 1.0 (Sharpe/bar 0.0651 vs SR0 (i) 0.0114, (ii) 0.0299); biggest bar 2.0%; failed: none)

## KN-A-RANDOM-1d 1× honest

### KN-A-RANDOM-1d -- FAIL

- Registered in commit `accc44b2678b`; bars: 1d; costs at 1x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +295.33% | 0.0545 | 0.87 | -18.72% |
| strategy, net at 1x costs | +105.31% | 0.0294 | 0.47 | -20.41% |
| strategy, net after survivorship mark-down | +87.74% | 0.0261 | 0.41 | -20.63% |
| **benchmark VWRP.L** (same period) | **+265.07%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-08-13 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +105.31%, after +87.74% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 3467; bars: 5815; net mean per bar +0.01187% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.4030 (null Sharpe/bar 0.0253 ± 0.0051)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0299 (null Sharpe/bar 0.0166 ± 0.0048)
- Pounds: 741 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 0.876 over 48 trials (luck ceiling 0.0109 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 0.4030 < 0.05); failed: Deflated Sharpe 0.876 >= 0.95; failed: beats the benchmark (+87.74% vs +265.07%)

## KN-A-GAP-1d 1× honest

### KN-A-GAP-1d -- FAIL

- Registered in commit `accc44b2678b`; bars: 1d; costs at 1x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +214.53% | 0.0464 | 0.74 | -23.42% |
| strategy, net at 1x costs | +70.36% | 0.0227 | 0.36 | -25.86% |
| strategy, net after survivorship mark-down | +55.56% | 0.0192 | 0.30 | -26.07% |
| **benchmark VWRP.L** (same period) | **+265.07%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-08-13 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +70.36%, after +55.56% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 3250; bars: 5815; net mean per bar +0.00860% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.9751 (null Sharpe/bar 0.0298 ± 0.0055)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.3781 (null Sharpe/bar 0.0179 ± 0.0049)
- Pounds: 813 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 0.731 over 48 trials (luck ceiling 0.0111 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 0.9751 < 0.05); failed: Deflated Sharpe 0.731 >= 0.95; failed: beats the benchmark (+55.56% vs +265.07%)

## KN-A-PLANT-v2-1d 1× honest

### KN-A-PLANT-v2-1d -- PASS

- Registered in commit `accc44b2678b`; bars: 1d; costs at 1x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +119066.51% | 0.2618 | 4.16 | -16.36% |
| strategy, net at 1x costs | +66551.07% | 0.2387 | 3.79 | -17.28% |
| strategy, net after survivorship mark-down | +60381.20% | 0.2352 | 3.73 | -17.32% |
| **benchmark VWRP.L** (same period) | **+265.07%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-08-13 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +66551.07%, after +60381.20% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 3077; bars: 5815; net mean per bar +0.11132% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar 0.0328 ± 0.0055)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar 0.0289 ± 0.0056)
- Pounds: 868 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 1.000 over 48 trials (luck ceiling 0.0126 per bar)
- Verdict: PASS -- every check met

## KN-A-PLANT-v2-1d 2× honest

### KN-A-PLANT-v2-1d -- PASS

- Registered in commit `accc44b2678b`; bars: 1d; costs at 2x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +119066.51% | 0.2618 | 4.16 | -16.36% |
| strategy, net at 2x costs | +37131.52% | 0.2141 | 3.40 | -18.20% |
| strategy, net after survivorship mark-down | +33685.19% | 0.2106 | 3.34 | -18.24% |
| strategy, net at 1x costs | +66551.07% | 0.2387 | 3.79 | -17.28% |
| **benchmark VWRP.L** (same period) | **+265.07%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-08-13 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +37131.52%, after +33685.19% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 3077; bars: 5815; net mean per bar +0.10134% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar 0.0139 ± 0.0052)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar 0.0037 ± 0.0056)
- Pounds: 868 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 1.000 over 48 trials (luck ceiling 0.0126 per bar)
- Verdict: PASS -- every check met

## KN-A-PLANT-1d 1× honest

### KN-A-PLANT-1d -- PASS

- Registered in commit `accc44b2678b`; bars: 1d; costs at 1x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +1896.66% | 0.1158 | 1.84 | -17.67% |
| strategy, net at 1x costs | +990.83% | 0.0924 | 1.47 | -19.81% |
| strategy, net after survivorship mark-down | +893.81% | 0.0889 | 1.41 | -20.04% |
| **benchmark VWRP.L** (same period) | **+265.07%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-08-13 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +990.83%, after +893.81% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 3202; bars: 5815; net mean per bar +0.04054% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar 0.0296 ± 0.0050)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar 0.0181 ± 0.0050)
- Pounds: 824 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 1.000 over 48 trials (luck ceiling 0.0113 per bar)
- Verdict: PASS -- every check met

## KN-A-PLANT-1d 2× honest

### KN-A-PLANT-1d -- PASS

- Registered in commit `accc44b2678b`; bars: 1d; costs at 2x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +1896.66% | 0.1158 | 1.84 | -17.67% |
| strategy, net at 2x costs | +495.17% | 0.0685 | 1.09 | -22.26% |
| strategy, net after survivorship mark-down | +442.24% | 0.0651 | 1.03 | -22.49% |
| strategy, net at 1x costs | +990.83% | 0.0924 | 1.47 | -19.81% |
| **benchmark VWRP.L** (same period) | **+265.07%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-08-13 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +495.17%, after +442.24% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 3202; bars: 5815; net mean per bar +0.03015% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar 0.0091 ± 0.0048)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.0066 ± 0.0050)
- Pounds: 824 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 1.000 over 48 trials (luck ceiling 0.0114 per bar)
- Verdict: PASS -- every check met

## KN-A-GAP-1d 1× same_bar_fill

### KN-A-GAP-1d -- PASS

- Registered in commit `accc44b2678b`; bars: 1d; costs at 1x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +30565.09% | 0.1955 | 3.10 | -12.02% |
| strategy, net at 1x costs | +16571.64% | 0.1732 | 2.75 | -12.44% |
| strategy, net after survivorship mark-down | +15121.33% | 0.1702 | 2.70 | -12.46% |
| **benchmark VWRP.L** (same period) | **+265.07%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-08-13 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +16571.64%, after +15121.33% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 3250; bars: 5815; net mean per bar +0.08778% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar 0.0298 ± 0.0055)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar 0.0678 ± 0.0049)
- Pounds: 821 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 1.000 over 48 trials (luck ceiling 0.0110 per bar)
- Verdict: PASS -- every check met

## KN-A-PLANT-v2-1d 1× no_slot_weights

### KN-A-PLANT-v2-1d -- FAIL

- Registered in commit `accc44b2678b`; bars: 1d; costs at 1x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +253.06% | 0.2597 | 4.12 | -3.08% |
| strategy, net at 1x costs | +218.57% | 0.2368 | 3.76 | -3.27% |
| strategy, net after survivorship mark-down | +213.14% | 0.2333 | 3.70 | -3.27% |
| **benchmark VWRP.L** (same period) | **+265.07%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-08-13 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +218.57%, after +213.14% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 3077; bars: 5815; net mean per bar +0.01967% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar 0.0327 ± 0.0055)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar 0.0289 ± 0.0056)
- Pounds: 868 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 1.000 over 48 trials (luck ceiling 0.0126 per bar)
- Verdict: FAIL -- failed: beats the benchmark (+213.14% vs +265.07%)
