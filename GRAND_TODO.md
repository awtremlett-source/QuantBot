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
- [~] §7 VALIDATION FIREWALL — MANDATORY: all three required BEFORE any strategy is built,
      and the firewall must demonstrably FAIL a worthless strategy:
  - [x] Backtest tests — honest engine + no-lookahead spy guard (research/backtester.py)
  - [ ] Walk-forward tests — strategies scored ONLY on data they were not trained on
        (purged + embargoed CV · CPCV)
  - [ ] Monte Carlo / known-null tests — randomize/shuffle data or trades many times to
        measure luck; a random/worthless strategy MUST score worthless (deflated by number
        of trials: trials.jsonl · Deflated Sharpe · PBO · placebo). The firewall's birth-certificate.
  - [ ] DESIGN — sweep-level (portfolio) multiple testing: running the pipeline over ~100
        tickers and keeping winners = ~100 extra lottery tickets. Count the WHOLE sweep as
        trials, OR reserve one untouched cross-ticker holdout stretch tested ONCE at the very end.
  - [ ] DESIGN — cross-ticker generalization: run an NVDA-fitted strategy UNTOUCHED (no
        re-tuning) on 2–3 other tickers; still working = real pattern, not a curve-fit.
- [ ] NEAR-TERM (before ANY real strategy):
  - [ ] Re-ingest NVDA history back to ~2015 so stress/downtrend regimes have REAL examples
        (2018 selloff, 2020 COVID crash, 2022 bear). Split handling already covers older splits.
  - [ ] Judge strategies on RISK-ADJUSTED terms (Sharpe, max drawdown), NOT raw total return:
        buy-and-hold NVDA (+343%, ~4.4x near-straight-up) is a rigged benchmark a long-only
        strategy structurally cannot beat on total return.
  - [ ] Auto append-only TRIAL LOG — every backtest/fit run recorded, so Deflated Sharpe counts
        EVERY try (incl. casual tweak-and-reruns). Feeds trials.jsonl in the firewall.
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
- [ ] SPY/QQQ above 200-day MA + vol-target (~10% ann.), else cash
- [ ] Run through firewall (discipline), then paper it; show the equity curve

## Phase 3 — EXPLORER (10–20%, one at a time, each through the firewall)
- [ ] RSI(2) dip-buy above 200-DMA
- [ ] Dual-momentum ETF rotation
- [ ] Turn-of-month (the multiple-testing lesson; must survive deflation)

## Phase 4 — Regime gate (trend/chop/stress; risk-off insurance; validate on stress)
   GATED: build only if it beats the single always-on strategy OUT-OF-SAMPLE (see Phase 2 sequencing).
## Phase 5 — ML meta-labeling (triple-barrier, frac-diff features, GBM; NO deep nets)
## Phase 6 — Portfolio (3–6 low-corr; effective-N monitor; stressed-corr caps)
## Phase 7 — Graduation rubric (§15), then live at irrelevant size

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
