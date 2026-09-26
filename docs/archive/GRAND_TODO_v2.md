# GRAND_TODO (V2 stages) — ARCHIVED 2026-09-26 (quarantine, never delete)

The backlog as it stood at commit 22c67f7, kept whole. The direction became
the two-part bot/advisor design on 2026-09-26: see docs/plan/PLAN_V3.md.
Rows still true were carried across to GRAND_TODO.md; nothing was deleted.

---

# GRAND_TODO — QuantBot (archive DONE rows to keep this ≤10k chars)

Legend: [ ] open · [~] in progress · [x] done

**Direction changed 2026-09-21 → v2, the Simons direction.** The plan and the
detail for every stage below live in **docs/plan/PLAN_V2.md**; this page is only
the running order. The v1 backlog is archived whole at
`docs/archive/GRAND_TODO_v1.md` (quarantine, never delete).

## v2 — one box per stage (detail: docs/plan/PLAN_V2.md)
- [x] S0 Plan + plan gate (2026-09-21; gate proven red before green)
- [x] S1 `qb2/` skeleton + its own pinned env + wall/fingerprint tests (2026-09-26):
      8 importable empty subpackages · .venv-qb2 with 13 pins resolved exactly
      (docs/plan/ENV_QB2.md) · wall 44 -> 52 · v1 fingerprint and pip-freeze
      both unchanged. NEXT BOX: QT-05, the two-part plan revision.
- [ ] S2 Cost model + fill recorder + READ-ONLY T212 demo client + throttle + killswitch
- [ ] S3 ETF universe PROPOSE→GO + front-door ingest + census ≥95% CLEAN + first chart
- [ ] S4 Firewall v2: pre-registration file, search trial logging, known-null re-proved on ETFs
- [ ] S5 First signals, each pre-registered and through the full firewall
- [ ] S6 Combining model + calibration test; must beat the best single signal AND v1 OOS at 2× cost
- [ ] S7 Sizing-shapes test (equal / slow ladder / halving) + inverse-ETF test with a hold cap
- [ ] S8 Machine search loop — stops on CORRECT/EXHAUSTED, never on profit (#21)
- [ ] S9 Demo execution: batched open orders, daily paper-vs-T212 reconciliation, killswitch
      fire-drill. **v2's forward clock starts here.**
- [ ] S10 Front end rebuilt as v2's own interface (one app, not tabs)
- [ ] S11 Forward run → graduation rubric (DSR ≥ 0.95 at then-current N) → live at irrelevant size

Every stage ships an Exit gate (proven red-on-broken, #9), an Enforcer (the test
or monitor that holds it) and a Built/Wired/Armed checklist.

## Awaiting the operator (blocks nothing, but S0 is not closed until answered)
- [ ] D1 operator role · D2 which clock counts · D3 instrument list
      — recommended defaults in PLAN_V2 "DECISION REQUESTED"

## v1 — KEEPS RUNNING, UNTOUCHED (the baseline v2 must beat)
The live NVDA regime-switcher, its journal, monitors, backups and scheduled runs
carry on exactly as they are. v2 replaces v1 only by beating it out-of-sample at
2× costs. Do not edit v1's engine folders; the fingerprint is checked in every box.
- [ ] OPERATOR ACTION: set `QUANTBOT_BACKUP_DIR` to an off-laptop folder (OneDrive)
      — rubric condition 7 counts as MET only when backups land off-laptop
- [ ] OPERATOR ACTION: daily auto clock-sync scheduled task (needs admin)
- [ ] Run the loop once to clear the catch-up gap — 31 completed trading days
      unprocessed as of 2026-09-21 (newest bar 2026-08-06; the loop is catch-up-safe)
- [ ] Verify T212 auth scheme against the official docs before ANY order (also S2)
- [ ] Flatten-all half of the killswitch still TBD; monthly fire-drill via the GUI

## Known defects (found, recorded, not yet fixed)
- [x] FLAKY TEST, nightly (found 2026-09-21, FIXED 2026-09-26): the status fixture
      built its bars on the LOCAL date while `run_drill` defaults to UTC, so for one
      hour a night under BST the drill's doctored mark sorted before the fixture's
      healthy one and the drawdown light could not fire. Fixture now builds on UTC;
      SCAR #24; tests/museum/test_drill_utc_local_skew.py recreates the hour.
- [ ] 52 inherited type errors in 5 `manual/scout/*` modules — counts and burn-down
      in `docs/merge/TYPING_DEBT.md`
- [ ] Manual suite prints 2 pre-existing Qt "access violation" lines at teardown
      (present in the untouched original repo too); not diagnosed
- [ ] Manual trade journal not migrated — `trades.shares` is INTEGER where the code
      declares REAL; needs a one-table rebuild under PROPOSE→GO (MERGE_PLAN 3b)

## Standing / cross-cutting (carried from v1, still true)
- [ ] EDUCATION entry + learning-log line per milestone
- [ ] `docs/WATCH_LIST.md` (verify channels live; refresh monthly)
- [ ] Nightly carousel = simplest correctness loop (§10)

## Deferred / shelved
- [ ] Sentiment (StockGeist): free tier lacks the history to backtest, so it cannot
      pass the firewall. Collect now to build history; OUT of buy/sell decisions.
- [ ] Intraday / severity-weighted faster polling: does nothing on daily data.
      Shelved unless the system goes intraday (which needs a paid feed — PLAN_V2 §1).
- [ ] Sweep-level deflation + untouched cross-ticker holdout — folded into S4/S6
- [ ] Refit-cadence experiment, risk ladder, cash-floor sizing — v1 ideas that only
      matter if v1 continues past v2; re-open from the archive if so
