# Known-null gate, 2026-10-12 (QT-16 A3: turnover-matched luck test, US in pounds)

Re-run on the REAL clean store after QT-16 A1 (the verdict's luck test is now the turnover-matched null; the coin-flip stays as a description and still feeds the Deflated Sharpe) and A2 (a dollar line's money is in pounds). QT-15's report (known_null_2026-10-10_QT15.md) is kept as it was.

## Red first, on deliberately broken code (nothing logged)

| breakage | drill | expected | got | luck p | DSR | gate |
|---|---|---|---|---|---|---|
| luck test on the OLD coin-flip null (code before A1) | KN-LAZY-5m | FAIL, luck test failed | FAIL, luck test PASSED (p 0.005) | 0.005 | 0.000 | RED |
| delay removed | KN-INSTANT-5m | FAIL | PASS | 0.005 | 1.000 | RED |
| costs off | KN-PLANT-SMALL-5m | FAIL | PASS | 0.005 | 1.000 | RED |

## Honest code: Gate 1 GREEN · Gate 2 GREEN

| drill | costs | expected | got | OOS trades (old → new) | luck test p, matched (new) | coin-flip p (old luck test, now description) | DSR (old → new) | net marked (old → new; US now in £) | VWRP same period | gate |
|---|---|---|---|---|---|---|---|---|---|---|
| KN-COIN-5m | 1× | FAIL | FAIL (failed: luck, dsr, benchmark) | 42,481 → 42,481 | 0.333 | 0.413 → 0.388 | 0.000 → 0.000 | -97.52% → -97.51% | +2.65% | GREEN |
| KN-INSTANT-5m | 1× | FAIL | FAIL (failed: dsr, benchmark) | 2,062 → 2,062 | 0.005 | 0.005 → 0.005 | 0.000 → 0.000 | -42.69% → -42.71% | +2.65% | GREEN |
| KN-COIN-1d | 1× | FAIL | FAIL (failed: luck, dsr, benchmark) | 2,952 → 2,952 | 0.134 | 0.080 → 0.100 | 0.464 → 0.272 | +0.16% → -1.27% | +17.39% | GREEN |
| KN-LAZY-5m | 1× | FAIL (luck test must fail) | FAIL (failed: luck, dsr, benchmark) | new → 2,125 | 0.075 | — → 0.005 | — → 0.000 | — → -16.76% | +2.65% | GREEN |
| KN-PLANT-5m | 1× | PASS | PASS | 2,064 → 2,064 | 0.005 | 0.005 → 0.005 | 1.000 → 1.000 | +243.93% → +244.07% | +2.65% | GREEN |
| KN-PLANT-5m | 2× | PASS | PASS | 2,064 → 2,064 | 0.005 | 0.005 → 0.005 | 1.000 → 1.000 | +187.87% → +187.99% | +2.65% | GREEN |
| KN-PLANT-1d | 1× | PASS | PASS | 557 → 557 | 0.005 | 0.005 → 0.005 | 1.000 → 1.000 | +183.61% → +178.78% | +17.39% | GREEN |
| KN-PLANT-1d | 2× | PASS | PASS | 557 → 557 | 0.005 | 0.005 → 0.005 | 1.000 → 1.000 | +169.38% → +164.79% | +17.39% | GREEN |
| KN-PLANT-SMALL-5m | 1× | FAIL | FAIL (failed: dsr, benchmark) | 2,064 → 2,064 | 0.005 | 0.005 → 0.005 | 0.186 → 0.013 | -1.23% → -1.19% | +2.65% | GREEN |

FX: every held dollar bar had a GBPUSD rate (no INSUFFICIENT); held bars that took the previous FX bar (within pounds.TOLERANCE): KN-COIN-1d 1× 142, KN-PLANT-1d 1× 87, KN-PLANT-1d 2× 87.

Reading it:

- **KN-LAZY-5m is the point of A1.** Against the churning coin-flip it "beat luck"
  (p 0.005); against its own trades placed at random it does not (p 0.075). Gate 1
  now rejects a slow rule on the luck test itself, not only on DSR and benchmark.
- **DSR moved for KN-COIN-1d (0.464 → 0.272) and KN-PLANT-SMALL-5m (0.186 → 0.013)**
  because qb2's trial count is now 18 (P19's batch), not 2 as in QT-15 — deflation
  over more trials. Its inputs are otherwise unchanged (the coin-flip's variance).
- **Pounds:** net figures moved slightly for the daily drills (US names now carry
  the dollar's move against the pound); 5-minute figures barely moved.
- **Flagged, not fixed:** KN-INSTANT-5m still "beats" the luck test (p 0.005) while
  losing 42.7%. Its losses land on the same bar in every session, so its per-bar
  returns are noisier, and a negative Sharpe reads better when noisier. The verdict
  holds (DSR 0.000, benchmark), as in QT-14 and QT-15.

## Each drill's firewall report

### KN-COIN-5m -- FAIL

- Registered in commit `b2a892bdd803`; bars: 5m; costs at 1x; out-of-sample 2026-07-21 to 2026-09-18
- Names: 50 (48 independent bets; 0 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +0.65% | 0.0029 | 0.41 | -2.91% |
| strategy, net at 1x costs | -97.51% | -1.2437 | -174.36 | -97.51% |
| strategy, net after survivorship mark-down | -97.51% | -1.2438 | -174.38 | -97.51% |
| **benchmark VWRP.L** (same period) | **+2.65%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc))
- Mark-down: before -97.51%, after -97.51% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 42481; bars: 6732
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.3333 (null Sharpe/bar -1.2490 ± 0.0123)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.3881 (null Sharpe/bar -1.2469 ± 0.0121)
- Deflated Sharpe: 0.000 over 18 trials (luck ceiling 0.0224 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 0.3333 < 0.05); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-97.51% vs +2.65%)

### KN-INSTANT-5m -- FAIL

- Registered in commit `b2a892bdd803`; bars: 5m; costs at 1x; out-of-sample 2026-07-21 to 2026-09-18
- Names: 50 (48 independent bets; 0 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | -31.60% | -0.0795 | -11.14 | -31.61% |
| strategy, net at 1x costs | -42.71% | -0.1016 | -14.24 | -42.71% |
| strategy, net after survivorship mark-down | -42.71% | -0.1016 | -14.24 | -42.71% |
| **benchmark VWRP.L** (same period) | **+2.65%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc))
- Mark-down: before -42.71%, after -42.71% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 2062; bars: 6732
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar -0.4443 ± 0.0147)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.7375 ± 0.0092)
- Deflated Sharpe: 0.000 over 18 trials (luck ceiling 0.0171 per bar)
- Verdict: FAIL -- failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-42.71% vs +2.65%)

### KN-COIN-1d -- FAIL

- Registered in commit `b2a892bdd803`; bars: 1d; costs at 1x; out-of-sample 2024-10-07 to 2025-10-09
- Names: 49 (47 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +30.56% | 0.1071 | 1.70 | -12.71% |
| strategy, net at 1x costs | -0.86% | -0.0009 | -0.01 | -18.46% |
| strategy, net after survivorship mark-down | -1.27% | -0.0025 | -0.04 | -18.57% |
| **benchmark VWRP.L** (same period) | **+17.39%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc))
- Mark-down: before -0.86%, after -1.27% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 2952; bars: 506
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.1343 (null Sharpe/bar -0.0185 ± 0.0131)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0995 (null Sharpe/bar -0.0185 ± 0.0132)
- Pounds: 142 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 0.272 over 18 trials (luck ceiling 0.0245 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 0.1343 < 0.05); failed: Deflated Sharpe 0.272 >= 0.95; failed: beats the benchmark (-1.27% vs +17.39%)

### KN-LAZY-5m -- FAIL

- Registered in commit `b2a892bdd803`; bars: 5m; costs at 1x; out-of-sample 2026-07-21 to 2026-09-18
- Names: 50 (48 independent bets; 0 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +0.37% | 0.0047 | 0.66 | -0.97% |
| strategy, net at 1x costs | -16.74% | -0.2104 | -29.50 | -16.74% |
| strategy, net after survivorship mark-down | -16.76% | -0.2106 | -29.53 | -16.76% |
| **benchmark VWRP.L** (same period) | **+2.65%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc))
- Mark-down: before -16.74%, after -16.76% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 2125; bars: 6732
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0746 (null Sharpe/bar -0.2266 ± 0.0103)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -1.2469 ± 0.0121)
- Deflated Sharpe: 0.000 over 18 trials (luck ceiling 0.0224 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 0.0746 < 0.05); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-16.76% vs +2.65%)

### KN-PLANT-5m -- PASS

- Registered in commit `b2a892bdd803`; bars: 5m; costs at 1x; out-of-sample 2026-07-21 to 2026-09-18
- Names: 50 (48 independent bets; 0 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +311.15% | 0.4475 | 62.74 | -0.55% |
| strategy, net at 1x costs | +244.21% | 0.3697 | 51.83 | -0.67% |
| strategy, net after survivorship mark-down | +244.07% | 0.3696 | 51.82 | -0.67% |
| **benchmark VWRP.L** (same period) | **+2.65%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc))
- Mark-down: before +244.21%, after +244.07% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 2064; bars: 6732
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar -0.0706 ± 0.0090)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -1.0464 ± 0.0082)
- Deflated Sharpe: 1.000 over 18 trials (luck ceiling 0.0152 per bar)
- Verdict: PASS -- every check met

### KN-PLANT-5m -- PASS

- Registered in commit `b2a892bdd803`; bars: 5m; costs at 2x; out-of-sample 2026-07-21 to 2026-09-18
- Names: 50 (48 independent bets; 0 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +311.15% | 0.4475 | 62.74 | -0.55% |
| strategy, net at 2x costs | +188.10% | 0.2721 | 38.15 | -0.80% |
| strategy, net after survivorship mark-down | +187.99% | 0.2720 | 38.14 | -0.80% |
| strategy, net at 1x costs | +244.21% | 0.3697 | 51.83 | -0.67% |
| **benchmark VWRP.L** (same period) | **+2.65%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc))
- Mark-down: before +188.10%, after +187.99% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 2064; bars: 6732
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar -0.1521 ± 0.0091)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -1.5793 ± 0.0101)
- Deflated Sharpe: 1.000 over 18 trials (luck ceiling 0.0187 per bar)
- Verdict: PASS -- every check met

### KN-PLANT-1d -- PASS

- Registered in commit `b2a892bdd803`; bars: 1d; costs at 1x; out-of-sample 2024-10-07 to 2025-10-09
- Names: 49 (47 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +194.43% | 0.3405 | 5.40 | -3.62% |
| strategy, net at 1x costs | +179.67% | 0.3206 | 5.09 | -3.64% |
| strategy, net after survivorship mark-down | +178.78% | 0.3198 | 5.08 | -3.65% |
| **benchmark VWRP.L** (same period) | **+17.39%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc))
- Mark-down: before +179.67%, after +178.78% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 557; bars: 506
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar 0.0508 ± 0.0196)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.0245 ± 0.0122)
- Pounds: 87 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 1.000 over 18 trials (luck ceiling 0.0226 per bar)
- Verdict: PASS -- every check met

### KN-PLANT-1d -- PASS

- Registered in commit `b2a892bdd803`; bars: 1d; costs at 2x; out-of-sample 2024-10-07 to 2025-10-09
- Names: 49 (47 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +194.43% | 0.3405 | 5.40 | -3.62% |
| strategy, net at 2x costs | +165.64% | 0.3006 | 4.77 | -3.67% |
| strategy, net after survivorship mark-down | +164.79% | 0.2999 | 4.76 | -3.68% |
| strategy, net at 1x costs | +179.67% | 0.3206 | 5.09 | -3.64% |
| **benchmark VWRP.L** (same period) | **+17.39%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc))
- Mark-down: before +165.64%, after +164.79% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 557; bars: 506
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar 0.0280 ± 0.0194)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.1185 ± 0.0131)
- Pounds: 87 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 1.000 over 18 trials (luck ceiling 0.0242 per bar)
- Verdict: PASS -- every check met

### KN-PLANT-SMALL-5m -- FAIL

- Registered in commit `b2a892bdd803`; bars: 5m; costs at 1x; out-of-sample 2026-07-21 to 2026-09-18
- Names: 50 (48 independent bets; 0 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +18.07% | 0.0756 | 10.59 | -1.00% |
| strategy, net at 1x costs | -1.15% | -0.0044 | -0.62 | -4.17% |
| strategy, net after survivorship mark-down | -1.19% | -0.0046 | -0.64 | -4.19% |
| **benchmark VWRP.L** (same period) | **+2.65%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc))
- Mark-down: before -1.15%, after -1.19% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 2064; bars: 6732
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar -0.1134 ± 0.0069)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -1.2465 ± 0.0121)
- Deflated Sharpe: 0.013 over 18 trials (luck ceiling 0.0224 per bar)
- Verdict: FAIL -- failed: Deflated Sharpe 0.013 >= 0.95; failed: beats the benchmark (-1.19% vs +2.65%)

