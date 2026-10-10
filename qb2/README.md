# qb2 — QuantBot v2

**Built:** data (front door, census, universe), ingest (recorder, daily, dividends,
earnings, the S4 freshness meter and shadow cross-check), research (total return,
**firewall v2**: pre-registration, holdout, delay-rule fills, costs, walk-forward,
coin-flip null, Deflated Sharpe, benchmark, verdicts, known-null gate), execution
(costs, T212 client, P20 cross-check, anchor buyer — practice orders only),
signals (indicators only). **Empty:** model, sizing, ui. The plan is
[docs/plan/PLAN_V3.md](../docs/plan/PLAN_V3.md).

## Why a separate package

v1 is running a live forward paper record on a Trading 212 demo account. That
record is only worth something because nothing has been changed underneath it,
so v1 is frozen: it keeps running, untouched, and stays the baseline v2 has to
beat out-of-sample after double costs. Building v2 alongside it means neither
gets in the other's way.

## Its own environment, on purpose

qb2 has ONE environment for engine and interface together:

```
py -3.13 -m venv .venv-qb2
.venv-qb2\Scripts\python.exe -m pip install -r requirements-qb2.txt
```

Exact resolved versions: [docs/plan/ENV_QB2.md](../docs/plan/ENV_QB2.md).

This is the real fix for the version clash that forces v1 to run two
environments (its engine on pandas 3.x, its window on pandas 2.x). qb2 has no
inherited code, so it takes the modern pins and the UI toolkit together.

**Never install `requirements-qb2.txt` into `.venv` or `.venv-ui`.** Those belong
to v1 and are frozen.

## What is in each folder

| folder | holds |
|---|---|
| `data/` | prices, dividends, corporate actions, FX, the instrument universe |
| `research/` | firewall v2 (S4): `firewall.py` scores one registered candidate; `known_null.py` proves it; `preregister.py`, `holdout.py`, `trial_log.py` (data/qb2/trials.jsonl), `benchmark.py` (D3 = VWRP) |
| `signals/` | one small, testable signal per file |
| `model/` | the combining model — many signals in, one calibrated probability out |
| `sizing/` | position sizing, risk limits, the trailing-stop ledger |
| `execution/` | the broker doorway: demo orders, throttle, killswitch, fill recorder |
| `ui/` | the operator's screens |
| `tools/` | scripts run by hand |

## The walls around it

`qb2` imports nothing from v1's engine packages, and v1 imports nothing from
`qb2`. `tests/wall/` fails if either ever happens, and the engine fingerprint
proves v1's files have not moved.

## What it inherits

The shipped work from the earlier merge stages: the one-way wall, the two
doorways to v1's books (read-only reads, allow-listed launches), the journal,
the monitors and the data-layer laws. Nothing is rebuilt that already works.
