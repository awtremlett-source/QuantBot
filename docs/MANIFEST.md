# MANIFEST — QuantBot system inventory (single page)

Updated: 2026-07-15. What exists, what is proven, and what must be true before
this logic leaves NVDA or this laptop.

## ENVIRONMENT
- Python 3.13.7 in .venv; 12 pinned deps (requirements.txt).
- Windows 10 laptop, sometimes-off → every loop is catch-up-safe by design.

## DATA
- NVDA: 2,898 CLEAN daily bars, 2015-01-02 → present. Splits pass continuity
  (2021 4:1 boundary move 0.90%; 2024 10:1 move 0.74%).
- RAW self-heals: trailing re-fetch-and-supersede on every ingest;
  quarantine-never-delete throughout. DB: data/quantbot.db (SQLite WAL, gitignored).

## VALIDATED STRATEGY
- NVDA SMA-200 always-on, long-only (execution/config.py — FROZEN: any change =
  new strategy = full firewall re-run).
- Stitched OOS 2018→2026: sharpe +1.19, maxDD −48.8% (vs buy-and-hold −66.4%).
- Monte Carlo: full-series p=0.003; matched-window p=0.007 (99.4th pct).
- Next refit due 2027-07-14.

## FIREWALL
- Backtester (no-lookahead spy) · walk-forward (no-fit-on-test spy) · Monte Carlo
  known-null gate (coin-flip REJECTED p=0.85; exploitable pattern PASSED p=0.005 —
  it fails junk without failing everything).
- Trial log: data/trials.jsonl, append-only — every try counts toward Deflated Sharpe.

## PAPER
- Live since 2026-07-14. First fill: 48.030740 sh @ 208.3041 (07-14 open + slippage).
- Daily rhythm — each MORNING (processes yesterday's bar):
  `python -m execution.paper_loop --db data/quantbot.db`

## LAWS
- docs/SCARS.md — 23, binding on every session and every loop.

## END GOAL
- QuantBot ships as an installable application; target = the always-on home PC;
  migration is rubric-gated (see GRADUATION RUBRIC below + GRAND_TODO "Deployment").

## OUT OF SCOPE
- Long-horizon thematic investing (innovation/narrative theses) = separate product,
  separate rules — NOT QuantBot. Thematic names may enter only as RESEARCH candidates
  via the Phase-6 watchlist generator, through the full firewall, never as positions.

## OPEN FLAGS
- QUANTBOT_BACKUP_DIR unset → backups LOCAL-ONLY (rubric 7) · cash-floor sizing
  (firewall-gated).

## GRADUATION RUBRIC — before this logic moves to ticker #2 or another device (ALL required)
1. ≥1 month clean daily paper runs, incl. at least one real catch-up after dark days.
   [~ half met: real 8-bar catch-up banked 2026-07-28; month-clock runs to ~2026-08-14]
2. Deflated Sharpe formally applied to the logged trials.
   [MET-as-mechanism 2026-07-28 — verdicts at N=481, bar 0.95: champion DSR=0.898
   FAIL / challenger 0.800 FAIL / switcher (live) 0.933 FAIL; governance in STATE.md]
3. Challenger experiment complete: ≥1 alternative strategy through the full firewall.
4. Regime-switcher experiment DECIDED: adopted only if it beats SMA-200 OOS,
   else rejected-and-recorded.
5. Cross-ticker generalization test run (NVDA-fit strategy untouched on 2–3 tickers).
6. Monitors brick live with red-on-broken proof.
   [MET 2026-08-06 — 5 observe-only meters in the digest; each unit-proven RED on
   broken fixtures + live RED on doctored DB copies (stale CLEAN, -40% drawdown)]
7. Journal backup policy in place.
