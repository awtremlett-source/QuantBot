# CLAUDE.md — QuantBot operating memory

## Mission & phase
Many-small-edges paper-trading system on a Trading 212 DEMO account — the Simons
direction (v2, from 2026-09-21). North star £100/day net — honesty FIRST (£10k →
1%/day = fantasy; anchor only). Operator is a complete beginner: teach before
building; define terms on first use; decisions arrive as `DECISION REQUESTED` +
recommended default. CURRENT: v2 planned; S1 DONE (qb2 skeleton + .venv-qb2) — next box
= QT-05, the two-part plan revision. v1 KEEPS RUNNING UNTOUCHED as the baseline v2 must beat out-of-sample at 2×
costs; its engine folders are read-only. Machine: sometimes-off laptop → loops
catch-up-safe.

## Commands (venv: .venv — activate first)
- Tests: python -m pytest -q · Lint/types: ruff check . && mypy --strict .
- Run: python -m ingest/reconcile --tickers T --db PATH · python -m execution.paper_loop --db data/quantbot.db [--dry-run]

## Architecture map (one line per area)
- ingest/ ONLY writer to the data store (front door, §5); unit/scale checks here
- data_store/ storage API; SQLite(WAL) system-of-record; RAW vs CLEAN (parquet deferred)
- research/ §7 firewall, backtester, labelers, feature builders
- strategies/ one file per strategy + trigger_fixture / anti_fixture
- risk/ sizing (1% rule wins), ratchet exits, killswitch
- execution/ T212 demo client + paper book
- monitors/ meters, canary, daily digest
- tools/ operational scripts
- tests/ mirrors tree; tests/museum/ = incident regression fixtures
- docs/ SCARS.md, EDUCATION.md, FOUNDING_DIRECTIVE.md, sessions/

## Locked decisions (rationale → STATE.md · v2 detail → docs/plan/PLAN_V2.md)
- Price=yfinance daily OHLCV, delayed; sources decoupled, point-in-time.
  yfinance OHLC is ALREADY split-adjusted: CLEAN = validated copy, never re-divide (#22).
- Validation: walk-forward + untouched holdout; backtests simulate live delay;
  costs inside; Deflated Sharpe penalised by #trials.
- v1 execution/config is FROZEN: any change = new strategy = full firewall re-run.
- Two envs for v1 (.venv engine · .venv-ui window), AMENDED for v2: qb2/ gets one
  fresh env (.venv-qb2). Never install one env's pins into another.
- v1's regime/cadence/NVDA knobs: STATE.md "Settled decisions" (v1 runs untouched).

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
- Loops stop on CORRECT/EXHAUSTED, never PROFIT (#21,§2c)
- Birth-certificate: monitors prove red-on-broken before trusted (#9)
- 3 mandatory pre-commit checks: correctness · spelling · numbers (FRAMEWORK)

## Token rules (§12)
This file ≤4k chars; GRAND_TODO ≤10k (archive DONE). grep-then-read-range;
never cat data files (head/tail/count). Update STATE.md at session end.
Surgical edits only — never full rewrites.

## Pointers
Resume → STATE.md · PLAN v2 → docs/plan/PLAN_V2.md · Backlog → GRAND_TODO.md ·
Manifest → docs/MANIFEST.md ·
History → docs/sessions/ · Deploy → docs/DEPLOY.md ·
Constitution → docs/FOUNDING_DIRECTIVE.md · Curriculum → docs/EDUCATION.md
