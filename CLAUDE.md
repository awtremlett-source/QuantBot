# CLAUDE.md — QuantBot operating memory

## Mission & phase
TWO PARTS on a Trading 212 DEMO account (v3, 2026-09-26): a BOT (automatic, holds
days, Simons' method) on 30%, and an ADVISOR (suggests only; he trades; weeks to
12 months) on 70%. Judged in PERCENT after costs vs a do-nothing index fund — no
£/day target. Operator is a complete beginner: teach before building; define
terms on first use; decisions arrive as `DECISION REQUESTED` + default.
CURRENT: S3d DONE; S3 NOT complete — only the measured quote delay is left
(1 US session of 3, London 0). Dividends, FX, earnings in. P18+P19 agreed 2026-10-03.
v1 KEEPS RUNNING UNTOUCHED as the baseline v2 must beat out-of-sample at 2×
costs; engine folders read-only. Machine: sometimes-off laptop → loops
catch-up-safe.

## Commands (venv: .venv — activate first)
- Tests: python -m pytest -q · Lint/types: ruff check . && mypy --strict .
- Run: python -m ingest/reconcile --tickers T --db PATH · python -m execution.paper_loop --db data/quantbot.db [--dry-run]

## Architecture map (full per-folder map → docs/MANIFEST.md)
- v1 FROZEN, still running: ingest/ (only writer) · data_store/ · research/ ·
  strategies/ · risk/ · execution/ · monitors/ · tools/
- v2: qb2/ — data research signals model sizing execution ui tools → qb2/README.md
- manual/ operator's own app · tests/ mirrors the tree · tests/museum/ = incidents

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
This file ≤3.6k chars; GRAND_TODO ≤10k (archive DONE). grep-then-read-range;
never cat data files (head/tail/count). Update STATE.md at session end.
Surgical edits only — never full rewrites.

## Pointers
Resume → STATE.md · PLAN v3 → docs/plan/PLAN_V3.md · Backlog → GRAND_TODO.md ·
Manifest → docs/MANIFEST.md ·
History → docs/sessions/ · Deploy → docs/DEPLOY.md ·
Constitution → docs/FOUNDING_DIRECTIVE.md · Curriculum → docs/EDUCATION.md
