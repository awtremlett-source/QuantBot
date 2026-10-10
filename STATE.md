# STATE.md — resume in seconds (current only; ≤6k chars, tested)

Updated: 2026-10-10. History → docs/archive/STATE_2026-10-10.md (QT-13b state,
verbatim) and earlier archives. Box in hand: QT-14 (S4) → docs/reports/QT-14.md.

Phase: v2 BUILDING. **S0–S4 DONE** (S3 close = QT-13 + QT-13b; S4 = QT-14, 2026-10-10,
every exit item GREEN). Part A ARMED: T212 London freshness meter + P20 cross-check
in SHADOW inside every in-session recorder run (sender carries it, disarmed).
Part B: firewall v2 in qb2/research; known-null gate GREEN on the real store,
each half seen RED on broken code first. No P19 trial has been run (QT-15).

## QT-14 operator's words (verbatim, 2026-10-10)
- *"write QT-14 (S4)"*

## Applied under standing GO (2026-10-10, QT-14) — each a starting figure
- Freshness polls: 10 per London-session run, 30 s apart, cap 5 min (starting figure).
- Freshness counts only if the best lag (0–30 min) is 25% below the next-best and
  the name is MINUTE_OK; a lag is judged only if 80% of polls have a bar (starting figure).
- P20 lines scaled √(row-o delay ÷ 1.6): US warn 0.221% · block 0.442%; London warn
  0.807% · block 1.613%; ATR term scaled the same (starting figure). 5% one-name stop
  and the 3-names rule NOT scaled (strict side). Broker price max age 60 s (starting figure).
- Holdout: daily sealed from 2025-10-10; 5m sealed from 2026-09-21 + all after 2026-10-10.
- D3 = VWRP (VWRPl_EQ, IE00BK5BQT80, GBP, Acc). Survivorship 1.0%/yr held, single
  shares only (starting figure, published averages). INSUFFICIENT < 30 OOS trades or
  < 30 bars. Stake GBP 300/order. Walk-forward 252/63 daily, 10/5 sessions 5m.
  Coin-flip null 200 runs. Flat by the bar starting 15 min before the close (P4).

## NEXT, in order
1. QT-15 (mentor writes it): run P19's 18 registered trials through the firewall at 2x.
   Note: daily trials are registered on advisor-universe-v1; the firewall loads the
   bot list today, so QT-15 adds the advisor loader. Daily clean store ends 2026-10-01.
2. Mon 12 Oct: status page should show runs on :00, no DRIFT, "Clean store: … · OK",
   and the two new lines "T212 London freshness: …" and "Cross-check (shadow): …".
   Tue 07:00 cleans Monday → first freshness samples measured.
3. OPERATOR: keep the PC on (or Sleep) 08:00–21:00 UK on weekdays.
4. OPERATOR (optional, admin): Task Scheduler history log —
   `wevtutil set-log Microsoft-Windows-TaskScheduler/Operational /enabled:true`

## DECISION REQUESTED (open)
- Backups on the university OneDrive? Default: keep (2026-10-06 archive).

## Standing GOs (operator words, verbatim)
- 2026-10-07: *"STANDING GO: For routine settings and thresholds, go with the
  recommended default and log it. Three things always need my own words: switching
  the bot on to trade, real money, and removing any safety fence."*
- 2026-10-07: *"From now on, every box ends by saving its report in the repo and
  pushing, so the mentor can read it from GitHub."* → docs/reports/<BOX>.md.
- Live anchors, 2026-10-05: "One GO until the £100 cap". Raising a cap (£3/order ·
  £100 lifetime · 50/UTC day) needs its own GO. QT-12 CLOSED: 50/50 priced.
- 2026-10-09: *"GO on recorder triggers: 14 fixed hourly"* (applied) · *"GO on S4
  delay: (c), measure T212 freshness"* (S4).

## CARRIED (unchanged from QT-13)
- GOOG/GOOGL and VUAG/VUSA each count as ONE bet when the bot trades (same company /
  same index fund); both still get an anchor. Built: docs/research/bet_groups.json v1.
- FX: costs.py charges 0.15% per leg on US names; an ISA holds no USD, so every US
  trade converts. Can an API order choose USD? UNKNOWN.
- Parked: advisor trial counting (S9) · v1 revive-or-retire.

## Recorder facts
QB2-Recorder (Mon–Fri, 14 fixed triggers 07:00…20:00 local, wake, catch-up,
IgnoreNew, 3h limit). Run order: delay sample → hourly top-up → S4 measurements
(qb2/ingest/fresh_run.py) → after-hours step (raw → clean, censuses, labels; once
per finished day, marker data/clean/after_hours.json) → freshness measuring. RED =
5m census <95%, 1m <50%, or clean store older than its last finished session.
Status page (QB2-StatusPush, :50): raw.githubusercontent.com/awtremlett-source/
QuantBot/status/status/recorder_status.md. Daily digest: logs/digest/.

## Open flags
- anchors.py 1,422 lines (pinned oversize): splitting = its own PROPOSE→GO.
- v1 QuantBot-Daily has not run since 28 Jul (0x800710E0); revive-or-retire deferred.
- Recorder freshness prints RED for 15m (never recorded; nothing asks for 15m).
- .env.example keeps the old T212 "to verify" note (inside the engine fingerprint).
- No daily clock-sync task (admin). gh CLI absent → plain git.
- Manual journal not migrated (MERGE_PLAN 3b). Two killswitch faces until stage 4.
- Daily clean store ends 2026-10-01 (no scheduled daily top-up found).
- Typing debt: 52 mypy errors silenced in 5 inherited modules (docs/merge/TYPING_DEBT.md).
- Clean 5m store: TSLA, STX, WDC, WMT, V have day files stamped Europe/London (right
  instants, wrong zone label); research reads normalise it; front-door fix not done.

## Fingerprints
v1 4add56ec…743b6 (must never move; re-verified 2026-10-10). qb2 hashes bytes on
this PC's working tree (0dfd931e…92f0b after QT-13b; moved by QT-14 — new value
in docs/reports/QT-14.md). qb2 trial log: data/qb2/trials.jsonl, 8 drills, 0 trials.
