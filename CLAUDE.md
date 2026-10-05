# CLAUDE.md — QuantBot operating memory

## Mission & phase
Trading 212 PRACTICE account, judged in % GBP total return (FX + dividends) after
costs vs a do-nothing index fund (D3). BOT 30%: automatic, SAME DAY, flat overnight
(P4), Simons' method. ADVISOR 70%: suggests only, operator trades, weeks–12 months.
v1 = frozen baseline v2 must beat out-of-sample at 2× costs (its daily task fails
since 28 Jul; revive/retire open). Laptop sometimes off → loops catch-up-safe.
Operator is a beginner: teach first, define terms on first use, decisions as
`DECISION REQUESTED` + default. Phase: v2 build → STATE.md.
Resume cheaply: STATE.md → PLAN_V3 grep P#/S#, read that range → FACTS grep row.
FOUNDING_DIRECTIVE and docs/sessions/ only when asked.

## Commands
- Tests: .venv/Scripts/python -m pytest -q (v1) · .venv-qb2/Scripts/python -m pytest tests/qb2 -q
- Lint: ruff check . && mypy --strict . · Anchors: python -m qb2.execution.anchors [--live]

## Map (full → docs/MANIFEST.md)
- v1 FROZEN, 9 folders (tools/engine_fingerprint.py): ingest/ (only writer) reconcile/
  data_store/ research/ strategies/ risk/ execution/ monitors/ tools/
- v2: qb2/ → qb2/README.md · manual/ operator's app · tests/ mirrors the tree
- Envs never cross: .venv (v1) · .venv-ui (window) · .venv-qb2 (qb2).

## Laws (stories → docs/SCARS.md) — money first
- Orders ONLY via qb2/execution/anchors.py (fences F1–F12 in its docstring). `--live`
  needs an operator GO; one GO covers top-ups to the £100 cap. Caps £3/order ·
  £100 lifetime · 50/UTC day: raising one = GO. Practice host only; v1 sender unarmed.
- POST isn't idempotent: unknown outcome = UNRESOLVED, never resend, settle from
  order history; a REFUSED name lifts only on the operator's words (FACTS e,x).
- STOP_NEW_TRADES at repo root is the human's lever: never remove it; tests use tmp.
- Secrets in .env; names-only in any output (#1).
- Point-in-time: rows carry knowable_time; read as-of AFTER own writes; UTC in code
  and fixtures (#23,#24). yfinance OHLC is already split-adjusted (#22).
- Costs only via qb2/execution/costs.py; gross AND net; 2× stress (#15). Fill at
  next-bar open − slippage, at the delay we'd really see; paper = upper bound (#16,#17).
- Pre-register every variant BEFORE running; Deflated Sharpe over the full count;
  net ≈0.7–1.2 is real, higher = red flag (#15). Holdout is spent once.
- Loops stop on CORRECT/EXHAUSTED, never PROFIT (#21).
- One writer, checks at the front door (#2,#3). Fail-first test with every fix (#2).
- No silent exceptions: handle+log or re-raise (#12). Monitors prove red-on-broken (#9).
- Quarantine DATA, never delete; dead CODE may go (git keeps it).
  PROPOSE→GO→APPLY for destructive/expensive (#7).
- Operator words verbatim at issue time. Pre-commit: correctness · spelling · numbers.
- v1 change = new strategy + full firewall re-run.

## Lean code
- Smallest change meeting the requirement; verify vs the requirement, not the plan.
- One job per module, ≤250 lines; oversize pinned, may shrink never grow
  (tests/qb2/test_lean_lines.py); splitting = PROPOSE→GO.
- Contracts first (types/dataclasses/Protocols, mypy --strict). Pure logic, injected
  I/O (broker, clock, network) so tests run offline.
- No new dependency without GO. grep before any helper; extend, never a variant.
- One-in-one-out: each change names the dead/duplicate code it removes.
- Before coding, 3 lines: Impact (files +/~/−) · Consolidation · Contracts.
  Per-file +/− → commit message, not the report.

## Token rules
Budgets (tests/plan/test_plan_v3.py): CLAUDE 4k · STATE 6k · GRAND_TODO 10k ·
MANIFEST 8k. STATE = current only; history → docs/archive/. Surgical edits;
grep-then-read-range; never cat data files.
End of task: update STATE.md, commit, push, end the report with
"CLEAR ME NOW (/clear) — state is saved."

## Pointers
Plan → docs/plan/PLAN_V3.md · Backlog → GRAND_TODO.md · Deploy → docs/DEPLOY.md ·
Constitution → docs/FOUNDING_DIRECTIVE.md · Curriculum → docs/EDUCATION.md
