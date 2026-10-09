# GRAND_TODO — QuantBot (archive DONE rows to keep this ≤10k chars)

Legend: [ ] open · [~] in progress · [x] done

**Direction 2026-09-26 → TWO PARTS: a bot that trades, an advisor that suggests.**
The plan and the detail for every stage below live in **docs/plan/PLAN_V3.md**;
this page is only the running order. Earlier backlogs are archived whole at
`docs/archive/GRAND_TODO_v2.md` and `docs/archive/GRAND_TODO_v1.md`
(quarantine, never delete).

## The stages (detail: docs/plan/PLAN_V3.md)
- [x] S0 Plans V2 + V3, each pinned by its own gate (2026-09-21 / 2026-09-26)
- [x] S1 `qb2` skeleton + one fresh pinned env + the qb2 wall (2026-09-26, 22c67f7)
- [x] S2a Broker facts + READ-ONLY demo client (2026-09-27): docs/t212/FACTS.md
      (one row per fact, sourced and dated) · qb2/execution/t212_client.py, GET-only,
      practice-host-only, per-endpoint throttle, 429 back-off · no trailing stop and
      no amend endpoint at T212 -> the stop is OURS (P10) · no price for an instrument
      we do not hold -> S2b must design around it · auth flag resolved
- [x] S2b Cost model, fill recorder, killswitch, price checks, disarmed sender,
      qb2 fingerprint (2026-09-27). Bot horizon REVERSED to same-day (P4); P17 added
      to decide the market by test; S13 gained power safety; FACTS 2c → CONFLICT
- [x] S3a INTRADAY RECORDER (2026-09-30): 119-name provisional recording list, 1m +
      5m/1h backfill, forming-bar drop, quarantine-never-overwrite, DST-week tested,
      LOST gaps recorded, freshness meter red-on-broken, QB2-Recorder task registered
      per-user MON-FRI hourly. Demo smoke test run; key is read-only (no orders scope)
- [x] S3d (2026-10-03) Dividends for 221 names (0 suspect, pence converted at the
      boundary) · daily bars + GBP/USD · total return in POUNDS (P3) refusing Adj
      Close · advisor earnings 171 · minute-label rule enforced at the data layer.
      S3 now waits only on the quote delay (1 US session of 3, London 0)
- [x] S3c (2026-10-02) Recorder made observable and fast; the 131-name fault was
      runs being KILLED part-way (log was literally "^C"); ledger per run; delay
      sampler first; earnings dates for the bot 50; census GREEN 98.2% on 5m.
      STILL OPEN for S3: dividends not ingested; advisor earnings not fetched
- [~] S3b (2026-10-01) Universes built from evidence: 226 recorded, bot 50 PROPOSED
      in three tagged sleeves, advisor 171, provably disjoint · every name resolved
      against T212's own instrument list (4 old names were WRONG, incl. a company
      that became another company) · FRONT DOOR RAW→CLEAN, one writer, manifest as
      commit point, pence→pounds once, splits never re-applied · census + meter with
      birth certificate · first-light charts. STILL OPEN: earnings dates not
      ingested (S3 gate line) · quote delay NOT YET ENOUGH (US 9, London 4 of 20)
- [x] (2026-10-06 CLOSED: 50/50 priced, £46.59 of £100) QT-12 P20 ANCHOR BUYER (2026-10-04): qb2/execution/anchors.py BUILT + dry-run
      (45 names to buy, est £45.69; 5 already held), fences F1–F12 each seen red;
      the ONE order path, practice-only. LIVE = Part B. S3 close renumbered QT-13
- [x] QT-12R (2026-10-07) Recorder London diagnosis: PC shut down every London
      morning (no code fault). Session meter wired + RED below 3/session;
      delay_count.py: full calendar sessions only, each bar once → docs/reports/QT-12R.md
- [x] QT-12S (2026-10-08) Hourly status push: task QB2-StatusPush (Mon–Fri :50,
      08:50–21:50 UK) pushes logs/status_push/recorder_status.md to orphan branch
      "status" (one commit, force-pushed); recorder untouched → docs/reports/QT-12S.md
- [x] QT-13 (2026-10-09) row o VERIFIED (US 1.25 / London 16.66 min); census RED
      (clean store unfed since 2 Oct); offline default run → docs/reports/QT-13.md
- [x] QT-13b (2026-10-10) **S3 DONE**: after-hours step runs front door + 5m/1m
      census + labels + digest; stale/below-gate = RED; label pass needs new bars;
      real-store 5m census 98.2% fresh to 9 Oct → docs/reports/QT-13b.md
- [ ] S4 Firewall v2: pre-registration, known-null re-proved, benchmark (D3),
      survivorship mark-down
- [ ] S5 Safety layer FIRST: stops, brakes, pot limits, age + earnings checks,
      crash replays (2008/2020/2022) + false-alarm counts
- [ ] S6 Bot signals, one at a time, each pre-registered + moving buys (P11)
- [ ] S7 Bot combined model + calibration + sizing (D2) + inverse test; must beat
      best single signal, v1 AND the benchmark out-of-sample at 2× costs
- [ ] S8 Bot evolution: challengers in shadow + machine search (stops on
      CORRECT/EXHAUSTED, never on profit)
- [ ] S9 Advisor engine + scorecard (every suggestion recorded as if followed)
- [ ] S10 Demo execution: batched open orders, stops held at T212 and raised
      daily, daily reconciliation, killswitch fire-drill. **Forward clock starts**
- [ ] S11 One app: TradeScout rebuilt with advisor screens AND bot screens
- [ ] S12 Forward paper run → graduation rubric (DSR ≥ 0.95 at then-current N).
      Demo only; no real money at this stage
- [ ] S13 Move to the always-on home PC, every check re-proved there. Comes BEFORE
      real money: our code holds the stops, so it must be a machine that stays awake
- [ ] S14 Stocks ISA at a size that does not matter yet — only after S13
- [ ] S15 Phone alerts — LAST, as asked; prefer T212's own mobile app if it can

Every stage ships an Exit gate (proven red-on-broken, #9), an Enforcer and a
Built/Wired/Armed checklist.

## Awaiting the operator
- [ ] D1 advisor risk rule (loss-at-stop cap vs the 1% rule) · D2 bot sizing ·
      D3 the benchmark — recommended defaults in PLAN_V3 "DECISION REQUESTED"
- [x] PRACTICE API KEY in .env (2026-09-30) — smoke test connects and reads
- [x] KEY REPLACED (2026-10-01) with all ten read endpoints granted, Execute OFF.
      Closed both gaps: instrument list saved and the recording list verified
      against it; FACTS row g settled from order history (one position per share)
- [x] RECORDER FIXED (2026-10-02, S3c): operator applied the battery/catch-up
      settings; hourly run cut from >1h (never finishing) to 1.6–2.6 min; the task
      now runs windowless via pythonw with "Start in" set — the System32 window and
      the missing log are both gone, confirmed by probe and a real task run
- [x] BOT UNIVERSE AGREED (2026-10-02), operator verbatim: "GO on bot universe
      v1" — 50 names in three tagged sleeves. Permission to BUILD and BACK-TEST;
      the sender stays disarmed. S4 still blocked by S3's other two gate items
- [x] (2026-10-05 LIVE: 26 filled, 18 refused) ORDER KEY for the P20 anchors (QT-12 Part B): a NEW practice key with ONLY
      Orders – Execute + Account data → T212_ORDER_KEY / T212_ORDER_SECRET in .env
      (the read-only key stays as it is) → say "GO QT-12 LIVE". docs/t212/SETUP.md
- [ ] FACTS row 2c must be settled before S14: can Limit/Stop/Stop-Limit orders be
      placed on a REAL-MONEY account? One tiny live test, or a written answer from
      T212 support. Sources disagree and going live on a guess is not acceptable

## v1 — KEEPS RUNNING, UNTOUCHED (the baseline v2 must beat)
The live NVDA regime-switcher, its journal, monitors, backups and scheduled runs
carry on exactly as they are. Do not edit v1's engine folders; the fingerprint is
checked in every box.
- [x] `QUANTBOT_BACKUP_DIR` → OneDrive QuantBot_Backups (user env var), 2026-10-05:
      first journal + ledger backups landed there, hash-verified (rubric 7)
- [ ] OPERATOR ACTION: daily auto clock-sync scheduled task (needs admin)
- [ ] Run the loop once to clear the catch-up gap (31 trading days unprocessed as
      of 2026-09-21; the loop is catch-up-safe)
- [x] Verify T212 auth scheme against the official docs (2026-09-27): Basic,
      base64 of KEY:SECRET — docs/t212/FACTS.md row a
- [ ] Flatten-all half of the killswitch still TBD; monthly fire-drill via the GUI

## Known defects (found, recorded, not yet fixed)
- [ ] `.env.example` still says the T212 auth scheme is "to verify" and may be a
      single api-key header. It is not: it is Basic KEY:SECRET (FACTS.md row a).
      The file sits inside the engine fingerprint, so a box that may change engine
      config must correct the comment and prune the unused name.
- [ ] 52 inherited type errors in 5 `manual/scout/*` modules — counts and burn-down
      in `docs/merge/TYPING_DEBT.md`
- [ ] Manual suite prints 2 pre-existing Qt "access violation" lines at teardown
      (present in the untouched original repo too); not diagnosed
- [ ] Manual trade journal not migrated — `trades.shares` is INTEGER where the code
      declares REAL; needs a one-table rebuild under PROPOSE→GO (MERGE_PLAN 3b)

## Standing / cross-cutting
- [ ] EDUCATION entry + learning-log line per milestone
- [ ] `docs/WATCH_LIST.md` (verify channels live; refresh monthly)
- [ ] Nightly carousel = simplest correctness loop (§10)

## Deferred / shelved
- [ ] Sentiment (StockGeist): free tier lacks the history to backtest, so it cannot
      pass the firewall. Collect now to build history; OUT of buy/sell decisions.
- [ ] Intraday / faster polling: does nothing on daily data, and true speed needs a
      paid feed (PLAN_V3 "the honest limit"). Shelved.
- [ ] Sweep-level deflation + untouched cross-ticker holdout — folded into S4/S7
- [ ] Refit-cadence experiment, risk ladder, cash-floor sizing — v1 ideas that only
      matter if v1 continues past v2; re-open from the archive if so
