# CLAUDE.md — QuantBot operating memory

## Mission & phase
ML-focused, long-only US-equity paper-trading system on a Trading 212 DEMO account.
North star £100/day net — honesty FIRST (£10k → 1%/day = fantasy; anchor only).
Operator is a complete beginner: teach before building; define every term on first
use; decisions arrive as `DECISION REQUESTED` with a recommended default.
CURRENT PHASE: 1 (Foundations) — safety rails done; building the data layer + the
§7 validation firewall BEFORE any strategy. Machine: sometimes-off laptop → loops
must be catch-up-safe.

## Commands (venv: .venv — activate first)
- Tests: python -m pytest -q · Lint/types: ruff check . && mypy --strict .
- Planned: python -m ingest ... · python -m execution.paper_loop

## Architecture map (one line per area; files fill in as built)
- ingest/      ONLY writer to the data store (front door, §5); unit/scale checks here
- data_store/  storage API; SQLite(WAL) system-of-record; RAW vs CLEAN (parquet deferred)
- research/    §7 firewall, backtester, labelers, feature builders
- strategies/  one file per strategy + trigger_fixture / anti_fixture
- risk/        sizing (1% rule wins), ratchet exits, killswitch
- execution/   T212 demo client + paper book
- monitors/    meters, canary, daily digest
- tools/       operational scripts
- tests/       mirrors tree; tests/museum/ = incident regression fixtures
- docs/        SCARS.md, EDUCATION.md, FOUNDING_DIRECTIVE.md, sessions/

## Locked decisions (rationale → STATE.md)
- Data: Price=yfinance (daily OHLCV, ~15-min delay; fine at 4h). Sentiment=StockGeist
  (free 10k cr/mo). Sources decoupled, point-in-time. Real-time deferred.
  yfinance OHLC already split-adjusted; RAW->CLEAN verifies continuity, never re-divides (SCARS).
- Cadence/budget: 4h poll floor over ~100 names (~4,200 cr/mo); spare=emergency reserve.
  Severity-weighted: calm 4h / mild ~2h / severe 1h+. Guard: global credit ceiling +
  optional weekly rationing.
- Regime detector: emits 0–1 severity SCORE (not a label). Jobs: pick strategy + set
  cadence. Price=ground truth; sentiment=feature/confirmation only, never standalone.
- Strategy: shared TEMPLATES + one fitted CONFIG/ticker (not 100 hand-written). 1st=NVDA.
- NVDA regimes: 4 states (stress/calm-uptrend/choppy/calm-downtrend) from RV20 vs own
  1-yr median + SMA50 slope. Thresholds=walk-forward params, NOT constants. Defenses:
  hysteresis, min dwell, severity blending, early-&-small sizing, blunt stress rules.
- Validation: walk-forward + untouched holdout; backtests simulate live delay; Deflated
  Sharpe (penalised by #trials).

## Laws (one line each — full stories in docs/SCARS.md)
- Front-door ingest: one writer; checks at the boundary (#2,#3)
- Fail-first tests: a test that fails on OLD code ships with every fix (#2)
- No silent exceptions: handle+log or re-raise, always (#12)
- Quarantine, never delete; PROPOSE→GO→APPLY for destructive/expensive (#7,§12)
- Costs INSIDE the backtest; report gross AND net; stress 2× (#15)
- Fill at next-bar open − slippage; paper = upper bound (#16,#17)
- Honest trial counting → Deflated Sharpe; real ≈ 0.7–1.2 net (#15)
- Secrets in env; names-only in any output (#1)
- Requirements-verbatim: record operator words at issue time (§12)
- Loops stop on CORRECT / EXHAUSTED, never on PROFIT (#21,§2c)
- Birth-certificate: monitors prove red-on-broken before trusted (#9)

## Token rules (§12)
This file ≤4k chars; GRAND_TODO ≤10k (archive DONE). grep-then-read-range;
never cat data files (head/tail/count). Update STATE.md at session end. Make
surgical edits to this file — never full rewrites.

## Pointers
Resume → STATE.md · Backlog → GRAND_TODO.md · History → docs/sessions/ ·
Constitution → docs/FOUNDING_DIRECTIVE.md · Curriculum → docs/EDUCATION.md
