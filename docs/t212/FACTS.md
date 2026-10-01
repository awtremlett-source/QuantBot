# Trading 212 API — checked facts

Every row was read from Trading 212's own documentation on the date shown. A row
is **VERIFIED** only if their page says it; **UNVERIFIED** if nobody has found it
stated; **CONTRADICTED** if what we believed is not supported by the docs.

Nothing in the plan may rely on an UNVERIFIED row. When one is settled later, the
row gets updated here first, then the plan.

Checked 2026-09-27. The API is **in beta** and "under active development"
([general information](https://docs.trading212.com/api/section/general-information)),
so these rows have a shelf life: re-check them in any box that places an order.

## The headlines

Four findings change the plan:

1. **There is no trailing-stop order type, and no way to amend an order.** So the
   trailing stop in P10 cannot live at the broker. It must be run by our own
   code — which is exactly what the operator said: *"the stop needs to come from
   either Trading 212 or the algorithm."* It comes from the algorithm.
2. **The API cannot tell us the price of a share we do not already own.**
   `currentPrice` exists only inside a *position*. So P14's pre-trade price check
   cannot be "ask Trading 212 first" for a new buy. S2b has to design around it.
3. **Order endpoints are not idempotent** — their own words. A resend can create a
   second real order, so every send must check pending orders first.
4. **Whether stop orders work on a real-money account is still UNRESOLVED**, and
   it is the one open question that touches money. One source says yes, the other
   is silent, and the page that once said no has gone. It changes nothing we
   build -- our own code holds every stop -- but it must be settled before S14.
   See row c.

## The facts

| # | Fact | Source | Checked | Status |
|---|---|---|---|---|
| a | Authentication is HTTP Basic: base64 of `<API_KEY>:<API_SECRET>`, sent as `Authorization: Basic <credentials>` | [quickstart](https://docs.trading212.com/api/section/general-information/quickstart) | 2026-09-27 | **VERIFIED** |
| b1 | Demo (paper) base URL is `https://demo.trading212.com/api/v0` | [api-environments](https://docs.trading212.com/api/section/general-information/api-environments) | 2026-09-27 | **VERIFIED** |
| b2 | Live base URL is `https://live.trading212.com/api/v0` — never called by this project until S14 | [api-environments](https://docs.trading212.com/api/section/general-information/api-environments) | 2026-09-27 | **VERIFIED** |
| c | Can Limit / Stop / Stop-Limit orders be placed on a REAL-MONEY account via the API? | **A** [stop-limit endpoint](https://docs.trading212.com/api/orders/placestoplimitorder) and [market endpoint](https://docs.trading212.com/api/orders/placemarketorder) · **B** [help centre](https://helpcentre.trading212.com/hc/en-us/articles/14584770928157-Trading-212-API-key) | 2026-09-27 | **CONFLICT — UNRESOLVED.** **B says yes:** "You can place Limit, Stop and Stop Limit orders via the Trading 212 API for live accounts." **A neither confirms nor denies:** its only "Order Limitations" line is "Orders can be executed only in the main account currency" — no real-money split, and no `NotAvailableForRealMoneyAccounts` error code on either page. The page previously cited as restricting live to market orders (`/api/equity-orders/placestoporder_1.md`) now returns **404**, and a T212 community thread dated Jan 2026 says the restriction was lifted. So: one source asserts it, one is silent, and the restricting page is gone — that is not corroboration, so it stays UNRESOLVED for money purposes. **An earlier VERIFIED, read from A alone, was premature.** Impact on design: **none** — our algorithm holds every stop (rows d1/d2) and the bot is same-day, so no stop is ever parked at the broker. **Must be settled before S14** by one tiny live test or a written answer from T212 support |
| d1 | There is **no trailing-stop order type**. The only order endpoints are limit, market, stop and stop_limit | [orders](https://docs.trading212.com/api/orders) | 2026-09-27 | **VERIFIED** (by enumeration of the documented endpoints) |
| d2 | There is **no amend/modify endpoint**. An order can only be cancelled: `DELETE /api/v0/equity/orders/{id}` "Attempts to cancel an active, unfilled order by its unique ID" | [orders](https://docs.trading212.com/api/orders) | 2026-09-27 | **VERIFIED** — changing an order means cancel then replace |
| e | "This endpoint is not idempotent. Sending the same request multiple times may result in duplicate orders" (limit, market, stop, stop_limit) | [place market order](https://docs.trading212.com/api/orders/placemarketorder) | 2026-09-27 | **VERIFIED** |
| f1 | Maximum **50 pending orders per ticker, per account** | [function-specific limits](https://docs.trading212.com/api/section/rate-limiting/function-specific-limits) | 2026-09-27 | **VERIFIED** |
| f2 | "The API currently only supports placing orders by QUANTITY" — order-by-value is not available | [place market order](https://docs.trading212.com/api/orders/placemarketorder) | 2026-09-27 | **VERIFIED** |
| f3 | "Orders can be executed only in the primary account currency"; "Multi-currency accounts are not currently supported through the API" | [api-limitations](https://docs.trading212.com/api/section/general-information/api-limitations) | 2026-09-27 | **VERIFIED** |
| f4 | "The Trading 212 Public API is enabled and usable only for **Invest and Stocks ISA** account types" | [api-limitations](https://docs.trading212.com/api/section/general-information/api-limitations) | 2026-09-27 | **VERIFIED** |
| f5 | "All rate limits are applied on a per-account basis, regardless of which API key is used or which IP address the request originates from" | [rate limiting](https://docs.trading212.com/api/section/rate-limiting) | 2026-09-27 | **VERIFIED** |
| f6 | The limiter allows **bursts**: 50-per-minute may be spent in the first few seconds, then you wait for the reset | [how it works](https://docs.trading212.com/api/section/rate-limiting/how-it-works) | 2026-09-27 | **VERIFIED** |
| f7 | `x-ratelimit-reset` response header gives the reset time | [how it works](https://docs.trading212.com/api/section/rate-limiting/how-it-works) | 2026-09-27 | **VERIFIED** |
| f8 | The further headers `x-ratelimit-limit`, `-period`, `-remaining`, `-used` | search summaries of the rate-limiting pages, not seen in a direct read | 2026-09-27 | **UNVERIFIED** — our client reads them if present and works without them |
| f9 | The HTTP status returned when a limit is exceeded is **429** | OBSERVED live on the practice account, not documented | 2026-09-30 | **VERIFIED BY OBSERVATION** — calling `account/summary` twice inside its 5-second window returned HTTP 429. Still absent from the docs, so it is recorded as observed rather than documented; our client backs off on 429 *and* honours `x-ratelimit-reset` |
| g | One position per share per account | [fetch all open positions](https://docs.trading212.com/api/positions/getpositions) + LIVE practice account read + order history | 2026-10-01 | **VERIFIED.** The decisive case was found in the practice account's order history once the new key could read it: `MU_US_EQ` has **two separate filled BUY orders** (12.5711224 and 10.0) and one filled SELL (10.0), and `positions` returns it as **exactly one row, quantity 12.5711224** — the net of the three. So the broker aggregates; a second buy of a share we already hold adds to the existing position rather than opening a second one. Consequence for us: a position is identified by its ticker alone, there is no position id to track, and 'how much do I hold' is always one number |
| h | Can the API price a share we do **not** hold? | [positions schema](https://docs.trading212.com/api/positions/getpositions) · [instruments](https://docs.trading212.com/api/instruments) | 2026-09-27 | **NO — VERIFIED by enumeration.** `currentPrice` ("Current price, in instrument currency, of a single share") appears only on a POSITION. The instrument metadata endpoints carry no price and are "refreshed every 10 minutes". No quotes/candles/market-data section exists in the API |
| i | Instrument fields: `ticker`, `type` (CRYPTOCURRENCY, ETF, FOREX, FUTURES, INDEX, STOCK, WARRANT, CRYPTO, CVR, CORPACT), `currencyCode` (ISO 4217), `isin`, `name`, `shortName`, `addedOn`, `maxOpenQuantity`, `extendedHours`, `workingScheduleId` | [instruments schema](https://docs.trading212.com/api/instruments/instruments) | 2026-09-27 | **VERIFIED** |
| j1 | Market orders take `extendedHours` (boolean) so a fill can happen outside the regular session | [place market order](https://docs.trading212.com/api/orders/placemarketorder) | 2026-09-27 | **VERIFIED** — the request schema is `ticker`, `quantity`, optional `extendedHours` |
| j2 | An order placed while the market is shut is queued to the next open | no page read states this | 2026-09-27 | **UNVERIFIED** — so the bot simply never sends a buy into a closed market (PLAN_V3 P4). A queued buy would fill while nothing is watching, which is the risk regardless of what the docs say |
| j3 | The order endpoints are not idempotent, so a resend can duplicate | see row e | 2026-09-27 | **VERIFIED** (row e) |
| k1 | Which order types accept `extendedHours` | [orders reference](https://docs.trading212.com/api/orders) | 2026-09-27 | **PARTLY VERIFIED** — confirmed on the market-order schema; not seen on the limit/stop/stop-limit schemas. The bot only ever sends market orders, so only the market case matters |
| k2 | US extended-hours sessions: "Pre-market: 04:00 - 09:30 ET" and "After-hours: 16:00 - 20:00 ET", for "the most liquid and widely traded US stocks" | [extended market hours](https://helpcentre.trading212.com/hc/en-us/articles/9946943754013-What-are-extended-market-hours) | 2026-09-27 | **VERIFIED** (quoted in ET) |
| k3 | The same sessions on the UK clock: pre-market ≈09:00–14:30, after-hours ≈21:00–01:00 | arithmetic from k2, not a quote | 2026-09-27 | **DERIVED, not verified** — the UK is normally 5 hours ahead of New York, but the two change clocks on different dates, so for about two weeks a year the offset is 4 hours. Code must convert with a real timezone database, never a fixed +5 |
| k4 | Extended hours for LONDON shares | [extended market hours](https://helpcentre.trading212.com/hc/en-us/articles/9946943754013-What-are-extended-market-hours) | 2026-09-27 | **NONE DOCUMENTED** — the page is about US stocks and says nothing about UK extended hours. Treat London as regular session only |
| l | Currency-conversion (FX) fee: **0.15%**, charged whenever you buy or sell a share priced in a currency you do not hold — so **twice** on a round trip (0.30%) | [Invest/ISA/SIPP fees](https://helpcentre.trading212.com/hc/en-us/articles/11471996799517-What-are-the-fees-in-the-Invest-ISAs-and-SIPP) | 2026-10-01 | **VERIFIED, AND NOW CONFIRMED FIRST-HAND.** The practice account's own transaction history carries a `CURRENCY_CONVERSION_FEE` line on real deposits and fills at exactly **0.150%** — −£15.00 on £10,000.00 and −£25.87 on £17,218.11 (both 0.1500% to four decimals). So the published rate is the charged rate, measured on our own account rather than taken on trust. Row r makes this expensive in a way that is easy to miss: some London lines are quoted in US dollars, so buying a *UK* share can pay it twice |
| m1 | UK Stamp Duty Reserve Tax: "Stamp Duty Reserve Tax is charged at 0.5% on share purchases made for stocks listed on the London Stock Exchange." Buy only, never sell | [T212 fees](https://helpcentre.trading212.com/hc/en-us/articles/11471996799517-What-are-the-fees-in-the-Invest-ISAs-and-SIPP) · [gov.uk](https://www.gov.uk/tax-buy-shares) ("you usually pay a tax or duty of 0.5% on the transaction") | 2026-09-27 | **VERIFIED** by two independent sources |
| m2 | No stamp duty on ETFs: "There is no Stamp Duty charge applied to gilts, bonds or ETFs" | [T212 fees](https://helpcentre.trading212.com/hc/en-us/articles/11471996799517-What-are-the-fees-in-the-Invest-ISAs-and-SIPP) | 2026-09-27 | **VERIFIED** |
| m3 | No SDRT on AIM shares: growth-market securities "not listed on that or any other market are excluded from the definition of chargeable securities" | [HMRC STSM041270](https://www.gov.uk/hmrc-internal-manuals/stamp-taxes-shares-manual/stsm041270) | 2026-09-27 | **VERIFIED** — AIM is a recognised growth market. Note this depends on the *instrument*, so the cost model needs a per-instrument flag it cannot infer from the ticker alone |
| m4 | PTM levy: "£1.5 per trade for orders over £10,000", charged "on purchase and sale" | [T212 fees](https://helpcentre.trading212.com/hc/en-us/articles/11471996799517-What-are-the-fees-in-the-Invest-ISAs-and-SIPP) | 2026-09-27 | **VERIFIED** — note v1's old config used £1.00; £1.5 is the figure T212 states today |
| n | yfinance intraday history depth, **PROBED not assumed** (2026-09-27, yfinance 1.4.1, AAPL): **1m → nothing**, Yahoo's own error being "Only 8 days worth of 1m granularity data are allowed to be fetched per request"; **5m → 4,680 bars** spanning 2026-07-02→09-25; **15m → 1,560 bars**, same span; **1h → 420 bars** for 60d, and **5,082 bars spanning 1,064 days** when 730d was asked. Asking 730d at 5m/15m returned nothing: "The requested range must be within the last 60 days" | direct probe, recorded | 2026-09-27 | **VERIFIED by probe.** The consequence is the important part: minute data must be fetched ≤8 days at a time, 5m/15m reach back only ~60 trading days (~85 calendar days measured), and **anything not recorded as it happens is gone** |
| o | yfinance quote delay, MEASURED | direct probe: 5 US + 5 London tickers, 5 samples each | 2026-09-27 21:30 UTC | **UNMEASURED — markets were shut.** Last-bar ages came back at ~2,976 minutes (US) and ~3,246 minutes (London), i.e. ~50 and ~54 hours: that is Friday's close seen on a Sunday night, not a delay. It is recorded because it proves the probe ran and the market was closed. **The real delay must be measured during market hours** — added to the S3 exit gate. The often-quoted "20 minutes" is NOT assumed anywhere |
| i2 | An **ISA-eligibility field** on an instrument | [instruments schema](https://docs.trading212.com/api/instruments/instruments) | 2026-09-27 | **ABSENT** — no such field is documented. ISA eligibility cannot be read from the instrument list; it must come from elsewhere or be treated as unknown |

| p | What the practice API key is actually permitted to do | LIVE probe of every read endpoint, GET only | 2026-10-01 | **VERIFIED BY OBSERVATION, for the key in use since 2026-10-01.** The operator replaced the key (the old one was deleted) and states its permissions as, verbatim: **"Orders – Execute OFF, Pies – Write OFF"**. Probing all ten documented READ endpoints with GET only: `account/summary`, `account/cash`, `account/info`, `positions`, `orders`, `metadata/instruments`, `metadata/exchanges`, `history/orders`, `history/dividends`, `history/transactions` — **all ten granted**. This is a wider key than the previous one (which was 403 on five of them), so two gaps recorded on 2026-09-30 are now closed: the instrument list is saved and the recording list is verified against it, and row g is settled from order history. **Execute remains OFF**, and the client is GET-only in code regardless — two independent reasons no order can be placed. The earlier narrower map is kept in git history, not overwritten here |
| q | **Trading 212's `ticker` is a HISTORICAL identifier and does not track renames** | the saved instrument list, `data/raw/t212/instruments-2026-10-01.json` (18,483 rows) | 2026-10-01 | **VERIFIED BY OBSERVATION, and it is a trap.** T212 keeps the ticker a company had when it was added. Meta Platforms is `FB_US_EQ`; RTX is `UTX_US_EQ` (United Technologies); Booking is `PCLN_US_EQ` (Priceline); Elevance Health is `ANTM_US_EQ` (Anthem); NatWest in London is `RBSl_EQ` (Royal Bank of Scotland). **30 of the 503 S&P 500 names and 9 of the 100 FTSE 100 names are affected.** The danger is not the odd name: `NWG_US_EQ` also exists and is NatWest's *New York* listing in dollars, so a program that builds a T212 ticker from the letters it knows would trade the wrong share, in the wrong currency, on the wrong continent, at plausible-looking prices. Consequence: tickers are never constructed. Every name is resolved against this saved list on `shortName` **and** exchange, and the answer is pinned with its ISIN (`qb2/ingest/verify_universe.py`) |
| r | **London quote currency is a three-way split, per instrument** | the saved instrument list + yfinance metadata, independently | 2026-10-01 | **VERIFIED BY TWO SOURCES THAT AGREE.** Of 4,495 London instruments T212 offers: **2,420 in GBX (pence), 557 in GBP (pounds), 1,323 in USD, 195 in EUR.** yfinance reports the same currency for the same instrument in every case checked — BP.L, LLOY.L, AZN.L, ISF.L pence (yfinance spells it `GBp`); VWRL.L, VUSA.L pounds; CPG.L (Compass Group, a FTSE 100 member), AGGG.L, IGLN.L, XDWD.L **US dollars on the London Stock Exchange**. Our own recorded bars match the magnitudes. Consequences: (1) the quote currency is carried per row and never inferred from a ".L" suffix, or a series acquires a silent 100x step; (2) a London share quoted in USD pays the row-l FX fee on **both legs**, which is a real cost attached to a UK name |
| s | **AIM is a separate exchange in T212's list** | the saved exchange list, `data/raw/t212/exchanges-2026-10-01.json` | 2026-10-01 | **VERIFIED.** T212 names "London Stock Exchange" (3,848 instruments) and "London Stock Exchange AIM" (647) separately, so the stamp-duty exemption in row m3 can be read off the data per instrument instead of guessed. "OTC Markets" (1,616) is also named, and is excluded from every universe: it is where the thin ADR lines live (`LNSTY` for LSEG, `ASHTY` for Sunbelt) and is never the line we mean |

## Endpoints this project will call (GET only, demo only)

| Endpoint | Purpose | Documented rate limit |
|---|---|---|
| `GET /api/v0/equity/account/summary` | cash and account value | 1 req / 5s |
| `GET /api/v0/equity/positions` | open positions, with `currentPrice` | 1 req / 1s |
| `GET /api/v0/equity/orders` | pending orders (needed before any resend, per row e) | 1 req / 5s |
| `GET /api/v0/equity/metadata/instruments` | the tradable universe | 1 req / 50s |
| `GET /api/v0/equity/metadata/exchanges` | trading hours | 1 req / 30s |

Sources: [accounts](https://docs.trading212.com/api/accounts) ·
[positions](https://docs.trading212.com/api/positions) ·
[orders](https://docs.trading212.com/api/orders) ·
[instruments](https://docs.trading212.com/api/instruments). Checked 2026-09-27.

**Order endpoints are recorded here for completeness and are deliberately not
implemented.** `POST /equity/orders/{market,limit,stop,stop_limit}` (50 req/1m for
market, 1 req/2s for the others) and `DELETE /equity/orders/{id}` (50 req/1m) are
out of scope until S10, and the client built in S2a has no method that can reach
them.

## Getting the demo API key (what the operator does)

From the Trading 212 **mobile app**: "Tap ☰. Select Settings. Select API (Beta).
Select Generate API key." Choose the permissions, and prefer "Restrict access to
trusted IPs (recommended)" over "Unrestricted (less secure)".

You get two values. The **API Secret Key** "works like a password and will be
shown only once after generation" — if it is lost, a new pair must be generated.
The docs also note "API Key versions may differ between real and demo accounts",
so generate the key **from the practice account** for this project.

Source: [Trading 212 API key, help centre](https://helpcentre.trading212.com/hc/en-us/articles/14584770928157-Trading-212-API-key),
checked 2026-09-27.
