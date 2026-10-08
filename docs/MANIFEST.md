# MANIFEST — QuantBot system inventory (single page)

Updated: 2026-10-05 (lines on qb2, the daily run and the scar count refreshed). What exists, what is proven, and what must be true before
this logic leaves NVDA or this laptop.

## ENVIRONMENT
- Python 3.13.7 in .venv; 12 pinned deps (requirements.txt).
- Windows 10 laptop, sometimes-off → every loop is catch-up-safe by design.

## ARCHITECTURE MAP (moved here from CLAUDE.md 2026-09-27 to keep it small)
- ingest/ ONLY writer to the data store (front door, §5); unit/scale checks here
- data_store/ storage API; SQLite(WAL) system-of-record; RAW vs CLEAN (parquet deferred)
- research/ §7 firewall, backtester, labelers, feature builders
- strategies/ one file per strategy + trigger_fixture / anti_fixture
- risk/ sizing (1% rule wins), ratchet exits, killswitch
- execution/ T212 demo client + paper book
- monitors/ meters, canary, daily digest
- tools/ operational scripts
- tests/ mirrors tree; tests/museum/ = incident regression fixtures
- docs/ SCARS.md, EDUCATION.md, FOUNDING_DIRECTIVE.md, sessions/
- manual/ the operator's own app (walled off; two read-only doorways to v1)
- qb2/ v2: data ingest research execution tools built; signals model sizing ui empty (-> qb2/README.md)
  - qb2/ingest/ recorder.py (RAW capture) · tickers.py (T212<->yfinance spelling)
    verify_universe.py (resolve names against T212's OWN list; never constructs a
    ticker) · constituents.py (index membership, parsed from a saved page)
  - qb2/data/ front_door.py (the ONLY writer into data/clean) · census.py (how much
    data is really there, with a red-on-broken meter)
  - qb2/ingest/earnings.py when each company reports · dividends.py what each
    paid, converted at the boundary and checked against the price it came from ·
    daily.py daily bars + GBP/USD. All three carry knowable_time, so a back-test
    cannot use a fact before it was published
  - qb2/research/total_return.py P3's number: return in POUNDS = price + dividends
    + the currency effect. Refuses Adj Close (that would count dividends twice)
  - qb2/data/access.py THE way a strategy reads bars; enforces the minute label
    (MINUTE_OK / FIVE_MIN_ONLY) so a series of real gaps never reaches a model
  - qb2/execution/ t212_client.py (GET-only) · costs.py · fill_recorder.py ·
    safety.py (killswitch, P14 checks, flatten = position − anchor) · sender.py
    (ARMED = False) · anchors.py (QT-12: P20 anchor buyer — the ONE order path,
    practice-only, buy-only, own key, capped; nothing in qb2 may import it) ·
    anchor_ledger.py (its append-only ledger, data/anchors/ledger.jsonl; the bot
    reads anchor quantities from here, never from anchors.py)
  - qb2/tools/ build_universe.py (writes docs/universe/) · first_light.py (charts
    from CLEAN only) · sample_delay.py (measures FACTS row o) · delay_count.py
    (which samples count: full calendar sessions, each bar once; the meter that
    goes red when a session has under 3 samples) · status_push.py (QB2-StatusPush
    task: hourly status file → orphan branch "status", secret scan first) · record_now.py (hourly top-up
    vs after-hours catch-up, under a single-writer lock, with a per-name ledger) ·
    run_recorder.bat (one log per run, kept 30 days) · fingerprint.py
- logs/recorder/ one log per recorder run, gitignored, rotated after 30 days
- docs/universe/ the versioned universes + README (start here for what we trade)
- reports/first_light/ the dated charts drawn from the clean store

## DATA
- NVDA: 2,898 CLEAN daily bars, 2015-01-02 → present. Splits pass continuity
  (2021 4:1 boundary move 0.90%; 2024 10:1 move 0.74%).
- RAW self-heals: trailing re-fetch-and-supersede on every ingest;
  quarantine-never-delete throughout. DB: data/quantbot.db (SQLite WAL, gitignored).

## VALIDATED STRATEGY
- NVDA SMA-200 always-on, long-only = the champion; LIVE since 2026-07-16 is the
  severity-gated regime switcher (execution/config.py — FROZEN: any change =
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
- Daily rhythm (STOPPED: Windows refuses the task since 28 Jul; revive/retire open):
  scheduled task runs the loop each morning; operator reads the
  Telegram message (digest + MONITORS) and acts only on RED. Manual run:
  `python -m execution.paper_loop --db data/quantbot.db`
- Monthly rhythm: QuantBot-Monthly (day 1, 07:45) writes data/health/ report;
  read the health summary; act only on RED (shadow reconciliation is the
  ongoing birth certificate).

## LAWS
- docs/SCARS.md — 24, binding on every session and every loop.

## END GOAL
- QuantBot ships as an installable application = headless engine + control-panel
  GUI (observe + governance only; tools/run_gui.bat); target = the always-on
  home PC; migration is rubric-gated (see GRADUATION RUBRIC + docs/DEPLOY.md).
- Installer built + verified locally 2026-08-06:
  `powershell -ExecutionPolicy Bypass -File install.ps1` (install; also
  -Verify / -Uninstall) → `python -m tools.installer install|verify|uninstall`.

## OUT OF SCOPE
- Long-horizon thematic investing (innovation/narrative theses) = separate product,
  separate rules — NOT QuantBot. Thematic names may enter only as RESEARCH candidates
  via the Phase-6 watchlist generator, through the full firewall, never as positions.

## OPEN FLAGS
- Backups off-laptop since 2026-10-05 (OneDrive QuantBot_Backups) · cash-floor sizing
  (firewall-gated).

## GRADUATION RUBRIC — before this logic moves to ticker #2 or another device (ALL required)
1. ≥1 month clean daily paper runs, incl. at least one real catch-up after dark days.
   [~ half met: real 8-bar catch-up banked 2026-07-28; month-clock stopped: daily task dead since 28 Jul]
2. Deflated Sharpe formally applied to the logged trials.
   [MET-as-mechanism 2026-07-28 — verdicts at N=481, bar 0.95: champion DSR=0.898
   FAIL / challenger 0.800 FAIL / switcher (live) 0.933 FAIL; governance in docs/archive/STATE_2026-10-05.md]
3. Challenger experiment complete: ≥1 alternative strategy through the full firewall.
4. Regime-switcher experiment DECIDED: adopted only if it beats SMA-200 OOS,
   else rejected-and-recorded.
5. Cross-ticker generalization test run (NVDA-fit strategy untouched on 2–3 tickers).
6. Monitors brick live with red-on-broken proof.
   [MET 2026-08-06 — 5 observe-only meters in the digest; each unit-proven RED on
   broken fixtures + live RED on doctored DB copies (stale CLEAN, -40% drawdown)]
7. Journal backup policy in place.
