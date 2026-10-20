# QT-23R — the resource cap (Step 0 and Step 1)

2026-10-20 · Claude Code (Opus 5.5) · Step 1 committed alone, then QT-23 Parts B–F
(their report: docs/reports/QT-23.md).

## In plain words

- **Your rule is now built in, and it is a fence.** Your words, recorded verbatim in STATE and
  PLAN_V3: *"I stopped QT23 halfway through, there needs to be a limit on the amount of memory
  and CPU it takes up. like 80% limit for each. otherwise the PC cannot take it and will
  crash."* Everything QuantBot runs, all its programs together, now stays at or under 80% of
  the CPU and 80% of the memory. Only your own words can raise or remove that.
- **How it works.** Windows has a feature called a *Job Object*: a box that programs are put
  in, with limits that Windows itself enforces. Every heavy QuantBot run now starts inside one
  shared box:
  - **CPU:** at most 80% of the machine, and only 12 of the 16 processor threads at any moment
    (75%).
  - **Memory:** at most 80% of the RAM.
  - **Priority:** lower than your own apps, so your desktop always comes first.

  When a run ends, whether it finished or you stopped it, everything it started ends with it.
  Nothing is left running in the background.
- **Measured on your PC, with your own apps open:**
  - **CPU:** a program built to grab 100% of the CPU got at most 74.8% in any one second
    (70.8% on average) over a full minute. Your desktop stayed instant: a timer outside the
    box was late by 0.3 ms on average.
  - **Memory:** a program built to eat memory was stopped exactly at its limit, with a
    plain-words message, and the rest of the PC never noticed.
- **One thing to know.** Today your own apps were already using 60–77% of the memory. The 80%
  box alone would still let QuantBot *plus* your apps go past what the PC has. So QuantBot also
  watches the **whole** PC:
  - at **80%**, it waits before starting more work;
  - at **90% for a minute**, or **95% at once**, it stops cleanly, and the run carries on later.
- **Nothing from the interrupted run was lost or half-written.** That unfinished work is kept
  aside (a git stash named "QT-23-interrupted"). No advisor stop or brake was ever written, and
  the trial count is still 54.

## Step 0 — the interrupted run, checked before anything else

| check | finding |
|---|---|
| pull / status | main = origin/main at 8fb2c49 (QT-23 A pushed); 5 modified + 2 new files uncommitted |
| stash | stashed as `stash@{0}` "QT-23-interrupted" (never deleted); a diff copy kept outside the repo |
| half-written files | none (`*.tmp`, `*.part`, `*.partial`): only the routine after-hours writes since Part A |
| stops.jsonl / brakes.jsonl | **neither file exists** → no advisor rows (Part F never reached) |
| trial log | 113 lines; the two newest are Part A's register notes (N stays 54); no ADV-0 run |
| leftover processes | no Python process running; the CPU load then (~40–60%) was your own apps |
| what was interrupted | Part B half-built: the advisor's stop still opened with the old ATR rule (`fall = None` in `Ledger.open`), so it is rebuilt test-first in Part B, reusing only reviewed pieces |
| fingerprints | v1 4add56ec…743b6 · advisor daily (a) 0f3a960c…f1f9 · (b) f7aae670…768e — all as STATE |
| suite under the cap | 785 passed, then 790 after the cap's own tests (below) |

## Step 1 — what was built

- `qb2/tools/capped.py` — the launcher: `python -m qb2.tools.capped -- <command>`. Builds on:
  - **One named Job Object, shared by every QuantBot run, so the budget is one budget.** A
    process cannot *join* a job in another job tree, because the venv's `python.exe` is itself
    a small launcher with a job of its own. So the command starts **suspended**, is placed in
    the job, then resumed: it runs no instruction outside.
  - **A run started from somewhere else can't double the budget.** If it is Task Scheduler vs
    a console and the shared job won't take it, it waits for that job to close.
  - **Fail closed.** Not Windows, a library missing, or the job refused → exit 3, in plain
    words, and nothing runs.
- `qb2/tools/job_object.py` — the limits, set and read back: the CPU rate hard cap (CpuRate 8000),
  processor affinity (12 of 16), memory 80% of RAM, no breakaway, kill-on-close, below-normal
  priority. `problems()` is the one rule a job must meet.
- `qb2/tools/governor.py`:
  - `workers()` = max(1, floor(0.8 × cores) − 1) = **11** here.
  - `gate()` is the whole-PC memory rule.
  - `assert_capped()` refuses outside the cap; inside it, it starts a background watch that
    stops the run cleanly on the memory rule.
  - `run_pool()` is **the** process pool.
- **Wired:** `assert_capped()` is the first call of:
  - every `main()` in qb2/research: advisor_run, advisor_drills, s6_run, p19_run, known_null,
    stop_description, brake_report, p15_coverage;
  - `firewall.load()` (every back-test's data load);
  - `firewall.score()` (the firewall and its null runs).

  So a copy of an old driver script is refused at its first data load. The qb2 test suite
  refuses to start outside the cap (one message, not hundreds).
- **Walls** (tests/qb2/test_qt23r_cap.py), each one seen RED on a plant:
  - no process pool outside `governor.run_pool`;
  - no pool as wide as its job list;
  - no `pytest -n`;
  - every heavy entry point refuses first.

  The two drivers from before the cap (QT-21, QT-22) stay as records of what ran.
- `psutil 7.2.2` and `pywin32 312` added to `.venv-qb2` only, pinned and logged
  (requirements-qb2.txt, docs/plan/ENV_QB2.md). Neither brought another package.
- CLAUDE.md, qb2/README.md, ENV_QB2.md now give the capped commands. STATE and PLAN_V3 carry your
  words as a standing rule, and a plan test pins them.

## The proofs, with figures

**(a) CPU** — `docs/reports/QT-23R_cap_proof.py.txt cpu`. 16 spinning processes inside the cap
(they try to take 100%). An observer outside it sampled every second for 60 s, using Windows'
own accounting for the job.

| run | QuantBot's share of the machine, per second | whole machine | outside timer late |
|---|---|---|---|
| **the real cap (final)** | **peak 74.8% · mean 70.8% · min 61.5% — 0 of 60 seconds over 80%** | peak 94.3%, mean 85.3% | mean 0.3 ms, max 0.7 ms |
| first two tries: rate cap alone | peaks 76.2% and **85.1%** (the second: 6 of 60 seconds over 80%) · means 67.4%, 68.0% | means 100% and 97.8% | max 42.9 ms and 14.6 ms |
| a 30% test cap (rate cap alone) | mean 29.6% · peak 37.2% | mean 58.8% | max 2.8 ms |

The first try was not good enough. Windows enforces the rate cap **on average**: it lets the
job run ahead for a moment, then throttles it (the 30% run's seconds go 36, 36, 18, …). Your rule
says "always". So a second, hard limit was added: the job may use at most 12 of the 16 processor
threads. That is physically 75% at every instant. The rate cap at 80% stays as the box
specified, so there are two fences. The whole machine still showed 94% because your own apps
were busy; at normal priority they come first.

**(b) Memory** — `… memory`. The hog took memory 16 MB at a time inside a cap **lowered to 3% of
RAM (0.95 GB)**. Never the real 80%: with your apps at ~60–77% of RAM, an 80% hog is exactly the
crash you stopped.

| | |
|---|---|
| hog | "Windows refused more memory at **944 MB**" (exit 1) |
| launcher | "STOPPED AT THE MEMORY CAP: QuantBot used 0.96 GB of its 0.95 GB limit (3% of RAM) and the run failed: Windows refused it more memory, so it stopped. Nothing else on the PC was touched." |
| whole PC memory | 59.6% before · peak 62.7% · 59.6% after |
| outside timer | late at most 0.6 ms (16 samples) |

The real job's limit is read back by a live test: 80% of RAM to the 4 KB page, CpuRate 8000,
12 processors, below normal.

**(c) Red-first, without endangering the PC** — `docs/reports/QT-23R_redfirst.py.txt`.

| mutant | what went RED |
|---|---|
| M1: the launcher never puts the command in the Job Object (phase 1, plain console, child = one `assert_capped()` call) | the child **REFUSED**: "this process is not inside QuantBot's cap" |
| M1 again, inside the real cap (phase 2) | 2 live tests: the probe is not inside; the bounded hog is **not** stopped (it stayed inside the real shared cap all along, so it was never uncapped) |
| M2: `advisor_run.main` without `assert_capped()` | the door wall: "advisor_run.py: main() does not refuse outside the cap first" |
| M3: a planted driver with a pool as wide as its job list | the pool wall (2 breaches: pool, width) |
| everything restored (sha256 checked) | the whole cap test file GREEN, 37 passed |

**(d) The advisor's daily/weekly step under the cap** — Part D (it does not exist yet); in
QT-23.md.

## Decided while operator away (STANDING GO 2026-10-07: routine figures → the default, logged)

- **Processor affinity (12 of 16) on top of the 80% rate cap.** It is stricter, never looser,
  and makes "always" true second by second (proof (a)).
- **≥ 95% whole-PC memory stops at once** (beside the box's ≥ 90% for 60 s): past 95%, a minute
  is too long to wait. Stricter.
- **One shared job, not one per run**, so "all its processes together" holds across runs. A run
  from another place that the job will not take waits for it.
- **`--mem-share` / `--cpu-share` may only LOWER the cap** (tests, demos), and then the run gets
  a private job, never the shared one.

## End checks (all under the cap)

qb2 790 passed (1 deselected; +39: 37 cap tests, 2 new pins) · plan+wall 243 (+1, the cap's
words) · v1 443 · ruff clean · mypy the same 4 (manual/ui Qt stubs) · **v1 4add56ec…743b6
unchanged** · advisor daily (a) 0f3a960c…f1f9, (b) f7aae670…768e unchanged · the heaviest run
(the full qb2 suite) peaked at 1.34 GB of the 25.35 GB allowed.

## For you

Heavy commands now go through the cap. For example, the qb2 tests:

```
.venv-qb2\Scripts\python.exe -m qb2.tools.capped -- .venv-qb2\Scripts\python.exe -m pytest tests/qb2 -q
```

Started any other way, a heavy entry point says REFUSED and shows this line. The cap's own
diary is `logs/cap/cap.log` (every start, finish, refusal and wait).
