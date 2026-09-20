# PLAN v2 — QuantBot, the Simons direction

Written 2026-09-21. **Nothing in here is built yet.** This is the plan and the
order; each stage below is one box of work, and every one of them has to prove
itself before the next starts.

The live v1 engine keeps running throughout, untouched. It is the thing v2 has
to beat.

**How to read this.** Jargon is defined the first time it appears. If a number
about Trading 212 is not followed by a link and a date, it says UNVERIFIED —
that means nobody has checked it yet, so do not plan around it.

---

## Operator words

Verbatim, 2026-09-20 and 2026-09-21. Each quote is on one long line on purpose:
a quote that has been re-wrapped or tidied is no longer evidence. The typos are
his and are kept.

> "re-writing the quant bot to find mathmatical strategys to edge out small margins of money from patterns found in stock markets, even small amounts. Taking Strategies from Jim Simons as well as a strategy to split the holdings of stocks by 50% everytime a new trade is made. eg: 50% 25% 12.5% etc. most of Quant bot should already be built and the UI of TradeScout still needs work in revamping. Using Trading 212's API to make those trades, and using yfinance to make the quickest trades it can. building small increments to a large sum overtime, a fast trader but automatically and mathatically precise."

> "the 50% 25% is based on confidence of the trade, we could even do a slower decline making everything more even, like 25% 20% 15%, and then exponetally carried on. if that worries you too much we can use that. there is also a limit to how many trades can happen with trading 212 per day or something, we need to find the balance in how fast and what yfinance says and what trading 212 allows."

> "I want to combine them, not just add more features"

> "lets move more towards Simon's"

> "we are still finding a strategy"

That last one is the whole posture of this plan. No strategy is chosen here.
What is chosen is the *machine for finding one honestly*, and the order the
parts get built in.

---

## What stays

None of this is rewritten. It is the part that already works, and v2 inherits it:

- **The data layer.** SQLite in WAL mode as the system of record, the RAW/CLEAN
  split (RAW = exactly what the source said; CLEAN = a validated copy, never
  re-adjusted), point-in-time reads, and quarantine-never-delete.
- **The three-layer firewall** — the honest backtester, walk-forward validation
  (fit only on the training stretch, never on the stretch you score), and the
  Monte-Carlo known-null gate (a coin-flip strategy must be REJECTED, or the
  gate is decoration). Plus `data/trials.jsonl`, the append-only tally of every
  attempt, and **Deflated Sharpe** — a score that is knocked down for how many
  things you tried, because trying 500 ideas guarantees one looks brilliant.
- **The 1% risk rule.** No single trade may risk more than 1% of the book.
- **The killswitch**, the journal, the five monitors, the installer, the
  scheduled runs, and the 3-checks before every commit.
- **Compounding, not withdrawals.** Gains stay in the book and position sizes
  scale with it — that is the operator's *"building small increments to a large
  sum overtime"*. No withdrawal policy is modelled anywhere; if he wants one,
  that is a decision to take deliberately, not a default to drift into.
- **The live v1 engine**, running untouched on its own frozen environment. Its
  forward track-record clock keeps counting. v2 replaces it only by beating it
  out-of-sample (on data neither was fitted on) at **2x costs**.

## What changes

Accepted at gist level by the operator on 2026-09-21. Eight changes:

**1 — Speed.** Decide once a day on daily bars; batch the orders near the open;
a self-imposed ceiling of roughly 10–20 trades a day. A **throttle** (code that
reads the broker's own rate-limit replies and slows down before it is refused)
means the bot is never blocked mid-run.

> **Honest correction to the brief.** The operator asked for "yfinance to make
> the quickest trades it can". yfinance is free delayed data — roughly a
> quarter-hour behind — so it cannot make anything quick. It is the **brake**,
> not the accelerator: it decides *whether* we may trade, and Trading 212
> executes. "Fast" in this plan therefore means **holding 1–10 days instead of
> months**, not trading by the second. Trading by the second needs a paid feed
> and loses to costs at this account size. If the operator wants true speed
> later, that is a separate decision with a separate budget.

**2 — Where.** Small, fast edges on **liquid London-listed ETFs priced in
pounds** (an ETF is a single tradeable basket of shares). Roughly 50–100 of
them. Pounds matter: buying a dollar line costs a currency-conversion fee every
time, and UK stamp duty does not apply to most ETFs (**UNVERIFIED** — S3 checks
both against Trading 212's own pages and records the date). US shares stay in
the plan only for slower, larger edges held for weeks.

**3 — One model, not a folder of strategies.** A library of small **signals**
(a signal is one measurable hint, e.g. "this fell hard for three days and tends
to bounce"): short-term reversal, RSI(2) dip-buying, momentum ranking behind a
regime filter, calendar effects (turn-of-month, day-of-week), post-earnings
drift on US names, a low-volatility tilt, an overnight effect (test only), and
a hidden-Markov regime detector (a model that infers which "weather" the market
is in from price behaviour alone). These are combined into **one calibrated
probability per instrument per day**. *Calibrated* means the number is honest:
when it says 60%, it is right about 60% of the time. This replaces
one-file-per-strategy. It is the operator's *"I want to combine them, not just
add more features"*, taken literally.

**4 — Machine search.** A loop that proposes candidate signals. Every candidate
is **written down before it is tested** (pre-registration), logged to
`trials.jsonl`, and put through the firewall. The loop stops on CORRECT or
EXHAUSTED, **never on profit** — a loop that stops when it finds money is a
loop that has found luck (SCARS #21).

**5 — The ladder.** The operator's halving idea, with his own softer variant as
the working choice: **25% / 20% / 15% and then tapering**, rather than
50/25/12.5. Four rules around it:
- Size is the **smaller** of the rung and the 1% risk rule. Risk wins ties.
- Trades that are really the same bet (two ETFs tracking one index) share one
  rung, so the ladder cannot be gamed by buying the same thing twice.
- Rungs stay **equal-sized until calibration is proven**. Confidence-based
  sizing is only honest once the confidence numbers are honest.
- The firewall compares **three shapes fixed in advance** — equal / slow ladder
  / straight halving — and the ladder is kept only if it beats equal *after
  costs*.

**6 — The sell side.** Trading 212 cannot short (bet on a fall). Inverse ETFs
(funds built to rise when an index falls) are **tested** as the sell side. They
decay when held, so they get a maximum hold, and they may need a broker
knowledge check. Nothing relies on them until they pass.

**7 — Execution.** Trading 212 **DEMO only** until graduation. Authentication
and rate limits get verified against the official documentation *in the box
that builds them*, citing the page and the date. Every order records expected
price versus actual price, and that gap feeds the cost model with a safety
margin on top — demo fills are kinder than real ones.

**8 — One system.** v2 lives in a new package `qb2/` in this repo, with **one
fresh pinned environment** for engine and interface together. This is the real
fix for the pandas/yfinance version conflict that currently forces two
environments; v1's environment stays frozen so its record stays trustworthy.
TradeScout's screens are rebuilt as v2's front end — one app, not a tab bolted
onto another app. The beginner rules stay: plain words on screen, the numbers
in tooltips, and every change plainly visible.

> **This amends a locked decision, and says so.** STATE.md locked "two
> environments, permanently" on 2026-09-20. That lock stands *for v1* — its
> engine and its window keep their frozen pins. v2 adds a third, fresh
> environment for itself, and when v2 replaces v1 the count goes back down to
> one. The reason the lock existed (never silently swap the libraries that
> produced a live record) is honoured, not overturned.

---

## Stages

One box each. S1 is specified in full; later stages are provisional and will be
detailed in their own box. Every stage carries three lines:

- **Exit gate:** how you know it is finished — and it must have been seen to go
  red on something broken, or it proves nothing (SCARS #9).
- **Enforcer:** the test or monitor that keeps it finished afterwards.
- **Built/Wired/Armed:** built = the code exists; wired = it is connected to the
  thing that runs it; armed = it is actually switched on. A step that is built
  but never armed is the most common way a system quietly does nothing.

### S0 — This plan, and the gate that holds it
Write the plan, pin the operator's words, and put a test around it.
- Exit gate: the plan gate runs green, having been seen red first; D1–D3 answered.
- Enforcer: `tests/plan/test_plan_v2.py`.
- Built/Wired/Armed: plan written · gate collected by the default test run · red-before-green recorded in the session log.

### S1 — `qb2/` skeleton, its environment, and the walls around it
The empty shell, done properly, so nothing later can leak between v1 and v2.
Contents: the `qb2/` package with its folder layout; `requirements-qb2.txt`
pinned and installed into a fresh `.venv-qb2`; the engine fingerprint extended
so v1 is provably frozen while v2 moves; wall tests saying v1 never imports
`qb2` and `qb2` never imports v1's engine packages; a README for `qb2/` in
plain words. No trading logic, no data, no signals.
- Exit gate: v1's fingerprint identical before and after; `qb2` imports nothing from v1 and v1 imports nothing from `qb2`; all existing suites unchanged; the new wall tests proven red on a planted violation kept in `tests/museum/`.
- Enforcer: `tools/engine_fingerprint.py` plus the new `tests/wall/` rules.
- Built/Wired/Armed: package + pins written · environment created and the suite runs in it · wall tests collected by the default run.

### S2 — Costs, fills, a read-only broker client, the throttle, the killswitch
The cost model (commission, spread, slippage, and currency conversion where it
applies), a fill recorder that stores expected versus actual price, a Trading
212 demo client that can **only read** at this stage, the rate-limit throttle,
and v2's own killswitch.
- Exit gate: costs are inside the backtest by construction and a test proves a zero-cost path cannot be taken; the read-only client cannot place an order (proven by a test that tries); the throttle backs off on a simulated rate-limit reply; the killswitch halts a dry run.
- Enforcer: wall test — no order-placing call exists outside the execution doorway; cost-model test with a hand-computed example.
- Built/Wired/Armed: model + client + throttle written · wired into the backtester and the dry-run loop · killswitch armed and fire-drilled.

### S3 — The ETF universe, the front door, and the first chart
Propose the 50–100 GBP-priced London ETFs, get a GO, then ingest them through
the existing single-writer front door, run a data census, and draw a chart.
- Exit gate: universe agreed by PROPOSE→GO; census shows ≥95% CLEAN across the active universe; every instrument asserted to be the GBP line; a chart of any one of them renders from CLEAN data.
- Enforcer: the front-door ingest checks plus a universe test asserting currency and listing for every row.
- Built/Wired/Armed: universe file written · ingest wired to the scheduler with catch-up · census meter armed in the digest.

### S4 — Firewall v2
The existing firewall, re-pointed at ETFs and given the two things a search
loop needs: a **pre-registration file** (what we are about to test, written
before the test runs) and trial logging for every candidate the search proposes.
- Exit gate: the known-null gate re-proved on ETF data — a coin-flip strategy is REJECTED and a deliberately exploitable pattern is PASSED; a test shows an unregistered candidate cannot be scored.
- Enforcer: `research/` firewall tests extended to the ETF universe; the pre-registration check.
- Built/Wired/Armed: pre-registration format written · wired so every scoring path refuses unregistered candidates · trial logging armed on the search path.

### S5 — The first signals, one at a time
Implement signals from the library, each pre-registered, each through the full
firewall, each recorded whether it passes or fails. A recorded failure is a
result, not a waste.
- Exit gate: at least one signal passes both Monte-Carlo gates and survives 2x costs; every attempt appears in `trials.jsonl`; failures are written up.
- Enforcer: the firewall itself, plus the trial-count check feeding Deflated Sharpe.
- Built/Wired/Armed: signals written · wired into the feature builder · armed only after their own firewall pass.

### S6 — The combining model, and proof that its confidence is honest
Combine the surviving signals into one calibrated probability per instrument.
- Exit gate: the combined model beats the best single signal AND beats v1 out-of-sample at 2x costs; a calibration test shows a "60% sure" call is right about 60% of the time, within stated tolerance.
- Enforcer: the calibration test and the out-of-sample comparison, both re-run on every change to the model.
- Built/Wired/Armed: model written · wired to the signal library · armed only when calibration passes.

### S7 — Sizing shapes, and the inverse-ETF question
Test the three sizing shapes fixed in advance (equal / slow ladder / halving),
and test inverse ETFs as the sell side with a maximum hold.
- Exit gate: the winning shape is chosen by out-of-sample result after costs, not by preference, and the choice is recorded with its evidence; inverse ETFs either pass with a hold cap or are dropped and recorded as dropped.
- Enforcer: a sizing test pinning the three shapes so none can be added or quietly changed later.
- Built/Wired/Armed: shapes written · wired into the sizer behind the 1% rule · armed only for the shape that won.

### S8 — The machine search loop
The loop that proposes candidates, pre-registers them, tests them and records
everything.
- Exit gate: the loop stops on CORRECT or EXHAUSTED and demonstrably not on a profitable result; a planted "jackpot" candidate does not stop it early.
- Enforcer: a loop-termination test with the jackpot fixture kept in `tests/museum/`.
- Built/Wired/Armed: loop written · wired to the firewall and the trial log · armed on a schedule with a budget ceiling.

### S9 — Demo execution, and the moment v2's clock starts
Batched orders near the open on the Trading 212 demo account, a daily
reconciliation of our paper book against the broker's own record, and a
killswitch fire-drill.
- Exit gate: paper book and broker record agree to the stated tolerance for five consecutive days; the killswitch is drilled and stops new orders; expected-versus-actual price is recorded for every fill.
- Enforcer: the daily reconciliation monitor, red-on-broken proven on a doctored copy.
- Built/Wired/Armed: client upgraded to place demo orders · wired to the scheduler · armed with the throttle and killswitch live. **v2's forward clock starts here.**

### S10 — The front end, rebuilt
TradeScout's screens rebuilt as v2's own interface: one app, plain words,
numbers in tooltips, and the bot's state visible with the age on every figure.
- Exit gate: every screen opens offscreen and closes clean; no screen can change a strategy setting; the staleness warning goes red on an old fixture and green on a fresh one.
- Enforcer: the interface smoke tests plus the read-only rule from the existing wall.
- Built/Wired/Armed: screens written · wired to v2's read path · armed as the default way the operator looks at the system.

### S11 — The forward run, the rubric, and only then real money
Run it forward on demo, then judge it against the graduation rubric.
- Exit gate: all rubric conditions met, including Deflated Sharpe ≥ 0.95 at the then-current trial count, and v2 ahead of v1 out-of-sample at 2x costs.
- Enforcer: the monthly health report and the rubric checklist in `docs/MANIFEST.md`.
- Built/Wired/Armed: forward run under way · wired to the monitors and backups · armed for live only at an irrelevant position size, and only after the rubric passes.

---

## Premortem

Imagine each of these has already gone wrong, and name the guard now.

| What goes wrong | The guard |
|---|---|
| The search finds noise and calls it an edge | Pre-registration before testing · Deflated Sharpe on the honest trial count · one untouched holdout stretch spent once |
| Costs are underestimated, so a real edge is actually a loss | Fill recorder (expected vs actual) · costs inside the backtest · 2x cost stress · a safety margin on top because demo fills are kinder |
| All the ETFs secretly track the same index, so "many edges" is one bet | Effective-N monitor (how many genuinely independent bets do we hold?) · look-alike trades share one rung |
| A dollar-priced line is picked by mistake and currency fees eat the edge | The universe file asserts the GBP line for every instrument, and a test enforces it |
| yfinance goes slow, changes, or blocks us | Local cache · exponential back-off · a second source for a quorum check · every loop catch-up-safe |
| Trading 212's beta API changes under us | The documentation check is repeated in every execution box, with the URL and the date recorded |
| Inverse ETFs decay while held and bleed money | A maximum hold, fixed in advance and enforced in code |
| A stage gets half-built and quietly skipped | The Built/Wired/Armed checklist on every stage |
| v1 gets changed by accident and its record is spoiled | The engine fingerprint is taken at the start and end of every box |
| The environments' pins leak into each other | Separate environment per system, plus the wall test that checks what is actually installed |
| We drift back to "add another strategy file" | The combining model is the design; the plan gate pins the operator's words |

---

## DECISION REQUESTED

Three decisions, with the recommended default in brackets. Answering "yes to all
three" is a complete answer.

**D1 — What is the operator's role?**
[Recommended: the bot trades automatically on the demo account; the operator
supervises, holds the killswitch, and may log his own manual paper trades in
the same journal.] The alternative is the bot proposing and the operator
confirming every trade, which is slower and makes the record a test of his
reaction time rather than of the strategy.

**D2 — Which track record counts?**
[Recommended: v2's clock starts at its first demo order in S9; v1 keeps running
untouched as the baseline until v2 beats it out-of-sample at 2x costs.] Nothing
is thrown away and no clock is restarted retrospectively.

**D3 — Which instruments exactly?**
[Recommended: decided at S3 by PROPOSE→GO, not now.] Choosing the list before
the cost model and the data census exist would be choosing blind.

---

## Sources

- Every Trading 212 figure — fees, currency conversion, stamp duty, rate limits,
  daily order limits, whether a knowledge check is needed for inverse products —
  is **UNVERIFIED** at the time of writing. None is asserted as fact in this
  plan. Each must be checked against Trading 212's own page in the box that
  depends on it, and recorded with the URL and the date it was checked.
- yfinance behaviour (delay, throttling) is treated as unreliable by design and
  handled with cache, back-off and a quorum check, rather than trusted.
- Repo facts cited here — the firewall, the 1% rule, Deflated Sharpe, the
  rubric, the two-environment lock — come from `STATE.md`,
  `docs/MANIFEST.md`, `docs/FRAMEWORK.md` and `docs/SCARS.md` as they stood at
  commit `8a81c6a` on 2026-09-21.
