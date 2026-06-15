# EDUCATION — the self-taught-quant track

One entry per significant concept, written the day it enters the codebase: what it
is, why we need it, and the one beginner mistake to avoid. The glossary grows via the
jargon gate (every new term defined on first use). You don't have to read code or
trade — the goal is that, milestone by milestone, you come to understand every rule
this system runs on.

---

## Entry #1 — How this system makes (and loses) money: the honest version

**The idea in one breath.** Stock prices drift upward over long stretches and lurch
downward in crises. A simple, robust machine can ride most of the upward drift while
stepping aside in the worst falls. Done patiently, with costs respected, that grinds
out a slow gain. That is the *whole* engine. There is no secret sauce — the edge is
**discipline plus survival**, not prediction.

**Where the money actually comes from.**
- *Being in the market when it rises.* Most long-run gains come from simply holding
  during uptrends. Our CORE strategy (Phase 2) holds a broad index when it's above
  its long-term average, and sits in cash otherwise.
- *Not giving it back.* Avoiding the worst drawdowns (big peak-to-trough falls)
  matters as much as catching gains — a −50% loss needs a +100% gain just to recover.

**Where the money leaks out (the costs that kill small edges).**
- *Spread* — the gap between the buy and sell price; you cross it every trade.
- *Slippage* — the price moves against you between deciding and filling.
- *FX fee* — a GBP account buying USD stocks pays ~0.15% **each way**. On thin
  edges, this alone can turn a paper "profit" into a real loss.
- We always put these **inside** the backtest and report **net**, not gross.
  "Profitable gross, dead net" is the *normal* result for small edges (Scar #15).

**The trap that loses real money: overfitting.** If you tweak a strategy over and
over until it looks great *on past data*, you've often just memorised that data's
noise — and noise doesn't repeat, so it fails live. This is why we build a
**validation firewall** (Phase 1) *before* any strategy, and why our automated loops
are forbidden from stopping "when the profit looks good" (Scar #21).

**The honest yardstick.** A real, surviving retail strategy earns a net,
cost-honest **Sharpe ratio** *(return per unit of risk)* of roughly **0.7–1.2**.
A backtest showing far more is a **red flag**, not a triumph.

**The one beginner mistake.** Believing a beautiful backtest. A backtest is a
*hypothesis*, not a result. It only earns trust after it survives the firewall.

---

## Glossary (grows on first use)
- **Share** — a small slice of ownership in a company.
- **Ticker** — a stock's short code (Apple = AAPL).
- **OHLCV** — Open, High, Low, Close prices and Volume for one time period.
- **Order** — an instruction to buy or sell (market = now at any price; limit = only
  at your price or better).
- **Paper trading** — placing pretend orders with pretend money, recorded as if real.
- **Spread / slippage** — trading costs; you rarely trade exactly at the mid-price.
- **Drawdown** — a peak-to-trough fall in account value; our main risk gauge.
- **Sharpe ratio** — return per unit of volatility (risk). Higher is better, but a
  suspiciously high one usually signals a measurement error.
- **Overfitting** — tuning a model so hard it fits past noise and fails on new data.
- **Backtest** — a simulation of a strategy on historical data. A hypothesis, not proof.
- **Demo / paper account** — a practice account with fake money (Trading 212 demo).
