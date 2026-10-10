# Known-null gate, 2026-10-10 (QT-14, real clean store)

## Gate 1 -- the worthless are rejected: GREEN

Expected FAIL, got FAIL (GREEN).

### KN-COIN-5m -- FAIL

- Registered in commit `21b154b6ade0`; bars: 5m; costs at 1x; out-of-sample 2026-07-21 to 2026-09-18
- Names: 50 (48 independent bets; 0 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +0.56% | 0.0023 | 0.33 | -2.99% |
| strategy, net at 1x costs | -369.32% | -1.2344 | -173.06 | -369.32% |
| strategy, net after survivorship mark-down | -369.38% | -1.2345 | -173.08 | -369.38% |
| **benchmark VWRP.L** (same period) | **+2.65%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc))
- Mark-down: before -369.32%, after -369.38% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 42481; bars: 6732
- Coin-flip null: p = 0.4129 (null Sharpe/bar -1.2370 ± 0.0119)
- Deflated Sharpe: 0.000 over 2 trials (luck ceiling 0.0062 per bar)
- Verdict: FAIL -- failed: beats the coin-flip null (p 0.4129 < 0.05); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-369.38% vs +2.65%)


Expected FAIL, got FAIL (GREEN).

### KN-INSTANT-5m -- FAIL

- Registered in commit `21b154b6ade0`; bars: 5m; costs at 1x; out-of-sample 2026-07-21 to 2026-09-18
- Names: 50 (48 independent bets; 0 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | -37.76% | -0.0793 | -11.12 | -37.77% |
| strategy, net at 1x costs | -55.51% | -0.1014 | -14.22 | -55.51% |
| strategy, net after survivorship mark-down | -55.51% | -0.1014 | -14.22 | -55.51% |
| **benchmark VWRP.L** (same period) | **+2.65%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc))
- Mark-down: before -55.51%, after -55.51% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 2062; bars: 6732
- Coin-flip null: p = 0.0050 (null Sharpe/bar -0.7339 ± 0.0091)
- Deflated Sharpe: 0.000 over 2 trials (luck ceiling 0.0047 per bar)
- Verdict: FAIL -- failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-55.51% vs +2.65%)


Expected FAIL, got FAIL (GREEN).

### KN-COIN-1d -- FAIL

- Registered in commit `21b154b6ade0`; bars: 1d; costs at 1x; out-of-sample 2024-09-30 to 2025-10-09
- Names: 49 (47 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +24.99% | 0.1033 | 1.64 | -12.86% |
| strategy, net at 1x costs | -3.14% | -0.0130 | -0.21 | -21.20% |
| strategy, net after survivorship mark-down | -3.57% | -0.0148 | -0.23 | -21.35% |
| **benchmark VWRP.L** (same period) | **+18.76%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc))
- Mark-down: before -3.14%, after -3.57% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 3018; bars: 516
- Coin-flip null: p = 0.4826 (null Sharpe/bar -0.0146 ± 0.0140)
- Deflated Sharpe: 0.309 over 2 trials (luck ceiling 0.0073 per bar)
- Verdict: FAIL -- failed: beats the coin-flip null (p 0.4826 < 0.05); failed: Deflated Sharpe 0.309 >= 0.95; failed: beats the benchmark (-3.57% vs +18.76%)


## Gate 2 -- the exploitable passes after costs: GREEN

Expected PASS, got PASS (GREEN).

### KN-PLANT-5m -- PASS

- Registered in commit `21b154b6ade0`; bars: 5m; costs at 1x; out-of-sample 2026-07-21 to 2026-09-18
- Names: 50 (48 independent bets; 0 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +143.75% | 0.4440 | 62.25 | -0.44% |
| strategy, net at 1x costs | +126.00% | 0.3689 | 51.71 | -0.55% |
| strategy, net after survivorship mark-down | +125.96% | 0.3688 | 51.70 | -0.55% |
| **benchmark VWRP.L** (same period) | **+2.65%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc))
- Mark-down: before +126.00%, after +125.96% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 2064; bars: 6732
- Coin-flip null: p = 0.0050 (null Sharpe/bar -1.0397 ± 0.0082)
- Deflated Sharpe: 1.000 over 2 trials (luck ceiling 0.0042 per bar)
- Verdict: PASS -- every check met


Expected PASS, got PASS (GREEN).

### KN-PLANT-5m -- PASS

- Registered in commit `21b154b6ade0`; bars: 5m; costs at 2x; out-of-sample 2026-07-21 to 2026-09-18
- Names: 50 (48 independent bets; 0 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +143.75% | 0.4440 | 62.25 | -0.44% |
| strategy, net at 2x costs | +108.24% | 0.2739 | 38.41 | -0.68% |
| strategy, net after survivorship mark-down | +108.20% | 0.2739 | 38.40 | -0.68% |
| strategy, net at 1x costs | +126.00% | 0.3689 | 51.71 | -0.55% |
| **benchmark VWRP.L** (same period) | **+2.65%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc))
- Mark-down: before +108.24%, after +108.20% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 2064; bars: 6732
- Coin-flip null: p = 0.0050 (null Sharpe/bar -1.5730 ± 0.0100)
- Deflated Sharpe: 1.000 over 2 trials (luck ceiling 0.0052 per bar)
- Verdict: PASS -- every check met


Expected PASS, got PASS (GREEN).

### KN-PLANT-1d -- PASS

- Registered in commit `21b154b6ade0`; bars: 1d; costs at 1x; out-of-sample 2024-09-30 to 2025-10-09
- Names: 49 (47 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +141.21% | 0.3929 | 6.24 | -3.17% |
| strategy, net at 1x costs | +136.04% | 0.3746 | 5.95 | -3.28% |
| strategy, net after survivorship mark-down | +135.72% | 0.3741 | 5.94 | -3.28% |
| **benchmark VWRP.L** (same period) | **+18.76%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc))
- Mark-down: before +136.04%, after +135.72% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 558; bars: 516
- Coin-flip null: p = 0.0050 (null Sharpe/bar -0.0147 ± 0.0126)
- Deflated Sharpe: 1.000 over 2 trials (luck ceiling 0.0065 per bar)
- Verdict: PASS -- every check met


Expected PASS, got PASS (GREEN).

### KN-PLANT-1d -- PASS

- Registered in commit `21b154b6ade0`; bars: 1d; costs at 2x; out-of-sample 2024-09-30 to 2025-10-09
- Names: 49 (47 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +141.21% | 0.3929 | 6.24 | -3.17% |
| strategy, net at 2x costs | +130.86% | 0.3562 | 5.65 | -3.40% |
| strategy, net after survivorship mark-down | +130.54% | 0.3556 | 5.65 | -3.40% |
| strategy, net at 1x costs | +136.04% | 0.3746 | 5.95 | -3.28% |
| **benchmark VWRP.L** (same period) | **+18.76%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc))
- Mark-down: before +130.86%, after +130.54% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 558; bars: 516
- Coin-flip null: p = 0.0050 (null Sharpe/bar -0.1082 ± 0.0136)
- Deflated Sharpe: 1.000 over 2 trials (luck ceiling 0.0071 per bar)
- Verdict: PASS -- every check met


Expected FAIL, got FAIL (GREEN).

### KN-PLANT-SMALL-5m -- FAIL

- Registered in commit `21b154b6ade0`; bars: 5m; costs at 1x; out-of-sample 2026-07-21 to 2026-09-18
- Names: 50 (48 independent bets; 0 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +16.62% | 0.0738 | 10.35 | -0.77% |
| strategy, net at 1x costs | -1.13% | -0.0044 | -0.62 | -4.18% |
| strategy, net after survivorship mark-down | -1.17% | -0.0046 | -0.65 | -4.20% |
| **benchmark VWRP.L** (same period) | **+2.65%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc))
- Mark-down: before -1.13%, after -1.17% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 2064; bars: 6732
- Coin-flip null: p = 0.0050 (null Sharpe/bar -1.2366 ± 0.0119)
- Deflated Sharpe: 0.187 over 2 trials (luck ceiling 0.0062 per bar)
- Verdict: FAIL -- failed: Deflated Sharpe 0.187 >= 0.95; failed: beats the benchmark (-1.17% vs +2.65%)

