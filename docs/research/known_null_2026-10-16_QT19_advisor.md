# Known-null gate on the advisor's monthly book, daily bars (QT-19 B2)

## gate1: GREEN · red-first NOT shown

- KN-A-RANDOM-1d at 1× honest: expected FAIL, got **FAIL** (net +81.5% vs D3 +265.2%, p 0.537, trades 3,498; failed: luck, dsr, benchmark)
- KN-A-GAP-1d at 1× honest: expected FAIL, got **FAIL** (net +55.9% vs D3 +265.2%, p 0.945, trades 3,278; failed: luck, dsr, benchmark)
- KN-A-GAP-1d at 1× BROKEN (same_bar_fill): expected PASS, got **FAIL** (net +15079.6% vs D3 +265.2%, p 0.005, trades 3,278; failed: dsr)

## gate2: RED · red-first shown

- KN-A-PLANT-v2-1d at 1× honest: expected PASS, got **PASS** (net +60164.7% vs D3 +265.2%, p 0.005, trades 3,098; failed: none)
- KN-A-PLANT-v2-1d at 2× honest: expected PASS, got **FAIL** (net +33655.1% vs D3 +265.2%, p 0.005, trades 3,098; failed: dsr)
- KN-A-PLANT-v2-1d at 1× BROKEN (no_slot_weights): expected FAIL, got **FAIL** (net +215.6% vs D3 +265.2%, p 0.005, trades 3,098; failed: benchmark)

## KN-A-PLANT-1d (0.1%/bar, superseded as Gate 2's instrument; reported)

- KN-A-PLANT-1d at 1× honest: expected PASS, got **FAIL** (net +889.9% vs D3 +265.2%, p 0.005, trades 3,230; failed: dsr)
- KN-A-PLANT-1d at 2× honest: expected PASS, got **FAIL** (net +441.4% vs D3 +265.2%, p 0.005, trades 3,230; failed: dsr)

## KN-A-RANDOM-1d 1× honest

### KN-A-RANDOM-1d -- FAIL

- Registered in commit `accc44b2678b`; bars: 1d; costs at 1x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +281.41% | 0.0535 | 0.85 | -18.72% |
| strategy, net at 1x costs | +98.41% | 0.0283 | 0.45 | -20.14% |
| strategy, net after survivorship mark-down | +81.52% | 0.0249 | 0.40 | -20.35% |
| **benchmark VWRP.L** (same period) | **+265.22%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-07-25 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +98.41%, after +81.52% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 3498; bars: 5815; net mean per bar +0.01127% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.5373 (null Sharpe/bar 0.0249 ± 0.0053)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.1167 ± 0.0721)
- Pounds: 742 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 0.000 over 48 trials (luck ceiling 0.1630 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 0.5373 < 0.05); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (+81.52% vs +265.22%)

## KN-A-GAP-1d 1× honest

### KN-A-GAP-1d -- FAIL

- Registered in commit `accc44b2678b`; bars: 1d; costs at 1x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +214.35% | 0.0468 | 0.74 | -23.38% |
| strategy, net at 1x costs | +70.61% | 0.0229 | 0.36 | -25.82% |
| strategy, net after survivorship mark-down | +55.88% | 0.0194 | 0.31 | -26.03% |
| **benchmark VWRP.L** (same period) | **+265.22%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-07-25 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +70.61%, after +55.88% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 3278; bars: 5815; net mean per bar +0.00862% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.9453 (null Sharpe/bar 0.0296 ± 0.0057)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.1162 ± 0.0719)
- Pounds: 808 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 0.000 over 48 trials (luck ceiling 0.1625 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 0.9453 < 0.05); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (+55.88% vs +265.22%)

## KN-A-PLANT-v2-1d 1× honest

### KN-A-PLANT-v2-1d -- PASS

- Registered in commit `accc44b2678b`; bars: 1d; costs at 1x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +118260.87% | 0.2632 | 4.18 | -15.92% |
| strategy, net at 1x costs | +66278.25% | 0.2401 | 3.81 | -16.84% |
| strategy, net after survivorship mark-down | +60164.67% | 0.2366 | 3.76 | -16.88% |
| **benchmark VWRP.L** (same period) | **+265.22%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-07-25 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +66278.25%, after +60164.67% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 3098; bars: 5815; net mean per bar +0.11125% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar 0.0328 ± 0.0059)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.1167 ± 0.0723)
- Pounds: 862 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 1.000 over 48 trials (luck ceiling 0.1634 per bar)
- Verdict: PASS -- every check met

## KN-A-PLANT-v2-1d 2× honest

### KN-A-PLANT-v2-1d -- FAIL

- Registered in commit `accc44b2678b`; bars: 1d; costs at 2x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +118260.87% | 0.2632 | 4.18 | -15.92% |
| strategy, net at 2x costs | +37079.19% | 0.2154 | 3.42 | -17.75% |
| strategy, net after survivorship mark-down | +33655.09% | 0.2119 | 3.36 | -17.79% |
| strategy, net at 1x costs | +66278.25% | 0.2401 | 3.81 | -16.84% |
| **benchmark VWRP.L** (same period) | **+265.22%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-07-25 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +37079.19%, after +33655.09% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 3098; bars: 5815; net mean per bar +0.10131% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar 0.0141 ± 0.0053)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.2709 ± 0.1532)
- Pounds: 862 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 0.000 over 48 trials (luck ceiling 0.3463 per bar)
- Verdict: FAIL -- failed: Deflated Sharpe 0.000 >= 0.95

## KN-A-PLANT-1d 1× honest

### KN-A-PLANT-1d -- FAIL

- Registered in commit `accc44b2678b`; bars: 1d; costs at 1x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +1882.75% | 0.1165 | 1.85 | -17.76% |
| strategy, net at 1x costs | +985.86% | 0.0930 | 1.48 | -19.92% |
| strategy, net after survivorship mark-down | +889.92% | 0.0895 | 1.42 | -20.15% |
| **benchmark VWRP.L** (same period) | **+265.22%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-07-25 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +985.86%, after +889.92% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 3230; bars: 5815; net mean per bar +0.04045% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar 0.0294 ± 0.0053)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.1167 ± 0.0722)
- Pounds: 824 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 0.000 over 48 trials (luck ceiling 0.1632 per bar)
- Verdict: FAIL -- failed: Deflated Sharpe 0.000 >= 0.95

## KN-A-PLANT-1d 2× honest

### KN-A-PLANT-1d -- FAIL

- Registered in commit `accc44b2678b`; bars: 1d; costs at 2x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +1882.75% | 0.1165 | 1.85 | -17.76% |
| strategy, net at 2x costs | +493.90% | 0.0690 | 1.10 | -22.39% |
| strategy, net after survivorship mark-down | +441.43% | 0.0655 | 1.04 | -22.61% |
| strategy, net at 1x costs | +985.86% | 0.0930 | 1.48 | -19.92% |
| **benchmark VWRP.L** (same period) | **+265.22%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-07-25 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +493.90%, after +441.43% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 3230; bars: 5815; net mean per bar +0.03011% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar 0.0093 ± 0.0049)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.2710 ± 0.1531)
- Pounds: 824 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 0.000 over 48 trials (luck ceiling 0.3460 per bar)
- Verdict: FAIL -- failed: Deflated Sharpe 0.000 >= 0.95

## KN-A-GAP-1d 1× same_bar_fill

### KN-A-GAP-1d -- FAIL

- Registered in commit `accc44b2678b`; bars: 1d; costs at 1x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +30396.70% | 0.1962 | 3.12 | -11.25% |
| strategy, net at 1x costs | +16515.88% | 0.1739 | 2.76 | -11.67% |
| strategy, net after survivorship mark-down | +15079.58% | 0.1709 | 2.71 | -11.69% |
| **benchmark VWRP.L** (same period) | **+265.22%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-07-25 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +16515.88%, after +15079.58% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 3278; bars: 5815; net mean per bar +0.08772% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar 0.0296 ± 0.0056)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.1167 ± 0.0721)
- Pounds: 816 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 0.743 over 48 trials (luck ceiling 0.1630 per bar)
- Verdict: FAIL -- failed: Deflated Sharpe 0.743 >= 0.95

## KN-A-PLANT-v2-1d 1× no_slot_weights

### KN-A-PLANT-v2-1d -- FAIL

- Registered in commit `accc44b2678b`; bars: 1d; costs at 1x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +255.94% | 0.2612 | 4.15 | -2.99% |
| strategy, net at 1x costs | +221.05% | 0.2383 | 3.78 | -3.18% |
| strategy, net after survivorship mark-down | +215.57% | 0.2348 | 3.73 | -3.18% |
| **benchmark VWRP.L** (same period) | **+265.22%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-07-25 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +221.05%, after +215.57% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 3098; bars: 5815; net mean per bar +0.01980% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar 0.0328 ± 0.0059)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.1136 ± 0.0738)
- Pounds: 862 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 1.000 over 48 trials (luck ceiling 0.1668 per bar)
- Verdict: FAIL -- failed: beats the benchmark (+215.57% vs +265.22%)
