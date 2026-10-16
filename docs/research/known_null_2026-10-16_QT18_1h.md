# Known-null gate on 1-hour bars, 2026-10-16 (QT-18 A3, real clean store, P15 history)

QT-17's six registered 1h drill runs (commit `983c700`; no new registration), re-run
on the REAL clean store's unsealed 1-hour bars (OOS 2024-02-01 → 2026-07-10) with
**P15 asked through the history rule** (operator GO 2026-10-16, qb2/research/p15_history.py):
a results date is known from the close of the one before it. 42 of 47 bets can now
trade; the stale five (RR.L, GLEN.L, RIO.L, AAL.L, ULVR.L) stay blocked as missing
quarters. Brakes are not applied inside back-tests. Honest runs logged kind=drill
(counted 0); the red-firsts were run on deliberately broken code and logged nowhere
(their figures: known_null_2026-10-16_QT18_1h_redfirst.json; the script:
docs/reports/QT-18_a3_known_null.py.txt).

## Red first, on deliberately broken code (nothing logged)

| breakage | drill | expected | got | luck p | DSR | trades | net (1×) | VWRP same dates | gate |
|---|---|---|---|---|---|---|---|---|---|
| delay removed | KN-INSTANT-1h | PASS (red) | **PASS** | 0.005 | 1.000 | 24,917 | +23,560% | +50.70% | **RED** ✓ |
| costs off | KN-PLANT-SMALL-1h | PASS (red) | **PASS** | 0.005 | 1.000 | 24,688 | +343.1% | +50.70% | **RED** ✓ (QT-17: did not show) |

Gate 2's red-first now shows: with 42 of 47 bets able to trade, the below-cost
drill beats VWRP once its costs are removed. QT-17's failure was P15's cash.

## Honest code: Gate 1 GREEN · Gate 2 GREEN

| drill | costs | expected | got (failed checks) | OOS trades | luck p (matched) | net marked | VWRP | gate |
|---|---|---|---|---|---|---|---|---|
| KN-COIN-1h | 1× | FAIL | FAIL (luck, positive, dsr, benchmark) | 34,988 | 0.488 | −93.80% | +50.70% | GREEN |
| KN-INSTANT-1h | 1× | FAIL | FAIL (positive, dsr, benchmark) | 24,742 | 0.005 | −99.99% | +50.70% | GREEN |
| KN-LAZY-1h | 1× | FAIL, luck must fail | FAIL (luck, positive, dsr, benchmark) | 20,331 | 0.239 | −79.62% | +50.70% | GREEN |
| KN-PLANT-1h | 1× | PASS | PASS | 24,688 | 0.005 | +327,211% | +50.70% | GREEN |
| KN-PLANT-1h | 2× | PASS | PASS | 24,688 | 0.005 | +44,211% | +50.70% | GREEN |
| KN-PLANT-SMALL-1h | 1× | FAIL | FAIL (positive, dsr, benchmark) | 24,688 | 0.005 | −39.79% | +50.70% | GREEN |

The planted drills' huge figures are a planted trend in every session, compounded
over 2½ years: a measuring instrument, not a result. The bench tells luck from an
edge on hours, both ways. Gate run 48 min; red-firsts 21 min (store load included).

The six drill reports, as the gate wrote them:


## Gate 1 -- the worthless are rejected: GREEN

Expected FAIL, got FAIL (GREEN).

### KN-COIN-1h -- FAIL

- Registered in commit `983c700ec2c9`; bars: 1h; costs at 1x; out-of-sample 2024-02-01 to 2026-07-10
- Names: 49 (47 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +4.05% | 0.0062 | 0.26 | -6.10% |
| strategy, net at 1x costs | -93.77% | -0.3891 | -16.34 | -93.78% |
| strategy, net after survivorship mark-down | -93.80% | -0.3897 | -16.37 | -93.81% |
| **benchmark VWRP.L** (same period) | **+50.70%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -93.77%, after -93.80% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 34988; bars: 9719; net mean per bar -0.02859% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.4876 (null Sharpe/bar -0.3894 ± 0.0084)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.5423 (null Sharpe/bar -0.3883 ± 0.0092)
- Deflated Sharpe: 0.000 over 18 trials (luck ceiling 0.0170 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 0.4876 < 0.05); failed: a positive net mean per bar (-0.02859% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-93.80% vs +50.70%)


Expected FAIL, got FAIL (GREEN).

### KN-INSTANT-1h -- FAIL

- Registered in commit `983c700ec2c9`; bars: 1h; costs at 1x; out-of-sample 2024-02-01 to 2026-07-10
- Names: 49 (47 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | -99.94% | -0.3363 | -14.13 | -99.94% |
| strategy, net at 1x costs | -99.99% | -0.3788 | -15.91 | -99.99% |
| strategy, net after survivorship mark-down | -99.99% | -0.3788 | -15.91 | -99.99% |
| **benchmark VWRP.L** (same period) | **+50.70%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -99.99%, after -99.99% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 24742; bars: 9719; net mean per bar -0.09569% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar -0.5096 ± 0.0053)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.4786 ± 0.0039)
- Deflated Sharpe: 0.000 over 18 trials (luck ceiling 0.0072 per bar)
- Verdict: FAIL -- failed: a positive net mean per bar (-0.09569% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-99.99% vs +50.70%)


Expected FAIL, got FAIL (GREEN).

### KN-LAZY-1h -- FAIL

- Registered in commit `983c700ec2c9`; bars: 1h; costs at 1x; out-of-sample 2024-02-01 to 2026-07-10
- Names: 49 (47 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +5.51% | 0.0111 | 0.46 | -4.59% |
| strategy, net at 1x costs | -79.56% | -0.3069 | -12.89 | -79.56% |
| strategy, net after survivorship mark-down | -79.62% | -0.3075 | -12.92 | -79.63% |
| **benchmark VWRP.L** (same period) | **+50.70%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -79.56%, after -79.62% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 20331; bars: 9719; net mean per bar -0.01635% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.2388 (null Sharpe/bar -0.3182 ± 0.0122)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.3883 ± 0.0092)
- Deflated Sharpe: 0.000 over 18 trials (luck ceiling 0.0170 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 0.2388 < 0.05); failed: a positive net mean per bar (-0.01635% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-79.62% vs +50.70%)


## Gate 2 -- the exploitable passes after costs: GREEN

Expected PASS, got PASS (GREEN).

### KN-PLANT-1h -- PASS

- Registered in commit `983c700ec2c9`; bars: 1h; costs at 1x; out-of-sample 2024-02-01 to 2026-07-10
- Names: 49 (47 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +2434408.04% | 0.5950 | 24.99 | -2.33% |
| strategy, net at 1x costs | +330129.76% | 0.4684 | 19.67 | -2.55% |
| strategy, net after survivorship mark-down | +327210.52% | 0.4680 | 19.66 | -2.55% |
| **benchmark VWRP.L** (same period) | **+50.70%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before +330129.76%, after +327210.52% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 24688; bars: 9719; net mean per bar +0.08347% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar 0.3696 ± 0.0011)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar 0.1654 ± 0.0036)
- Deflated Sharpe: 1.000 over 18 trials (luck ceiling 0.0067 per bar)
- Verdict: PASS -- every check met


Expected PASS, got PASS (GREEN).

### KN-PLANT-1h -- PASS

- Registered in commit `983c700ec2c9`; bars: 1h; costs at 2x; out-of-sample 2024-02-01 to 2026-07-10
- Names: 49 (47 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +2434408.04% | 0.5950 | 24.99 | -2.33% |
| strategy, net at 2x costs | +44605.60% | 0.3309 | 13.90 | -2.86% |
| strategy, net after survivorship mark-down | +44210.54% | 0.3305 | 13.88 | -2.86% |
| strategy, net at 1x costs | +330129.76% | 0.4684 | 19.67 | -2.55% |
| **benchmark VWRP.L** (same period) | **+50.70%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before +44605.60%, after +44210.54% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 24688; bars: 9719; net mean per bar +0.06290% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar 0.2456 ± 0.0010)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.1551 ± 0.0047)
- Deflated Sharpe: 1.000 over 18 trials (luck ceiling 0.0087 per bar)
- Verdict: PASS -- every check met


Expected FAIL, got FAIL (GREEN).

### KN-PLANT-SMALL-1h -- FAIL

- Registered in commit `983c700ec2c9`; bars: 1h; costs at 1x; out-of-sample 2024-02-01 to 2026-07-10
- Names: 49 (47 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +347.07% | 0.1183 | 4.97 | -3.96% |
| strategy, net at 1x costs | -39.25% | -0.0370 | -1.55 | -40.46% |
| strategy, net after survivorship mark-down | -39.79% | -0.0376 | -1.58 | -40.98% |
| **benchmark VWRP.L** (same period) | **+50.70%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -39.25%, after -39.79% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 24688; bars: 9719; net mean per bar -0.00513% (Gate 1 needs it above zero)
- Brakes (P12) are a live safety layer and are NOT applied inside back-tests (QT-17 A3): the maximum drawdown above stands in for them
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar -0.0546 ± 0.0005)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.3108 ± 0.0081)
- Deflated Sharpe: 0.000 over 18 trials (luck ceiling 0.0149 per bar)
- Verdict: FAIL -- failed: a positive net mean per bar (-0.00513% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-39.79% vs +50.70%)

