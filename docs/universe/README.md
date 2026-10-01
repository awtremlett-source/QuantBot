# The universes — which shares we watch, and which we may trade

Written for the operator. Three files live in this folder, all dated and all
rebuilt rather than edited by hand. Nothing here is chosen because a name is
familiar; every entry carries the evidence that put it there.

| file | what it is | how many |
|---|---|---|
| `recording-list-v2-*.json` | everything we **record prices for**. Recording is cheap; not having the data later is permanent. | 221 instruments + 4 gauges + 1 exchange rate |
| `bot-universe-v1-*.json` | what the **bot** may trade. **Status: AGREED 2026-10-02.** | 50, in three tagged sleeves |
| `advisor-universe-v1-*.json` | what the **advisor** may suggest. | 171 |

The bot's list and the advisor's list **cannot overlap**, and a test proves it. If
both parts held the same share, the bot's stop-loss would sell the advisor's
holding and the advisor would be left with a position nobody decided to close
(PLAN_V3 P6).

---

## AGREED — 2026-10-02

> **"GO on bot universe v1"**

Your words, recorded verbatim and dated in the file itself, as the S4 exit gate
requires. The bot may now be **built and back-tested** against these 50 names.

**It does not mean anything trades.** The sender is still disarmed in code
(`ARMED = False`, and nothing in qb2 sets it True), and S3's own exit gate is still
open on two counts — see the bottom of this page. Agreeing a list is permission to
build, not permission to trade.

**Changing this list later is a new decision.** The build tool now refuses to
overwrite an agreed list with a freshly proposed one, because everything reads
whichever file sorts last: a rebuild would otherwise have closed the S4 gate again
with no error and no obvious cause.

The 50 names, in three sleeves:

| sleeve | names | what a round trip costs | why it is here |
|---|---|---|---|
| `uk_etf` | 10 London ETFs | **0.20%** (0.40% at 2× stress) | the cheapest thing available: ETFs pay no stamp duty, and sterling lines pay no currency fee |
| `us_liquid` | 30 US shares | **0.40%** (0.80%) | no stamp duty, but 0.15% currency conversion on *each* leg |
| `uk_share` | 10 FTSE 100 shares | **0.70%** (1.40%) | the **most expensive**: stamp duty takes 0.5% of every buy |

Those are measured from the cost model, not estimates of mood. They matter because
the bot trades **same day** — it pays the cost twice in one day. A same-day signal
on a UK share must clear **0.7%** before it earns a single penny, and 1.4% under
the stress test the firewall applies. The UK share sleeve is in the list
**deliberately, as the expensive arm**, so PLAN_V3's P17 ("decide the market by
test") is settled by measurement rather than by my opinion. I expect it to lose.

---

## How the names were chosen

Each rule is a number, measured over three months of daily bars (median of
close × volume — "how much of this share actually changes hands on a normal day"):

- **US:** a member of the S&P 500 trading **at least $800 million a day**. 98 of
  503 clear it.
- **UK shares:** every member of the FTSE 100. All 100 are available on Trading
  212 — checked, not assumed.
- **UK ETFs:** a London ETF quoted in **sterling**, trading at least **£6 million
  a day**, **one line per fund**, with no leveraged or "short" products. Trading 212
  offers 1,576 sterling-quoted London ETFs; 1,197 remain once leveraged, short and
  options products are removed; 1,090 of those have enough price history to measure;
  **23 clear the floor**.

Liquidity is measured because our own order has to not move the price. A name
everyone has heard of can still be thin.

### Sources, with the bytes we actually read

| what | where | when | sha256 (first 16) |
|---|---|---|---|
| Trading 212's instrument list (18,483 rows) | the broker's own API, GET only | 2026-10-01 | `e53d1757f3885de8` |
| Trading 212's exchange list | same | 2026-10-01 | `bb628adbeb49a382` |
| S&P 500 membership | `en.wikipedia.org/wiki/List_of_S%26P_500_companies` | 2026-10-01 | `21fa15f7d19444af` |
| FTSE 100 membership | `en.wikipedia.org/wiki/FTSE_100_Index` | 2026-10-01 | `f5fd6b75d76e77cc` |
| measured traded value | yfinance daily bars | 2026-10-01 | `071342142af5fbdf` |

The saved files live under `data/raw/`, which is deliberately outside git along
with the price bars. The hashes above are in git, so the bytes can always be
checked against what we read.

**The membership pages were parsed mechanically, not read by a language model.**
That is not pedantry: a model asked to read the S&P 500 table invented several
hundred ticker symbols that do not exist (`TOZZ`, `TOYZ`, and hundreds more). A
list of facts is parsed, and then every name is checked against the broker's own
list before it can enter a universe.

---

## ⚠ Survivorship bias — read this before trusting any back-test

Both membership lists are **today's** membership. The FTSE 100 of 2023 contained
companies that have since fallen out of it, and some that failed outright. They are
missing from this list, which means a back-test run over past years using these
names has quietly been handed only the survivors.

**Every result built on this list is therefore too good.** Not "possibly" — the
direction of the error is known. S4 carries a survivorship mark-down for exactly
this reason, and no result from these lists should be reported without it.

---

## Four things the broker's own data revealed

These were found by checking our list against Trading 212's, and each one would
have produced believable-looking nonsense:

**1. Trading 212's ticker is a *historical* name.** It keeps whatever a company was
called when it was listed. Meta is `FB_US_EQ`. RTX is `UTX_US_EQ` — United
Technologies. Booking is `PCLN_US_EQ` — Priceline. NatWest in London is `RBSl_EQ` —
Royal Bank of Scotland. **30 of the 98 US names and 9 of the 100 UK names** are
affected. And it is a trap, not a curiosity: `NWG_US_EQ` *also* exists, and it is
NatWest's **New York** listing in dollars. Build a ticker from the letters you know
and you trade the wrong share, in the wrong currency, on the wrong continent, at
prices that look entirely plausible. So tickers are never constructed — every name
is looked up, matched on exchange *and* currency, and recorded with its ISIN.

**2. London prices come in three currencies.** Of the London instruments Trading
212 offers, 2,420 are quoted in **pence**, 557 in **pounds**, and 1,323 in **US
dollars**. yfinance agrees instrument by instrument. Mix them and a price series
acquires a silent 100× step that looks like a crash. So the currency is carried per
instrument, and the clean store converts pence to pounds exactly once.

**3. A UK share can cost a currency fee.** `CPG.L` (Compass Group), `IHG.L` and
`MTLN.L` are FTSE 100 members that Trading 212 prices in dollars or euros, and
there is **no sterling line** for them. Buying them pays 0.15% on the way in and
0.15% on the way out, for nothing. They are flagged in the file.

**4. We were holding one fund twice.** `IGLN.L` and `SGLN.L` are both iShares
Physical Gold, ISIN `IE00B4ND3602` — the same fund, one priced in dollars and one
in pence. A list holding both looks like two holdings and behaves like one. Only
`SGLN.L` remains.

---

## Names that left the active list

Nothing was deleted. The prices already recorded under these names are still on
disk, untouched; they are simply no longer updated, and they are not promoted into
the clean store where a strategy could pick them up.

| name | why it left |
|---|---|
| `AHT.L` | **it is not Ashtead any more.** Trading 212's `AHTl_EQ` is now Sunbelt Rentals, on a US ISIN. The ticker survived a change of company — which is exactly the thing no price chart can show you. |
| `IEUR.L` | does not exist on Trading 212's London list at all. The London line of iShares Core MSCI Europe is `IMEU.L`. |
| `IGLN.L` | the same fund as `SGLN.L` (see above). |
| `RXRX` | trades $55m a day against an $800m floor — 1/14th of what the bot needs. |
| `AGGG.L`, `XDWD.L` | dollar-quoted lines whose sterling twins (`SAGG.L`, `XWLD.L`) are about **twice as thin**. Switching would save 0.30% in fees and may cost more than that in spread. **Undecided on purpose** — the measured spreads from real fills will settle it, not a guess. |
| 7 US names (`DHR`, `SPGI`, `LOW`, `BLK`, `SYK`, `ELV`, `PLD`) | below the $800m floor; all still liquid, just not liquid enough for same-day trading. |

---

## Rebuilding

```
python -m qb2.tools.build_universe
```

It reads the saved sources and writes new dated files beside the old ones. Old
files are never overwritten: a universe that changes silently makes every earlier
result impossible to reproduce.
