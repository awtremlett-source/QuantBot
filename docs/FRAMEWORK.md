# FRAMEWORK — how to build an honest trader: the order is the method

This page is the canonical build recipe. Someone starting from zero should be able
to rebuild QuantBot — or start trader #2 — by following it top to bottom. It
synthesizes; the details live where the pointers point (SCARS = the laws register,
MANIFEST = current inventory + graduation rubric, FOUNDING_DIRECTIVE = the
constitution, EDUCATION = the concepts).

## Why this order

Each phase exists to make the NEXT phase's results believable. Rails before data,
or you can't trust what you stored. Data before validation, or you validate
garbage. A firewall before any strategy, or every backtest flatters you. One
proven baseline before challengers, or there is no honest benchmark to beat.
Paper before breadth, or mistakes scale with tickers. Deflation before the
ensemble sweep, or the sweep manufactures its own luck. The rubric before
deployment, or you deploy hope. Skipping ahead doesn't save time — it moves the
cost to the moment you can least afford it.

## Phase 0 — GOVERNANCE (rails before anything)

- **Purpose:** make every later mistake survivable and every later claim auditable.
- **Build:** git + secrets hygiene (env-only, .gitignore before first commit);
  the laws register (docs/SCARS.md) read once, obeyed forever;
  requirements-verbatim (operator words recorded at issue time);
  PROPOSE→GO→APPLY for anything destructive or expensive; killswitch from day one.
- **Gate (done means):** the rails exist BEFORE any data is fetched.
- **Birth certificate:** .gitignore proven to block a planted secret; killswitch
  drill actually halts the loop.
- **Pointers:** docs/SCARS.md #1 · docs/FOUNDING_DIRECTIVE.md §2b, §12.

## Phase 1 — DATA LAYER (one honest store)

- **Purpose:** a store whose every row you can defend later.
- **Build:** single-writer front door with checks at the boundary; RAW/CLEAN
  split (CLEAN = validated COPY, never re-adjusted); point-in-time reads (event
  time vs knowable time — as-of captured AFTER your own writes);
  quarantine-never-delete; self-healing trailing re-fetch; split-continuity checks.
- **Gate (done means):** a lookahead/leak test proven red-on-broken.
- **Birth certificate:** the leak spy fails when the guard is removed; a planted
  discontinuity is quarantined loudly, not smoothed silently.
- **Pointers:** ingest/ · reconcile/ · data_store/ · SCARS #2–#8, #22, #23.

## Phase 2 — VALIDATION FIREWALL (before ANY strategy)

- **Purpose:** make it impossible to fool yourself before there is anything to
  be fooled about.
- **Build:** honest backtester (next-open fills, costs inside, gross AND net,
  no-lookahead spy); walk-forward (fit only ever on TRAIN — no-fit-on-test spy);
  Monte Carlo known-null gate (coin-flip must be REJECTED); append-only trial
  log; Deflated Sharpe policy — selection-N counting with verification-rerun
  and cross-ticker tags excluded (research/deflation.py docstring is the policy).
- **Gate (done means):** the firewall demonstrably FAILS a worthless strategy
  (and still passes a mechanically exploitable pattern).
- **Birth certificate:** coin-flip rejected; deterministic pattern harvested;
  both recorded in tests.
- **Pointers:** research/backtester.py · research/walk_forward.py ·
  research/monte_carlo.py · research/trial_log.py · research/deflation.py ·
  SCARS #15–#18, #21.

## Phase 3 — FIRST STRATEGY (simplest credible baseline)

- **Purpose:** one always-on strategy through the full firewall = the benchmark
  everything else must beat.
- **Build:** simplest credible rule (here: SMA-200 trend, long-only); judgment
  rules PRE-COMMITTED before results; risk-adjusted judging (Sharpe/maxDD,
  never raw return); 2× cost stress.
- **Gate (done means):** both MC gates + stress passed, verdicts recorded
  EITHER WAY (a recorded rejection is a success of the process).
- **Birth certificate:** the pre-committed rules are written down before the
  first result is seen; the trial log shows every try.
- **Pointers:** research/strategy.py · STATE.md "FIRST VALIDATED STRATEGY" ·
  SCARS #14, #15, #21.

## Phase 4 — PAPER (the forward test)

- **Purpose:** a live, no-capital track record under real operational friction.
- **Build:** local book proven ≡ backtester (birth certificate); catch-up-safe
  idempotent loop (sometimes-off machine is a feature: it forces this); journal
  as the product; scheduled autonomy (human = governance only); verified backups
  with an off-laptop destination.
- **Gate (done means):** at least one REAL dark-gap catch-up banked (evidence:
  2026-07-28, 8-bar replay via scheduled task).
- **Birth certificate:** book-vs-backtester equality test; catch-up proven on a
  genuine gap, not a simulated one.
- **Pointers:** execution/ · tools/backup.py · tools/run_paper_loop.bat ·
  SCARS #9–#13, #16, #17, #20, #23.

## Phase 5 — CHALLENGERS & META (competition under law)

- **Purpose:** improve the incumbent without reopening the door to self-deception.
- **Build:** every challenger through the FULL firewall; incumbents replaced
  only by pre-committed OUT-OF-SAMPLE victory; configs FROZEN once validated
  (any change = new strategy = full re-run); annual refit on schedule, never
  mid-flight.
- **Gate (done means):** adopt-or-reject decision recorded with the evidence,
  both outcomes honored.
- **Pointers:** strategies/ · execution/config.py · STATE.md challenger +
  switcher entries · SCARS #13, #21.

## Phase 6 — BREADTH (the Simons destination)

- **Purpose:** the ensemble of small edges — many thin, independent, validated
  signals; the portfolio is the edge.
- **Build:** cross-ticker generalization UNTOUCHED first (fit nothing, test
  transfer); then per-ticker fitting inside a deflation-counted sweep; ensemble
  of low-pairwise-correlation edges with effective-N monitoring; thematic ideas
  enter only as research candidates (watchlist), never as positions.
- **Gate (done means):** sweep-level multiple testing accounted — either deflate
  at sweep level or spend a final untouched cross-ticker holdout ONCE.
- **Pointers:** GRAND_TODO Phase 6 · EDUCATION Entry #2 · STATE.md Simons
  alignment + thematic decisions.

## Phase 7 — GRADUATION & DEPLOYMENT

- **Purpose:** move real (still irrelevant-sized) money only when the record
  has earned it.
- **Build/Gate:** the MANIFEST graduation rubric — ALL seven conditions — plus
  DSR ≥ 0.95 at then-current N. Live at irrelevant size first.
- **Deployment:** QuantBot ships as an installable application onto the
  always-on home PC; the installer may be BUILT early (packaging risks
  nothing), but EXECUTING it there is rubric-gated.
- **Pointers:** docs/MANIFEST.md (rubric + END GOAL) · GRAND_TODO "Deployment".

## The standing laws (one line each — the stories live in docs/SCARS.md)

Secrets in env, names-only in output (#1) · one writer, checks at the boundary
(#2,#3) · fail-first test with every fix (#2) · manifest truth, post-write
verified (#4) · corporate-action authority, refuse stale scales (#5) · reconcile
counts after bulk jobs (#6) · snapshot-vs-refresh, coverage checked (#7) ·
wallpaper rule: chronic red audits the METER (#8) · birth certificate for
every monitor (#9) · progress-stamps, not liveness (#10) · loud budgets (#11) ·
no silent exceptions (#12) · one promotion authority (#13) · per-regime judging
(#14) · costs inside, real ≈ 0.7–1.2 net (#15) · next-open fills (#16) · paper =
upper bound (#17) · stratified replays (#18) · ratchet exits are plumbing (#19) ·
clock sync (#20) · loops stop on CORRECT/EXHAUSTED, never PROFIT (#21) · CLEAN =
copy, never re-adjust (#22) · as-of AFTER your own writes (#23) · quarantine,
never delete; PROPOSE→GO→APPLY (§12).

## The 3-checks protocol (mandatory before every commit)

Before every commit, run 3 MANDATORY CHECKS and print the result as a
"3-checks:" line — (1) CORRECTNESS vs the repo record (every claim/config
cross-checked against STATE/MANIFEST/journal/trials), (2) LANGUAGE
(spelling/grammar of changed text), (3) NUMBERS (every figure traced to source
or recomputed). Corrections applied in the same step and named.
