# Known-null gate, 2026-10-10 (QT-15 A1 re-proof: compounded returns, real clean store)

Re-run after QT-15 A1 changed the return arithmetic from summed to compounded.
QT-14's report of the same date (known_null_2026-10-10.md) is kept as it was.

    loaded 5m 50 names, 1d 49 names in 15s
    [DELAY REMOVED] KN-INSTANT-5m: expected FAIL, got PASS -> gate RED (198s)
    [COSTS OFF] KN-PLANT-SMALL-5m: expected FAIL, got PASS -> gate RED (214s)
    honest gate in 1072s: Gate 1 GREEN · Gate 2 GREEN
| drill | costs | expected | got | OOS trades | p | DSR | net marked (compounded) | max DD | VWRP same period |
|---|---|---|---|---|---|---|---|---|---|
| KN-COIN-5m | 1x | FAIL | FAIL | 42,481 | 0.413 | 0.000 | -97.52% | -97.52% | +2.65% |
| KN-INSTANT-5m | 1x | FAIL | FAIL | 2,062 | 0.005 | 0.000 | -42.69% | -42.69% | +2.65% |
| KN-COIN-1d | 1x | FAIL | FAIL | 2,952 | 0.080 | 0.464 | +0.16% | -17.63% | +17.39% |
| KN-PLANT-5m | 1x | PASS | PASS | 2,064 | 0.005 | 1.000 | +243.93% | -0.67% | +2.65% |
| KN-PLANT-5m | 2x | PASS | PASS | 2,064 | 0.005 | 1.000 | +187.87% | -0.80% | +2.65% |
| KN-PLANT-1d | 1x | PASS | PASS | 557 | 0.005 | 1.000 | +183.61% | -3.17% | +17.39% |
| KN-PLANT-1d | 2x | PASS | PASS | 557 | 0.005 | 1.000 | +169.38% | -3.58% | +17.39% |
| KN-PLANT-SMALL-5m | 1x | FAIL | FAIL | 2,064 | 0.005 | 0.186 | -1.23% | -4.26% | +2.65% |

## Gate 1 -- the worthless are rejected: GREEN

Expected FAIL, got FAIL (GREEN).

### KN-COIN-5m -- FAIL

- Registered in commit `21b154b6ade0`; bars: 5m; costs at 1x; out-of-sample 2026-07-21 to 2026-09-18
- Names: 50 (48 independent bets; 0 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +0.53% | 0.0024 | 0.33 | -2.98% |
| strategy, net at 1x costs | -97.51% | -1.2352 | -173.17 | -97.51% |
| strategy, net after survivorship mark-down | -97.52% | -1.2353 | -173.19 | -97.52% |
| **benchmark VWRP.L** (same period) | **+2.65%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc))
- Mark-down: before -97.51%, after -97.52% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 42481; bars: 6732
- Coin-flip null: p = 0.4129 (null Sharpe/bar -1.2378 ± 0.0119)
- Deflated Sharpe: 0.000 over 2 trials (luck ceiling 0.0062 per bar)
- Verdict: FAIL -- failed: beats the coin-flip null (p 0.4129 < 0.05); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-97.52% vs +2.65%)


Expected FAIL, got FAIL (GREEN).

### KN-INSTANT-5m -- FAIL

- Registered in commit `21b154b6ade0`; bars: 5m; costs at 1x; out-of-sample 2026-07-21 to 2026-09-18
- Names: 50 (48 independent bets; 0 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | -31.57% | -0.0793 | -11.12 | -31.58% |
| strategy, net at 1x costs | -42.68% | -0.1015 | -14.23 | -42.68% |
| strategy, net after survivorship mark-down | -42.69% | -0.1015 | -14.23 | -42.69% |
| **benchmark VWRP.L** (same period) | **+2.65%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc))
- Mark-down: before -42.68%, after -42.69% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 2062; bars: 6732
- Coin-flip null: p = 0.0050 (null Sharpe/bar -0.7361 ± 0.0091)
- Deflated Sharpe: 0.000 over 2 trials (luck ceiling 0.0047 per bar)
- Verdict: FAIL -- failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-42.69% vs +2.65%)


Expected FAIL, got FAIL (GREEN).

### KN-COIN-1d -- FAIL

- Registered in commit `21b154b6ade0`; bars: 1d; costs at 1x; out-of-sample 2024-10-07 to 2025-10-09
- Names: 49 (47 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +32.46% | 0.1165 | 1.85 | -11.38% |
| strategy, net at 1x costs | +0.58% | 0.0048 | 0.08 | -17.52% |
| strategy, net after survivorship mark-down | +0.16% | 0.0031 | 0.05 | -17.63% |
| **benchmark VWRP.L** (same period) | **+17.39%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc))
- Mark-down: before +0.58%, after +0.16% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 2952; bars: 506
- Coin-flip null: p = 0.0796 (null Sharpe/bar -0.0165 ± 0.0137)
- Deflated Sharpe: 0.464 over 2 trials (luck ceiling 0.0071 per bar)
- Verdict: FAIL -- failed: beats the coin-flip null (p 0.0796 < 0.05); failed: Deflated Sharpe 0.464 >= 0.95; failed: beats the benchmark (+0.16% vs +17.39%)


## Gate 2 -- the exploitable passes after costs: GREEN

Expected PASS, got PASS (GREEN).

### KN-PLANT-5m -- PASS

- Registered in commit `21b154b6ade0`; bars: 5m; costs at 1x; out-of-sample 2026-07-21 to 2026-09-18
- Names: 50 (48 independent bets; 0 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +310.98% | 0.4429 | 62.09 | -0.55% |
| strategy, net at 1x costs | +244.06% | 0.3662 | 51.35 | -0.67% |
| strategy, net after survivorship mark-down | +243.93% | 0.3662 | 51.34 | -0.67% |
| **benchmark VWRP.L** (same period) | **+2.65%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc))
- Mark-down: before +244.06%, after +243.93% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 2064; bars: 6732
- Coin-flip null: p = 0.0050 (null Sharpe/bar -1.0411 ± 0.0082)
- Deflated Sharpe: 1.000 over 2 trials (luck ceiling 0.0042 per bar)
- Verdict: PASS -- every check met


Expected PASS, got PASS (GREEN).

### KN-PLANT-5m -- PASS

- Registered in commit `21b154b6ade0`; bars: 5m; costs at 2x; out-of-sample 2026-07-21 to 2026-09-18
- Names: 50 (48 independent bets; 0 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +310.98% | 0.4429 | 62.09 | -0.55% |
| strategy, net at 2x costs | +187.98% | 0.2702 | 37.88 | -0.80% |
| strategy, net after survivorship mark-down | +187.87% | 0.2701 | 37.87 | -0.80% |
| strategy, net at 1x costs | +244.06% | 0.3662 | 51.35 | -0.67% |
| **benchmark VWRP.L** (same period) | **+2.65%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc))
- Mark-down: before +187.98%, after +187.87% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 2064; bars: 6732
- Coin-flip null: p = 0.0050 (null Sharpe/bar -1.5748 ± 0.0100)
- Deflated Sharpe: 1.000 over 2 trials (luck ceiling 0.0052 per bar)
- Verdict: PASS -- every check met


Expected PASS, got PASS (GREEN).

### KN-PLANT-1d -- PASS

- Registered in commit `21b154b6ade0`; bars: 1d; costs at 1x; out-of-sample 2024-10-07 to 2025-10-09
- Names: 49 (47 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +199.54% | 0.3522 | 5.59 | -3.13% |
| strategy, net at 1x costs | +184.52% | 0.3317 | 5.27 | -3.16% |
| strategy, net after survivorship mark-down | +183.61% | 0.3309 | 5.25 | -3.17% |
| **benchmark VWRP.L** (same period) | **+17.39%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc))
- Mark-down: before +184.52%, after +183.61% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 557; bars: 506
- Coin-flip null: p = 0.0050 (null Sharpe/bar -0.0226 ± 0.0124)
- Deflated Sharpe: 1.000 over 2 trials (luck ceiling 0.0065 per bar)
- Verdict: PASS -- every check met


Expected PASS, got PASS (GREEN).

### KN-PLANT-1d -- PASS

- Registered in commit `21b154b6ade0`; bars: 1d; costs at 2x; out-of-sample 2024-10-07 to 2025-10-09
- Names: 49 (47 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +199.54% | 0.3522 | 5.59 | -3.13% |
| strategy, net at 2x costs | +170.25% | 0.3111 | 4.94 | -3.55% |
| strategy, net after survivorship mark-down | +169.38% | 0.3103 | 4.93 | -3.58% |
| strategy, net at 1x costs | +184.52% | 0.3317 | 5.27 | -3.16% |
| **benchmark VWRP.L** (same period) | **+17.39%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc))
- Mark-down: before +170.25%, after +169.38% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 557; bars: 506
- Coin-flip null: p = 0.0050 (null Sharpe/bar -0.1181 ± 0.0134)
- Deflated Sharpe: 1.000 over 2 trials (luck ceiling 0.0070 per bar)
- Verdict: PASS -- every check met


Expected FAIL, got FAIL (GREEN).

### KN-PLANT-SMALL-5m -- FAIL

- Registered in commit `21b154b6ade0`; bars: 5m; costs at 1x; out-of-sample 2026-07-21 to 2026-09-18
- Names: 50 (48 independent bets; 0 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +18.02% | 0.0739 | 10.37 | -0.81% |
| strategy, net at 1x costs | -1.19% | -0.0045 | -0.63 | -4.24% |
| strategy, net after survivorship mark-down | -1.23% | -0.0047 | -0.65 | -4.26% |
| **benchmark VWRP.L** (same period) | **+2.65%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc))
- Mark-down: before -1.19%, after -1.23% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 2064; bars: 6732
- Coin-flip null: p = 0.0050 (null Sharpe/bar -1.2374 ± 0.0119)
- Deflated Sharpe: 0.186 over 2 trials (luck ceiling 0.0062 per bar)
- Verdict: FAIL -- failed: Deflated Sharpe 0.186 >= 0.95; failed: beats the benchmark (-1.23% vs +2.65%)

