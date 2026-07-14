# STATE.md — resume in seconds

Phase: 1 (Foundations).  Updated: 2026-07-14.

## Settled decisions
- Repo root: c:\Users\mtrem\TRADING. Remote: github.com/awtremlett-source/QuantBot.
  LOCAL git identity: awtremlett-source <…@users.noreply.github.com>.
- Prior work: ARCHIVED to archive/ (gitignored), building fresh.
- Demo capital: £10,000 GBP. £100/day = 1%/day = fantasy; honesty anchor only.
- Universe: focused ~100 liquid US names (specific list TBD via PROPOSE→GO).
- Machine: sometimes-off laptop → loops catch-up-safe.
- Data sources (locked): Price = yfinance (daily OHLCV; ~15-min delay, fine at 4h
  cadence). Sentiment = StockGeist (free 10k credits/month). Sources decoupled;
  point-in-time. Real-time feed deferred.
- Storage (locked): SQLite(WAL) system-of-record, RAW vs CLEAN. Parquet deferred.
- Cadence/budget (locked): 4h polling floor across ~100 names (~4,200 credits/mo).
  Spare credits = emergency reserve. Severity-weighted polling: calm 4h / mild ~2h /
  severe 1h+. Guardrails: global credit ceiling + optional weekly rationing.
- Regime detector (locked): emits a 0–1 severity SCORE (not just a label). Two jobs:
  pick which strategy runs + set polling cadence. Price = ground truth; sentiment =
  feature/confirmation only, never a standalone signal.
- Strategy model (locked): shared strategy TEMPLATES + one fitted CONFIG file per
  ticker (not 100 hand-written strategies). First ticker: NVDA.
- NVDA regimes (locked): 4 states — stress / calm-uptrend / choppy / calm-downtrend —
  from RV20 vs its own 1-yr median + SMA50 slope. Thresholds are walk-forward-validated
  parameters, NOT hardcoded constants. Boundary defenses: hysteresis, minimum dwell
  time, continuous severity blending, early-and-small sizing, blunt stress rules.
- Validation (locked): walk-forward + final untouched holdout; backtests simulate live
  data delay; Deflated Sharpe (penalised by number of trials).
- Plan-review principles (locked 2026-07-08):
  - Judge strategies on RISK-ADJUSTED terms (Sharpe, max drawdown), NOT raw total return
    (buy-and-hold NVDA is a rigged benchmark long-only cannot beat on total return).
  - Prove ONE simple ALWAYS-ON strategy through the firewall BEFORE any regime-switching;
    add regime-switching only if it beats the always-on strategy out-of-sample.
  - Sentiment = v2: collect StockGeist now to build history, but OUT of v1 buy/sell decisions.
  - Emergency-polling / intraday cadence SHELVED until/unless the system goes intraday.
  - Pull NVDA history back to ~2015 before strategy work (real stress/downtrend regimes).
  - Deflate at the SWEEP level (count all ~100 tickers as trials) OR keep a final cross-ticker
    holdout tested once.

## Done
- Safety rails: git init, .gitignore (verified: .env blocked, template kept),
  .env.example, docs/SCARS.md (21 laws), session log. Clock resynced by operator.
- Scaffolding: CLAUDE.md, STATE.md, GRAND_TODO.md, README.md, EDUCATION#1,
  FOUNDING_DIRECTIVE (verbatim). First commit (314ab84) pushed.
- Phase-1 env pinned (Python 3.13).
- data_store API committed + pushed (feaa00b): SQLite(WAL) RAW/CLEAN, point-in-time reads.
- Front-door ingest + quarantine table committed + pushed (3e3bd2d): one writer,
  sanity/scale checks, quarantine.
- FIRST LIGHT: live NVDA ingest = 618 daily RAW bars, 0 quarantined. Idempotency
  verified (re-run wrote 0, skipped 618). Point-in-time read mechanism verified via
  knowable_time on RAW rows.
- RAW→CLEAN reconcile brick complete (verify-and-copy; yfinance OHLC are ALREADY
  split-adjusted, so CLEAN is a validated copy, NOT re-divided — see SCARS #22).
  Committed + pushed (2f83ee7). Live NVDA rebuild = 618 CLEAN rows; continuity check
  pass (2024-06-10 10:1 split = 0.74% boundary move); max daily move 18.72% on
  2025-04-09. read_price_asof returns 618 continuous bars ($48 era → $207 latest).
  618 old double-adjusted rows archived to quarantine (superseded_by_rebuild).
- §7 VALIDATION FIREWALL COMPLETE (3/3). Backtester (8994d7a) + walk-forward (34956c4)
  + Monte-Carlo known-null gate & append-only trial log (fd7d893). BIRTH CERTIFICATE
  PASSED 2026-07-14: coin-flip REJECTED (p=0.85), FlatStrategy rejected (p=0.19),
  exploitable-pattern strategy PASSED (p=0.005) — the firewall demonstrably fails a
  worthless strategy without rejecting everything. Verdicts are RISK-ADJUSTED (Sharpe,
  not raw return); every run_backtest/walk_forward/monte_carlo run auto-appends one
  record to data/trials.jsonl (gitignored) so Deflated Sharpe counts EVERY try.
  60 tests green; ruff + mypy --strict clean.
- NVDA history extended to 2015 (live run 2026-07-14): 2,898 CLEAN bars (2015-01-02 →
  2026-07-14), both in-window splits pass continuity (2021 4:1 = 0.90%, 2024 10:1 =
  0.74%), COVID crash bar −18.4% present, max daily move 29.81% (2016-11-11 earnings
  pop, verified real). Reconcile rebuild-style supersede confirmed working as designed:
  old 618 CLEAN rows archived to quarantine (superseded_by_rebuild now 1,236 = 618+618)
  before atomic replace; summary's rows_quarantined counts validation only.
- FIRST VALIDATED STRATEGY — NVDA always-on SMA-200 accepted as Phase 2 candidate
  (2026-07-14). Walk-forward 9 folds / 45 trials, lookback 200 chosen 7/9; stitched OOS
  (2018→2026, 2,142 bars): sharpe +1.19, max DD −48.8% (vs B&H −66.4%). Firewall:
  full-series MC p=0.003; stricter matched-window MC (null mean +0.61) p=0.007,
  99.4th pct — PASSED BOTH. Trial log = 5 records. Caveats logged: single-ticker,
  Deflated Sharpe pending, paper = upper bound.

## Known gap / next
- §7 VALIDATION FIREWALL: DONE (all 3 parts; birth certificate passed — see Done).
  Deferred hardening for later: purged/embargoed CPCV; sweep-level deflation + cross-ticker
  holdout before the ~100-ticker universe (GRAND_TODO "FIREWALL DESIGN follow-ups").
- NEXT ACTION: paper-trading loop for SMA-200 (execution/paper_loop) —
  signal→order→fill journal from trade one. Catch-up-safe (sometimes-off laptop).

## Open flags
- T212 auth scheme: verify single-key header vs KEY:SECRET Basic before any order (§6).
- Daily auto clock-sync task still to set up (admin).
- gh CLI not installed → use plain git for GitHub ops.
