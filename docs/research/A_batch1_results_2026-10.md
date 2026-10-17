# S9 advisor batch 1 — results, 2026-10 (built QT-19, run QT-21)

Run 1; 6 of 6 trials complete; register commit `accc44b`. Every trial run exactly as registered (docs/research/preregistered.json).

**Survived (walk-forward PASS and holdout PASS): none.**

Judged on net after 2× costs with the survivorship mark-down and dividends credited, compounded, against D3 over the same dates (VWRP; VWRL with dividends before VWRP's first traded close, 2019-08-13 since QT-21). PASS needs the luck test (p < 0.05) and a positive net mean, Deflated Sharpe ≥ 0.95 at N = 48 (luck bar from random-rank books), and beating D3; one bar over 25% of the variance = INSUFFICIENT. Dividends: 4,751 payouts credited; 8 not credited (SUSPECT or UNCHECKED).

| id | rule | trades | gross | net 1× | **net 2×** | D3 same dates | max DD | p (matched) | DSR (N) | biggest bar | verdict | holdout | turnover/yr | avg hold | stopped < 1 month |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A-01 | Momentum 12-1: rank by the 12-month return skipping the latest month | 2,213 | +201.44% | +85.62% | **+24.73%** | +265.07% | -34.97% | 1.000 | 0.469 (48) | 1.3% | **FAIL** | not run | +636.99% | 44 days | 42.0% |
| A-02 | Momentum 6-1: rank by the 6-month return skipping the latest month | 2,458 | +199.15% | +75.56% | **+12.38%** | +265.07% | -32.77% | 1.000 | 0.364 (48) | 1.0% | **FAIL** | not run | +702.42% | 39 days | 42.5% |
| A-03 | Risk-adjusted momentum: A-01's return / its 12-month daily volatility | 2,178 | +220.36% | +99.08% | **+34.84%** | +265.07% | -27.50% | 1.000 | 0.571 (48) | 1.1% | **FAIL** | not run | +627.16% | 45 days | 40.7% |
| A-04 | Near the 52-week high: rank by close / the 52-week high | 2,240 | +155.91% | +57.34% | **+5.37%** | +265.07% | -21.27% | 1.000 | 0.305 (48) | 1.3% | **FAIL** | not run | +645.58% | 44 days | 41.7% |
| A-05 | Low volatility: rank by the LOWEST 1-year daily volatility | 1,943 | +113.92% | +42.05% | **+2.07%** | +265.07% | -22.62% | 1.000 | 0.257 (48) | 2.0% | **FAIL** | not run | +560.19% | 50 days | 40.9% |
| A-06 | Momentum 12-1 with a market filter: A-01, but only when VWRP closes above its 200-day average | 1,787 | +141.85% | +64.24% | **+19.49%** | +265.07% | -33.51% | 1.000 | 0.447 (48) | 1.0% | **FAIL** | not run | +513.92% | 43 days | 39.7% |

## US / London split (net 2×)

> Description only. Choosing the US or London half because it looks better here would be a NEW trial: registered, and counted, before it is run.

| id | US net 2× (trades) | London net 2× (trades) |
|---|---|---|
| A-01 | +45.25% (1,173) | -14.12% (1,040) |
| A-02 | +29.37% (1,229) | -13.13% (1,229) |
| A-03 | +42.82% (1,098) | -5.59% (1,080) |
| A-04 | +29.30% (1,058) | -18.51% (1,182) |
| A-05 | +6.68% (849) | -4.33% (1,094) |
| A-06 | +33.35% (981) | -10.40% (806) |

## The book, per trial

| id | stopped | P13 re-justified | 1% ceiling binds (held name-days) | months in cash (A-06) | buys | P15 warning: results within 5 days | date unknown |
|---|---|---|---|---|---|---|---|
| A-01 | 1,967 | 0 | 0.01% | 0 | 2,213 | 96 | 779 |
| A-02 | 2,033 | 0 | 0.00% | 0 | 2,482 | 115 | 887 |
| A-03 | 1,934 | 0 | 0.00% | 0 | 2,178 | 84 | 810 |
| A-04 | 1,880 | 0 | 0.00% | 0 | 2,240 | 70 | 853 |
| A-05 | 1,895 | 0 | 0.00% | 0 | 1,943 | 56 | 725 |
| A-06 | 1,509 | 0 | 0.02% | 43 | 1,787 | 74 | 617 |

## The luck bar, two ways (SR0 at N; DSR uses (i))

(i) random-rank books built by the trial's own rules: how far skill-free books sit from each other on the one shared history. (ii) DESCRIPTION ONLY, one book's own Sharpe noise from its moments: the noise the PSR already charges in its denominator, so (ii) is expected to be the larger.

| id | Sharpe/bar (2×) | SR0 (i) random-rank | SR0 (ii) analytic |
|---|---|---|---|
| A-01 | 0.0099 | 0.0109 | 0.0298 |
| A-02 | 0.0065 | 0.0111 | 0.0297 |
| A-03 | 0.0133 | 0.0109 | 0.0298 |
| A-04 | 0.0043 | 0.0109 | 0.0297 |
| A-05 | 0.0027 | 0.0113 | 0.0297 |
| A-06 | 0.0092 | 0.0109 | 0.0297 |

## Why each did not pass

- **A-01**: failed: beats the turnover-matched luck test (p 1.0000 < 0.05); failed: Deflated Sharpe 0.469 >= 0.95; failed: beats the benchmark (+24.73% vs +265.07%)
- **A-02**: failed: beats the turnover-matched luck test (p 1.0000 < 0.05); failed: Deflated Sharpe 0.364 >= 0.95; failed: beats the benchmark (+12.38% vs +265.07%)
- **A-03**: failed: beats the turnover-matched luck test (p 1.0000 < 0.05); failed: Deflated Sharpe 0.571 >= 0.95; failed: beats the benchmark (+34.84% vs +265.07%)
- **A-04**: failed: beats the turnover-matched luck test (p 1.0000 < 0.05); failed: Deflated Sharpe 0.305 >= 0.95; failed: beats the benchmark (+5.37% vs +265.07%)
- **A-05**: failed: beats the turnover-matched luck test (p 1.0000 < 0.05); failed: Deflated Sharpe 0.257 >= 0.95; failed: beats the benchmark (+2.07% vs +265.07%)
- **A-06**: failed: beats the turnover-matched luck test (p 1.0000 < 0.05); failed: Deflated Sharpe 0.447 >= 0.95; failed: beats the benchmark (+19.49% vs +265.07%)

## A-01 — firewall report

### A-01 -- FAIL

- Registered in commit `accc44b2678b`; bars: 1d; costs at 2x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +201.44% | 0.0394 | 0.62 | -23.30% |
| strategy, net at 2x costs | +36.19% | 0.0128 | 0.20 | -33.69% |
| strategy, net after survivorship mark-down | +24.73% | 0.0099 | 0.16 | -34.97% |
| strategy, net at 1x costs | +102.67% | 0.0261 | 0.41 | -27.47% |
| **benchmark VWRP.L** (same period) | **+265.07%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-08-13 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +36.19%, after +24.73% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 2213; bars: 5815; net mean per bar +0.00515% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 1.0000 (null Sharpe/bar 0.0332 ± 0.0046)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.0081 ± 0.0048)
- Pounds: 941 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 0.469 over 48 trials (luck ceiling 0.0109 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 1.0000 < 0.05); failed: Deflated Sharpe 0.469 >= 0.95; failed: beats the benchmark (+24.73% vs +265.07%)


## A-02 — firewall report

### A-02 -- FAIL

- Registered in commit `accc44b2678b`; bars: 1d; costs at 2x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +199.15% | 0.0401 | 0.64 | -23.84% |
| strategy, net at 2x costs | +22.67% | 0.0095 | 0.15 | -30.82% |
| strategy, net after survivorship mark-down | +12.38% | 0.0065 | 0.10 | -32.77% |
| strategy, net at 1x costs | +91.63% | 0.0248 | 0.39 | -25.20% |
| **benchmark VWRP.L** (same period) | **+265.07%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-08-13 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +22.67%, after +12.38% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 2458; bars: 5815; net mean per bar +0.00328% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 1.0000 (null Sharpe/bar 0.0269 ± 0.0054)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.0078 ± 0.0049)
- Pounds: 850 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 0.364 over 48 trials (luck ceiling 0.0111 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 1.0000 < 0.05); failed: Deflated Sharpe 0.364 >= 0.95; failed: beats the benchmark (+12.38% vs +265.07%)


## A-03 — firewall report

### A-03 -- FAIL

- Registered in commit `accc44b2678b`; bars: 1d; costs at 2x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +220.36% | 0.0453 | 0.72 | -19.15% |
| strategy, net at 2x costs | +47.04% | 0.0165 | 0.26 | -26.41% |
| strategy, net after survivorship mark-down | +34.84% | 0.0133 | 0.21 | -27.50% |
| strategy, net at 1x costs | +117.09% | 0.0309 | 0.49 | -20.21% |
| **benchmark VWRP.L** (same period) | **+265.07%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-08-13 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +47.04%, after +34.84% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 2178; bars: 5815; net mean per bar +0.00624% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 1.0000 (null Sharpe/bar 0.0318 ± 0.0052)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.0081 ± 0.0048)
- Pounds: 866 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 0.571 over 48 trials (luck ceiling 0.0109 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 1.0000 < 0.05); failed: Deflated Sharpe 0.571 >= 0.95; failed: beats the benchmark (+34.84% vs +265.07%)


## A-04 — firewall report

### A-04 -- FAIL

- Registered in commit `accc44b2678b`; bars: 1d; costs at 2x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +155.91% | 0.0430 | 0.68 | -14.66% |
| strategy, net at 2x costs | +14.84% | 0.0080 | 0.13 | -19.92% |
| strategy, net after survivorship mark-down | +5.37% | 0.0043 | 0.07 | -21.27% |
| strategy, net at 1x costs | +71.48% | 0.0254 | 0.40 | -17.24% |
| **benchmark VWRP.L** (same period) | **+265.07%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-08-13 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +14.84%, after +5.37% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 2240; bars: 5815; net mean per bar +0.00170% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 1.0000 (null Sharpe/bar 0.0248 ± 0.0049)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.0081 ± 0.0048)
- Pounds: 862 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 0.305 over 48 trials (luck ceiling 0.0109 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 1.0000 < 0.05); failed: Deflated Sharpe 0.305 >= 0.95; failed: beats the benchmark (+5.37% vs +265.07%)


## A-05 — firewall report

### A-05 -- FAIL

- Registered in commit `accc44b2678b`; bars: 1d; costs at 2x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +113.92% | 0.0402 | 0.64 | -12.28% |
| strategy, net at 2x costs | +10.48% | 0.0067 | 0.11 | -21.02% |
| strategy, net after survivorship mark-down | +2.07% | 0.0027 | 0.04 | -22.62% |
| strategy, net at 1x costs | +53.76% | 0.0235 | 0.37 | -15.85% |
| **benchmark VWRP.L** (same period) | **+265.07%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-08-13 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +10.48%, after +2.07% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 1943; bars: 5815; net mean per bar +0.00094% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 1.0000 (null Sharpe/bar 0.0183 ± 0.0037)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0249 (null Sharpe/bar -0.0076 ± 0.0050)
- Pounds: 717 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 0.257 over 48 trials (luck ceiling 0.0113 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 1.0000 < 0.05); failed: Deflated Sharpe 0.257 >= 0.95; failed: beats the benchmark (+2.07% vs +265.07%)


## A-06 — firewall report

### A-06 -- FAIL

- Registered in commit `accc44b2678b`; bars: 1d; costs at 2x; out-of-sample 2014-03-28 to 2025-10-09
- Names: 170 (170 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +141.85% | 0.0370 | 0.59 | -22.45% |
| strategy, net at 2x costs | +28.06% | 0.0119 | 0.19 | -32.47% |
| strategy, net after survivorship mark-down | +19.49% | 0.0092 | 0.15 | -33.51% |
| strategy, net at 1x costs | +76.02% | 0.0245 | 0.39 | -27.57% |
| **benchmark VWRP.L** (same period) | **+265.07%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)); before 2019-08-13 (VWRP's first close) VWRL.L with its dividends added back, chained there
- Mark-down: before +28.06%, after +19.49% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 1787; bars: 5815; net mean per bar +0.00402% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 1.0000 (null Sharpe/bar 0.0334 ± 0.0056)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.0081 ± 0.0048)
- Pounds: 770 held dollar bar(s) took the previous GBPUSD bar (within pounds.TOLERANCE)
- Deflated Sharpe: 0.447 over 48 trials (luck ceiling 0.0109 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 1.0000 < 0.05); failed: Deflated Sharpe 0.447 >= 0.95; failed: beats the benchmark (+19.49% vs +265.07%)

