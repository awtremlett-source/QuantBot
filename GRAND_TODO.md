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
- [~] S3b (2026-10-01) Universes built from evidence: 226 recorded, bot 50 PROPOSED
      in three tagged sleeves, advisor 171, provably disjoint · every name resolved
      against T212's own instrument list (4 old names were WRONG, incl. a company
      that became another company) · FRONT DOOR RAW→CLEAN, one writer, manifest as
      commit point, pence→pounds once, splits never re-applied · census + meter with
      birth certificate · first-light charts. STILL OPEN: earnings dates not
      ingested (S3 gate line) · quote delay still UNMEASURED (0 samples)
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
- [ ] OPERATOR ACTION, loses data every day it waits: the QB2-Recorder task will
      not start on battery, is killed when the charger comes out, never makes up a
      missed run, and refuses the next hourly trigger because a run now takes over
      an hour. ONE command in docs/sessions/2026-10-01 fixes all four
- [x] BOT UNIVERSE AGREED (2026-10-02), operator verbatim: "GO on bot universe
      v1" — 50 names in three tagged sleeves. Permission to BUILD and BACK-TEST;
      the sender stays disarmed. S4 still blocked by S3's other two gate items
- [ ] FACTS row 2c must be settled before S14: can Limit/Stop/Stop-Limit orders be
      placed on a REAL-MONEY account? One tiny live test, or a written answer from
      T212 support. Sources disagree and going live on a guess is not acceptable

## v1 — KEEPS RUNNING, UNTOUCHED (the baseline v2 must beat)
The live NVDA regime-switcher, its journal, monitors, backups and scheduled runs
carry on exactly as they are. Do not edit v1's engine folders; the fingerprint is
checked in every box.
- [ ] OPERATOR ACTION: set `QUANTBOT_BACKUP_DIR` to an off-laptop folder
      (OneDrive) — rubric condition 7 counts as MET only when backups land off-laptop
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
