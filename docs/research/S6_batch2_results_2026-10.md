# S6 batch 2 results, 2026-10 (QT-27: the combined model — 2 models × 3 arms, 1-hour bars)

## In plain words (added by hand in QT-28; everything below it is written by cm_results from the run files)

- Run on Wed 28 Oct 2026, 21:59–22:12 UTC (QT-28), after the model's practice tests passed (its birth certificate
  v2: docs/research/known_null_2026-10-28_QT28_cm.md). Six trials, each counted for ever: **trial count N = 62**.
- **None of the six passed.** Nothing survives, so no holdout was run, nothing is wired to trade, and the bot stays off.
- **The simple straight-line model (ridge)** almost never found a forecast big enough to clear twice its costs: 10 to
  18 trades in two years per group of names. Too few to judge (INSUFFICIENT, the rule is at least 30). Those few trades
  made +0.14% to +1.04% after double costs, while the world index fund (VWRP) made +36.82% to +38.49% over the same dates.
- **The tree model (gbt)** traded more (92 to 193 trades) and **lost money after costs** in every group: −2.82% (US),
  −1.99% (London), −2.15% (both), at double costs; even at normal costs it lost 0.69% to 1.05%. Its forecasts ran well
  above what the trades then made (description only).
- How each is judged: after twice the real trading costs, against VWRP, through the luck test, the Deflated Sharpe at
  N = 62 and the benchmark — exactly as registered (6be96dad), with nothing changed after seeing a result.

Run 1 of 1; **6 of 6 trials complete**; interrupted runs logged (counted 0): none. Every trial run exactly as registered (docs/research/preregistered.json, commit 6be96dad, ids CM-L-US … CM-G-MIX). Code commit `bdd31fcad5b2`; data fingerprints (a) `ad36150c93b8…`, (b) `14a454fbe9d0…` (the agreed 50, GBPUSD and ^VIX).

**Survived both gates (walk-forward PASS at 2× costs AND holdout PASS): none.**

How each trial is judged — exactly as batch 1: net after 2× costs with the survivorship mark-down, compounded; 1× beside it; against VWRP's own hourly closes over the same dates. PASS needs all of: the turnover-matched luck test (p < 0.05) AND a positive net mean per bar; Deflated Sharpe ≥ 0.95 over N; a higher return than VWRP. INSUFFICIENT (under 30 out-of-sample trades) is its own answer, never a PASS. Graded window: the model's own out-of-sample sessions only. Brakes (P12) are NOT applied in back-tests; the maximum drawdown is shown instead.

**Read with care:** the P15 history rule lets the back-test always dodge the real results date (shares only). The model buys at most 3 bets a day per market, each holding 1/(the arm's bets) of the pot, the rest in cash (batch 1's equal weight per bet): even a real edge is diluted against a fully invested VWRP.

Trial count for deflation: **N = 62** (56 before + 6). qb2's trial log now counts 62 selection trials (78 drill and 0 holdout lines excluded). Trial runtime 13 minutes.

## The 6 trials

| id | arm | OOS dates | trades | net 1× | **net 2×** | VWRP same dates | max DD (2×) | p vs matched null | DSR (N) | verdict | holdout |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CM-L-US | US | 2024-06-18 → 2026-07-10 | 18 | +1.29% | **+1.04%** | +37.58% | -0.43% | — | — (—) | **INSUFFICIENT** | not run (no walk-forward PASS) |
| CM-L-LON | LON | 2024-06-19 → 2026-07-10 | 16 | +0.55% | **+0.37%** | +36.82% | -0.33% | — | — (—) | **INSUFFICIENT** | not run (no walk-forward PASS) |
| CM-L-MIX | MIX | 2024-06-14 → 2026-07-10 | 10 | +0.20% | **+0.14%** | +38.49% | -0.17% | — | — (—) | **INSUFFICIENT** | not run (no walk-forward PASS) |
| CM-G-US | US | 2024-06-18 → 2026-07-10 | 159 | -0.69% | **-2.82%** | +37.58% | -2.98% | 0.010 | 0.001 (62) | **FAIL** | not run (no walk-forward PASS) |
| CM-G-LON | LON | 2024-06-19 → 2026-07-10 | 92 | -1.05% | **-1.99%** | +36.82% | -2.19% | 0.070 | 0.000 (62) | **FAIL** | not run (no walk-forward PASS) |
| CM-G-MIX | MIX | 2024-06-14 → 2026-07-10 | 193 | -0.83% | **-2.15%** | +38.49% | -2.39% | 0.015 | 0.000 (62) | **FAIL** | not run (no walk-forward PASS) |

## Why each verdict

- **CM-L-US** INSUFFICIENT: one bar carries 27% of the result's variance (more than 25%): a result made by one bar is not judged; only 18 out-of-sample trades (need 30)
- **CM-L-LON** INSUFFICIENT: only 16 out-of-sample trades (need 30)
- **CM-L-MIX** INSUFFICIENT: only 10 out-of-sample trades (need 30)
- **CM-G-US** FAIL: failed: a positive net mean per bar (-0.00079% > 0); failed: Deflated Sharpe 0.001 >= 0.95; failed: beats the benchmark (-2.82% vs +37.58%)
- **CM-G-LON** FAIL: failed: beats the turnover-matched luck test (p 0.0697 < 0.05); failed: a positive net mean per bar (-0.00043% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-1.99% vs +36.82%)
- **CM-G-MIX** FAIL: failed: a positive net mean per bar (-0.00026% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-2.15% vs +38.49%)

## What the model did (description only, never judged)

> Calibration is description only: a forecast that runs above what was realised is an over-confident model. It is not a verdict and choosing a model or an arm from it is a NEW trial.

| id | model | out-of-sample sessions | rows dropped (a feature missing) | lines picked | P15 refused | lines bought | days traded | days in cash | mean forecast (bought) | mean realised gross (bought) |
|---|---|---|---|---|---|---|---|---|---|---|
| CM-L-US | ridge | 516 (2024-06-18 → 2026-07-10) | 841 | 21 | 3 | 18 | 14 | 502 | +0.955% | +2.585% |
| CM-L-LON | ridge | 521 (2024-06-19 → 2026-07-10) | 3,607 | 16 | 0 | 16 | 10 | 511 | +0.511% | +0.809% |
| CM-L-MIX | ridge | 533 (2024-06-14 → 2026-07-10) | 4,448 | 12 | 2 | 10 | 8 | 525 | +0.706% | +1.194% |
| CM-G-US | gbt | 516 (2024-06-18 → 2026-07-10) | 841 | 186 | 27 | 159 | 82 | 434 | +1.072% | +0.273% |
| CM-G-LON | gbt | 521 (2024-06-19 → 2026-07-10) | 3,607 | 93 | 1 | 92 | 52 | 469 | +0.573% | -0.034% |
| CM-G-MIX | gbt | 533 (2024-06-14 → 2026-07-10) | 4,448 | 216 | 16 | 200 | 82 | 451 | +0.916% | +0.125% |

## Per sleeve (net after 2× costs and mark-down, compounded)

> Per-sleeve figures are description only. **Picking a sleeve, an arm, a model or a year afterwards is a NEW trial** that must be registered first.

> Description only. Picking a sleeve (or a market) because it looks better here would be a NEW trial: it must be registered, and counted, before it is run.

| id | uk_etf net 2× (trades) | uk_share net 2× (trades) | us_liquid net 2× (trades) |
|---|---|---|---|
| CM-L-US | — | — | +1.04% (18) |
| CM-L-LON | +0.83% (16) | +0.00% (0) | — |
| CM-L-MIX | +0.19% (6) | +0.00% (0) | +0.17% (4) |
| CM-G-US | — | — | -2.82% (159) |
| CM-G-LON | -4.44% (92) | +0.00% (0) | — |
| CM-G-MIX | -4.76% (65) | +0.00% (0) | -2.16% (128) |

## Appendix: each trial's firewall report

### CM-L-US -- INSUFFICIENT

- Registered in commit `787d4a2788a9`; bars: 1h; costs at 2x; out-of-sample 2024-06-18 to 2026-07-10
- Names: 30 (29 independent bets; 0 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +1.54% | 0.0268 | 1.13 | -0.28% |
| strategy, net at 2x costs | +1.04% | 0.0182 | 0.77 | -0.43% |
| strategy, net after survivorship mark-down | +1.04% | 0.0182 | 0.77 | -0.43% |
| strategy, net at 1x costs | +1.29% | 0.0226 | 0.95 | -0.34% |
| **benchmark VWRP.L** (same period) | **+37.58%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before +1.04%, after +1.04% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 18; bars: 3588; net mean per bar +0.00029% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Verdict: INSUFFICIENT -- one bar carries 27% of the result's variance (more than 25%): a result made by one bar is not judged; only 18 out-of-sample trades (need 30)

### CM-L-LON -- INSUFFICIENT

- Registered in commit `787d4a2788a9`; bars: 1h; costs at 2x; out-of-sample 2024-06-19 to 2026-07-10
- Names: 19 (18 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +0.73% | 0.0156 | 0.65 | -0.27% |
| strategy, net at 2x costs | +0.37% | 0.0079 | 0.33 | -0.33% |
| strategy, net after survivorship mark-down | +0.37% | 0.0079 | 0.33 | -0.33% |
| strategy, net at 1x costs | +0.55% | 0.0117 | 0.49 | -0.30% |
| **benchmark VWRP.L** (same period) | **+36.82%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before +0.37%, after +0.37% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 16; bars: 4678; net mean per bar +0.00008% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Verdict: INSUFFICIENT -- only 16 out-of-sample trades (need 30)

### CM-L-MIX -- INSUFFICIENT

- Registered in commit `787d4a2788a9`; bars: 1h; costs at 2x; out-of-sample 2024-06-14 to 2026-07-10
- Names: 49 (47 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +0.26% | 0.0107 | 0.45 | -0.14% |
| strategy, net at 2x costs | +0.14% | 0.0057 | 0.24 | -0.17% |
| strategy, net after survivorship mark-down | +0.14% | 0.0056 | 0.24 | -0.17% |
| strategy, net at 1x costs | +0.20% | 0.0082 | 0.34 | -0.16% |
| **benchmark VWRP.L** (same period) | **+38.49%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before +0.14%, after +0.14% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 10; bars: 8307; net mean per bar +0.00002% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Verdict: INSUFFICIENT -- only 10 out-of-sample trades (need 30)

### CM-G-US -- FAIL

- Registered in commit `787d4a2788a9`; bars: 1h; costs at 2x; out-of-sample 2024-06-18 to 2026-07-10
- Names: 30 (29 independent bets; 0 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +1.50% | 0.0140 | 0.59 | -0.84% |
| strategy, net at 2x costs | -2.81% | -0.0259 | -1.09 | -2.97% |
| strategy, net after survivorship mark-down | -2.82% | -0.0260 | -1.09 | -2.98% |
| strategy, net at 1x costs | -0.68% | -0.0061 | -0.26 | -1.63% |
| **benchmark VWRP.L** (same period) | **+37.58%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -2.81%, after -2.82% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 159; bars: 3588; net mean per bar -0.00079% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0100 (null Sharpe/bar -0.0741 ± 0.0172)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.6724 ± 0.0144)
- Deflated Sharpe: 0.001 over 62 trials (luck ceiling 0.0340 per bar)
- Verdict: FAIL -- failed: a positive net mean per bar (-0.00079% > 0); failed: Deflated Sharpe 0.001 >= 0.95; failed: beats the benchmark (-2.82% vs +37.58%)

### CM-G-LON -- FAIL

- Registered in commit `787d4a2788a9`; bars: 1h; costs at 2x; out-of-sample 2024-06-19 to 2026-07-10
- Names: 19 (18 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | -0.10% | -0.0014 | -0.06 | -1.08% |
| strategy, net at 2x costs | -1.99% | -0.0290 | -1.22 | -2.19% |
| strategy, net after survivorship mark-down | -1.99% | -0.0290 | -1.22 | -2.19% |
| strategy, net at 1x costs | -1.05% | -0.0154 | -0.65 | -1.62% |
| **benchmark VWRP.L** (same period) | **+36.82%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -1.99%, after -1.99% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 92; bars: 4678; net mean per bar -0.00043% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0697 (null Sharpe/bar -0.0532 ± 0.0146)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.9791 ± 0.0177)
- Deflated Sharpe: 0.000 over 62 trials (luck ceiling 0.0417 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 0.0697 < 0.05); failed: a positive net mean per bar (-0.00043% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-1.99% vs +36.82%)

### CM-G-MIX -- FAIL

- Registered in commit `787d4a2788a9`; bars: 1h; costs at 2x; out-of-sample 2024-06-14 to 2026-07-10
- Names: 49 (47 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +0.52% | 0.0055 | 0.23 | -0.82% |
| strategy, net at 2x costs | -2.14% | -0.0223 | -0.94 | -2.39% |
| strategy, net after survivorship mark-down | -2.15% | -0.0224 | -0.94 | -2.39% |
| strategy, net at 1x costs | -0.82% | -0.0086 | -0.36 | -1.31% |
| **benchmark VWRP.L** (same period) | **+38.49%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -2.14%, after -2.15% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 193; bars: 8307; net mean per bar -0.00026% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0149 (null Sharpe/bar -0.0528 ± 0.0121)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.6637 ± 0.0120)
- Deflated Sharpe: 0.000 over 62 trials (luck ceiling 0.0284 per bar)
- Verdict: FAIL -- failed: a positive net mean per bar (-0.00026% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-2.15% vs +38.49%)

