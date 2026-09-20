# TradeScout

A desktop guide for **manual paper trading** on the London Stock Exchange —
built for practising discretionary trading with names available on
Trading 212. Every morning it ranks the FTSE 100 + 250 universe into a
**Best buys** board and an **Exit / avoid** board, shows exactly *why* each
name scored what it did, sizes a hypothetical position in pounds, and makes
you write a thesis before it will log the paper trade to your journal.

**It is a decision aid, not a trading system.** It places no orders, uses no
broker API, and is long-only in framing (SELL means *exit or avoid*, not
short). Not financial advice.

---

> **This app now lives inside the QuantBot repo, as `manual/`.** It is walled
> off from the trading engine: the engine cannot import it, and it cannot
> write to the engine's books (the one read-only doorway is
> `manual/bot_readonly.py`). See `docs/merge/MERGE_PLAN.md`.

## Install

Python 3.13. The manual app keeps its OWN environment: its pins conflict with
the engine's, so they are never installed together.

```
py -3.13 -m venv .venv-ui
.venv-ui\Scripts\python.exe -m pip install -r requirements-ui.txt
```

## Run

Double-click `tools_ui\TradeScout.bat`, or from the repo root:

```
py -3.13 -m manual.app
```

## First run

The app opens with an empty cache. Press **Refresh data** — it pulls ~2 years
of daily bars for ~255 tickers from Yahoo Finance in polite batches, which
takes a few minutes (watch the progress bar). Every day after that, refresh
is incremental (only new bars) and takes seconds.

Data etiquette is built in and worth keeping:

- **Cache-first**: the UI always renders from the local SQLite cache
  (`data/manual/trade_scout.db`); the network is touched only when you press
  Refresh.
- **Once per day**: a second Refresh on the same day is a no-op unless you
  press **Force**.
- **Batched + backoff**: downloads run in chunks with pauses, and retry with
  exponential backoff if Yahoo throttles. A failed chunk never blocks the
  rest — problems are listed in the footer.

Yahoo Finance is an unofficial free source: occasional gaps, delayed quotes
and throttling are normal. This app is built for end-of-day guidance, not
live prices.

## The tabs

**Finding things:** every stock picker shows "TICKER — Company Name" and
is type-to-search ("gold", "shell", "googl" all work); Home has a Find-any-
stock bar. **Add stock…** (top strip) searches Yahoo by name and adds
anything — LSE shares, ETFs/ETCs like iShares Physical Gold (SGLN.L), or
US names like Alphabet (GOOGL, ships included). Non-sterling names chart,
score and warn, but £ sizing and live £ P&L need a pounds quote.
**Record a trade I already have** (My Trades) logs holdings opened
elsewhere: shares + total £ paid, optional stop.

**Home** is where you live: your three daily steps with big buttons (update
prices, read the ideas, check your trades), today's market conditions in
plain words, and a top-5 glance at both boards. A "How to use" button in the
top strip explains everything in one screen.

1. **Spotlight** — durable climbers: large, liquid names that have spent
   80%+ of the last six months above their 200-day and are up on the year.
   Refreshes itself each scan; star to track.
2. **Today's Ideas** — the strongest names worth a look to buy (green) and
   the weakest to avoid or sell (red), each with a 0–100 score. Hover a
   score for the full point-by-point reasons. Double-click opens the stock;
   the star adds it to your watchlist.
3. **Stock Detail** — candlestick chart (20/50-day averages, volume), full
   reasoning both ways, and the money box: ATR-based stop, share count from
   your risk budget, stamp duty + PTM levy, breakeven move, % of bankroll.
   A five-point checklist and a required written thesis gate the
   **Log paper trade** button.
4. **My Trades** — every holding gets one clear verdict: **HOLD**,
   **BEWARE** or **SELL OUT**, with the reason in plain words (hover for
   detail and tips such as raising your sell alert). Recording an existing
   holding takes three numbers — shares, total £ paid, and a sell alert the
   app suggests automatically from the stock's own volatility. Close trades
   there and note the lesson. Starred stocks sit underneath.
5. **Results** — (with a Delete button on any record — for mistakes, not
   for rewriting history) two inner tabs: *My trading results* (win rate, average
   result in R, total P&L, per-pattern breakdown) and *The app's pick
   record* (every day's boards, measured since — is the scoring itself any
   good?).

The banner across the top is the **Timing Dial** — a 0–100 answer to "is
today a good day for new trades?", built from four checks each worth 25
points: index **Trend** (FTSE 100/250 vs their long-term averages),
**Breadth** (share of the whole universe above its 200-day — >60% healthy,
<40% hostile), **Fear** (VIX: <20 calm, 20–28 jumpy, >28 storm, penalised
when climbing fast), and **Flow** (3-month cyclicals-vs-defensives race —
money chasing growth vs money hiding). Checks without data are excluded and
the score rescaled. Underneath it, a two-clock **hiccup radar** flags a
*small hiccup* (shakeout inside an uptrend — historically a pullback-buying
window) and a *large hiccup* (correction risk — needs two independent
pieces of evidence; protect first). During LSE hours a polite **near-live
mode** polls your open positions, watchlist and the market gauges every few
minutes (config `live_interval_min`), driving live P&L, sell-alert breaches
and the LIVE stamp — the ~15-minute-delayed Yahoo feed applies, and the
full universe deliberately stays on daily bars. The dial is deliberately asymmetric: it needs three
straight qualifying days to upgrade, but downgrades the same day. Hover the
banner (or read Home's market box) for every check in plain words.

## The 50% money ladder

Position #1 may use up to 50% of the bankroll, #2 up to 25%, #3 up to
12.5%, halving each time — you're never fully invested, and each extra
idea must be smaller than the last. The ladder is a ceiling: the 1%-risk
rule still sizes each trade, the ladder just refuses to let one position
swallow the pot. The next slot and cap show in My Trades' header and as a
"Money split" step in every Recommended Path.

## Scoring, briefly

BUY = Trend 30 + Momentum 25 + Setup 25 (Breakout/Pullback) + Volume 10 +
Tradeability 10, minus penalties (big gap up, overheated RSI, thin trading,
penny prices), clamped 0–100. SELL mirrors it downward with Breakdown /
Death-cross setups. Every point appears as a plain-English reason — there
are no black boxes. Weights live in `scout/scoring.py` if you want to tune
them.

## Configuration

`config.json` (created on first run):

| Key | Default | Meaning |
|---|---|---|
| `bankroll_gbp` | 10000 | Paper bankroll used for sizing |
| `risk_pct` | 1.0 | % of bankroll risked per trade |
| `atr_stop_mult` | 2.0 | Stop distance in ATRs |
| `history_period` | "2y" | History pulled for new tickers |
| `chunk_size` / `chunk_pause_s` | 40 / 2.0 | Download batching politeness |
| `min_turnover_gbp` | 1000000 | Liquidity bar for full tradeability points |
| `stamp_duty_pct` / `ptm_levy_gbp` / `ptm_threshold_gbp` | 0.5 / 1.0 / 10000 | UK dealing-cost assumptions — **verify current rates yourself** |
| `top_n` | 25 | Rows per board |

## Editing the universe

`manual/assets/universe.csv` ships with a best-effort FTSE 100 + 250 snapshot
(~255 names). Index constituents drift constantly — treat the `index` column
as informational, prune names you can't trade, and add ones you can. The
`stamp_duty` column is Y/N (some non-UK-incorporated lines are exempt);
verify it per name before trusting cost maths. Always confirm a ticker is
actually offered inside Trading 212 — an LSE listing doesn't guarantee it.
Tickers use Yahoo's `.L` suffix (note `BT-A.L` style hyphens).

## Tests

64 offline tests (indicators verified against independent reference
implementations, scoring weights, risk maths, journal R-multiples,
incremental refresh with a mock provider, and offscreen UI smoke tests):

```
py -3.13 -m pytest tests/manual -q
```

No test touches the network. Run them with the UI interpreter: inside the
engine's `.venv` the suite is deliberately not collected (no PySide6 there).

## Where its files live

| what | where |
|---|---|
| code | `manual/` (package `manual.scout`, `manual.ui`) |
| tests | `tests/manual/` (131 tests) |
| shipped ticker list | `manual/assets/universe.csv` |
| settings | `manual/config.json` |
| its database + cache | `data/manual/` (gitignored) |
| launcher | `tools_ui/TradeScout.bat` |

The standalone repo it came from is untouched and still at its own remote;
this copy is the one that is developed from now on.

---

*Guide only · paper trading · not financial advice.*
