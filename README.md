# QuantBot

A patient, honesty-first **paper-trading** system for long-only US equities, run on
a **Trading 212 demo (practice) account**. It researches strategies, tests them
brutally for overfitting, paper-trades only the survivors, and teaches its operator
every rule it runs on. It trades **pretend money** — no live trading until a strict
graduation rubric passes.

> **North star:** £100/day net — but *honesty first*. On a £10,000 account that is
> 1%/day, which is fantasy. The first month's goal is **a machine that runs true**,
> not profit. The money compounds after the truth does.

## The one rule that keeps it honest
Automated loops chase **correctness and honest testing**, never a profit number.
A loop may stop when *"everything is correct"* or *"the search is finished"* — it is
**never** allowed to stop when *"the profit looks good."* P&L is a **thermometer we
read, not a thermostat we chase.** (See `docs/SCARS.md` #21.)

## Status
**Phase 1 — Foundations.** Building the data layer and the validation firewall
*before* any strategy. Not yet ingesting data or trading. See `STATE.md`.

## Map
- `CLAUDE.md` — operating memory / quick reference
- `STATE.md` — current phase and next actions (resume here)
- `GRAND_TODO.md` — the full phased backlog
- `docs/SCARS.md` — 21 hard-won laws this system obeys
- `docs/FOUNDING_DIRECTIVE.md` — the founding spec (the project's constitution)
- `docs/EDUCATION.md` — the self-taught-quant curriculum, grown as we build
- `docs/sessions/` — dated work logs
- `ingest/ data_store/ research/ strategies/ risk/ execution/ monitors/ tools/ tests/`
  — the system, built module by module

## Safety
Secrets live only in a local `.env` (gitignored); only `.env.example` (names, no
values) is tracked. This is educational paper trading — **not financial advice.**
