# STATE.md — resume in seconds

Phase: 1 (Foundations).  Updated: 2026-06-15.

## Settled decisions
- Repo root: c:\Users\mtrem\TRADING. Remote: github.com/AlexTreml/QuantBot.
- Prior work: ARCHIVED to archive/ (gitignored), building fresh.
- Demo capital: £10,000 GBP. £100/day = 1%/day = fantasy; honesty anchor only.
- Universe: focused ~100 liquid US names (specific list TBD via PROPOSE→GO).
- Machine: sometimes-off laptop → loops catch-up-safe.
- Data: Stooq bulk (primary) + yfinance (quorum second). Not yet ingested.

## Done
- Safety rails: git init, .gitignore (verified: .env blocked, template kept),
  .env.example, docs/SCARS.md (21 laws), session log.
- Clock: resynced by operator (w32tm /resync /force OK).
- Decisions captured; prior work archived; §4 repo layout created.
- Scaffolding: CLAUDE.md, STATE.md, GRAND_TODO.md, README.md,
  docs/EDUCATION.md#1, docs/FOUNDING_DIRECTIVE.md (verbatim).

## In flight / next actions (in order)
0. Push initial commit to GitHub (in progress this session).
1. Python venv + requirements.txt (pandas numpy pyarrow requests scikit-learn
   statsmodels matplotlib pytest hypothesis ruff mypy); verify imports.
2. Stooq PROPOSE doc: enumerate live db/h page (sizes/counts/disk) → operator GO.
3. Pick the focused ~100 universe (liquid US names) — PROPOSE list → GO.
4. §7 validation-firewall skeleton + known-null acceptance test (BEFORE any strategy).
5. Front-door ingest of the daily pack (counts reconciled) → census v1.
6. FIRST LIGHT: price chart of any named ticker + first daily digest.

## Open flags
- T212 auth scheme: verify single-key header vs KEY:SECRET Basic before any order (§6).
- Daily auto clock-sync task still to set up (admin).
- gh CLI not installed → use plain git for GitHub ops.
