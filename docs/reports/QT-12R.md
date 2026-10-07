# QT-12R — Recorder check: why London has so few delay samples

Date: 2026-10-07 (Wed), run at about 16:30 UK time. Base commit 278f2a2 (QB-HOLD-1).
No orders of any kind. Anchor buyer not run. ARMED stays False. v1 untouched.
No Windows setting was changed. Everything below was read, not guessed.

## In plain words

The PC is **shut down** every night (between 02:00 and 03:30 UK) and switched on
again only in the afternoon. A scheduled task cannot switch on a PC that has been
shut down, so the hourly recorder never ran during London's 08:00–16:30 session,
except in the few minutes after the PC was switched on. The code was not skipping
London: every run that happened while London was open took a London sample.

**What you must do:** on Thursday 8 and Friday 9 October, have the PC **on and
awake from 08:00 to 21:00 UK time** (08:00–16:30 for London, until 21:00 for the
US). Tonight, do **not** use *Shut down*. Either leave the PC on, or use *Sleep*
(Start → Power → Sleep). On mains power the recorder is allowed to wake it from
Sleep. It can never wake it from Shut down.

## 0. Ground truth

| Check | Result |
|---|---|
| Tree | clean at 278f2a2 = origin/main |
| v1 suite (.venv) | 433 passed |
| qb2 suite (.venv-qb2) | 390 passed |
| v1 fingerprint | 4add56ec…743b6 (unchanged, before and after) |
| qb2 fingerprint | ec7efd39…8646 at 278f2a2. STATE still showed d4dc0942…f269, which went stale when QT-12 MARGIN and QB-HOLD-1 changed anchors.py. |

**One premise of the box was wrong:** "London has 0 delay sessions" is stale
(STATE's line dated from S3d). On file, London has clock-checked samples on 3
days, but only **4 samples**. The plan's bar is **20 samples over 3 sessions**,
so the real blocker for both markets is the sample count, not the session count.
That is still the question the box asked (why London cannot close S3), so the
diagnosis went ahead.

## 1. The facts, day by day

Clock-checked delay samples (the counted kind), from data/raw/intraday/manifest.jsonl:

| Day | US | London | PC on (UK time) |
|---|---|---|---|
| Fri 2 Oct | 0 counted (3,106 unverified, from before the clock check existed) | 0 | on until 23:57 |
| Sat 3 / Sun 4 | weekend | weekend | — |
| Mon 5 Oct | 5 | **2** | off 02:13 → **14:26** |
| Tue 6 Oct | 3 | **1** | off 02:51 → 11:44, on 25 min, off 12:09 → 18:15 |
| Wed 7 Oct (so far) | 1 | **1** | off 03:24 → **16:13** |
| **Total** | **9** | **4** | |

London's delay is about **16–17 minutes** (BP.L, every reading). US is about 1–2
minutes (AAPL). The 15-minute gap is the London feed's own delay. It is real and
it is the number this measurement exists to find.

**Recorder runs** (logs/recorder/run-*.log; Task Scheduler's own history log is
switched off on this PC):

| Day | Runs that happened (UK) | Missed scheduled hours (UK) | Why missed |
|---|---|---|---|
| Mon 5 | 14:29 (catch-up), 16:00–21:00 hourly: 7 runs, all exit 0 | 07:00–14:00 (8) | PC shut down |
| Tue 6 | 11:47, then 18:47–02:47 hourly: 10 runs. 9 exit 0; the 01:47 run was cut off mid-catch-up and the next run caught up | 07:00–11:00 and 13:00–18:00 (11) | PC shut down |
| Wed 7 | 16:16 (exit 0) | 07:00–16:00 (10) | PC shut down |

No run was skipped by the scheduler for overlap, and none failed.

**Power** (Windows System log, read-only): this is a **desktop** (chassis type 3)
with **no battery**, so it is always on mains. "On battery" never applies. Every
night there is a user **logoff** (Winlogon 7002) and a Kernel-Power 42 with
TargetState 6 = *shutdown*, EffectiveState 5 = *hibernate*. That is Windows
**Fast Startup** (switched on here: HiberbootEnabled = 1). Each afternoon there
is a Fast Startup boot (Kernel-Boot 27, "boot type 0x1") and "Wake Source:
Unknown", meaning a person switched it on, not a timer.

**The RED meter for London on Mon and Tue: it did not fire.** That is a bug, but
not quite the one the box guessed. `session_meter` was written and tested in S3c
and **never called by anything**, so it could not fire on any day. Even if it had
been called, it only went red at **zero** samples, so London's 2 and 1 would have
read OK. It also counted unverified samples.

## 2. The real cause: evidence for each candidate

| Candidate | Verdict | Evidence |
|---|---|---|
| PC asleep or off in London hours | **THE CAUSE** | Shut down every night 02:13–03:24, back on at 14:26 / 11:44 (25 min) / 16:13. Its awake windows contain every one of the 4 London samples. |
| Task trigger times | not the cause | Mon–Fri, 07:00 + every hour for 14 h, which covers 08:00–16:30. WakeToRun on, StartWhenAvailable on. |
| Wake-only-on-mains setting | not the cause | Desktop with no battery, always on mains. "Allow wake timers" on mains = Enable. A wake timer cannot start a PC that is *shut down*, whatever this says. |
| Sampler skipping London | not the cause | Each of the 4 runs made while London was open wrote a London sample. |
| Clock check failing for London | not the cause | All 4 London samples have clock_checked = True (offset 0.18–0.76 s, time.google.com). |
| Anything else | found 4 counting faults, below | None of them lost London samples, but each could have miscounted. |

## 3. What was fixed (standing GO: our code)

The cause is the PC being off, so the operator action above is the fix. The
code fixes are the meter and the premortem guards. Each one was first watched
failing against the old code (4 red: half-day ×2, holiday sample written, meter
missing from the verdict), then made to pass.

- **New `qb2/tools/delay_count.py`** — one rule for which samples count:
  - inside a **full** session on the exchange's own calendar (exchange_calendars,
    already a dependency). Holidays and **half-days** do not count. Before, the
    check knew weekdays but not holidays, and on a holiday yfinance returns the
    last day's bars, so a day-old bar would have been written as a "delay";
  - taken between that session's real open and close;
  - of a bar from **that** session (yesterday's close just after the open is "no
    bar yet", not a 16-hour delay);
  - each observed bar **counted once**. A hand run of `python -m
    qb2.tools.sample_delay` is not covered by the recorder's lock, so two runs
    could read the same bar.
- **The meter now fires.** It runs inside `sample_delay.verdict()`, which every
  recorder run prints to its log. It is RED when a finished full session has
  fewer than **3** clock-checked samples. *Standing-GO default, logged:* a full
  session gives about 8 hourly readings in London and 6 in the US, so 3 means the
  PC was on for a good part of it. On today's real data it reads **London RED
  (5 Oct: 2 of 3, 6 Oct: 1 of 3), US OK**.
- The sampler checks the calendar before writing, so a holiday reading is never written.
- **Premortem tests** (tests/qb2/test_delay_count.py, 24 tests, all but one on BOTH
  markets): fix covers US only · holiday counted · half-day counted · out-of-hours
  counted · bar from before the open counted · overlapping runs double-count ·
  meter red at 0 and at 1 sample · unverified samples cannot turn it green · it
  can go green · it is in the printed verdict.
- One-in-one-out: three copies of the manifest-reading loop became one;
  `sample_delay.py` went from 274 to 179 lines and is off the oversize pin list;
  the meter's two old tests moved, now covering both markets.
- Side effect, intended: the 3,106 unverified 2 Oct readings drop to 71 once each
  bar counts once (they were 226 names read in the same minute). They were never
  counted towards the bar.

Nothing about Windows was changed. No DECISION REQUESTED: the cause is not a
setting.

## 4. Forecast

Both markets **already have 3 clock-checked sessions** (5, 6, 7 Oct). The binding
bar is **20 samples**. Assuming the PC is on 08:00–21:00 UK on Thu and Fri:

| | Now | Tonight (US runs 17:00–20:00) | Thu 8 Oct | Fri 9 Oct |
|---|---|---|---|---|
| London (≈8 a day: 09:00–16:00 runs) | 4 | 4 | 12 | **20 at the 16:00 run** |
| US (≈6 a day: 15:00–20:00 runs) | 9 | 13 | 19 | **20 at the 15:00 run**, 25 by close |

**QT-13 runs after the US close on Fri 9 Oct 2026 (21:00 UK).** London has
**no slack**: one missed hour on Thu or Fri moves QT-13 to after **Mon 12 Oct**.

## 5. Verify

| Check | Before | After |
|---|---|---|
| v1 suite | 433 passed | 433 passed |
| qb2 suite | 390 passed | **412 passed** (+24 new, −2 moved into them) |
| ruff | clean | clean |
| mypy --strict (qb2 env) | 4 errors, all in manual/ui Qt stubs | the same 4, none new |
| v1 fingerprint | 4add56ec…743b6 | 4add56ec…743b6 |
| qb2 fingerprint | ec7efd39…8646 | **10351678…bd67d**: changed because sample_delay.py changed and delay_count.py was added |

Not started: QT-13.
