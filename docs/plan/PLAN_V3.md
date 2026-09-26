# PLAN v3 — two parts: a bot that trades, an advisor that suggests

Written 2026-09-26. This replaces [PLAN_V2.md](PLAN_V2.md), which is kept for
history. Only **S1 is built** (the `qb2` skeleton and its environment, commit
`22c67f7`); everything else below is planned, in order, one box at a time.

**How to read this.** Every piece of jargon is explained the first time it
appears. Any claim about Trading 212 — a fee, a limit, an order type — that is
not followed by a link and the date it was checked says **UNVERIFIED**, which
means nobody has checked it yet, so nothing may be built on it.

Two words used throughout:

- **pot** — a share of the account set aside for one part of the system. The bot
  has its own pot, the advisor has its own, and neither may spend the other's.
- **stop** — a standing instruction to sell if the price falls to a set level.
  A **trailing stop** is one that follows the price up and never moves down.

---

## Operator words

Verbatim, 2026-09-21 → 2026-09-26. Each quote sits on one long line on purpose:
re-wrapping or tidying a quote turns evidence into paraphrase. The typos are his.

> "forget the £10k, we are looking for percentages."

> "I Want to create a short term bot that tries its hardest to immitate the jim simons strategy, and a manual large trader advisor that will automatically suggest long term strategies that advise staying, falling out of a stock and suggesting new stock. nothing should be held for more than a year."

> "You can break rules if you want to in order to make this happen."

> "both, all trades available on Trading 212."

> "The Advisor should track as many holdings as i want, perhaps it can use the 50%/25%/12.5% etc method of the 70% the advisor has in total of the holding investments. reguardless it shouldnt have a limit."

> "the massive amount of money as a 30%+ investment was a bad idea, however i still believe a strong primary investment isa good idea."

> "The escape would be a moving stop that follows the trends untill theres a massive fall that triggers that moving stop. theoretically the same should be the case with every trade, advisor and bot. even the opposite for the bot, a moving buy that triggers when a stock reaches a potential big climb with confidence."

> "The goal for the bot at least, is to be able to leave it alone and profit by doing nothing while it works. the advior will generally be a guide that drives the manual investments course."

> "the bot should be a ground for improvement and constantly iterating and improving itself, it should not get less for doing a worse job, it should be more precise and evolve."

> "If the bot really does THAT badly we can talk about changing it after testing, eg: probably making the 30%/70% scalable by the user or even moving to an all advisor setup, but the dream is to have it all automated honestly."

> "A phone alert should be the last thing to do, unless you can send a message directly from the Trading 212 app on mobile."

> "im using an ISA account, but before that we are using a paper trader."

---

## The two parts

| | **BOT** | **ADVISOR** |
|---|---|---|
| who acts | it trades by itself | it suggests; **he** places every trade |
| holding time | days | weeks up to 12 months |
| what it trades | the cheapest instruments to hold and turn over | shares he actually wants to own |
| method | Simons' **method**: many small patterns, one combined model, strict costs, no human overrides | reasons in plain words for hold / exit / new buy |
| his job | watch it | decide, using it as a guide |
| pot | 30% | 70% |

**Shared by both:** one app, one journal, one data layer, one validation
firewall. Neither part gets its own private version of the truth.

**The honest limit.** We cannot copy Jim Simons. He could bet on falls
(*shorting*), borrow to amplify positions (*leverage*), and buy data and speed
that cost more than this whole account. We have none of that, and our price data
is free and roughly a quarter-hour late. So we copy his **method** — many weak,
independently tested patterns combined, with costs taken seriously and no
overriding on a hunch — and we do not copy his speed or expect his returns.

**Rules that may be broken if the evidence says so** (he said: *"You can break
rules if you want to in order to make this happen"*): the 1% risk-per-trade rule
(see D1 and D2 below) and the bot trading only ETFs. Breaking one means testing
the change, not preferring it.

**Rules that are never broken:** every idea we try gets counted, costs live
inside every backtest, a search loop stops when it is correct or out of ideas and
**never on profit**, and nothing touches real money until it has been proven on a
practice account.

---

## Decisions

Sixteen decisions. Each has a rule and an **Enforcer** — the test or check that
holds it. Numbers that have not been tested yet are labelled a *starting figure,
tested first*, because an untested number that gets believed is how a plan
quietly becomes a guess.

**P1 — The advisor only ever suggests.** It never buys or sells for him. The one
and only thing the system does automatically to holdings he bought himself is
move their stop (P10), because a stop that needs a human awake is not protection.
*Enforcer:* the journal tags every position `bot` or `advisor`, and the bot is
permitted to sell only `bot`-tagged positions; a test plants an `advisor` position
and proves the bot refuses it.

**P2 — The account splits 70% advisor / 30% bot.** The bot keeps its **30%** and
is **not shrunk** for a poor run — he was explicit that it "should not get less
for doing a worse job". After a real test period he may revisit the split (he
suggested making it user-set, or going all-advisor); the stated aim is full
automation. *Enforcer:* a pot-limit check runs before every bot order and every
advisor suggestion, and refuses anything that would spend past its own pot.

**P3 — Judged in percent, after costs, against doing nothing.** No pounds-per-day
target: *"forget the £10k, we are looking for percentages."* The benchmark is a
do-nothing global index fund (D3). Returns are measured in pounds terms including
the effect of currency moves and dividends, so a US holding that rose while the
dollar fell is not reported as a win it was not. *Enforcer:* the firewall report
and the scorecard both show all three figures — bot, advisor, benchmark — and a
test fails if any is missing.

**P4 — The bot holds days, not weeks, on the cheapest instruments.** GBP-priced
London ETFs first (an **ETF** is a single tradeable basket of shares), widened
only if the cost test says a wider list still pays. *Enforcer:* the firewall plus
the cost model at **2× costs** — double the fees and spreads we expect, so an
edge that only survives at best-case costs is rejected.

**P5 — The bot improves itself, unattended.** New candidate versions
(*challengers*) run in **shadow** — on the same prices, recording what they would
have done, risking nothing. A challenger replaces the live version only after
beating it on data neither was fitted on, after costs, over a period fixed in
advance. *Enforcer:* the challenger gate, plus `trials.jsonl` and **Deflated
Sharpe** — a score marked down for how many things were tried, because trying
enough ideas guarantees one looks brilliant by luck.

**P6 — The advisor's universe is every US and UK share available on Trading 212,
filtered for liquidity, and never overlapping the bot's list.** *Liquidity* means
enough daily trading that our own order does not move the price. The no-overlap
rule matters more than it looks: if both parts held the same share, one part's
stop would sell the other part's position. *Enforcer:* a universe test asserting
the two lists are disjoint and that every advisor instrument passes the filter.

**P7 — The advisor reviews weekly, and checks for urgent exits daily.** A weekly
rhythm for thinking, a daily one for danger. *Enforcer:* both scheduled jobs are
proven red-on-broken — deliberately broken once, watched to fail — before either
is trusted.

**P8 — Advisor sizing: as many holdings as he likes, one strong primary, caps on
concentration.** No limit on the number of holdings, as he asked. One primary
position may be up to **25%** of the advisor pot — he judged a 30%+ single
investment "a bad idea" but still wanted "a strong primary investment". The rest
are sized by confidence, with caps per sector and per theme, and rebalancing only
when weights have drifted a lot, because frequent rebalancing is a fee machine.
25% is a *starting figure, tested first*. *Enforcer:* a pre-suggestion check that
refuses any suggestion breaching the primary cap or a sector cap.

**P9 — A scorecard records every suggestion as if it had been followed.** Kept
separately from what he actually did, so the advisor is judged on its own advice
rather than on his execution of it. It also runs his three sizing ideas side by
side as shadow portfolios — halving (50/25/12.5), his gentler 25/20/15, and
confidence-based-with-a-cap — and the evidence picks the winner. *Enforcer:* the
shadow portfolios, reconciled daily against recorded suggestions.

**P10 — Every trade gets a trailing stop, and a stop is only ever raised.** Set
when the position opens; the distance is drawn from how much that instrument
normally moves, so a jumpy share gets more room than a calm one; tightened when
markets are unsettled. This is his "moving stop that follows the trends untill
theres a massive fall". Stops are held **at Trading 212**, not in our code, so
they still work with the laptop shut, and are raised once a day. Whether the API
can place and amend the stop types we need is **UNVERIFIED** until S2. A stop
cannot protect against an overnight gap — if a share opens far below the stop,
the sale happens down there. *Enforcer:* a **stop ledger** — every open position
must have a stop, no stop may ever be lowered, and the daily sync with Trading
212 attaches a stop to any position he opened by hand.

**P11 — The bot may also have moving buys.** The opposite of a trailing stop: an
order that triggers when a price climbs convincingly, which is what he described.
Candidates only, with nothing adopted unproven. *Enforcer:* the full firewall,
same as any other signal.

**P12 — Each pot has a brake, measured from its own peak.** Down **10%**: no new
buys and stops tighten. Down **15%**: the bot pauses until he says go, and the
advisor's message becomes hold off. Both are *starting figures, tested first* —
against 2008, 2020 and 2022, and against false alarms, because a brake that
triggers on ordinary dips is worse than no brake. *Enforcer:* a brake check
before every order and every suggestion.

**P13 — Nothing is held longer than 12 months.** At the limit a position is
sold, or re-justified from scratch as a brand-new buy with a fresh stop. His
rule: "nothing should be held for more than a year". *Enforcer:* an age check
that flags every position approaching the limit and blocks silent rolling-over.

**P14 — Our price is checked against Trading 212's own before any automatic
trade.** Free data is late and occasionally wrong; acting on a stale price is how
a small edge becomes a loss. *Enforcer:* a pre-trade price check that refuses the
order when the two prices disagree by more than a set tolerance.

**P15 — The bot never holds a share through its results announcement.** Earnings
days are coin-flips with a spread, which is the opposite of a small repeatable
edge. The advisor, which holds for months, instead warns him beforehand.
*Enforcer:* an earnings-date check that blocks a bot entry into the window and
raises an advisor warning before it.

**P16 — Practice account first, real ISA later, phone alerts last.** Trading 212
demo until the graduation rubric passes; then a Stocks ISA (a UK account where
gains are not taxed) at a small size. Phone alerts are built last, exactly as he
asked. *Enforcer:* the rubric in `docs/MANIFEST.md` gates the move to real money,
and phone alerts are the final stage (S13) so they cannot be built early.

---

## Carried from V2

Unchanged and inherited, not rebuilt: the data layer (RAW kept separate from
CLEAN, quarantine-never-delete, point-in-time reads); the three-layer firewall
with `trials.jsonl` and Deflated Sharpe; the killswitch; the journal; the
monitors; the installer; **v1 left running untouched as the baseline**; decisions
made once a day with orders batched near the open; the Trading 212 throttle;
yfinance treated as the brake rather than the accelerator; many signals combined
into **one calibrated probability** (*calibrated* = when it says 60%, it is right
about 60% of the time); a machine search that stops on CORRECT or EXHAUSTED;
inverse-ETF hedging as a test only; demo-only execution; the fill recorder
comparing expected price with actual; `qb2` plus its single fresh environment;
and v2's forward clock starting at its first demo order.

## Superseded in V2

| V2 said | V3 says |
|---|---|
| US shares traded by the bot for slower edges | the advisor's territory, not the bot's (P6) |
| D1, "what is the operator's role?" | settled: the advisor only ever suggests (P1) |
| stages S2–S11 | replaced by the stages below |
| one front end with a bot tab | one app with advisor screens **and** bot screens |
| "extend the fingerprint as v2 moves" | the v1 fingerprint stays scoped to v1's nine folders (pinned by a test); qb2 gets its own fingerprint once it is more than a skeleton |

---

## Stages

One box each. S1 is done; S2 onward are provisional and get their detail in their
own box. Every stage carries three lines: an **Exit gate** (how you know it is
finished, and it must have been seen to fail on something broken), an **Enforcer**
(what keeps it finished afterwards), and **Built/Wired/Armed** — built means the
code exists, wired means it is connected to whatever runs it, armed means it is
actually switched on. Built-but-never-armed is the commonest way a system quietly
does nothing.

### S0 — The plans and their gates
PLAN_V2 and this plan, each pinned by a test holding the operator's own words.
- Exit gate: both plan gates green, each having been seen red first; D1–D3 answered.
- Enforcer: `tests/plan/test_plan_v2.py` and `tests/plan/test_plan_v3.py`.
- Built/Wired/Armed: plans written · gates collected by the default test run · red-before-green recorded in the session log.

### S1 — `qb2` skeleton and its single environment — **DONE** (commit `22c67f7`)
Eight importable, empty subpackages; one fresh pinned environment holding the
engine libraries and the GUI toolkit together; the wall extended so v1 and qb2
cannot import each other.
- Exit gate: v1's fingerprint identical before and after; neither side imports the other; existing suites unchanged; new wall rules proven red on a planted violation. **Met.**
- Enforcer: `tools/engine_fingerprint.py` and `tests/wall/test_qb2_separation.py`.
- Built/Wired/Armed: package and pins written · `.venv-qb2` created and its suite runs in it (18 tests) · wall rules collected by the default run (52 tests).

### S2 — The broker doorway, read-only, and the cost of trading
A Trading 212 demo client that can only **read**; the rate-limit throttle; qb2's
killswitch; the fill recorder; the cost model; and the pre-trade price check
(P14). This stage also **verifies against Trading 212's own documentation, citing
the page and the date**: which stop-order types exist and can be amended (P10),
and whether one share can hold two separate positions — which decides how hard
the no-overlap rule in P6 has to work.
- Exit gate: the read-only client cannot place an order, proven by a test that tries; the throttle backs off on a simulated rate-limit reply; costs are inside the backtest by construction; the killswitch halts a dry run; the stop-order and one-position-per-share questions are answered with a URL and a date, not an assumption; **and qb2 has its own fingerprint, separate from v1's, now that it holds more than a skeleton**.
- Enforcer: a wall test that no order-placing call exists outside the execution doorway; a cost-model test against a hand-computed example; the two fingerprints, checked in every later box.
- Built/Wired/Armed: client, throttle, cost model and recorder written · wired into the backtester and a dry-run loop · killswitch armed and fire-drilled.

### S3 — Both universes, and the data behind them
The bot's list (proposed, then agreed before use) and the advisor's filtered list,
with the no-overlap rule enforced. Ingest for prices plus **dividends, currency
rates and earnings dates**, because P3, P13 and P15 cannot be honest without them.
- Exit gate: both lists agreed; the two lists provably disjoint; at least 95% of the active universe passes the data census; every instrument asserted to be the GBP line where one exists; a chart renders from clean data.
- Enforcer: the front-door ingest checks, the universe test, the census meter.
- Built/Wired/Armed: universe files written · ingest wired to the scheduler with catch-up · census armed in the daily digest.

### S4 — Firewall v2
The existing firewall pointed at the new universes, plus **pre-registration** (the
candidate written down before it is tested), the benchmark (D3), and a
**survivorship mark-down**: historic lists quietly omit companies that failed, so
an untouched backtest of "today's shares" flatters itself, and the result is
marked down for it.
- Exit gate: the known-null gate re-proved — a coin-flip strategy is REJECTED and a deliberately exploitable pattern PASSES; an unregistered candidate cannot be scored; the benchmark appears in every report.
- Enforcer: the firewall tests, extended to the new universes, plus the pre-registration check.
- Built/Wired/Armed: pre-registration format written · wired so every scoring path refuses unregistered candidates · trial logging armed on the search path.

### S5 — The safety layer, before anything trades
Stops (P10), brakes (P12), pot limits (P2), the age check (P13) and the earnings
check (P15) — built and tested together, ahead of any strategy, so that nothing
later gets to run without them.
- Exit gate: a stop can never be lowered, proven by a test that tries; brakes fire on replays of 2008, 2020 and 2022 and are counted against false alarms on ordinary dips; the age and earnings checks block what they should; every check proven red-on-broken.
- Enforcer: the stop ledger, the brake check, the pot-limit check, each with its own planted-violation fixture.
- Built/Wired/Armed: checks written · wired ahead of every order and suggestion path · armed with the figures S5's own tests chose.

### S6 — The bot's signals, one at a time
Small patterns, each pre-registered, each through the full firewall alone before
joining anything, plus the moving buys from P11. A recorded failure is a result.
- Exit gate: at least one signal passes both gates and survives 2× costs; every attempt appears in the trial log; failures written up rather than discarded.
- Enforcer: the firewall, plus the trial count feeding Deflated Sharpe.
- Built/Wired/Armed: signals written · wired into the feature builder · armed only after their own firewall pass.

### S7 — The bot's combined model
The surviving signals combined into one calibrated probability, with sizing (D2)
and the inverse-ETF test.
- Exit gate: the combined model beats the best single signal, beats v1, and beats the benchmark out-of-sample at 2× costs; a calibration test shows a "60% sure" call is right about 60% of the time within a stated tolerance.
- Enforcer: the calibration test and the three-way out-of-sample comparison, re-run on every change to the model.
- Built/Wired/Armed: model written · wired to the signal library · armed only when calibration passes.

### S8 — The bot evolves
The challenger mechanism of P5 and the machine search that feeds it.
- Exit gate: the loop stops on CORRECT or EXHAUSTED and demonstrably not on a profitable result — a planted "jackpot" candidate does not stop it early; a challenger cannot be promoted without beating the incumbent on unseen data.
- Enforcer: the loop-termination test with its jackpot fixture, and the challenger gate.
- Built/Wired/Armed: loop and gate written · wired to the firewall and the trial log · armed on a schedule with a spending ceiling.

### S9 — The advisor
The engine that produces hold / exit / new-buy suggestions with plain-word
reasons, and the scorecard of P9.
- Exit gate: every suggestion carries a reason a beginner can read and a stop level; the scorecard reproduces a known week by hand; the weekly and daily jobs both proven red-on-broken.
- Enforcer: the scorecard reconciliation and the two scheduled jobs.
- Built/Wired/Armed: engine and scorecard written · wired to the universes and the journal · armed on the weekly and daily schedules.

### S10 — Demo execution, and the moment the clock starts
Batched orders near the open, stops placed at Trading 212 and raised daily, daily
reconciliation against the broker's own record, and a killswitch fire-drill.
- Exit gate: our book and the broker's record agree to a stated tolerance for five consecutive days; every open position has a stop at the broker; the killswitch stops new orders under drill; expected-versus-actual price recorded for every fill.
- Enforcer: the daily reconciliation monitor and the stop ledger, both proven red-on-broken on doctored copies.
- Built/Wired/Armed: client upgraded to place demo orders · wired to the scheduler · armed with throttle, brakes and killswitch live. **The forward clock starts here.**

### S11 — One app
TradeScout rebuilt as the single interface: advisor screens and bot screens
together, plain words, numbers in tooltips, an age on every figure.
- Exit gate: every screen opens offscreen and closes clean; no screen can change a strategy setting; the staleness warning goes red on an old fixture and green on a fresh one.
- Enforcer: the interface smoke tests and the existing read-only wall rules.
- Built/Wired/Armed: screens written · wired to the read path and the suggestion feed · armed as the operator's default way of looking at the system.

### S12 — The forward run, then the rubric, then real money
Run both parts forward on the demo account, then judge against the graduation
rubric.
- Exit gate: every rubric condition met, including Deflated Sharpe ≥ 0.95 at the then-current trial count, and both parts ahead of the benchmark out-of-sample at 2× costs.
- Enforcer: the monthly health report and the rubric checklist in `docs/MANIFEST.md`.
- Built/Wired/Armed: forward run under way · wired to monitors and verified backups · armed for the ISA only at a size that does not matter yet, and only after the rubric passes.

### S13 — Phone alerts
Last, as he asked. If Trading 212's own mobile app can carry the message, that is
preferred over building anything.
- Exit gate: an alert arrives on the phone for a real event and not for noise; nothing in the alert path can place or cancel an order; a silent failure is impossible because the absence of a heartbeat is itself alerted.
- Enforcer: an alert-path test proving it is read-only, plus a heartbeat monitor.
- Built/Wired/Armed: alert path written · wired to the brake, stop and reconciliation events only · armed last, after S12.

---

## Premortem

Each of these has already gone wrong somewhere. The guard goes in first.

| What goes wrong | The guard |
|---|---|
| Both parts hold the same share, and one part's stop sells the other's position | P6's no-overlap rule, enforced by a universe test |
| The bot sells a holding he bought himself | P1's `bot`/`advisor` tags; the bot may only sell its own |
| A bug lowers a stop and quietly widens the loss | P10's stop ledger: a stop may only ever be raised |
| The API turns out not to support the stop orders we need | a daily raise-the-stop job instead, catching up when the laptop wakes, and the protection honestly labelled weaker |
| The brake is too twitchy and sells every ordinary dip | false-alarm counting in S5, on real history, before the figures are fixed |
| A challenger wins by fitting luck | unseen data, a period fixed in advance, and every attempt counted into Deflated Sharpe |
| Survivorship flatters the advisor's backtest | the S4 mark-down, and the forward scorecard treated as the real test |
| He buys something by hand and the system never sees it | the daily broker sync flags any position with no stop as RED |
| An untested number gets believed | the "starting figure, tested first" label, and S5 is where they stop being guesses |

---

## DECISION REQUESTED

Three decisions. The recommended default is in brackets; "yes to all three" is a
complete answer.

**D1 — The advisor's risk rule.** A 25% primary holding is 17.5% of the whole
account, and a stop 15% below the entry price would cost about 2.6% of the
account if it were hit — well over the 1% risk-per-trade rule the system
currently obeys. [Recommended: for the advisor, replace the 1% rule with a cap on
*how much the account can lose if the stop is hit* per holding, with the figure
chosen by S5's crash tests rather than picked now.] The bot keeps a stricter
rule; this changes the advisor only.

**D2 — How the bot sizes a position.** [Recommended: size by how much each
instrument normally moves, so a jumpy instrument gets a smaller position, tested
at S7; until that is proven, the 1% rule stays as the ceiling.]

**D3 — The benchmark to be judged against.** [Recommended: a GBP-priced global
all-world tracker available on Trading 212, chosen at S4 by proposal and
agreement.] It has to be something he could genuinely have bought instead, or
beating it means nothing.

---

## Sources

- Every Trading 212 figure and behaviour — fees, currency conversion, stamp duty,
  rate limits, daily order limits, available stop-order types, whether one share
  can hold two positions, whether inverse products need a knowledge check — is
  **UNVERIFIED** at the time of writing and is not asserted as fact anywhere
  above. Each must be checked against Trading 212's own page in the box that
  depends on it, and recorded with the URL and the date it was checked. S2 owns
  the first of those checks.
- yfinance is treated as unreliable by design: delayed, occasionally wrong, and
  rate-limited. It is handled with a local cache, exponential back-off and a
  second-source check, not trusted.
- Repo facts cited here — the firewall, the trial log, Deflated Sharpe, the
  graduation rubric, the 1% rule, v1's frozen baseline, the fingerprint's scope —
  come from `STATE.md`, `docs/MANIFEST.md`, `docs/FRAMEWORK.md`, `docs/SCARS.md`
  and `tests/wall/` as they stood at commit `22c67f7` on 2026-09-26.
