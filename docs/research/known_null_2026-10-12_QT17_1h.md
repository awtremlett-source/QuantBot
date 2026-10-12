# Known-null gate on 1-hour bars, 2026-10-12 (QT-17 A4, real clean store)

The gate proven on the bar size it judges (P17). Five drills registered alone first
(commit `983c700`), then run on the REAL clean store's unsealed 1-hour bars
(to 2026-07-10; sealed from 2026-07-13) of the agreed 50, on the QT-17 bench:
Gate 1 with its positive-mean half (A2), 1h fills two bars later, a bar held only
if it ends by the P4 cut-off, VWRP's own hourly closes as the benchmark (A1/A3),
and **P15 asked exactly as the sender asks it**. Brakes are not applied inside
back-tests; each drill's maximum drawdown is in its report below.

**What P15 did to this bench.** Every earnings date in the store was first recorded
on 2026-10-02 or later, so before then no share had a knowable date: the sender's
check blocks all 40 shares on every unsealed hour (30 US, 10 London). Only the 9
London ETFs with unsealed bars trade (VALL.L has none); the 40 shares' slots sit in
cash, equal weight per bet (47 bets). OOS 2024-02-01 → 2026-07-10, VWRP +50.70%.

## Red first, on deliberately broken code (nothing logged)

| breakage | drill | expected | got | luck p | net mean / bar | DSR | net (1×) | VWRP same dates | gate |
|---|---|---|---|---|---|---|---|---|---|
| delay removed | KN-INSTANT-1h | FAIL | **PASS** | 0.005 | +0.0128% | 1.000 | +245.02% | +50.70% | **RED** (as it must) |
| costs off | KN-PLANT-SMALL-1h | FAIL | **FAIL** — benchmark only | 0.005 | +0.0015% | 1.000 | +15.32% | +50.70% | **NOT RED: the expected PASS did not show** |
| *diagnostic, not a proof:* costs off, the 9 tradeable ETFs only | KN-PLANT-SMALL-1h | — | PASS | 0.005 | — | 1.000 | +130.49% | +47.33% | the cause: 40 blocked names in cash |

With costs off the below-cost drill clears the luck test, the positive mean and the
Deflated Sharpe — costs were what failed them — but on the full universe its gain is
spread over 47 bets of which 39 never trade (P15), so it trails VWRP. On the nine
names that can trade it passes. **By the box's rule this is a STOP:** the 1h bench,
with P15 as it stands, cannot show Gate 2 going red. S6 batch 1 was not registered.

## Honest code: Gate 1 GREEN · Gate 2 GREEN

| drill | costs | expected | got (failed checks) | OOS trades | luck p (matched) | coin-flip p (description) | net mean / bar | DSR (N 18) | net marked | VWRP | gate |
|---|---|---|---|---|---|---|---|---|---|---|---|
| KN-COIN-1h | 1× | FAIL | FAIL (luck, positive, dsr, benchmark) | 8,972 | 0.090 | 0.134 | −0.00337% | 0.000 | −27.93% | +50.70% | GREEN |
| KN-INSTANT-1h | 1× | FAIL | FAIL (positive, dsr, benchmark) | 5,137 | 0.005 | 0.005 | −0.01662% | 0.000 | −80.15% | +50.70% | GREEN |
| KN-LAZY-1h | 1× | FAIL, luck must fail | FAIL (luck, positive, dsr, benchmark) | 5,127 | 0.876 | 0.005 | −0.00194% | 0.000 | −17.22% | +50.70% | GREEN |
| KN-PLANT-1h | 1× | PASS | PASS | 5,104 | 0.005 | 0.005 | above 0 | 1.000 | +464.35% | +50.70% | GREEN |
| KN-PLANT-1h | 2× | PASS | PASS | 5,104 | 0.005 | 0.005 | above 0 | 1.000 | +365.80% | +50.70% | GREEN |
| KN-PLANT-SMALL-1h | 1× | FAIL | FAIL (positive, dsr, benchmark) | 5,104 | 0.005 | 0.005 | −0.00050% | 0.000 | −4.78% | +50.70% | GREEN |

Reading it:

- **Gate 1's new half works on the real store.** KN-INSTANT-1h and KN-PLANT-SMALL-1h
  both beat random timing on p alone (0.005) while losing money; the positive-mean
  half now fails them (A2). KN-INSTANT-5m, re-scored the same day like-for-like
  with QT-16 (P15 held off for that one run): p 0.005, −42.71%, 2,062 trades, now
  FAIL on positive, DSR and benchmark (VWRP 5m closes +2.62%).
- **The lazy drill fails the luck test itself** (p 0.876): the matched null is fair
  on hours too.
- FX: every held dollar bar had a rate — but no dollar line traded (P15).
- Logged as kind=drill (trial count unchanged at 18).

The six drill reports, as the gate wrote them (the "net mean per bar" and "Brakes"
lines were added to the report after this run):


## Gate 1 -- the worthless are rejected: GREEN

Expected FAIL, got FAIL (GREEN).

### KN-COIN-1h -- FAIL

- Registered in commit `983c700ec2c9`; bars: 1h; costs at 1x; out-of-sample 2024-02-01 to 2026-07-10
- Names: 49 (47 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +0.88% | 0.0068 | 0.29 | -1.34% |
| strategy, net at 1x costs | -27.93% | -0.2407 | -10.11 | -27.93% |
| strategy, net after survivorship mark-down | -27.93% | -0.2407 | -10.11 | -27.93% |
| **benchmark VWRP.L** (same period) | **+50.70%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -27.93%, after -27.93% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 8972; bars: 9719
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0896 (null Sharpe/bar -0.2613 ± 0.0171)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.1343 (null Sharpe/bar -0.2625 ± 0.0177)
- Deflated Sharpe: 0.000 over 18 trials (luck ceiling 0.0328 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 0.0896 < 0.05); failed: a positive net mean per bar (-0.00337% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-27.93% vs +50.70%)


Expected FAIL, got FAIL (GREEN).

### KN-INSTANT-1h -- FAIL

- Registered in commit `983c700ec2c9`; bars: 1h; costs at 1x; out-of-sample 2024-02-01 to 2026-07-10
- Names: 49 (47 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | -75.96% | -0.2565 | -10.77 | -75.96% |
| strategy, net at 1x costs | -80.15% | -0.2736 | -11.49 | -80.15% |
| strategy, net after survivorship mark-down | -80.15% | -0.2736 | -11.49 | -80.15% |
| **benchmark VWRP.L** (same period) | **+50.70%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -80.15%, after -80.15% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 5137; bars: 9719
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar -0.3075 ± 0.0085)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.3145 ± 0.0038)
- Deflated Sharpe: 0.000 over 18 trials (luck ceiling 0.0070 per bar)
- Verdict: FAIL -- failed: a positive net mean per bar (-0.01662% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-80.15% vs +50.70%)


Expected FAIL, got FAIL (GREEN).

### KN-LAZY-1h -- FAIL

- Registered in commit `983c700ec2c9`; bars: 1h; costs at 1x; out-of-sample 2024-02-01 to 2026-07-10
- Names: 49 (47 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +0.33% | 0.0041 | 0.17 | -0.79% |
| strategy, net at 1x costs | -17.22% | -0.2164 | -9.09 | -17.23% |
| strategy, net after survivorship mark-down | -17.22% | -0.2164 | -9.09 | -17.23% |
| **benchmark VWRP.L** (same period) | **+50.70%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -17.22%, after -17.22% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 5127; bars: 9719
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.8756 (null Sharpe/bar -0.1928 ± 0.0207)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.2625 ± 0.0177)
- Deflated Sharpe: 0.000 over 18 trials (luck ceiling 0.0328 per bar)
- Verdict: FAIL -- failed: beats the turnover-matched luck test (p 0.8756 < 0.05); failed: a positive net mean per bar (-0.00194% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-17.22% vs +50.70%)


## Gate 2 -- the exploitable passes after costs: GREEN

Expected PASS, got PASS (GREEN).

### KN-PLANT-1h -- PASS

- Registered in commit `983c700ec2c9`; bars: 1h; costs at 1x; out-of-sample 2024-02-01 to 2026-07-10
- Names: 49 (47 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +583.72% | 0.5369 | 22.55 | -0.26% |
| strategy, net at 1x costs | +464.35% | 0.4927 | 20.69 | -0.28% |
| strategy, net after survivorship mark-down | +464.35% | 0.4927 | 20.69 | -0.28% |
| **benchmark VWRP.L** (same period) | **+50.70%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before +464.35%, after +464.35% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 5104; bars: 9719
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar 0.2127 ± 0.0039)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar 0.0546 ± 0.0040)
- Deflated Sharpe: 1.000 over 18 trials (luck ceiling 0.0075 per bar)
- Verdict: PASS -- every check met


Expected PASS, got PASS (GREEN).

### KN-PLANT-1h -- PASS

- Registered in commit `983c700ec2c9`; bars: 1h; costs at 2x; out-of-sample 2024-02-01 to 2026-07-10
- Names: 49 (47 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +583.72% | 0.5369 | 22.55 | -0.26% |
| strategy, net at 2x costs | +365.80% | 0.4374 | 18.37 | -0.29% |
| strategy, net after survivorship mark-down | +365.80% | 0.4374 | 18.37 | -0.29% |
| strategy, net at 1x costs | +464.35% | 0.4927 | 20.69 | -0.28% |
| **benchmark VWRP.L** (same period) | **+50.70%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before +365.80%, after +365.80% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 5104; bars: 9719
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar 0.1590 ± 0.0037)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.0685 ± 0.0043)
- Deflated Sharpe: 1.000 over 18 trials (luck ceiling 0.0081 per bar)
- Verdict: PASS -- every check met


Expected FAIL, got FAIL (GREEN).

### KN-PLANT-SMALL-1h -- FAIL

- Registered in commit `983c700ec2c9`; bars: 1h; costs at 1x; out-of-sample 2024-02-01 to 2026-07-10
- Names: 49 (47 independent bets; 1 left out)

| | total return | Sharpe / bar | annualised | max drawdown |
|---|---|---|---|---|
| strategy, gross (no costs) | +15.32% | 0.1128 | 4.74 | -0.63% |
| strategy, net at 1x costs | -4.78% | -0.0363 | -1.52 | -5.10% |
| strategy, net after survivorship mark-down | -4.78% | -0.0363 | -1.52 | -5.10% |
| **benchmark VWRP.L** (same period) | **+50.70%** | | | |

- Benchmark: VWRP: Trading 212 VWRPl_EQ, ISIN IE00BK5BQT80, GBP, accumulating (Vanguard FTSE All-World (Acc)) (1h closes)
- Mark-down: before -4.78%, after -4.78% (survivorship mark-down: 1.0%/yr held on single shares, 0 on ETFs -- a starting figure from published averages, not measured on these names)
- Out-of-sample trades: 5104; bars: 9719
- Luck test (turnover-matched null: the rule's own trades at random times): p = 0.0050 (null Sharpe/bar -0.0757 ± 0.0046)
- Coin-flip null (description only -- it churns, so a slow rule beats it on costs): p = 0.0050 (null Sharpe/bar -0.2353 ± 0.0161)
- Deflated Sharpe: 0.000 over 18 trials (luck ceiling 0.0298 per bar)
- Verdict: FAIL -- failed: a positive net mean per bar (-0.00050% > 0); failed: Deflated Sharpe 0.000 >= 0.95; failed: beats the benchmark (-4.78% vs +50.70%)

