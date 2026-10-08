# QT-12S — Hourly recorder status push

Date: 2026-10-08 (Thu), worked 17:33–17:5x UK, all outside the recorder's
:00–:20 window. Base commit a10ebf3 (QT-12R). No orders. No keys used (the
secret scan only reads .env to make sure no value from it appears in the file).
ARMED stays False. v1 untouched. QB2-Recorder not edited, restarted or
re-registered. Nothing written to data/. No packages installed.

Operator, 2026-10-08: *"can the recorder automatically push every set interval
and then you can check it automatically?"*

## In plain words

Yes. A second, separate scheduled task, **QB2-StatusPush**, runs at **:50 past
every hour, 08:50–21:50 UK, Monday to Friday**. It counts the recorder's samples
(read-only), writes a short status page, checks that page for anything secret,
and pushes **only that page** to a branch called `status` on GitHub. The mentor
reads it here, with nobody pasting anything:

https://raw.githubusercontent.com/awtremlett-source/QuantBot/status/status/recorder_status.md

GitHub caches that address for about 5 minutes, so it can lag one push behind.
The recorder itself was not touched.

## 0. Ground truth

| Check | Result |
|---|---|
| Tree | clean at a10ebf3 = origin/main |
| v1 suite (.venv) | 433 passed |
| qb2 suite (.venv-qb2) | 412 passed |
| v1 fingerprint | 4add56ec…743b6 |
| qb2 fingerprint | 10351678…bd67d (matches STATE) |
| QB2-Recorder settings | exported to XML, SHA-256 4312DD9E…E038B |

## 1–2. What was built

- **qb2/tools/status_push.py** (new, 222 lines). It counts with `delay_count`:
  `scan_samples` → `countable(verified_only=True)` → `session_meter`. That is the
  same rule the recorder's verdict uses, not a second copy. Per market it shows:
  counted today, counted since 2026-10-05 against the target of 20, a count per
  session, the meter colour, how many hours were expected by now today (and which
  ones), any missed hour by name, and the median delay. It also shows the last
  recorder run (start, end, exit code). It contains no keys, no account values,
  no holdings, no orders, and no paths outside the repo.
- **Expected hour**, defined: one of the recorder's hourly runs (07:00–20:00 UK)
  that falls between today's open + the feed's delay and today's close, and is
  at least 20 minutes old. Today that gives London 09:00–16:00 (8) and US
  15:00–20:00 (6). London's 08:00 run sees a bar from before the open, because
  London's delay is about 16 minutes.
- **The push** uses git plumbing (`hash-object`, `mktree`, `commit-tree`, then
  `push --force <commit>:refs/heads/status`). It makes one commit with no parent,
  rebuilt each run. Git's index, the checkout and main are never touched, so the
  working tree cannot be disturbed even while you are editing. The file is pushed
  byte for byte (`--no-filters`, written with LF line endings).
- **Secret scan** before every push: any value from .env, an .env name followed
  by a value, any secret-named assignment (…KEY/SECRET/TOKEN/PASS=), any
  key-shaped string (24+ characters with both letters and digits), and any path
  outside the repo. A hit means it **refuses to push**, writes `REFUSED to push:
  <what was found>` to the log (never the value itself), and exits 2.
- **Log**: every run adds one line to logs/status_push/push.log (`pushed`,
  `REFUSED`, `PUSH FAILED`, `STATUS FAILED`). A failure exits non-zero.
- **qb2/tools/delay_count.py**: `read_samples` now hands off to a new
  `scan_samples`, which also counts unreadable sample lines. The status page
  says "N unreadable manifest line skipped" instead of hiding them. The file is
  also opened with `errors="replace"`, so a cut-off UTF-8 byte cannot crash the
  read. Same loop, no second copy.
- **Task QB2-StatusPush**: runs as the operator (interactive token, so the
  existing git credentials work) with pythonw (no window). Time limit 10 min,
  IgnoreNew. It **does not wake the PC** and does not "start when available",
  so it never piles up next to the recorder after a wake.

## 3. Premortem — each guard watched red

The tests were written first and were red (the module did not exist). After
the build, each guard was broken on purpose and its test went red. All were
restored and checked identical to backups:

| Failure | Test | Mutant that turned it red |
|---|---|---|
| Counts differ from delay_count | same planted data through both | count unverified rows too |
| Secret leaks | planted fake key refused, nothing reaches git, value not logged | skip the scan / scan returns nothing (3 shapes) |
| Half-written manifest line | no crash, skipped, noted, counts unchanged | stop counting bad lines |
| Push to main or other files staged | real git in a tmp folder with a bare remote: main unchanged, branch holds exactly one file in one parentless commit, index and HEAD untouched, other.txt not carried | target refs/heads/main · `git add -A` added |
| Push fails silently | bad remote → non-zero exit + `PUSH FAILED` line | return 0 on failure |
| Job clashes with recorder | no lock and no data/ writes in the source; manifest set read-only and still read, bytes unchanged | — (checks the source) |

The real-git test caught one real bug before it shipped. On Windows, text-mode
stdin wrote CR LF into the tree entries, which turned the path into
`status\r/recorder_status.md\r`. Git I/O is now bytes.

## 4. Live proof

- Registered QB2-StatusPush. Ran it by hand at 17:41 and 17:43: LastTaskResult 0,
  log says `pushed status/recorder_status.md to refs/heads/status`.
- `git fetch origin status`: the branch's file is **byte-identical** to
  logs/status_push/recorder_status.md. 1 commit, no parent, 1 file. main on
  GitHub is unchanged.
- The raw URL answers 200 (`Cache-Control: max-age=300`). It first served the
  17:41 copy from cache; once the cache expired it matched (section 6).
- QB2-Recorder XML before and after: **identical** (SHA-256 4312DD9E…E038B both
  times). Its last run at 17:12 had exit 0. Next run 18:00.

Today's counts (status at 17:43 UK):

| | Today | Since 2026-10-05 (target 20) | Expected so far today | Missed | Meter | Delay median |
|---|---|---|---|---|---|---|
| London | 10 | 14 | 8 (09:00–16:00) | none | RED (5–7 Oct short) | 16.7 min |
| US | 3 | 19 | 3 (15:00–17:00) | none | OK | 1.2 min |

London gave 10 today, not 8: the 09:00 and 10:00 hours each had two runs that
read different bars, and each bar counts once. The London meter stays RED
because it checks the three finished sessions before today (5, 6 and 7 Oct, all
short). It turns OK once Thursday and Friday are the sessions it checks.
Forecast: US reaches 20 at tonight's 18:00 run. London needs 6 more, so it
reaches 20 at Friday's 14:00 run if every hour from 09:00 lands. QT-13 can
still run after Fri 9 Oct 21:00 UK.

## 5. Verify

| Check | Before | After |
|---|---|---|
| v1 suite | 433 passed | 433 passed |
| qb2 suite | 412 passed | **425 passed** (+13 new) |
| plan tests (budgets) | — | 159 passed (STATE 4,979 / 6,000 chars) |
| ruff | clean | clean |
| mypy --strict | 4 errors in manual/ui Qt stubs | the same 4, none new |
| v1 fingerprint | 4add56ec…743b6 | 4add56ec…743b6 |
| qb2 fingerprint | 10351678…bd67d | **073e0978…fe543**: status_push.py added, delay_count.py gained scan_samples. (6b390f5f…234ce in d8b2bda's message was taken with LF files on disk; this is the normal CRLF checkout) |

One-in-one-out: nothing dead to remove. The new code reuses `delay_count`,
`sample_delay.MANIFEST` and its targets, and `t212_client.read_env_file`.

## 6. Raw-URL check

At 17:47, after the 5-minute cache expired, the raw URL (HTTP 200) was
**byte-identical** to the local file. The trigger starts 2026-10-08, so the
first scheduled run is 17:50 today and the mentor gets 18:50–21:50 tonight.
The recorder XML was hashed a third time after that change: still 4312DD9E…E038B.

Not started: QT-13.
