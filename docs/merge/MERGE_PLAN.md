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

## Two environments, permanently (LOCKED 2026-09-20)

This is a locked decision, not a temporary state:

* the ENGINE keeps `.venv`; the WINDOW keeps `.venv-ui`;
* `manual/` never imports an engine package, and the engine never imports
  `manual/`, `tools_ui/` or PySide6;
* the window talks to the bot through exactly TWO doorways --
  `manual/bot_readonly.py` (read-only reads) and `manual/bot_governance.py`
  (allow-listed launches) -- and through nothing else;
* version alignment is DEFERRED to the July 2027 refit, where a change of
  pandas or yfinance can ride a full firewall re-run. A library version is part
  of what produced the live record, so it does not move between refits.

Enforced by `tests/wall/test_two_environments.py`, which checks the declaration
(no requirement line is shared) and the installation (the engine's `.venv` holds
no UI distribution).

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

> **SUPERSEDED 2026-09-21 from stage 3b onwards.** The direction changed to v2
> (the Simons direction): see **docs/plan/PLAN_V2.md**, which replaces stages
> 3b, 4, 5 and 6 below. They are kept here, not deleted, because they record
> what was intended and why. Stages 0, 1, 2 and 3a SHIPPED and stand — the
> manual app, the one-way wall, the two doorways and the Bot tab are all live
> and are inherited by v2.

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

**Stage 3a — housekeeping + the Bot tab. DONE 2026-09-20.** The dependency
question is ANSWERED, by locking two environments (above) rather than merging
them. `.venv-ui` created from `requirements-ui.txt` and the launcher pointed at
it -- it no longer falls back to a global Python. The old folder's launcher now
prints where the app went and exits, so two live copies cannot both start.
Ruff clean repo-wide (16 findings fixed, one of them a REAL latent crash -- see
below); `mypy --strict .` green with 52 inherited errors recorded in
`TYPING_DEBT.md` rather than silently ignored. And the window gained a **Bot
tab**: the engine's figures in plain words with an age on every one, a header
that turns red when a completed trading day has gone unprocessed, and the
control panel's seven governance buttons behind an allow-list. The wall grew
from 18 tests to 44.

**Stage 3b — the journal migration. STOPPED, and now SUPERSEDED by docs/plan/PLAN_V2.md.** The operator's
existing manual trade journal was NOT copied in. Its `trades` table declares
`shares INTEGER`; the current code declares `shares REAL` (changed by TradeScout
commit 4e15cf4 "Support fractional shares", and `CREATE TABLE IF NOT EXISTS`
never altered the existing table). Stage 3a's own rule was to stop on a schema
difference rather than force it, so it stopped. The data is safe -- a verified
copy sits in the pre-merge backup folder -- and the fix is a deliberate rebuild
of that one table preserving both rows, which needs PROPOSE->GO.

**Stage 4 — retire the Tkinter panel. SUPERSEDED by docs/plan/PLAN_V2.md (folded into S10, the rebuilt front end).** There are now
two faces of the same governance: `tools/gui.py` and the Bot tab. That is
deliberate for one stage -- the panel is the reference the Bot tab is tested
against -- but two faces must not become permanent. Retiring the panel is its
own box, with the killswitch drill re-run through the new face first.

**Stage 5 — one view of two books. SUPERSEDED by docs/plan/PLAN_V2.md (folded into S10).** Show the bot's
record and the operator's record side by side through the read-only doorway.
Reporting only; still two writers, still two books.

**Stage 6 — "revise how it works". SUPERSEDED: this IS docs/plan/PLAN_V2.md.** Not started, and
deliberately last: the merge is plumbing, the revision is strategy, and
strategy changes are rubric- and firewall-gated (a config change = a new
strategy = a full firewall re-run).

Stages 3–6 are PROPOSALS awaiting PROPOSE→GO→APPLY. Nothing in them is
committed by this document.

## What stage 3a is still blind to

Written down because a merge that hides its gaps is worse than one that admits
them.

* **The meters are on request, not on open.** The Bot tab shows the bot's own
  status check only after "Refresh Status" is pressed, because the window must
  never start an engine command by itself. Until it is pressed, that box is
  empty -- the tab cannot tell you a meter is RED that it has not been asked to
  read.
* **Staleness ignores market holidays.** A US market holiday shows as one day
  of false staleness. That is the safe direction: it over-reports, never under-
  reports. A holiday calendar would fix it and is not worth the dependency yet.
* **"Last run" comes from the run log, which only the scheduled task writes.**
  `tools\run_paper_loop.bat` redirects into `data/loop.log`; a loop run by hand
  in a terminal does not land there. So the log time can UNDERSTATE how recently
  the engine ran. The authoritative figure -- and the one staleness uses -- is
  the newest bar in the journal, which the engine writes however it is started.
* **The window mirrors the panel; it does not replace it.** Both can arm the
  killswitch. Until stage 4 retires one, two faces exist.
* **A pre-existing Qt fault at teardown.** The manual suite prints two "Windows
  fatal exception: access violation" lines from a worker thread and still passes
  131/131. Confirmed pre-existing: the untouched original repo does the same
  under the same PySide6. Not introduced here, not yet diagnosed.
* **52 type errors in five inherited modules** are silenced, with counts, in
  `TYPING_DEBT.md`. New errors in those five files are silenced too.
* **The bot itself is 31 trading days behind** as of 2026-09-20 (newest bar
  2026-08-06). That is the laptop being off, not a fault -- the loop is
  catch-up-safe -- but the Bot tab will read RED until it is run.

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
