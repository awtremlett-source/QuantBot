# S6 batch 1 results, 2026-10 (QT-18: 8 same-day rules × 3 arms, 1-hour bars)

Run 1 of 1; **20 of 24 trials complete**; interrupted runs logged (counted 0): none. Every trial run exactly as registered (docs/research/preregistered.json, ids S6-01-US … S6-08-MIX); code commit and data fingerprints in docs/reports/QT-18_progress.md.

**Survived both gates (walk-forward PASS at 2× costs AND holdout PASS): none.**

How each trial is judged: net after 2× costs with the survivorship mark-down, compounded; 1× beside it; against VWRP's own hourly closes over the same dates. PASS needs all of: the turnover-matched luck test (p < 0.05) AND a positive net mean per bar; Deflated Sharpe ≥ 0.95 over N; a higher return than VWRP. INSUFFICIENT (under 30 out-of-sample trades) is its own answer, never a PASS. Brakes (P12) are NOT applied in back-tests; the maximum drawdown is shown instead.

**Read with care:** the P15 history rule lets the back-test always dodge the real results date. Live, a date can move, so share results are slightly optimistic (ETFs are not affected) -- most of all in the holdout, where each share's next date is the one first recorded on 2026-10-02, treated as known from its July/August results.

Trial count for deflation: **N = 42** (18 before + 24). qb2's trial log now counts 38 selection trials (38 drill and 0 holdout lines excluded). Trial runtime 92 minutes.

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
| S6-03-MIX | MIX | 2024-02-01 → 2026-07-10 | 2,099 | -14.79% | **-28.43%** | +50.70% | -28.46% | 0.005 | 0.000 (42) | **FAIL** | not run (no walk-forward PASS) |
| S6-04-US | US | 2024-02-01 → 2026-07-10 | 4,652 | -49.29% | **-72.80%** | +50.70% | -72.81% | 0.025 | 0.000 (42) | **FAIL** | not run (no walk-forward PASS) |
| S6-04-LON | LON | 2024-02-12 → 2026-07-10 | 3,360 | -48.41% | **-73.29%** | +47.33% | -73.29% | 0.005 | 0.000 (42) | **FAIL** | not run (no walk-forward PASS) |
| S6-04-MIX | MIX | 2024-02-01 → 2026-07-10 | 8,012 | -48.93% | **-72.97%** | +50.70% | -72.97% | 0.005 | 0.000 (42) | **FAIL** | not run (no walk-forward PASS) |
| S6-05-US | US | 2024-02-01 → 2026-07-10 | 10,904 | -78.28% | **-94.92%** | +50.70% | -94.92% | 0.249 | 0.000 (42) | **FAIL** | not run (no walk-forward PASS) |
| S6-05-LON | LON | 2024-02-12 → 2026-07-10 | 4,892 | -64.84% | **-87.57%** | +47.33% | -87.57% | 0.005 | 0.000 (42) | **FAIL** | not run (no walk-forward PASS) |
| S6-05-MIX | MIX | 2024-02-01 → 2026-07-10 | 15,796 | -73.84% | **-92.83%** | +50.70% | -92.83% | 0.035 | 0.000 (42) | **FAIL** | not run (no walk-forward PASS) |
| S6-06-US | US | 2024-02-01 → 2026-07-10 | 3,286 | -34.89% | **-58.15%** | +50.70% | -58.16% | 0.080 | 0.000 (42) | **FAIL** | not run (no walk-forward PASS) |
| S6-06-LON | LON | 2024-02-12 → 2026-07-10 | 1,264 | -24.63% | **-44.94%** | +47.33% | -44.94% | 0.005 | 0.000 (42) | **FAIL** | not run (no walk-forward PASS) |
| S6-06-MIX | MIX | 2024-02-01 → 2026-07-10 | 4,550 | -31.11% | **-53.49%** | +50.70% | -53.49% | 0.010 | 0.000 (42) | **FAIL** | not run (no walk-forward PASS) |
| S6-07-US | US | 2024-02-01 → 2026-07-10 | 3,263 | -36.50% | **-59.07%** | +50.70% | -59.07% | 0.537 | 0.000 (42) | **FAIL** | not run (no walk-forward PASS) |
| S6-07-LON | LON | 2024-02-12 → 2026-07-10 | 1,324 | -28.71% | **-49.23%** | +47.33% | -49.32% | 0.194 | 0.000 (42) | **FAIL** | not run (no walk-forward PASS) |

## Why each verdict

- **S6-01-US** FAIL: failed: a positive net mean per bar (-0.05740% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-91.31% vs +50.70%)
- **S6-01-LON** FAIL: failed: a positive net mean per bar (-0.03482% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-85.15% vs +47.33%)
- **S6-01-MIX** FAIL: failed: a positive net mean per bar (-0.02299% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-89.31% vs +50.70%)
- **S6-02-US** FAIL: failed: a positive net mean per bar (-0.01750% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-52.68% vs +50.70%)
- **S6-02-LON** FAIL: failed: a positive net mean per bar (-0.00484% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-23.33% vs +47.33%)
- **S6-02-MIX** FAIL: failed: a positive net mean per bar (-0.00576% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-43.00% vs +50.70%)
- **S6-03-US** FAIL: failed: a positive net mean per bar (-0.01064% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-36.46% vs +50.70%)
- **S6-03-LON** FAIL: failed: beats the turnover-matched luck test (p 0.0697 < 0.05); failed: a positive net mean per bar (-0.00263% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-13.40% vs +47.33%)
- **S6-03-MIX** FAIL: failed: a positive net mean per bar (-0.00344% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-28.43% vs +50.70%)
- **S6-04-US** FAIL: failed: a positive net mean per bar (-0.03060% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-72.80% vs +50.70%)
- **S6-04-LON** FAIL: failed: a positive net mean per bar (-0.02411% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-73.29% vs +47.33%)
- **S6-04-MIX** FAIL: failed: a positive net mean per bar (-0.01345% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-72.97% vs +50.70%)
- **S6-05-US** FAIL: failed: beats the turnover-matched luck test (p 0.2488 < 0.05); failed: a positive net mean per bar (-0.06997% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-94.92% vs +50.70%)
- **S6-05-LON** FAIL: failed: a positive net mean per bar (-0.03807% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-87.57% vs +47.33%)
- **S6-05-MIX** FAIL: failed: a positive net mean per bar (-0.02708% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-92.83% vs +50.70%)
- **S6-06-US** FAIL: failed: beats the turnover-matched luck test (p 0.0796 < 0.05); failed: a positive net mean per bar (-0.02046% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-58.15% vs +50.70%)
- **S6-06-LON** FAIL: failed: a positive net mean per bar (-0.01090% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-44.94% vs +47.33%)
- **S6-06-MIX** FAIL: failed: a positive net mean per bar (-0.00787% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-53.49% vs +50.70%)
- **S6-07-US** FAIL: failed: beats the turnover-matched luck test (p 0.5373 < 0.05); failed: a positive net mean per bar (-0.02100% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-59.07% vs +50.70%)
- **S6-07-LON** FAIL: failed: beats the turnover-matched luck test (p 0.1940 < 0.05); failed: a positive net mean per bar (-0.01238% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-49.23% vs +47.33%)

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
| S6-03-MIX | -10.24% (203) | -15.87% (131) | -36.46% (1,765) |
| S6-04-US | — | — | -72.80% (4,652) |
| S6-04-LON | -63.48% (2,226) | -79.23% (1,134) | — |
| S6-04-MIX | -63.48% (2,226) | -79.23% (1,134) | -72.80% (4,652) |
| S6-05-US | — | — | -94.92% (10,904) |
| S6-05-LON | -73.67% (2,982) | -93.19% (1,910) | — |
| S6-05-MIX | -73.67% (2,982) | -93.19% (1,910) | -94.92% (10,904) |
| S6-06-US | — | — | -58.15% (3,286) |
| S6-06-LON | -21.07% (614) | -58.77% (650) | — |
| S6-06-MIX | -21.07% (614) | -58.77% (650) | -58.15% (3,286) |
| S6-07-US | — | — | -59.07% (3,263) |
| S6-07-LON | -27.87% (613) | -61.69% (711) | — |

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

### S6-03-MIX -- FAIL

- Registered in commit `c89f2fd7202c`; bars: 1h; costs at 2x; out-of-sample 2024-02-01 to 2026-07-10
- Names: 49 (47 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +1.53% | 0.0049 | 0.21 | -3.12% |
| strategy, net at 2x costs | -28.37% | -0.0959 | -4.03 | -28.40% |
| strategy, net after survivorship mark-down | -28.43% | -0.0962 | -4.04 | -28.46% |
| strategy, net at 1x costs | -14.72% | -0.0486 | -2.04 | -15.54% |
| **benchmark VWRP.L** (same period) | **+50.70%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -28.37%, after -28.43% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 2099; bars: 9719; net mean per bar -0.00344% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar -0.1483 ± 0.0090)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.6820 ± 0.0115)
- Deflated Sharpe: 0.000 over 42 trials (luck ceiling 0.0255 per bar)
- Verdict: FAIL -- failed: a positive net mean per bar (-0.00344% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-28.43% vs +50.70%)

### S6-04-US -- FAIL

- Registered in commit `c89f2fd7202c`; bars: 1h; costs at 2x; out-of-sample 2024-02-01 to 2026-07-10
- Names: 30 (29 independent bets; 0 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | -5.29% | -0.0178 | -0.75 | -7.47% |
| strategy, net at 2x costs | -72.75% | -0.3436 | -14.43 | -72.75% |
| strategy, net after survivorship mark-down | -72.80% | -0.3441 | -14.45 | -72.81% |
| strategy, net at 1x costs | -49.18% | -0.2092 | -8.79 | -49.20% |
| **benchmark VWRP.L** (same period) | **+50.70%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -72.75%, after -72.80% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 4652; bars: 4249; net mean per bar -0.03060% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0249 (null Sharpe/bar -0.4056 ± 0.0268)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.6979 ± 0.0137)
- Deflated Sharpe: 0.000 over 42 trials (luck ceiling 0.0303 per bar)
- Verdict: FAIL -- failed: a positive net mean per bar (-0.03060% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-72.80% vs +50.70%)

### S6-04-LON -- FAIL

- Registered in commit `c89f2fd7202c`; bars: 1h; costs at 2x; out-of-sample 2024-02-12 to 2026-07-10
- Names: 19 (18 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | -0.29% | -0.0008 | -0.04 | -4.90% |
| strategy, net at 2x costs | -73.26% | -0.3636 | -15.27 | -73.26% |
| strategy, net after survivorship mark-down | -73.29% | -0.3638 | -15.28 | -73.29% |
| strategy, net at 1x costs | -48.35% | -0.2264 | -9.51 | -48.35% |
| **benchmark VWRP.L** (same period) | **+47.33%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -73.26%, after -73.29% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 3360; bars: 5470; net mean per bar -0.02411% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar -0.4452 ± 0.0208)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.9900 ± 0.0157)
- Deflated Sharpe: 0.000 over 42 trials (luck ceiling 0.0346 per bar)
- Verdict: FAIL -- failed: a positive net mean per bar (-0.02411% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-73.29% vs +47.33%)

### S6-04-MIX -- FAIL

- Registered in commit `c89f2fd7202c`; bars: 1h; costs at 2x; out-of-sample 2024-02-01 to 2026-07-10
- Names: 49 (47 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | -3.36% | -0.0109 | -0.46 | -5.16% |
| strategy, net at 2x costs | -72.92% | -0.3257 | -13.68 | -72.93% |
| strategy, net after survivorship mark-down | -72.97% | -0.3261 | -13.70 | -72.97% |
| strategy, net at 1x costs | -48.84% | -0.1987 | -8.34 | -48.85% |
| **benchmark VWRP.L** (same period) | **+50.70%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -72.92%, after -72.97% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 8012; bars: 9719; net mean per bar -0.01345% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar -0.3908 ± 0.0188)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.6820 ± 0.0115)
- Deflated Sharpe: 0.000 over 42 trials (luck ceiling 0.0255 per bar)
- Verdict: FAIL -- failed: a positive net mean per bar (-0.01345% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-72.97% vs +50.70%)

### S6-05-US -- FAIL

- Registered in commit `c89f2fd7202c`; bars: 1h; costs at 2x; out-of-sample 2024-02-01 to 2026-07-10
- Names: 30 (29 independent bets; 0 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | -6.73% | -0.0106 | -0.44 | -12.06% |
| strategy, net at 2x costs | -94.90% | -0.3959 | -16.63 | -94.90% |
| strategy, net after survivorship mark-down | -94.92% | -0.3966 | -16.66 | -94.92% |
| strategy, net at 1x costs | -78.17% | -0.2328 | -9.78 | -78.17% |
| **benchmark VWRP.L** (same period) | **+50.70%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -94.90%, after -94.92% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 10904; bars: 4249; net mean per bar -0.06997% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.2488 (null Sharpe/bar -0.4092 ± 0.0164)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.6979 ± 0.0137)
- Deflated Sharpe: 0.000 over 42 trials (luck ceiling 0.0303 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 0.2488 < 0.05); failed: a positive net mean per bar (-0.06997% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-94.92% vs +50.70%)

### S6-05-LON -- FAIL

- Registered in commit `c89f2fd7202c`; bars: 1h; costs at 2x; out-of-sample 2024-02-12 to 2026-07-10
- Names: 19 (18 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | -0.46% | -0.0012 | -0.05 | -5.24% |
| strategy, net at 2x costs | -87.54% | -0.4497 | -18.89 | -87.54% |
| strategy, net after survivorship mark-down | -87.57% | -0.4501 | -18.90 | -87.57% |
| strategy, net at 1x costs | -64.77% | -0.2919 | -12.26 | -64.77% |
| **benchmark VWRP.L** (same period) | **+47.33%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -87.54%, after -87.57% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 4892; bars: 5470; net mean per bar -0.03807% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar -0.5333 ± 0.0163)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.9900 ± 0.0157)
- Deflated Sharpe: 0.000 over 42 trials (luck ceiling 0.0346 per bar)
- Verdict: FAIL -- failed: a positive net mean per bar (-0.03807% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-87.57% vs +47.33%)

### S6-05-MIX -- FAIL

- Registered in commit `c89f2fd7202c`; bars: 1h; costs at 2x; out-of-sample 2024-02-01 to 2026-07-10
- Names: 49 (47 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | -4.25% | -0.0070 | -0.29 | -8.28% |
| strategy, net at 2x costs | -92.80% | -0.3500 | -14.70 | -92.80% |
| strategy, net after survivorship mark-down | -92.83% | -0.3504 | -14.72 | -92.83% |
| strategy, net at 1x costs | -73.74% | -0.2091 | -8.78 | -73.74% |
| **benchmark VWRP.L** (same period) | **+50.70%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -92.80%, after -92.83% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 15796; bars: 9719; net mean per bar -0.02708% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0348 (null Sharpe/bar -0.3706 ± 0.0115)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.6820 ± 0.0115)
- Deflated Sharpe: 0.000 over 42 trials (luck ceiling 0.0255 per bar)
- Verdict: FAIL -- failed: a positive net mean per bar (-0.02708% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-92.83% vs +50.70%)

### S6-06-US -- FAIL

- Registered in commit `c89f2fd7202c`; bars: 1h; costs at 2x; out-of-sample 2024-02-01 to 2026-07-10
- Names: 30 (29 independent bets; 0 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +1.46% | 0.0050 | 0.21 | -4.38% |
| strategy, net at 2x costs | -58.07% | -0.2535 | -10.65 | -58.08% |
| strategy, net after survivorship mark-down | -58.15% | -0.2540 | -10.67 | -58.16% |
| strategy, net at 1x costs | -34.77% | -0.1335 | -5.61 | -35.00% |
| **benchmark VWRP.L** (same period) | **+50.70%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -58.07%, after -58.15% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 3286; bars: 4249; net mean per bar -0.02046% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0796 (null Sharpe/bar -0.2898 ± 0.0225)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.6979 ± 0.0137)
- Deflated Sharpe: 0.000 over 42 trials (luck ceiling 0.0303 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 0.0796 < 0.05); failed: a positive net mean per bar (-0.02046% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-58.15% vs +50.70%)

### S6-06-LON -- FAIL

- Registered in commit `c89f2fd7202c`; bars: 1h; costs at 2x; out-of-sample 2024-02-12 to 2026-07-10
- Names: 19 (18 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +3.25% | 0.0146 | 0.61 | -1.62% |
| strategy, net at 2x costs | -44.90% | -0.2110 | -8.86 | -44.90% |
| strategy, net after survivorship mark-down | -44.94% | -0.2113 | -8.87 | -44.94% |
| strategy, net at 1x costs | -24.57% | -0.1181 | -4.96 | -24.57% |
| **benchmark VWRP.L** (same period) | **+47.33%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -44.90%, after -44.94% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 1264; bars: 5470; net mean per bar -0.01090% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar -0.2886 ± 0.0200)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.9900 ± 0.0157)
- Deflated Sharpe: 0.000 over 42 trials (luck ceiling 0.0346 per bar)
- Verdict: FAIL -- failed: a positive net mean per bar (-0.01090% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-44.94% vs +47.33%)

### S6-06-MIX -- FAIL

- Registered in commit `c89f2fd7202c`; bars: 1h; costs at 2x; out-of-sample 2024-02-01 to 2026-07-10
- Names: 49 (47 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +2.18% | 0.0071 | 0.30 | -2.85% |
| strategy, net at 2x costs | -53.42% | -0.2164 | -9.09 | -53.43% |
| strategy, net after survivorship mark-down | -53.49% | -0.2168 | -9.11 | -53.49% |
| strategy, net at 1x costs | -31.01% | -0.1150 | -4.83 | -31.11% |
| **benchmark VWRP.L** (same period) | **+50.70%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -53.42%, after -53.49% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 4550; bars: 9719; net mean per bar -0.00787% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0100 (null Sharpe/bar -0.2566 ± 0.0156)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.6820 ± 0.0115)
- Deflated Sharpe: 0.000 over 42 trials (luck ceiling 0.0255 per bar)
- Verdict: FAIL -- failed: a positive net mean per bar (-0.00787% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-53.49% vs +50.70%)

### S6-07-US -- FAIL

- Registered in commit `c89f2fd7202c`; bars: 1h; costs at 2x; out-of-sample 2024-02-01 to 2026-07-10
- Names: 30 (29 independent bets; 0 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | -1.31% | -0.0043 | -0.18 | -5.76% |
| strategy, net at 2x costs | -59.00% | -0.2853 | -11.98 | -59.00% |
| strategy, net after survivorship mark-down | -59.07% | -0.2858 | -12.01 | -59.07% |
| strategy, net at 1x costs | -36.38% | -0.1561 | -6.56 | -36.38% |
| **benchmark VWRP.L** (same period) | **+50.70%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -59.00%, after -59.07% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 3263; bars: 4249; net mean per bar -0.02100% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.5373 (null Sharpe/bar -0.2840 ± 0.0204)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.6979 ± 0.0137)
- Deflated Sharpe: 0.000 over 42 trials (luck ceiling 0.0303 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 0.5373 < 0.05); failed: a positive net mean per bar (-0.02100% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-59.07% vs +50.70%)

### S6-07-LON -- FAIL

- Registered in commit `c89f2fd7202c`; bars: 1h; costs at 2x; out-of-sample 2024-02-12 to 2026-07-10
- Names: 19 (18 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +0.17% | 0.0011 | 0.05 | -2.30% |
| strategy, net at 2x costs | -49.18% | -0.2693 | -11.31 | -49.28% |
| strategy, net after survivorship mark-down | -49.23% | -0.2696 | -11.32 | -49.32% |
| strategy, net at 1x costs | -28.65% | -0.1744 | -7.33 | -29.01% |
| **benchmark VWRP.L** (same period) | **+47.33%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -49.18%, after -49.23% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 1324; bars: 5470; net mean per bar -0.01238% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.1940 (null Sharpe/bar -0.2905 ± 0.0186)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.9900 ± 0.0157)
- Deflated Sharpe: 0.000 over 42 trials (luck ceiling 0.0346 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 0.1940 < 0.05); failed: a positive net mean per bar (-0.01238% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-49.23% vs +47.33%)

