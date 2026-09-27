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
4. **The live-versus-demo order-type split we believed does not appear anywhere.**
   All four order types are documented for the API without an environment caveat.

## The facts

| # | Fact | Source | Checked | Status |
|---|---|---|---|---|
| a | Authentication is HTTP Basic: base64 of `<API_KEY>:<API_SECRET>`, sent as `Authorization: Basic <credentials>` | [quickstart](https://docs.trading212.com/api/section/general-information/quickstart) | 2026-09-27 | **VERIFIED** |
| b1 | Demo (paper) base URL is `https://demo.trading212.com/api/v0` | [api-environments](https://docs.trading212.com/api/section/general-information/api-environments) | 2026-09-27 | **VERIFIED** |
| b2 | Live base URL is `https://live.trading212.com/api/v0` — never called by this project until S14 | [api-environments](https://docs.trading212.com/api/section/general-information/api-environments) | 2026-09-27 | **VERIFIED** |
| c | "Live allows MARKET orders only via the API; stop / stop-limit exist for demo only" | [orders](https://docs.trading212.com/api/orders) · [api-limitations](https://docs.trading212.com/api/section/general-information/api-limitations) | 2026-09-27 | **CONTRADICTED** — the orders reference documents POST market, limit, stop and stop_limit with no live/demo distinction, and the limitations page lists no such split. Absence of a statement is not proof of absence, so treat the split as **not established** rather than disproved, and re-check before relying on stop orders |
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
| f9 | The HTTP status returned when a limit is exceeded (presumed 429) | not stated on any page read | 2026-09-27 | **UNVERIFIED** — our client backs off on 429 *and* honours `x-ratelimit-reset`, so either behaviour is safe |
| g | One position per share per account | [fetch all open positions](https://docs.trading212.com/api/positions/getpositions) | 2026-09-27 | **UNVERIFIED, strong indirect evidence** — the response is one object per instrument, `instrument.ticker` is described as the "Unique instrument identifier", quantities arrive pre-aggregated (`quantity`, `quantityAvailableForTrading`, `quantityInPies`), and the endpoint takes an optional `ticker` filter. No sentence states it. Settle by reading the demo account and counting rows per ticker |
| h | Can the API price a share we do **not** hold? | [positions schema](https://docs.trading212.com/api/positions/getpositions) · [instruments](https://docs.trading212.com/api/instruments) | 2026-09-27 | **NO — VERIFIED by enumeration.** `currentPrice` ("Current price, in instrument currency, of a single share") appears only on a POSITION. The instrument metadata endpoints carry no price and are "refreshed every 10 minutes". No quotes/candles/market-data section exists in the API |
| i | Instrument fields: `ticker`, `type` (CRYPTOCURRENCY, ETF, FOREX, FUTURES, INDEX, STOCK, WARRANT, CRYPTO, CVR, CORPACT), `currencyCode` (ISO 4217), `isin`, `name`, `shortName`, `addedOn`, `maxOpenQuantity`, `extendedHours`, `workingScheduleId` | [instruments schema](https://docs.trading212.com/api/instruments/instruments) | 2026-09-27 | **VERIFIED** |
| i2 | An **ISA-eligibility field** on an instrument | [instruments schema](https://docs.trading212.com/api/instruments/instruments) | 2026-09-27 | **ABSENT** — no such field is documented. ISA eligibility cannot be read from the instrument list; it must come from elsewhere or be treated as unknown |

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
