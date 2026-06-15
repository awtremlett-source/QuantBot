# CLAUDE.md — QuantBot operating memory

## Mission & phase
ML-focused, long-only US-equity paper-trading system on a Trading 212 DEMO account.
North star £100/day net — honesty FIRST (£10k → 1%/day = fantasy; anchor only).
Operator is a complete beginner: teach before building; define every term on first
use; decisions arrive as `DECISION REQUESTED` with a recommended default.
CURRENT PHASE: 1 (Foundations) — safety rails done; building the data layer + the
§7 validation firewall BEFORE any strategy. Capital £10,000 GBP. Universe: focused
~100 liquid US names. Machine: sometimes-off laptop → loops must be catch-up-safe.

## Commands
- Tests:      python -m pytest -q
- Lint/types: ruff check . && mypy --strict .
- Ingest:     (planned) python -m ingest ...
- Paper loop: (planned) python -m execution.paper_loop
(venv: .venv — activate before running.)

## Architecture map (one line per area; files fill in as built)
- ingest/      ONLY writer to the data store (front door, §5); unit/scale checks here
- data_store/  storage API code; SQLite(WAL) system-of-record + parquet; RAW vs CLEAN
- research/    §7 firewall, backtester, labelers, feature builders
- strategies/  one file per strategy + trigger_fixture / anti_fixture
- risk/        sizing (1% rule wins), ratchet exits, killswitch
- execution/   T212 demo client + paper book (fill at NEXT-bar open − slippage)
- monitors/    meters, canary, daily digest
- tools/       operational scripts
- tests/       mirrors tree; tests/museum/ = incident regression fixtures
- docs/        SCARS.md, EDUCATION.md, FOUNDING_DIRECTIVE.md, sessions/

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
This file ≤4k chars; GRAND_TODO ≤10k (archive DONE rows). grep-then-read-range;
never cat data files (head/tail/count). Update STATE.md at session end. Make
surgical edits to this file — never full rewrites.

## Pointers
Resume → STATE.md · Backlog → GRAND_TODO.md · History → docs/sessions/ ·
Constitution → docs/FOUNDING_DIRECTIVE.md · Curriculum → docs/EDUCATION.md
