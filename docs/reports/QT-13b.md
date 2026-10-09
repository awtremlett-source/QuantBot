# QT-13b — recorder triggers, scheduled clean + census, stale alarm, S3 exit

Date: 2026-10-09 (Fri) evening UK, finished after midnight (10 Oct). Base d7e912a (QT-13-GO) = main.
No orders. Anchor buyer not run. Read-only key only. ARMED stays False. v1 untouched.
S4 not started.

Operator, 2026-10-09, verbatim: *"write QT-13b"*. The other two GOs this box
quotes (*"GO on recorder triggers: 14 fixed hourly"*, *"GO on S4 delay: (c),
measure T212 freshness"*) were **already recorded** by QT-13-GO (d7e912a, STATE
"Decided 2026-10-09"), so they are not duplicated here.

## In plain words

- **S3 is DONE.** Every item on the plan's exit check is now green, on evidence.
- **The cleaning step is switched on.** The recorder already saved the raw price
  bars every hour. Now, once a trading day has finished, it also makes the
  cleaned copy the census reads, takes both censuses, updates the minute labels
  and writes a daily digest. It does this after the hourly sampling, never
  before it.
- **Tonight's proof:** I started the recorder through Windows, the same way the
  schedule does. It cleaned the week it had missed (7,217 files), and the census
  on the **real** store read **98.2%** (217 of 221) against the 95% bar, with
  prices up to Friday 9 Oct.
- **Stale is now loud.** If the cleaned copy falls behind, or a census drops
  below its bar, every run log, the digest and the status page say **RED**. The
  three quiet days of "0.0%" cannot happen again: a test re-creates them and they
  turn red.
- **Labels need new data.** A second pass on the same prices no longer counts.
  165 names have their first pass; the second can come on Tuesday morning, after
  Monday's prices are in.
- **Triggers:** already fixed by QT-13-GO (14 runs on the hour). I checked them;
  nothing changed. The next run is Mon 12 Oct 07:00.
- **One thing only you can do (optional):** switch on Windows' task history log.
  It needs an administrator window. The command is in §1.

## 0. Ground truth

| | Step 0 |
|---|---|
| Tree | clean, main = d7e912a (QT-13-GO) |
| qb2 suite (.venv-qb2) | 440 passed, 1 deselected |
| v1 suite (.venv) | 434 passed |
| plan + wall (.venv-qb2) | 233 passed |
| ruff / mypy --strict | clean / the 4 known Qt-stub errors |
| v1 fingerprint | 4add56ec…743b6 |
| qb2 fingerprint | a087ffbf…1580e |
| Disk | C: 1.6 TB of 1.9 TB used (335 GB free); data/raw 358 MB, data/clean 208 MB |
| Task exports (logs/tasks/, local only: they name the Windows account) | QB2-Recorder-step0.xml `DFB8FFE3…13EF6` · QB2-StatusPush-step0.xml `8BBDD15F…900906` (SHA-256) |

**One difference between the repo and the box: not a STOP.** Step 1 asks for the
triggers to be re-registered. QT-13-GO had already done that at about 21:10
tonight (14 triggers, start boundary Mon 12 Oct). Re-registering again would have
changed nothing, so step 1 became *verify*. The box's other premise held: PLAN_V3
asks for "census armed in the daily digest", but qb2 had no daily digest (v1's
lives in the frozen monitors/). This box adds a small one (§2).

## 1. Recorder triggers — verified, not re-registered

- **Now:** 14 weekly triggers, Mon–Fri, at 07:00, 08:00 … 20:00 local, with no
  repetition. Wake, run after a missed start, IgnoreNew, 3-hour limit, battery
  allowed, user mtrem (Interactive, Limited), `pythonw.exe -m qb2.tools.record_now`,
  started in the repo folder.
- **Diff:** the step-0 export and the end-of-box export are **byte-identical** (QB2-Recorder `DFB8FFE3…13EF6` both; QB2-StatusPush `8BBDD15F…900906` both): this box changed no task. The
  before/after diff of the change itself belongs to QT-13-GO, which reported that
  only the trigger blocks changed. Its "before" XML was not kept on disk, so this
  box cannot show that diff again.
- **Next 3 runs:** Windows reports NextRunTime **Mon 12 Oct 07:00**. From the
  triggers, the next two are 08:00 and 09:00 the same day.
- **Status page, new rule** (`qb2/tools/run_times.py`):
  - runs should start on :00, within 5 minutes;
  - one late run that is the day's first is named "the catch-up after switch-on
    (expected)";
  - the same off-hour minute twice is flagged **DRIFT** (the QT-13 fault);
  - any :00 slot with no run is listed under "Missed runs today".
- **Task Scheduler history log: not changed.** The command is below. It needs an
  **administrator** prompt (right-click PowerShell → Run as administrator):

  `wevtutil set-log Microsoft-Windows-TaskScheduler/Operational /enabled:true`

## 2. The cleaning step, switched on (Wired + Armed)

`qb2/data/clean_step.py`, called by the recorder (`record_now._clean_step`).

- **When it runs:** on the first recorder run after a trading day has finished,
  meaning every market that traded that day has closed. New York closes last, at
  21:00 UK.
  - A marker file (data/clean/after_hours.json) records the last day cleaned, so
    the step runs once per finished day.
  - After a RED result it is retried, but only in after-hours runs.
  - It catches up **every** day not yet cleaned: the front door takes every raw
    file that is not already in the clean store.
- **What it does, in order:**
  1. the front door (raw → clean, the only writer);
  2. the 5-minute census, then the 1-minute census, both saved to data/clean;
  3. the minute labels (P18);
  4. the daily digest, logs/digest/digest-<date>.md.
- **Never in the sampling's way:** it is called after the delay sample and every
  fetch. If it fails, that is a complaint in the run log ("RUN NOT CLEAN"); the
  run does not crash.
- **Idempotent:** running it twice leaves the clean bars, the manifest's
  ingested entries and the labels unchanged (test). Each run still adds one
  "run" line to the manifest, as before.
- **Half-written raw file:** skipped and **named** in the run's complaints, never
  half-ingested. It gets no manifest line, so the next run tries it again (test).
  Raw files are not written atomically by the recorder (`to_parquet` straight to
  the path), so a killed run can really leave one.
- **One-in-one-out:** `record_now._update_minute_labels` was removed. It ran on
  every catch-up, which is how two passes over the same data happened. The step
  replaces it.

## 3. Stale is loud

- **RED when:**
  - a census is below its gate (5m: PLAN_V3's 95%; 1m: 50%); or
  - a market's newest clean bar is older than that market's last finished session.
- **Holidays are not missing days.** The real exchange calendars (XNYS, XLON)
  decide, so US Thanksgiving and UK bank holidays are handled (tests).
- **Where RED shows:**
  - the step's own lines in the run log (strict rule);
  - the daily digest;
  - one line in every run log, and on the status page:
    `Clean store: fresh to <date> · 5m census <x>% · RED/OK`.
- **The status page does not cry wolf.** It counts a session only once its step
  is overdue: 10:00 UK on the next weekday. So at 21:50 it does not complain
  about a day the 07:00 run will clean. A step that stops running (job errors,
  PC off) turns the page RED by 10:50 on the next trading day (test).
- **The 1m gate (50%)** is a starting figure under the 2026-10-07 standing GO.
  The plan sets no 1m gate. 50% is below QT-13's rebuild (74.7%), so only a
  collapse like 7–9 Oct's 0.0% trips it.
- **The three silent days are now impossible.** A fixture of exactly that
  situation (clean bars ending 2 Oct, a 0.0% 1m census, 9 Oct) turns RED.

## 4. Labels need NEW data

- A pass counts only if the name's newest bar is newer than at its previous
  pass. On the same data nothing moves at all: not the count, the label or the
  reason (`qb2/data/access.py`).
- **The 5 Oct case, as a fixture:** a pass on 3 Oct, then a pass on 5 Oct with
  bars that still end on 2 Oct.
  - Under the old rule it promoted the name to MINUTE_OK (watched).
  - Under the new rule it stays FIVE_MIN_ONLY with 1 pass.
- Labels saved before this box still load (`newest_bar` defaults to empty).

## 5. The wiring, proven live

- **How:** `Start-ScheduledTask QB2-Recorder` at 23:04 UK. That is the task's
  own command (`pythonw.exe -m qb2.tools.record_now`), not a Python prompt. Both
  markets were shut, so it ran in mode `hourly+catchup`.
- **Order, from the run log:**
  - delay sample: none, correctly, because the markets were shut;
  - 1m top-up, 2.3 min;
  - 1m backfill, 5m and 1h catch-up, all done by 23:10;
  - **then** the after-hours step;
  - exit 0, 61.7 min in total, inside the 150-minute alarm and the 3-hour limit.
- **The step, from its own lines:**
  - Clean: 7,217 files written, 18,916 unchanged, 0 unreadable, 0 rows
    quarantined. The reconciliation was exact; the front door asserts it.
  - **5m census on the REAL store: 217 of 221 = 98.2%, GREEN.**
    - uk_etf 22/23 (95.7%), uk_share 97/100 (97.0%), us_liquid 98/98 (100%).
    - Not passing: BNZL.L (last bar 36 weekdays old), DCC.L (76% of bars),
      ITRK.L (65%), MIDD.L (63%).
  - **1m census: 74.7%.** uk_etf 14/23, uk_share 53/100, us_liquid 98/98.
    Labels only; its gate is 50%.
  - **Labels per sleeve: 0 MINUTE_OK everywhere.**
    - uk_etf: 14 on pass 1 of 2, 9 failing.
    - uk_share: 53 on pass 1, 47 failing.
    - us_liquid: 98 on pass 1.
    - In total 165 on pass 1, as QT-13's dry run predicted. One name has too
      little history.
  - **Clean store: fresh to 2026-10-09 · 5m census 98.2% · OK.**
  - Marker: cleaned through 2026-10-09. Digest:
    logs/digest/digest-2026-10-09.md. Census files:
    data/clean/census-2026-10-09.json and census-1m-2026-10-09.json.
- **QB2-StatusPush:** started by hand at 00:06. Result 0; push.log reads "pushed
  status/recorder_status.md to refs/heads/status". The page fetched back from
  origin/status carries `- Clean store: fresh to 2026-10-09 · 5m census 98.2% · OK`.
- **Not new, and not this box's:**
  - The freshness meter prints RED for 15m, an interval that is never recorded.
  - London's delay meter is RED for 6 and 7 Oct (too few samples while the PC
    was off).

## 6. S3 exit check — against PLAN_V3, not this box

| Item (PLAN_V3 S3) | Verdict | Evidence |
|---|---|---|
| Bot list agreed | GREEN | "GO on bot universe v1", 2026-10-02, in the file; its test |
| Advisor list agreed (P6's rule) | GREEN | derived by the agreed rule; disjoint and filter tests |
| Lists disjoint | GREEN | `test_the_bot_and_advisor_lists_cannot_overlap` |
| ≥95% census | **GREEN** | 98.2% (217/221) on the real store, fresh to 9 Oct, taken by the scheduled path (§5) |
| Sterling line by ISIN | GREEN | `test_the_sterling_line_of_a_fund_is_found_by_isin` |
| Chart from clean data | GREEN | `test_first_light_never_reads_the_raw_store`; the clean data is now fresh |
| Quote delay measured (row o) | GREEN | VERIFIED, US 1.25 / London 16.66 min |
| Wired: ingest to the scheduler, with catch-up | **GREEN** | QB2-Recorder ran the front door at 23:09; it caught up 2–9 Oct in one run; catch-up and idempotency tests |
| Armed: census in the daily digest | **GREEN** | digest-2026-10-09.md written by the step; RED on stale or below gate (tests); the same line on every run log and the status page |

**S3 DONE, 2026-10-10.** The PLAN_V3 heading, status prose and exit-check line are
updated, and `test_s3_is_done_only_when_every_exit_item_is_green` passes. The
gate criteria are unchanged. STATE says S0–S3 DONE.

- **Honest limit:** "wired" was proven by starting the task by hand, which the
  box allows. The first run started by a trigger to clean a day will be Tue 13 Oct
  07:00 (cleaning Monday). Monday's own runs only check that the store is fresh.
  The status page will show it either way.
- **Carried into S4, unchanged in STATE:**
  - GOOG/GOOGL and VUAG/VUSA count as one bet each.
  - P20's thresholds use the row-o delays.
  - The S4 delay rule (c), and measuring T212's freshness.
  - The FX note.
  - P19's 18 trials.
  - The parked items.

## 7. Premortem — each guard watched red first

| Failure | Guard | Seen red by |
|---|---|---|
| Trigger change breaks recording | exports identical, NextRunTime Mon 07:00; `test_a_missing_on_the_hour_run_on_monday_is_listed` | old status_push (feature absent) |
| Re-based trigger comes back | `test_runs_that_start_late_in_the_hour_are_flagged` (DRIFT) | old status_push said only "OFF THE HOUR" |
| Cleaning runs while sampling | `test_cleaning_comes_after_the_sampling_and_every_fetch` | old record_now (no clean call) |
| Step error kills the run, or is silent | `test_a_failing_step_is_a_complaint_not_a_crash` | old record_now |
| Ingest twice | `test_running_the_step_twice_changes_nothing` | mutant: front door without its hash skip (restored byte for byte) |
| Holiday counted as a missing day | Thanksgiving + UK bank-holiday tests | mutant: weekdays at 21:00 instead of the exchange calendar |
| Cleaning silently skipped (error, PC off) | `test_a_step_that_stops_running_goes_red_within_one_trading_day` | mutant: judge ignores staleness |
| The 3 silent 0.0% days | `test_the_three_silent_days_of_a_zero_minute_census_turn_red` | same mutant (the fixture's 1m staleness reason disappears) |
| Promotion on old data | `test_the_5_oct_promotion_on_unchanged_data_does_not_promote` | old access.py promoted (MINUTE_OK) |
| Half-written raw file | `test_a_half_written_raw_file_is_skipped_and_named` | mutant: the read guard catches nothing (the torn file crashes the run) |
| v1 pyproject.toml touched | v1 fingerprint | identical 4add56ec…743b6 |
| Network in the default run | `network` marker, deselected | still 1 deselected |
| ARMED flipped | wall test | still False |

## 8. Verify

| Check | Before (step 0) | After |
|---|---|---|
| qb2 suite (.venv-qb2) | 440 passed, 1 deselected | **468 passed, 1 deselected** (+23 new in test_qt13b_clean_step.py, +5 status page; the live smoke test still deselected) |
| v1 suite (.venv) | 434 passed | 434 passed |
| plan + wall (.venv-qb2) | 233 passed | 233 passed |
| ruff | clean | clean |
| mypy --strict | the 4 known Qt-stub errors | the same 4, none new |
| lean lines | — | clean_step.py 248, run_times.py 64, status_push.py 227 (was 247); front_door.py 470 and record_now.py 383 stay within their pins |
| v1 fingerprint | 4add56ec…743b6 | **4add56ec…743b6, identical**; pyproject.toml not touched |
| qb2 fingerprint | a087ffbf…1580e | **0dfd931e…92f0b**. It moved because qb2 code changed: clean_step.py and run_times.py are new; front_door.py, access.py, record_now.py and status_push.py changed |

- **Fingerprint footnote.** Both values are of this PC's working tree, which is
  how a087ffbf… was taken. The fingerprint hashes bytes, so a fresh checkout,
  with every line ending CRLF, reads differently for the same code: HEAD
  d7e912a gives 6c050461…c399, and this commit gives b21be477…89945. STATE's old
  phrase "normal CRLF checkout" was therefore not quite right, and STATE now
  says which tree was measured.
- **Tests changed, with the reason for each:**
  - `test_promotion_needs_two_passes…`: its fake names now carry a last bar,
    because the new rule needs one.
  - `test_runs_on_the_hour_raise_no_flag`: 17:12 became 17:00, because "on the
    hour" is now 5 minutes, not 20.
  - `test_runs_that_start_late…`: now also asserts DRIFT.
  - The weekend test's stub now targets `_clean_step`.
- **One-in-one-out:** `record_now._update_minute_labels` and
  `status_push.runs_today` were removed. Their jobs moved to `clean_step` and
  `run_times`.
- **History:** STATE was archived verbatim to docs/archive/STATE_2026-10-09.md.
  GRAND_TODO now marks QT-13 and QT-13b done.

Not started: S4.
