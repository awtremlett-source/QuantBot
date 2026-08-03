# GRAND_TODO — QuantBot   (archive DONE rows to keep this ≤10k chars)

Legend: [ ] open · [~] in progress · [x] done

## Phase 1 — Foundations (data layer + firewall + paper plumbing)
- [x] Safety rails: git, .gitignore, .env.example, SCARS.md, session log
- [x] Onboarding decisions captured; clock resynced; prior work archived
- [x] Repo scaffolding (CLAUDE/STATE/GRAND_TODO/README/EDUCATION/FOUNDING_DIRECTIVE)
- [x] First GitHub push → github.com/awtremlett-source/QuantBot
- [x] venv + requirements.txt (pandas numpy pyarrow requests scikit-learn
      statsmodels matplotlib pytest hypothesis ruff mypy)
- [x] Data sources locked: yfinance (price) + StockGeist (sentiment)
- [x] data_store API: SQLite(WAL) RAW+CLEAN schema; single-writer law
- [x] Front-door ingest (one writer; unit/scale/sanity; quarantine)
- [x] RAW→CLEAN reconciliation (verify-and-copy; split-adjusted source) → price_clean
- [x] §7 VALIDATION FIREWALL — all three parts built; birth certificate passed 2026-07-14:
      coin-flip rejected p=0.85, exploitable pattern passed p=0.005.
  - [x] Backtest tests — honest engine + no-lookahead spy guard (research/backtester.py)
  - [x] Walk-forward tests — no-fit-on-test guard, anchored/rolling (research/walk_forward.py;
        purged/embargoed CPCV deferred to a later hardening pass)
  - [x] Monte Carlo / known-null tests — coin-flip null distribution + significance gate
        (research/monte_carlo.py); verdict on RISK-ADJUSTED Sharpe; feeds trials.jsonl
- [ ] FIREWALL DESIGN follow-ups (needed before the ~100-ticker sweep, not before NVDA):
  - [ ] Sweep-level (portfolio) multiple testing: ~100 tickers × keep-winners = ~100 extra
        lottery tickets. Count the WHOLE sweep as trials, OR reserve one untouched
        cross-ticker holdout stretch tested ONCE at the very end.
  - [ ] Cross-ticker generalization: run an NVDA-fitted strategy UNTOUCHED (no re-tuning)
        on 2–3 other tickers; still working = real pattern, not a curve-fit.
- [ ] NEAR-TERM (before ANY real strategy):
  - [x] Re-ingest NVDA history back to ~2015 — DONE 2026-07-14: 2,898 CLEAN bars from
        2015-01-02; splits pass; COVID crash / 2018 / 2022 storm data in.
  - [x] Judge strategies on RISK-ADJUSTED terms — wired: walk-forward selection metric and
        Monte-Carlo verdict are both Sharpe-based, not raw return.
  - [x] Auto append-only TRIAL LOG — research/trial_log.py; run_backtest/walk_forward/
        monte_carlo auto-append to data/trials.jsonl (gitignored), so Deflated Sharpe
        counts EVERY try.
- [ ] Universe: choose ~100 liquid US names → GO
- [ ] Count reconciliation (in-zip vs staged vs DB) + ±10% universe invariant
- [ ] Integrity census v1 (CLEAN/SUSPECT/CORRUPT certificates) + data-quality meter
- [ ] FIRST LIGHT: chart any ticker + first daily digest
- [ ] Telegram bot live (BotFather → .env → "hello")
EXIT: firewall passes its known-null test; census ≥95% CLEAN on active universe.

## Phase 2 — CORE (consistency engine; ~80–90% paper capital)
- SEQUENCING: prove ONE simple ALWAYS-ON strategy through the FULL firewall FIRST.
  Regime-switching is UNPROVEN (adds knobs/lag/switching costs, often fails to beat a single
  strategy once tested honestly) — add it ONLY if it beats the always-on strategy OUT-OF-SAMPLE.
- [x] NVDA always-on SMA trend strategy through the full firewall (validated 2026-07-14,
      both MC gates)
- [x] Paper loop: SMA-200 NVDA (live 2026-07-14) — book ≡ backtester birth certificate;
      killswitch/catch-up/resume/partial-bar all test-proven
- [x] ingest: re-fetch-and-supersede trailing RAW bars (frozen partial-bar fix; live
      2026-07-15 — 07-14 bar healed to official values, old rows archived)
- [ ] sizing: cash-floor (no slippage overdraft at full weight) — changes fill physics,
      MUST re-run the full firewall before adoption
- [ ] monitors: prove drawdown warning red-on-broken (#9)
- [x] Deflated Sharpe formally applied to the logged trials (2026-07-28, N=481:
      champion DSR=0.898 FAIL / challenger 0.800 FAIL / switcher 0.933 FAIL at
      the pre-committed 0.95 bar — mechanism MET, verdicts recorded; see STATE.md
      governance line)
- STRATEGY DEEPENING (NVDA — before any ticker #2; rubric = docs/MANIFEST.md):
  - [x] Challenger 1: mean-reversion through the FULL firewall (2026-07-15) —
        validated spare part, SURVIVED 2× costs (base gates thin: p=0.039/0.041;
        2× stress sharpe +0.93, gate-B p=0.025 with null also at 2×). Does NOT
        beat champion (+1.04 vs +1.19 OOS) — complementary low-exposure/shallow-DD
        profile for the switcher. NOT live. Trial count 108+/run (rubric #2)
  - [x] Regime-switcher experiment — DECIDED 2026-07-16: ADOPTED per pre-committed
        rules. Beat champion OOS base +1.27 vs +1.19 (matched MC p=0.004); 2× cost
        stress sharpe +1.1999 > champion-at-2× +1.19 (RAZOR-THIN, ~+0.01) with the
        matched-window null also at 2× p=0.002. Threshold instability (1.8/1.2/1.5
        across folds) = known wart for the annual refit. NOT live yet — see swap brick.
  - [x] LIVE SWAP — DONE 2026-07-16: paper config SMA-200 → regime switcher
        (deployment threshold 1.5, fit_best on full history, in-sample sharpe +1.37,
        3 trials logged; rides the switcher's firewall pass). Transition = no-op
        (calm regime → SMA-200 → stay long). Drawdown warning re-anchored −48.8% →
        −36.5%. Rubric condition 4 FULLY CLOSED (switcher adopted + live).
  - [~] Journal backup policy — mechanism LIVE 2026-07-17 (SQLite online-backup +
        verify + 14-day retention; piggybacks every live loop run, failure warns but
        never blocks; tools/backup.py CLI). OPERATOR ACTION REQUIRED: set
        QUANTBOT_BACKUP_DIR to an off-laptop folder (OneDrive) — rubric condition 7
        counts as MET only when backups land off-laptop; stays [~] until the
        operator confirms the destination.
  - [ ] Monthly health report (measure, never refit): rolling OOS-vs-live tracking,
        drawdown vs validated envelope, regime-fire counts, trade/cost tally —
        diagnostics feed the ANNUAL refit; no parameter changes outside the annual
        cycle (or firewall-approved cadence change).
  - [ ] Refit-cadence experiment (after switcher): same walk-forward, monthly step
        vs annual step, OOS decides — adopt faster cadence ONLY if it wins.
  - [ ] Risk ladder (drawdown-based de-risking): mechanical daily overlay on the live
        engine — cut to half-size at drawdown rung X, flat beyond the validated-worst
        rung Y, re-enter on recovery rung Z; rungs chosen via firewall (candidates:
        -35% / -55% / -30%). Changes fill physics -> FULL firewall re-run required
        before going live. Complements (does not replace) the annual refit; responds
        to strategy health, never to operator mood.
  - (Deflated Sharpe + monitors items above = rubric conditions 2 and 6 — not duplicated)
- [ ] SPY/QQQ above 200-day MA + vol-target (~10% ann.), else cash (subsequent)
- [ ] Run through firewall (discipline), then paper it; show the equity curve

## Phase 3 — EXPLORER (10–20%, one at a time, each through the firewall)
- [ ] RSI(2) dip-buy above 200-DMA
- [ ] Dual-momentum ETF rotation
- [ ] Turn-of-month (the multiple-testing lesson; must survive deflation)

## Phase 4 — Regime gate (trend/chop/stress; risk-off insurance; validate on stress)
   GATED: build only if it beats the single always-on strategy OUT-OF-SAMPLE (see Phase 2 sequencing).
## Phase 5 — ML meta-labeling (triple-barrier, frac-diff features, GBM; NO deep nets)
## Phase 6 — ENSEMBLE (the Simons destination): 3–6 validated strategy families ×
   many tickers, low pairwise correlation, effective-N monitored; each signal thin
   alone, the portfolio is the edge. (Was "Portfolio"; effective-N monitor and
   stressed-corr caps unchanged. No new items — cross-ticker test, universe
   selection and the portfolio items above were already heading here.)
- [ ] Thematic watchlist generator — candidate-DISCOVERY feed into Phase-6 universe
      selection; nominates tickers for RESEARCH, never positions; every candidate
      faces the full firewall. (Thematic theses REJECTED as a trading signal,
      2026-07-28 — see STATE.md.)
## Phase 7 — Graduation rubric (§15), then live at irrelevant size

## Deployment (end goal)
- [ ] Installer/deployment package: one command bootstraps venv from pinned
      requirements, initializes/verifies the DB, registers the scheduled tasks,
      wires killswitch + digest access. May be BUILT pre-graduation (packaging
      risks nothing); EXECUTING it on the always-on PC is gated behind the full
      rubric.

## Standing / cross-cutting
- [ ] Killswitch (STOP_NEW_TRADES + flatten-all) from day one; monthly fire-drill
- [ ] Fast drawdown-based risk-off ("position drops X% → cut risk NOW") — immediate complement
      to the laggy volatility stress signal (acts before vol confirms).
- [ ] Trade journal from first paper trade (signal→order→fill→exit→feature snapshot)
- [ ] Nightly carousel = simplest correctness loop (§10)
- [ ] EDUCATION entry + ONE ≤20-min video + learning-log line per milestone
- [ ] docs/WATCH_LIST.md in week one (verify channels live; refresh monthly)
- [ ] Daily auto clock-sync scheduled task (admin)
- [ ] Verify T212 auth scheme against official docs before any order

## Deferred / shelved
- [ ] Sentiment (StockGeist) = v2 feature: free tier lacks history to backtest → can't pass the
      firewall. START COLLECTING now to build future history, but keep OUT of v1 buy/sell decisions.
- [ ] Emergency-budget / severity-weighted faster polling (4h→1h, credit reserve) is INTRADAY-ONLY;
      does nothing on daily data — SHELVE until/unless the system goes intraday.
