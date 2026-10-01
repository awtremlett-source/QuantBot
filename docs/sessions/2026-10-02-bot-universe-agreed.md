# 2026-10-02 — bot universe v1 AGREED

## What you said

> **"GO on bot universe v1"**

Recorded verbatim and dated inside `docs/universe/bot-universe-v1-2026-10-01.json`,
not just in a commit message — the S4 exit gate asks for the word AGREED, your own
words, and the date, and a test now checks all three. "AGREED" on its own is just a
word somebody typed.

## What it does and does not allow

**Allows:** the bot may now be **built and back-tested** against those 50 names —
30 US, 10 London ETFs, 10 FTSE 100 shares.

**Does not allow:** anything to trade. The sender is still disarmed in code
(`ARMED = False`, and nothing in qb2 sets it True), and there is now a test tying
the two together, so agreeing a list can never arm anything.

**S4 is still shut.** Your GO removed one of its three blockers. The other two are
S3's own exit-gate items, unchanged from yesterday:

1. the data census is **RED at 40.7%** against a 95% gate;
2. **earnings dates are still not ingested**.

So the next box still finishes S3, not S4.

## One thing I added while recording it

`build_universe` always writes its bot list as **PROPOSED**, and everything reads
whichever universe file sorts last. So a rebuild — for any reason, weeks from now —
would have quietly replaced your agreed list with a proposed one, and the S4 gate
would have closed again with no error and no obvious cause. The build now **refuses**
to overwrite an agreed list unless superseding is asked for explicitly, in which
case the new list needs a fresh agreement in your words. Proven red-on-broken.

## Still outstanding, and still costing data

The recorder has produced nothing since 20:27 yesterday and the quote delay still
has **0 samples**. The one command from yesterday's log has not been run:

```powershell
Set-ScheduledTask -TaskName 'QB2-Recorder' -Settings (New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances Queue -ExecutionTimeLimit (New-TimeSpan -Hours 3))
```

Until it runs, the census cannot climb towards its 95% gate — the 131 names with no
history can only fill in by being recorded, and minute bars cannot be fetched after
about 30 days.

## Gate

qb2 176→178 · engine 198 · museum 3 · wall 65 · plan 129 · manual 147. Default run
395. ruff and mypy --strict clean. v1 fingerprint `4add56ec…743b6` — identical.

**3-checks.** Correctness: the agreement is recorded verbatim with its date and
tested three ways; the rebuild hole was found and closed before it could bite; AGREED
was explicitly separated from ARMED. Language: written for a beginner, stating plainly
what the GO does *not* permit. Numbers: 50 names (30+10+10) checked against the file
rather than assumed; CLAUDE.md 3,537 of 3,600 chars.
