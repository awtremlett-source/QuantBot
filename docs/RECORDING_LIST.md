# Recording list — what gets CAPTURED (not what gets traded)

Generated from `qb2/ingest/tickers.py` on 2026-09-30, so the counts here
cannot drift from the code.

**This is not a universe decision.** S3b picks the bot's universe out of
this list under PROPOSE→GO. The list is deliberately wider than anything we
will trade, for one reason: recording something we never trade costs a little
disk, while failing to record something we later want costs the data
permanently. Intraday history cannot be fetched after the fact — minute bars
come only 8 days per request (docs/t212/FACTS.md row n).

## Counts

| group | count |
|---|---:|
| US shares | 64 |
| UK shares (FTSE-100 subset) | 30 |
| UK-listed ETFs | 20 |
| gauges (^FTSE ^FTMC ^GSPC ^VIX) | 4 |
| exchange rate (GBPUSD) | 1 |
| **total recorded** | **119** |

## The honest gap: not checked against Trading 212

Every name must exist on Trading 212 before it can ever be traded. **We could
not check that.** The practice API key returns 403 on the instruments
endpoint (FACTS row p), so T212's own list is unreadable with this key.

So membership of this list means only *"yfinance has it"*. The names below
are the ONLY ones proven to exist on T212, because the live practice account
held them on 2026-09-30:

| T212 ticker | yfinance | certain? |
|---|---|---|
| `GEV_US_EQ` | `GEV` | yes |
| `MU_US_EQ` | `MU` | yes |
| `RXRX_US_EQ` | `RXRX` | yes |
| `SPCX_US_EQ` | `SPCX` | yes |
| `IREN_US_EQ` | `IREN` | yes |
| `SGLNl_EQ` | `SGLN.L` | yes |
| `TSLA_US_EQ` | `TSLA` | yes |
| `ALCC1_US_EQ` | — | NO — trailing digit: T212 disambiguator, yfinance name unknown -- needs a human |
| `3LGO1l_EQ` | — | NO — trailing digit: T212 disambiguator, yfinance name unknown -- needs a human |
| `SNDK1_US_EQ` | — | NO — trailing digit: T212 disambiguator, yfinance name unknown -- needs a human |

S3b must verify the rest against T212's instrument list, which needs a key
with the instruments permission (docs/t212/SETUP.md explains how).

## The mapping rule

Read off the live account, not invented:

```
AAPL_US_EQ   ->  AAPL        (SYMBOL_US_EQ -> SYMBOL)
SGLNl_EQ     ->  SGLN.L      (SYMBOLl_EQ   -> SYMBOL.L)
SNDK1_US_EQ  ->  UNCERTAIN   (a trailing digit is T212's disambiguator)
```

Anything with T212's trailing digit is returned as **uncertain** and listed
for a human. It is never mapped by guesswork: mapping `SNDK1_US_EQ` to the
wrong `SNDK` would quietly record a different company's prices, and no test
of a strategy would notice.

## What is captured for each name

- **1-minute bars**, every run, catching up since the last saved bar.
- **5-minute** (~60 trading days) and **1-hour** (~2.9 years) as a one-time
  backfill, because those reach back and minutes do not.
- Closed bars only. The still-forming bar is dropped every time.

Files land in `data/raw/intraday/<interval>/<ticker>/<date>.parquet`
(gitignored), with one append-only manifest line per capture recording the
first and last bar, the row count, the currency, the fetch time and a file
hash. A gap that cannot be filled is written down as **LOST**, never faked.
