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
- [ ] Deflated Sharpe formally applied to the logged trials
- STRATEGY DEEPENING (NVDA — before any ticker #2; rubric = docs/MANIFEST.md):
  - [ ] Challenger 1: mean-reversion strategy through the FULL firewall (validated
        spare part; not live)
  - [ ] Regime-switcher experiment: SMA-200 + challenger, severity-gated; judged vs
        SMA-200 OOS; adopt ONLY if it wins, else record the rejection
  - [ ] Journal backup policy: data/ journal + trials.jsonl protected off-laptop
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
