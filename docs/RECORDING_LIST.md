# Recording list — what gets CAPTURED (not what gets traded)

**Superseded 2026-10-01 by `docs/universe/`.** The list is no longer kept by hand:
it is built from evidence and written to a dated file, so it cannot drift from the
code or from the broker. Read **`docs/universe/README.md`** for the names, the
rules, the sources and the traps found along the way.

This page keeps only what does not live there.

## Counts (v2, 2026-10-01)

| group | count |
|---|---:|
| US shares (S&P 500, ≥ $800m traded/day) | 98 |
| UK shares (the whole FTSE 100) | 100 |
| UK-listed ETFs (sterling, ≥ £6m/day, one line per fund) | 23 |
| gauges (^FTSE ^FTMC ^GSPC ^VIX) | 4 |
| exchange rate (GBPUSD) | 1 |
| **total recorded** | **226** |

Was 119 on 2026-09-30. Nothing recorded under the old names was deleted.

## The gap of 2026-09-30 is CLOSED

That version of this page said, honestly, that membership meant only *"yfinance has
it"* — the practice API key returned 403 on the instruments endpoint, so Trading
212's own list could not be read.

The key replaced on 2026-10-01 can read it. **All 503 S&P 500 names and all 100
FTSE 100 names resolve to a real Trading 212 instrument**, matched on exchange and
currency rather than on spelling, each recorded with its ISIN. See FACTS rows q, r
and s for what that check turned up — including that T212's ticker does not track
company renames, which made four of our old names wrong.

## What it costs to record this much

Measured from the files on disk, not estimated:

| interval | median file | what one file holds |
|---|---:|---|
| 1m | 15,505 B | one ticker, one trading day |
| 5m | 7,226 B | one ticker, one trading day |
| 1h | 10,222 B | one ticker, one **month** |

Per ticker per weekday that is **22.7 KiB** (one 1m file + one 5m file + a
twenty-first of a monthly 1h file).

| names | per weekday | per month | per year |
|---:|---:|---:|---:|
| 119 (the old list) | 2.6 MiB | 55 MiB | 0.65 GiB |
| **226 (now)** | **5.0 MiB** | **105 MiB** | **1.23 GiB** |

Disk is not the constraint and was not the reason the list stayed small. Widening
costs about 2.4 MiB a weekday more. **Time** is the constraint: see the warning
below.

## ⚠ The recorder's schedule needs changing before this list is safe

Found 2026-10-01 while checking whether the delay had been measured. The
`QB2-Recorder` scheduled task is configured in three ways that quietly lose data on
a laptop:

- `DisallowStartIfOnBatteries: True` — it **will not start** on battery.
- `StopIfGoingOnBatteries: True` — it is **killed** the moment the charger comes out.
- `StartWhenAvailable: False` — a missed run is **never made up**.
- `MultipleInstances: IgnoreNew` — and a run now takes **over an hour**, so the next
  hourly trigger is refused. That is the `4320` ("the operator or administrator has
  refused the request") recorded against today's 20:55 run.

Every day the recorder does not run is a day of minute bars that can never be
recovered. The one command that fixes all four is in the session log for
2026-10-01; it is the operator's to run, since it changes a system setting.
