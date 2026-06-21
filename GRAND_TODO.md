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
- [ ] §7 validation firewall skeleton + known-null birth-certificate test (NEXT — before
      any strategy): purged+embargoed CV · CPCV · trials.jsonl · Deflated Sharpe · PBO · placebo
- [ ] Universe: choose ~100 liquid US names → GO
- [ ] Count reconciliation (in-zip vs staged vs DB) + ±10% universe invariant
- [ ] Integrity census v1 (CLEAN/SUSPECT/CORRUPT certificates) + data-quality meter
- [ ] FIRST LIGHT: chart any ticker + first daily digest
- [ ] Telegram bot live (BotFather → .env → "hello")
EXIT: firewall passes its known-null test; census ≥95% CLEAN on active universe.

## Phase 2 — CORE (consistency engine; ~80–90% paper capital)
- [ ] SPY/QQQ above 200-day MA + vol-target (~10% ann.), else cash
- [ ] Run through firewall (discipline), then paper it; show the equity curve

## Phase 3 — EXPLORER (10–20%, one at a time, each through the firewall)
- [ ] RSI(2) dip-buy above 200-DMA
- [ ] Dual-momentum ETF rotation
- [ ] Turn-of-month (the multiple-testing lesson; must survive deflation)

## Phase 4 — Regime gate (trend/chop/stress; risk-off insurance; validate on stress)
## Phase 5 — ML meta-labeling (triple-barrier, frac-diff features, GBM; NO deep nets)
## Phase 6 — Portfolio (3–6 low-corr; effective-N monitor; stressed-corr caps)
## Phase 7 — Graduation rubric (§15), then live at irrelevant size

## Standing / cross-cutting
- [ ] Killswitch (STOP_NEW_TRADES + flatten-all) from day one; monthly fire-drill
- [ ] Trade journal from first paper trade (signal→order→fill→exit→feature snapshot)
- [ ] Nightly carousel = simplest correctness loop (§10)
- [ ] EDUCATION entry + ONE ≤20-min video + learning-log line per milestone
- [ ] docs/WATCH_LIST.md in week one (verify channels live; refresh monthly)
- [ ] Daily auto clock-sync scheduled task (admin)
- [ ] Verify T212 auth scheme against official docs before any order
