# QT-13-GO — two decisions from QT-13, applied

Date: 2026-10-09 (Fri), evening UK. Base dd15e77 (QT-13).
No orders. ARMED stays False. v1 untouched. No code changed. Nothing written under data/.

Operator, 2026-10-09, verbatim:

> QT-13 done
>
> GO on recorder triggers: 14 fixed hourly
> GO on S4 delay: (c), measure T212 freshness

## In plain words

- **The recorder now starts on the hour, every hour.** It used to have one start
  time that repeated hourly. After the PC had been off, the repeats followed the
  late catch-up run (9 Oct: every run at :53). Now there are 14 separate start
  times, 07:00 to 20:00, Monday to Friday. A missed hour is still made up once
  after switch-on, but the next run is back on :00.
- **S4 will face London's 17-minute delay honestly.** The bot may act only on bars
  it can see complete, at each market's measured delay. S4 will also measure, as a
  read-only check, how fresh Trading 212's own prices are for London. If they are
  fresh, London can be looked at again on that evidence.

## 1. Recorder triggers — APPLIED

| | Before | After |
|---|---|---|
| Triggers | 1 weekly (Mon–Fri) 07:00, repeat every 1 h for 14 h | 14 weekly (Mon–Fri) at 07:00, 08:00 … 20:00, no repetition |
| Time zone | local wall clock (no offset) | local wall clock (no offset), so runs stay at 07:00 local after the 25 Oct clock change |
| Action, account | `.venv-qb2\Scripts\pythonw.exe -m qb2.tools.record_now`, mtrem, Interactive, Limited | unchanged |
| Settings | wake, catch-up (StartWhenAvailable), IgnoreNew, 3 h limit, runs on battery | unchanged |
| Next run | Mon 12 Oct 07:00 | Mon 12 Oct 07:00 |

- **How:** `Set-ScheduledTask -TaskName QB2-Recorder -Trigger <14 triggers>`. Only
  the triggers were replaced. A diff of the exported task XML, before against
  after, shows only trigger blocks changed (Repetition removed, 13 triggers added).
  The run finished at 20:53 and nothing was running during the change.
- **Revert:** a single trigger with `-Weekly -DaysOfWeek Monday..Friday -At 07:00`,
  and Repetition set to Interval PT1H, Duration PT14H.
- **Not proven yet:** that a catch-up after switch-on no longer shifts later runs.
  This is first visible on Mon 12 Oct. The status page's `OFF THE HOUR: N of M`
  should read 0, or 1 if the PC was switched on after 07:00.
- **Still the operator's own setting, not done:** switching on Task Scheduler's
  history log. It needs admin, and it would let the next fault be proven rather
  than inferred.

## 2. S4 delay — DECIDED (c), and measure (a)

- **Written into PLAN_V3, S4:** a "Delay rule, decided 2026-10-09" line, with the
  operator's words.
- **The rule:** the bot acts only on bars it can see complete, each market at its
  measured delay (FACTS row o: US 1.25 min, London 16.66 min). This is P17's
  existing rule, now with numbers. P17's pre-registered text was not edited.
- **To measure in S4 (read-only):** how fresh Trading 212's `currentPrice` is for
  anchored London names. Same bar as row o: 20 counted over 3 full sessions.
- **No new trials:** P19's 18 pre-registered trials are unchanged.
- **If London fails:** (b), meaning London advisor-only, follows by evidence, not
  by choice.

## 3. Verify

| Check | Result |
|---|---|
| plan + wall suites (.venv-qb2) | 233 passed, same as QT-13 |
| STATE budget | 4,830 chars of 6,000 |
| v1 fingerprint | 4add56ec…743b6, unchanged (no code or config touched) |

Not started: QT-13b. Not started: S4.
