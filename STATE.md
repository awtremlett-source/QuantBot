# STATE.md — resume in seconds

Phase: 1 (Foundations).  Updated: 2026-07-16.

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
- Simons alignment (2026-07-20): breadth of thin validated edges over depth of one
  edge; daily horizon locked (costs kill short horizons at our scale — measured);
  returns anchors stay honesty-first.

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
- PAPER LOOP LIVE (2026-07-14): first decision journaled — NVDA above SMA-200, pending
  buy at next open, £10k cash. Book ≡ backtester to 1e-9 (birth certificate).
  Killswitch, catch-up, crash-resume, partial-bar exclusion all test-proven.
  (execution/: frozen config law — any change = new strategy = full firewall re-run.
  69 tests green; ruff + mypy --strict clean.)
- Partial-bar fix live (2026-07-15): 07-14 bar superseded to official (close
  211.24→211.80, vol 71M→118M), bonus 07-13 volume revision caught; old rows archived
  to quarantine (never deleted). Trailing 7-day re-fetch window on every ingest;
  rows_superseded in the summary.
- FOUND+FIXED same night: loop read CLEAN as-of its PRE-sync clock, so a rebuild
  night made it silently process nothing (bars=0) — now re-reads the clock post-sync;
  fail-first test proven red on old code, green on fix.
- FIRST FILL (2026-07-15): order #1 settled at 07-14 open — sized at raw open 208.20
  → 48.030740 shares; fill 208.3041 = open × 1.0005 (the £5 is SLIPPAGE, not
  commission; commission_pct is 0). cash −£5.00 = slippage overdraft; matches
  validated backtest physics; cash-floor sizing queued as a firewall-gated
  refinement. Equity 10,167.91 at close 211.80. 76 tests green.
- CHALLENGER 1 (2026-07-15): mean-reversion (Cutler-RSI dip-buy above SMA-200 trend,
  strategies/mean_reversion.py) through the FULL firewall — VALIDATED SPARE PART,
  NOT live. Base: stitched OOS 2018→2026 sharpe +1.04, maxDD −29.6%, exposure 31.1%,
  420 trades; both MC gates passed THINLY (full-series p=0.039, matched-window
  p=0.041 vs alpha 0.05). 2× cost stress (law #15): sharpe +0.93, gate-B p=0.025
  with the null ALSO paying 2× — SURVIVED (champion at 2×: +1.19, barely moved).
  Does NOT beat the champion (+1.04 vs +1.19); value = complementary profile
  (shallower DD −29.6% vs −48.8%, 31% exposure) → regime-switcher ingredient.
  Honest trial count now 108+/walk-forward run — Deflated Sharpe pending (rubric
  #2). 91 tests green; ruff + mypy --strict clean.
- REGIME SWITCHER ADOPTED per pre-committed rules (2026-07-16). Severity-gated
  SMA-200/mean-reversion switcher (strategies/regime_switcher.py; threshold walk-forward
  tuned over {1.2,1.5,1.8}, re-entry hysteresis 0.8 FIXED). Base: beat champion OOS
  stitched 2018→2026 sharpe +1.27 vs +1.19, matched-window MC p=0.004. 2× cost stress
  (law #15, 2026-07-16): stitched sharpe +1.1999 vs champion-at-2× +1.19 — pre-committed
  bar (> +1.19) passed by a RAZOR-THIN margin (~+0.01, and the champion figure is a
  2-dp record — honesty note, not a re-litigation); matched-window null ALSO at 2×
  (n=1000, seed=0) p=0.002, 99.9th pct, null mean +0.43; maxDD at 2× −36.9% (champion
  −48.8%); base-run repro before stressing landed exactly +1.2734. VERDICT: SURVIVED →
  ADOPTED. Live swap of the paper config = separate next brick (config law: the swap
  rides THIS firewall pass; execution/ stays frozen on SMA-200 until that brick).
  Threshold instability (1.8/1.2/1.5 across folds) recorded as a known wart for the
  annual refit. Trial log now 17 records (walk-forward repro + 2× walk-forward + 2× null).
- PAPER NOW DRIVEN BY SWITCHER (2026-07-16): deployment threshold 1.5 fit on full
  history per validated process (fit_best over {1.2,1.5,1.8} on all 2,898 CLEAN bars,
  in-sample sharpe +1.3692; 3 trials logged → trials.jsonl now 20); transition
  journaled (no-op — first live decision on the 07-15 bar: calm regime → SMA-200 →
  stay long 48.030740 shares, placed=0, equity £10,201.53); drawdown warning
  re-anchored to −36.5% (switcher stitched OOS maxDD; −36.9% at 2×; warning fires at
  the shallower line). Config law intact: swap rides the switcher's firewall pass
  (be6f007/f55b738) — no loop-mechanics or research/ changes; loop tests now pin
  their small SMA fixture explicitly, and the config has its own birth-certificate
  test (tests/execution/test_config.py). 102 tests green; ruff + mypy --strict clean.
  next_refit_due unchanged: 2027-07-14.
- JOURNAL BACKUP (2026-07-17): backup mechanism live (SQLite online-backup + verify +
  14-day retention), piggybacked on the loop — every LIVE run snapshots the journal;
  backup failure warns loudly but NEVER blocks trading (scoped catch+log, law #12
  compliant). tools/backup.py + CLI: python -m tools.backup --db data/quantbot.db
  [--dest DIR] [--retain-days N]. Verify-before-trust: snapshot must open read-only,
  pass integrity_check, match all 6 table counts vs source + trials line count; a
  failed verify deletes the artifacts and raises. Dest: arg > QUANTBOT_BACKUP_DIR >
  data/backups/ (gitignored via data/). First live run: quantbot-20260717.db verified
  (6 tables, 15,737 rows) + trials-20260717.jsonl, LOCAL-ONLY warning fired as
  designed. OPERATOR ACTION REQUIRED: set QUANTBOT_BACKUP_DIR to an off-laptop folder
  (OneDrive) — rubric condition 7 counts as MET only when backups land off-laptop.
  113 tests green; ruff + mypy --strict clean.

## Known gap / next
- §7 VALIDATION FIREWALL: DONE (all 3 parts; birth certificate passed — see Done).
  Deferred hardening for later: purged/embargoed CPCV; sweep-level deflation + cross-ticker
  holdout before the ~100-ticker universe (GRAND_TODO "FIREWALL DESIGN follow-ups").
- NEXT ACTIONS: (a) daily MORNING loop (python -m execution.paper_loop --db
  data/quantbot.db — processes yesterday's bar; a bar counts finished once its date
  is fully past UTC, so 07-15's bar is readable after 1am UK; loop now trades the
  SWITCHER config). (b) Strategy deepening per docs/MANIFEST.md graduation rubric
  (condition 4 closed by the switcher adoption + live swap). NO export / NO ticker
  #2 until the rubric passes (all 7 conditions).

## Open flags
- QUANTBOT_BACKUP_DIR not yet set → backups are LOCAL-ONLY (data/backups/ on the
  same laptop). Rubric condition 7 NOT met until the operator points it at an
  off-laptop folder (e.g. OneDrive).
- Drawdown-warning red-on-broken proof deferred to monitors brick (law #9).
- T212 auth scheme: verify single-key header vs KEY:SECRET Basic before any order (§6).
- Daily auto clock-sync task still to set up (admin).
- gh CLI not installed → use plain git for GitHub ops.
