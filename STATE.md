# STATE.md — resume in seconds

Phase: 1 (Foundations).  Updated: 2026-06-21.

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

## Known gap / next
- CLEAN gap CLOSED: read_price_asof now serves the reconciled, split-adjusted series.
- NEXT BRICK = §7 validation firewall skeleton + known-null birth-certificate test
  (BEFORE any strategy).

## Open flags
- T212 auth scheme: verify single-key header vs KEY:SECRET Basic before any order (§6).
- Daily auto clock-sync task still to set up (admin).
- gh CLI not installed → use plain git for GitHub ops.
