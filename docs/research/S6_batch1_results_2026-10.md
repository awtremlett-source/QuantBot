# S6 batch 1 results, 2026-10 (QT-18: 8 same-day rules × 3 arms, 1-hour bars)

Run 1 of 1; **4 of 24 trials complete**; interrupted runs logged (counted 0): none. Every trial run exactly as registered (docs/research/preregistered.json, ids S6-01-US … S6-08-MIX); code commit and data fingerprints in docs/reports/QT-18_progress.md.

**Survived both gates (walk-forward PASS at 2× costs AND holdout PASS): none.**

How each trial is judged: net after 2× costs with the survivorship mark-down, compounded; 1× beside it; against VWRP's own hourly closes over the same dates. PASS needs all of: the turnover-matched luck test (p < 0.05) AND a positive net mean per bar; Deflated Sharpe ≥ 0.95 over N; a higher return than VWRP. INSUFFICIENT (under 30 out-of-sample trades) is its own answer, never a PASS. Brakes (P12) are NOT applied in back-tests; the maximum drawdown is shown instead.

**Read with care:** the P15 history rule lets the back-test always dodge the real results date. Live, a date can move, so share results are slightly optimistic (ETFs are not affected) -- most of all in the holdout, where each share's next date is the one first recorded on 2026-10-02, treated as known from its July/August results.

Trial count for deflation: **N = 42** (18 before + 24). qb2's trial log now counts 22 selection trials (38 drill and 0 holdout lines excluded). Trial runtime 20 minutes.

## The 24 trials

| id | arm | OOS dates | trades | net 1× | **net 2×** | VWRP same dates | max DD (2×) | p vs matched null | DSR (N) | verdict | holdout |
|---|---|---|---|---|---|---|---|---|---|---|---|
| S6-01-US | US | 2024-02-01 → 2026-07-10 | 8,851 | -71.69% | **-91.31%** | +50.70% | -91.31% | 0.005 | 0.000 (42) | **FAIL** | not run (no walk-forward PASS) |
| S6-01-LON | LON | 2024-02-12 → 2026-07-10 | 4,708 | -62.41% | **-85.15%** | +47.33% | -85.15% | 0.005 | 0.000 (42) | **FAIL** | not run (no walk-forward PASS) |
| S6-01-MIX | MIX | 2024-02-01 → 2026-07-10 | 13,559 | -68.42% | **-89.31%** | +50.70% | -89.31% | 0.005 | 0.000 (42) | **FAIL** | not run (no walk-forward PASS) |
| S6-02-US | US | 2024-02-01 → 2026-07-10 | 2,742 | -31.59% | **-52.68%** | +50.70% | -53.05% | 0.005 | 0.000 (42) | **FAIL** | not run (no walk-forward PASS) |

## Why each verdict

- **S6-01-US** FAIL: failed: a positive net mean per bar (-0.05740% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-91.31% vs +50.70%)
- **S6-01-LON** FAIL: failed: a positive net mean per bar (-0.03482% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-85.15% vs +47.33%)
- **S6-01-MIX** FAIL: failed: a positive net mean per bar (-0.02299% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-89.31% vs +50.70%)
- **S6-02-US** FAIL: failed: a positive net mean per bar (-0.01750% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-52.68% vs +50.70%)

## Per sleeve (net after 2× costs and mark-down, compounded)

> Per-year figures are not shown; per-sleeve figures are description only. Picking a sleeve, an arm or a year afterwards is a NEW trial that must be registered first.

> Description only. Picking a sleeve (or a market) because it looks better here would be a NEW trial: it must be registered, and counted, before it is run.

| id | uk_etf net 2× (trades) | uk_share net 2× (trades) | us_liquid net 2× (trades) |
|---|---|---|---|
| S6-01-US | — | — | -91.31% (8,851) |
| S6-01-LON | -76.97% (3,108) | -89.56% (1,600) | — |
| S6-01-MIX | -76.97% (3,108) | -89.56% (1,600) | -91.31% (8,851) |
| S6-02-US | — | — | -52.68% (2,742) |

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

