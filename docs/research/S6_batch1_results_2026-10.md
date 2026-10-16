# S6 batch 1 results, 2026-10 (QT-18: 8 same-day rules × 3 arms, 1-hour bars)

Run 1 of 1; **8 of 24 trials complete**; interrupted runs logged (counted 0): none. Every trial run exactly as registered (docs/research/preregistered.json, ids S6-01-US … S6-08-MIX); code commit and data fingerprints in docs/reports/QT-18_progress.md.

**Survived both gates (walk-forward PASS at 2× costs AND holdout PASS): none.**

How each trial is judged: net after 2× costs with the survivorship mark-down, compounded; 1× beside it; against VWRP's own hourly closes over the same dates. PASS needs all of: the turnover-matched luck test (p < 0.05) AND a positive net mean per bar; Deflated Sharpe ≥ 0.95 over N; a higher return than VWRP. INSUFFICIENT (under 30 out-of-sample trades) is its own answer, never a PASS. Brakes (P12) are NOT applied in back-tests; the maximum drawdown is shown instead.

**Read with care:** the P15 history rule lets the back-test always dodge the real results date. Live, a date can move, so share results are slightly optimistic (ETFs are not affected) -- most of all in the holdout, where each share's next date is the one first recorded on 2026-10-02, treated as known from its July/August results.

Trial count for deflation: **N = 42** (18 before + 24). qb2's trial log now counts 26 selection trials (38 drill and 0 holdout lines excluded). Trial runtime 35 minutes.

## The 24 trials

| id | arm | OOS dates | trades | net 1× | **net 2×** | VWRP same dates | max DD (2×) | p vs matched null | DSR (N) | verdict | holdout |
|---|---|---|---|---|---|---|---|---|---|---|---|
| S6-01-US | US | 2024-02-01 → 2026-07-10 | 8,851 | -71.69% | **-91.31%** | +50.70% | -91.31% | 0.005 | 0.000 (42) | **FAIL** | not run (no walk-forward PASS) |
| S6-01-LON | LON | 2024-02-12 → 2026-07-10 | 4,708 | -62.41% | **-85.15%** | +47.33% | -85.15% | 0.005 | 0.000 (42) | **FAIL** | not run (no walk-forward PASS) |
| S6-01-MIX | MIX | 2024-02-01 → 2026-07-10 | 13,559 | -68.42% | **-89.31%** | +50.70% | -89.31% | 0.005 | 0.000 (42) | **FAIL** | not run (no walk-forward PASS) |
| S6-02-US | US | 2024-02-01 → 2026-07-10 | 2,742 | -31.59% | **-52.68%** | +50.70% | -53.05% | 0.005 | 0.000 (42) | **FAIL** | not run (no walk-forward PASS) |
| S6-02-LON | LON | 2024-02-12 → 2026-07-10 | 582 | -11.15% | **-23.33%** | +47.33% | -23.41% | 0.005 | 0.000 (42) | **FAIL** | not run (no walk-forward PASS) |
| S6-02-MIX | MIX | 2024-02-01 → 2026-07-10 | 3,324 | -24.30% | **-43.00%** | +50.70% | -43.24% | 0.005 | 0.000 (42) | **FAIL** | not run (no walk-forward PASS) |
| S6-03-US | US | 2024-02-01 → 2026-07-10 | 1,765 | -19.38% | **-36.46%** | +50.70% | -36.51% | 0.005 | 0.000 (42) | **FAIL** | not run (no walk-forward PASS) |
| S6-03-LON | LON | 2024-02-12 → 2026-07-10 | 334 | -6.93% | **-13.40%** | +47.33% | -13.66% | 0.070 | 0.000 (42) | **FAIL** | not run (no walk-forward PASS) |

## Why each verdict

- **S6-01-US** FAIL: failed: a positive net mean per bar (-0.05740% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-91.31% vs +50.70%)
- **S6-01-LON** FAIL: failed: a positive net mean per bar (-0.03482% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-85.15% vs +47.33%)
- **S6-01-MIX** FAIL: failed: a positive net mean per bar (-0.02299% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-89.31% vs +50.70%)
- **S6-02-US** FAIL: failed: a positive net mean per bar (-0.01750% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-52.68% vs +50.70%)
- **S6-02-LON** FAIL: failed: a positive net mean per bar (-0.00484% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-23.33% vs +47.33%)
- **S6-02-MIX** FAIL: failed: a positive net mean per bar (-0.00576% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-43.00% vs +50.70%)
- **S6-03-US** FAIL: failed: a positive net mean per bar (-0.01064% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-36.46% vs +50.70%)
- **S6-03-LON** FAIL: failed: beats the turnover-matched luck test (p 0.0697 < 0.05); failed: a positive net mean per bar (-0.00263% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-13.40% vs +47.33%)

## Per sleeve (net after 2× costs and mark-down, compounded)

> Per-year figures are not shown; per-sleeve figures are description only. Picking a sleeve, an arm or a year afterwards is a NEW trial that must be registered first.

> Description only. Picking a sleeve (or a market) because it looks better here would be a NEW trial: it must be registered, and counted, before it is run.

| id | uk_etf net 2× (trades) | uk_share net 2× (trades) | us_liquid net 2× (trades) |
|---|---|---|---|
| S6-01-US | — | — | -91.31% (8,851) |
| S6-01-LON | -76.97% (3,108) | -89.56% (1,600) | — |
| S6-01-MIX | -76.97% (3,108) | -89.56% (1,600) | -91.31% (8,851) |
| S6-02-US | — | — | -52.68% (2,742) |
| S6-02-LON | -6.78% (274) | -34.48% (308) | — |
| S6-02-MIX | -6.78% (274) | -34.48% (308) | -52.68% (2,742) |
| S6-03-US | — | — | -36.46% (1,765) |
| S6-03-LON | -10.24% (203) | -15.87% (131) | — |

## Appendix: each trial's firewall report

### S6-01-US -- FAIL

- Registered in commit `c89f2fd7202c`; bars: 1h; costs at 2x; out-of-sample 2024-02-01 to 2026-07-10
- Names: 30 (29 independent bets; 0 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | -7.74% | -0.0247 | -1.04 | -8.41% |
| strategy, net at 2x costs | -91.30% | -0.4454 | -18.70 | -91.30% |
| strategy, net after survivorship mark-down | -91.31% | -0.4455 | -18.71 | -91.31% |
| strategy, net at 1x costs | -71.64% | -0.3186 | -13.38 | -71.64% |
| **benchmark VWRP.L** (same period) | **+50.70%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -91.30%, after -91.31% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 8851; bars: 4249; net mean per bar -0.05740% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar -0.7926 ± 0.0198)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.6979 ± 0.0137)
- Deflated Sharpe: 0.000 over 42 trials (luck ceiling 0.0303 per bar)
- Verdict: FAIL -- failed: a positive net mean per bar (-0.05740% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-91.31% vs +50.70%)

### S6-01-LON -- FAIL

- Registered in commit `c89f2fd7202c`; bars: 1h; costs at 2x; out-of-sample 2024-02-12 to 2026-07-10
- Names: 19 (18 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | -4.90% | -0.0255 | -1.07 | -5.51% |
| strategy, net at 2x costs | -85.15% | -0.3799 | -15.95 | -85.15% |
| strategy, net after survivorship mark-down | -85.15% | -0.3799 | -15.95 | -85.15% |
| strategy, net at 1x costs | -62.40% | -0.3177 | -13.34 | -62.40% |
| **benchmark VWRP.L** (same period) | **+47.33%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -85.15%, after -85.15% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 4708; bars: 5470; net mean per bar -0.03482% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar -0.7259 ± 0.0266)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.9900 ± 0.0157)
- Deflated Sharpe: 0.000 over 42 trials (luck ceiling 0.0346 per bar)
- Verdict: FAIL -- failed: a positive net mean per bar (-0.03482% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-85.15% vs +47.33%)

### S6-01-MIX -- FAIL

- Registered in commit `c89f2fd7202c`; bars: 1h; costs at 2x; out-of-sample 2024-02-01 to 2026-07-10
- Names: 49 (47 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | -6.63% | -0.0215 | -0.90 | -6.89% |
| strategy, net at 2x costs | -89.30% | -0.3844 | -16.14 | -89.30% |
| strategy, net after survivorship mark-down | -89.31% | -0.3844 | -16.14 | -89.31% |
| strategy, net at 1x costs | -68.38% | -0.2846 | -11.95 | -68.38% |
| **benchmark VWRP.L** (same period) | **+50.70%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -89.30%, after -89.31% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 13559; bars: 9719; net mean per bar -0.02299% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar -0.6721 ± 0.0136)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.6820 ± 0.0115)
- Deflated Sharpe: 0.000 over 42 trials (luck ceiling 0.0255 per bar)
- Verdict: FAIL -- failed: a positive net mean per bar (-0.02299% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-89.31% vs +50.70%)

### S6-02-US -- FAIL

- Registered in commit `c89f2fd7202c`; bars: 1h; costs at 2x; out-of-sample 2024-02-01 to 2026-07-10
- Names: 30 (29 independent bets; 0 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | -0.94% | -0.0009 | -0.04 | -7.09% |
| strategy, net at 2x costs | -52.58% | -0.1182 | -4.97 | -52.96% |
| strategy, net after survivorship mark-down | -52.68% | -0.1186 | -4.98 | -53.05% |
| strategy, net at 1x costs | -31.45% | -0.0620 | -2.60 | -32.47% |
| **benchmark VWRP.L** (same period) | **+50.70%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -52.58%, after -52.68% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 2742; bars: 4249; net mean per bar -0.01750% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar -0.2153 ± 0.0146)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.6979 ± 0.0137)
- Deflated Sharpe: 0.000 over 42 trials (luck ceiling 0.0303 per bar)
- Verdict: FAIL -- failed: a positive net mean per bar (-0.01750% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-52.68% vs +50.70%)

### S6-02-LON -- FAIL

- Registered in commit `c89f2fd7202c`; bars: 1h; costs at 2x; out-of-sample 2024-02-12 to 2026-07-10
- Names: 19 (18 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +3.00% | 0.0106 | 0.44 | -3.05% |
| strategy, net at 2x costs | -23.29% | -0.0815 | -3.42 | -23.38% |
| strategy, net after survivorship mark-down | -23.33% | -0.0816 | -3.43 | -23.41% |
| strategy, net at 1x costs | -11.11% | -0.0394 | -1.65 | -11.25% |
| **benchmark VWRP.L** (same period) | **+47.33%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -23.29%, after -23.33% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 582; bars: 5470; net mean per bar -0.00484% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar -0.1887 ± 0.0187)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.9900 ± 0.0157)
- Deflated Sharpe: 0.000 over 42 trials (luck ceiling 0.0346 per bar)
- Verdict: FAIL -- failed: a positive net mean per bar (-0.00484% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-23.33% vs +47.33%)

### S6-02-MIX -- FAIL

- Registered in commit `c89f2fd7202c`; bars: 1h; costs at 2x; out-of-sample 2024-02-01 to 2026-07-10
- Names: 49 (47 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +0.67% | 0.0015 | 0.06 | -4.29% |
| strategy, net at 2x costs | -42.91% | -0.0916 | -3.85 | -43.16% |
| strategy, net after survivorship mark-down | -43.00% | -0.0919 | -3.86 | -43.24% |
| strategy, net at 1x costs | -24.19% | -0.0472 | -1.98 | -24.87% |
| **benchmark VWRP.L** (same period) | **+50.70%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -42.91%, after -43.00% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 3324; bars: 9719; net mean per bar -0.00576% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar -0.1729 ± 0.0102)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.6820 ± 0.0115)
- Deflated Sharpe: 0.000 over 42 trials (luck ceiling 0.0255 per bar)
- Verdict: FAIL -- failed: a positive net mean per bar (-0.00576% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-43.00% vs +50.70%)

### S6-03-US -- FAIL

- Registered in commit `c89f2fd7202c`; bars: 1h; costs at 2x; out-of-sample 2024-02-01 to 2026-07-10
- Names: 30 (29 independent bets; 0 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +2.41% | 0.0075 | 0.32 | -5.11% |
| strategy, net at 2x costs | -36.38% | -0.1249 | -5.25 | -36.42% |
| strategy, net after survivorship mark-down | -36.46% | -0.1253 | -5.26 | -36.51% |
| strategy, net at 1x costs | -19.28% | -0.0624 | -2.62 | -20.47% |
| **benchmark VWRP.L** (same period) | **+50.70%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -36.38%, after -36.46% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 1765; bars: 4249; net mean per bar -0.01064% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar -0.1977 ± 0.0153)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.6979 ± 0.0137)
- Deflated Sharpe: 0.000 over 42 trials (luck ceiling 0.0303 per bar)
- Verdict: FAIL -- failed: a positive net mean per bar (-0.01064% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-36.46% vs +50.70%)

### S6-03-LON -- FAIL

- Registered in commit `c89f2fd7202c`; bars: 1h; costs at 2x; out-of-sample 2024-02-12 to 2026-07-10
- Names: 19 (18 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +0.03% | 0.0003 | 0.01 | -1.54% |
| strategy, net at 2x costs | -13.38% | -0.0907 | -3.81 | -13.64% |
| strategy, net after survivorship mark-down | -13.40% | -0.0908 | -3.81 | -13.66% |
| strategy, net at 1x costs | -6.92% | -0.0514 | -2.16 | -7.56% |
| **benchmark VWRP.L** (same period) | **+47.33%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -13.38%, after -13.40% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 334; bars: 5470; net mean per bar -0.00263% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0697 (null Sharpe/bar -0.1309 ± 0.0189)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.9900 ± 0.0157)
- Deflated Sharpe: 0.000 over 42 trials (luck ceiling 0.0346 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 0.0697 < 0.05); failed: a positive net mean per bar (-0.00263% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-13.40% vs +47.33%)

