# Known-null gate for the combined model, 2026-10-28 (QT-27 E: LON arm, real clean store)

Drills registered with the six trials (commit 6be96dad), run through the trials' own code (cm_arm.score -> the unchanged firewall). Honest runs logged kind=drill (counted 0); red-firsts on deliberately broken code, logged nowhere (docs/reports/QT-27_e3_redfirst.py.txt).

## Honest code: Gate 1 RED · Gate 2 RED

| drill | model | costs | verdict (failed checks) | OOS trades | luck p | net mean / bar | net | VWRP | gate |
|---|---|---|---|---|---|---|---|---|---|
| KN-CM-NULL | ridge | 1× | **INSUFFICIENT** (—) | 7 | — | +0.00001% | +0.06% | +36.82% | GREEN |
| KN-CM-NULL | ridge | 2× | **INSUFFICIENT** (—) | 7 | — | -0.00000% | -0.00% | +36.82% | GREEN |
| KN-CM-NULL | gbt | 1× | **INSUFFICIENT** (—) | 137 | 0.020 | -0.00017% | -0.80% | +36.82% | **RED** |
| KN-CM-NULL | gbt | 2× | **INSUFFICIENT** (—) | 137 | 0.005 | -0.00046% | -2.15% | +36.82% | **RED** |
| KN-CM-EDGE | ridge | 1× | **PASS** (—) | 1,147 | 0.005 | +0.01971% | +151.05% | +36.82% | GREEN |
| KN-CM-EDGE | ridge | 2× | **PASS** (—) | 1,147 | 0.005 | +0.01537% | +104.98% | +36.82% | GREEN |
| KN-CM-EDGE | gbt | 1× | **PASS** (—) | 803 | 0.005 | +0.02337% | +197.67% | +36.82% | GREEN |
| KN-CM-EDGE | gbt | 2× | **PASS** (—) | 803 | 0.005 | +0.01846% | +136.79% | +36.82% | GREEN |
| KN-CM-BELOW | ridge | 1× | **FAIL** (dsr, benchmark) | 69 | 0.020 | +0.00016% | +0.73% | +36.82% | **RED** |
| KN-CM-BELOW | ridge | 2× | **FAIL** (dsr, benchmark) | 69 | 0.010 | +0.00000% | +0.02% | +36.82% | **RED** |
| KN-CM-BELOW | gbt | 1× | **INSUFFICIENT** (—) | 246 | 0.040 | -0.00021% | -1.02% | +36.82% | GREEN |
| KN-CM-BELOW | gbt | 2× | **INSUFFICIENT** (—) | 246 | 0.015 | -0.00076% | -3.53% | +36.82% | GREEN |

## Red first, on deliberately broken code (nothing logged)

| drill | model | costs | verdict (failed checks) | OOS trades | luck p | net mean / bar | net | VWRP | red? |
|---|---|---|---|---|---|---|---|---|---|
| KN-CM-NULL | ridge | 1× | **INSUFFICIENT** (—) | 14 | — | +0.00011% | +0.51% | +36.82% | fold_boundary_leaked: not red |
| KN-CM-NULL | gbt | 1× | **FAIL** (benchmark) | 143 | 0.005 | +0.00141% | +6.82% | +36.82% | fold_boundary_leaked: **RED** ✓ |
| KN-CM-BELOW | ridge | 1× | **FAIL** (luck, benchmark) | 1,096 | 0.100 | +0.00193% | +9.41% | +36.82% | costs_off: not red |
| KN-CM-BELOW | gbt | 1× | **FAIL** (luck, benchmark) | 908 | 0.159 | +0.00182% | +8.87% | +36.82% | costs_off: not red |

Seen: fold_boundary_leaked YES, costs_off NO

## What it means (QT-27, written after the runs)

- **The exploitable passes (EDGE, 4 of 4 PASS).** A planted edge three times the 2× cost was found by both models
  and passed every check at 1× and 2× (+105% to +198% against VWRP's +36.8%). The model and the bench can see a
  real edge.
- **The worthless and the below-cost were rejected by the firewall's own verdicts (8 of 8 not PASS)** — but two
  of the stricter gate words written into the register that morning came out RED:
  - KN-CM-NULL / gbt: luck p 0.020 (1×) and 0.005 (2×) on a **losing** book (net −0.8% / −2.2%; the verdict
    INSUFFICIENT: one bar carries 38% of the variance). The register's gate asked for p ≥ 0.05. The firewall's
    own Gate 1 needs p < 0.05 **and** a positive net mean (QT-17 A2: a losing book that is noisier reads better
    on p alone), so by the bench's rule this null failed Gate 1, as it should.
  - KN-CM-BELOW / ridge: 69 trades ended **+0.73%** net at 1× and +0.02% at 2× over two years (FAIL: Deflated
    Sharpe 0.006 and 0.001, VWRP not beaten). The register's gate asked for a net mean not above zero.
- **Red-firsts:** the fold boundary leaked → the gradient-boosted null's luck test passes on a positive net mean
  (**RED, seen** — the drill catches a model that sees its own test sessions; ridge, as expected, does not move).
  Costs off → the below-cost drill makes money (+8.9% / +9.4%) but its luck test stays at p 0.10 / 0.16 (**not
  seen**): an edge of half a round trip is too small against real price noise for this drill to prove that costs
  are what reject it.
- **Verdict on the birth certificate: NOT PROVEN.** Gate 1 and Gate 2 are RED by their registered words, and one
  red-first did not show. By the box's STOP rule (and the register's "not seen = NOT PROVEN"), **none of the six
  CM trials was run; nothing was counted; N stays 56.** No defect was found in the bench or the model code — the
  gate words and the BELOW drill's size are what failed. The fix is a re-registration of the drills, BEFORE any
  run, in the next box (docs/reports/QT-27.md, PROPOSE 1).
