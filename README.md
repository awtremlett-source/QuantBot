# QuantBot

A patient, honesty-first **paper-trading** system for long-only US and UK shares and funds, run on
a **Trading 212 demo (practice) account**. It researches strategies, tests them
brutally for overfitting, paper-trades only the survivors, and teaches its operator
every rule it runs on. It trades **pretend money** — no live trading until a strict
graduation rubric passes.

> **Judged in percent** after costs against a do-nothing index fund (PLAN_V3 P3).
> The old £100/day north star was retired on 2026-09-26. Honesty first.

## The one rule that keeps it honest
Automated loops chase **correctness and honest testing**, never a profit number.
A loop may stop when *"everything is correct"* or *"the search is finished"* — it is
**never** allowed to stop when *"the profit looks good."* P&L is a **thermometer we
read, not a thermostat we chase.** (See `docs/SCARS.md` #21.)

## Status
**v2 building** (stage S3 of `docs/plan/PLAN_V3.md`); v1 frozen as the baseline.
See `STATE.md`.

## Map
- `CLAUDE.md` — operating memory / quick reference
- `STATE.md` — current phase and next actions (resume here)
- `GRAND_TODO.md` — the full phased backlog
- `docs/SCARS.md` — 24 hard-won laws this system obeys
- `docs/FOUNDING_DIRECTIVE.md` — the founding spec (the project's constitution)
- `docs/EDUCATION.md` — the self-taught-quant curriculum, grown as we build
- `docs/sessions/` — dated work logs
- `ingest/ data_store/ research/ strategies/ risk/ execution/ monitors/ tools/ tests/`
  — the system, built module by module

## Safety
Secrets live only in a local `.env` (gitignored); only `.env.example` (names, no
values) is tracked. This is educational paper trading — **not financial advice.**
