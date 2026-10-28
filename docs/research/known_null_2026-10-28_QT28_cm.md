# Known-null gate for the combined model, 2026-10-28 (QT-28 D: drills v2, register 787d4a27, judged by the firewall's own verdicts; LON arm, real clean store)

Run through the trials' own code (cm_arm.score -> the unchanged firewall). Honest runs logged kind=drill (counted 0); red-firsts on deliberately broken code, logged nowhere (docs/reports/QT-28_d2_redfirst.py.txt).

## Honest code: KN-CM-NULL-v2 GREEN · KN-CM-EDGE-v2 GREEN · KN-CM-BELOW-v2 GREEN

| drill | model | costs | verdict (failed checks) | OOS trades | luck p | net mean / bar | net | VWRP | gate |
|---|---|---|---|---|---|---|---|---|---|
| KN-CM-NULL-v2 | ridge | 1× | **INSUFFICIENT** (—) | 7 | — | +0.00001% | +0.06% | +36.82% | GREEN |
| KN-CM-NULL-v2 | ridge | 2× | **INSUFFICIENT** (—) | 7 | — | -0.00000% | -0.00% | +36.82% | GREEN |
| KN-CM-NULL-v2 | gbt | 1× | **INSUFFICIENT** (—) | 137 | 0.020 | -0.00017% | -0.80% | +36.82% | GREEN |
| KN-CM-NULL-v2 | gbt | 2× | **INSUFFICIENT** (—) | 137 | 0.005 | -0.00046% | -2.15% | +36.82% | GREEN |
| KN-CM-EDGE-v2 | ridge | 1× | **PASS** (—) | 1,147 | 0.005 | +0.01971% | +151.05% | +36.82% | GREEN |
| KN-CM-EDGE-v2 | ridge | 2× | **PASS** (—) | 1,147 | 0.005 | +0.01537% | +104.98% | +36.82% | GREEN |
| KN-CM-EDGE-v2 | gbt | 1× | **PASS** (—) | 803 | 0.005 | +0.02337% | +197.67% | +36.82% | GREEN |
| KN-CM-EDGE-v2 | gbt | 2× | **PASS** (—) | 803 | 0.005 | +0.01846% | +136.79% | +36.82% | GREEN |
| KN-CM-BELOW-v2 | ridge | 1× | **INSUFFICIENT** (—) | 478 | 0.005 | +0.00037% | +1.72% | +36.82% | GREEN |
| KN-CM-BELOW-v2 | ridge | 2× | **INSUFFICIENT** (—) | 478 | 0.005 | -0.00066% | -3.05% | +36.82% | GREEN |
| KN-CM-BELOW-v2 | gbt | 1× | **INSUFFICIENT** (—) | 512 | 0.015 | -0.00007% | -0.37% | +36.82% | GREEN |
| KN-CM-BELOW-v2 | gbt | 2× | **INSUFFICIENT** (—) | 512 | 0.005 | -0.00120% | -5.49% | +36.82% | GREEN |

## Red first, on deliberately broken code (nothing logged)

| drill | model | costs | verdict (failed checks) | OOS trades | luck p | net mean / bar | net | VWRP | red? |
|---|---|---|---|---|---|---|---|---|---|
| KN-CM-NULL-v2 | ridge | 1× | **INSUFFICIENT** (—) | 14 | — | +0.00011% | +0.51% | +36.82% | fold_boundary_leaked: not red |
| KN-CM-NULL-v2 | gbt | 1× | **FAIL** (benchmark) | 143 | 0.005 | +0.00141% | +6.82% | +36.82% | fold_boundary_leaked: **RED** ✓ |
| KN-CM-BELOW-v2 | ridge | 1× | **FAIL** (benchmark) | 1,123 | 0.020 | +0.00370% | +18.84% | +36.82% | costs_off: **RED** ✓ |
| KN-CM-BELOW-v2 | gbt | 1× | **FAIL** (benchmark) | 890 | 0.015 | +0.00364% | +18.51% | +36.82% | costs_off: **RED** ✓ |

Seen: fold_boundary_leaked YES, costs_off YES

**Birth certificate: PROVEN** (PROVEN = every v2 gate GREEN and both red-firsts SEEN).
