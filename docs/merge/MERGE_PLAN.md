# MERGE PLAN — one repo, two books

Started 2026-09-20. Operator requirement, verbatim (2026-09-18):

> "combine both the Manual paper trading dashboard, and the multi-strategy
> trader bot into one thing. and then i want to revise how it works."

Source app: TradeScout, copied (never moved) from `Documents\TradeScout`
at commit **29e8e747f3d5b716e94f26b2bf792671be6f4dbd**
("50% money ladder + friendlier GUI", 2026-08-21), tagged there as
`pre-merge-2026-09-18`. That repo and its GitHub remote are untouched.

## The two-books rule

There are two trading records in this repo now, and they must never become
one by accident:

| | the ENGINE's book | the MANUAL app's book |
|---|---|---|
| what | `data/quantbot.db` + `data/trials.jsonl` | `data/manual/trade_scout.db` |
| who writes it | the paper loop, on a schedule | the operator, by hand |
| what it proves | a forward track record under a validated, frozen config | practice at discretionary trading |
| who may write it | `ingest/` and `execution/` only | the manual app only |

The engine's book is evidence. Its whole value is that nothing outside the
engine has ever touched it — one stray "helpful" write from a GUI would not
corrupt the data so much as corrupt the PROOF. So the two books stay separate
even though the code now shares a repo.

## The one-way wall

Reading is allowed in one direction; writing in none.

```
   engine/                          manual/
   ingest, data_store, research,    the TradeScout app
   strategies, risk, execution,     (PySide6 GUI)
   monitors, tools
        |                                ^
        |   never imports manual,        |  reads, never writes,
        |   never learns the UI          |  ONLY via manual/bot_readonly.py
        +--------------- X --------------+
```

* The engine never imports `manual`, `tools_ui`, or PySide6. It runs headless
  at 07:30 and must not care whether a GUI exists, works, or is installed.
* The manual app may READ the engine's books through `manual/bot_readonly.py`
  — which opens the database with SQLite's `mode=ro` URI, so *SQLite itself*
  refuses every write. The guarantee belongs to the database engine, not to
  anyone's discipline.
* Nothing else under `manual/` may even name an engine artifact.

Enforced by `tests/wall/`, each test shipping a red-on-broken proof against a
planted violation in `tests/museum/wall_violations/` (SCARS #9: a check nobody
has watched fail is not a check).

## Two environments, on purpose

The two apps' pinned dependencies CONFLICT and are never installed together:

| package | engine (`requirements.txt`) | manual (`requirements-ui.txt`) |
|---|---|---|
| pandas | 3.0.2 | 2.3.3 |
| yfinance | 1.4.1 | 0.2.66 |
| matplotlib | 3.10.8 | 3.10.7 |
| pytest | 9.1.0 | 9.1.1 |

Installing the UI pins into `.venv` would silently swap the libraries the live
forward record is being produced with. Reconciling them is a stage-3 decision,
deliberately NOT taken here.

Commands:

```
python -m pytest -q                      # engine venv: engine + wall tests
py -3.13 -m pytest tests/manual -q       # UI interpreter: the manual app
py -3.13 -m manual.app                   # or tools_ui\TradeScout.bat
```

Inside the engine's `.venv` the manual suite is deliberately NOT collected
(it says so on stderr) — there is no PySide6 there and there must never be.

## The six stages

**Stage 0 — snapshot. DONE 2026-09-20.** Both repos clean and tagged
`pre-merge-2026-09-18`; journal + trial log backed up outside the repo and
verified (10 files, 82,320,834 bytes, every SHA-256 matching, plus a verified
logical snapshot: 6 tables, 82,670 rows); both suites run and recorded;
`tools/engine_fingerprint.py` added and `fingerprint_before.txt` taken.

**Stage 1 — move in. DONE 2026-09-20.** 54 of TradeScout's 59 tracked files
copied straight into `manual/` + `tests/manual/` and 5 transformed (its
`.gitignore`, two conftests, `requirements.txt`, `TradeScout.bat`).
Tracked-only, so no cache, venv or database could come across. Imports
resolve as `manual.scout.*` / `manual.ui.*`; nothing lives at repo top level;
its state moved to `data/manual/` (gitignored); launcher at
`tools_ui/TradeScout.bat`.

**Stage 2 — the wall. DONE 2026-09-20.** `tests/wall/` (18 tests), the
read-only doorway, and the planted-violation museum.

**Stage 3 — one dependency story. PROPOSED, not agreed.** Decide the pandas /
yfinance split: one environment or two, permanently. Gate: the engine's pins
may only move behind a full re-run of the validation firewall, because a
library version is part of what produced the record.

**Stage 4 — one front door. PROPOSED, not agreed.** Today there are two GUIs:
`tools/gui.py` (engine control panel — observe and govern only) and the
manual app. Merging them means the UI process could reach the engine's
controls, so the killswitch and promotion paths need re-proving first.

**Stage 5 — one view of two books. PROPOSED, not agreed.** Show the bot's
record and the operator's record side by side through the read-only doorway.
Reporting only; still two writers, still two books.

**Stage 6 — "revise how it works". THE OPERATOR'S REDESIGN.** Not started, and
deliberately last: the merge is plumbing, the revision is strategy, and
strategy changes are rubric- and firewall-gated (a config change = a new
strategy = a full firewall re-run).

Stages 3–6 are PROPOSALS awaiting PROPOSE→GO→APPLY. Nothing in them is
committed by this document.

## What stage 0–2 deliberately did NOT do

* No engine file was edited, moved, reformatted or re-linted. Proven by
  `fingerprint_before.txt` == `fingerprint_after.txt` — 52 files (48 in the
  engine folders, 4 config), combined hash
  `25c9ec06bb13167f7cb8fde7e054251ad8243a4c9bfe84a9a1b75babbd2477ee`.
* No UI was merged, no data layer was merged, no dependency conflict resolved.
* The operator's existing manual trade journal was NOT migrated. It is still
  at `Documents\TradeScout\cache\trade_scout.db`; the app in this repo starts
  with an empty database. Migrating it is a decision, not a side effect.
* The moved code was not retyped or re-linted to the engine's standard, so
  repo-wide `ruff check .` (16 findings) and `mypy --strict .` (623 errors)
  now report against `manual/` and `tests/manual/` only — zero in the engine,
  zero in new code. The engine-scoped commands stay clean:
  `ruff check data_store execution ingest monitors reconcile research risk
  strategies tools tests/wall` and the same list (minus the code-free `risk`)
  under `mypy --strict`. Clearing that debt belongs with stage 3, where
  `pyproject.toml` may be touched; it is frozen here by the fingerprint.
