# PLAN v3 — two parts: a bot that trades, an advisor that suggests

Written 2026-09-26. This replaces [PLAN_V2.md](PLAN_V2.md), which is kept for
history. Only **S1 is built** (the `qb2` skeleton and its environment, commit
`22c67f7`); everything else below is planned, in order, one box at a time.

**How to read this.** Every piece of jargon is explained the first time it
appears. Every claim about Trading 212 now lives in one place —
**[docs/t212/FACTS.md](../t212/FACTS.md)** — with its source, the date it was
checked, and whether it is VERIFIED, UNVERIFIED or CONTRADICTED. Rows there were
read from Trading 212's own documentation on 2026-09-27. Nothing may be built on
an UNVERIFIED row.

**Amended twice on 2026-09-27.** First (S2a): Checking those facts changed one decision: the
broker has no trailing-stop order type and no way to amend an order, so P10's
stop is run by our own code rather than held at Trading 212. See P10. Then
(S2b): the operator reversed the bot's horizon — it now trades **same day and
holds nothing overnight** (P4, replacing "holds days"), which markets it trades
is reopened and settled by a pre-registered test (P17), and the always-on
machine gains real power safety (S13).

Two words used throughout:

- **pot** — a share of the account set aside for one part of the system. The bot
  has its own pot, the advisor has its own, and neither may spend the other's.
- **stop** — a standing instruction to sell if the price falls to a set level.
  A **trailing stop** is one that follows the price up and never moves down.

---

## Operator words

Verbatim, 2026-09-21 → 2026-09-27. Each quote sits on one long line on purpose:
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

> "the project will LATER be ported to a always on home PC, that comes at the very end of development."

> "well the stop needs to come from either Trading 212 or the algorithm."

> "the bot trades very short (same day), holds nothing when the PC is off or overnight, sells before shutdown including pre-market; add power-off detection, UPS, auto-restart and an outside watchdog to the home-PC stage (S13); test BOTH markets to the limit after costs — US shares (live yfinance prices, currency fee), London (cheap, prices 20 min late) and a mix — every attempt counted."

---

## The two parts

| | **BOT** | **ADVISOR** |
|---|---|---|
| who acts | it trades by itself | it suggests; **he** places every trade |
| holding time | **same day** — flat every night | weeks up to 12 months |
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

**P4 — The bot trades SAME DAY and holds nothing overnight.** Replaced
2026-09-27 at the operator's instruction; the old "holds days" rule is in the
superseded table. It goes flat:

- before each market's close — last sell **15 minutes** before the bell
  (*starting figure, tested first*);
- overnight, always;
- before any shutdown, sleep, restart or lid-close;
- whenever the machine might be about to be off.

If a shutdown lands during US extended hours it sells with `extendedHours=true`
(FACTS.md row j1). **No buy is ever sent into a closed market**: an order placed
while the market is shut would be queued to the next open and fill with nothing
watching it (row j2 is UNVERIFIED, which is exactly why we do not rely on
knowing), and the bot's whole safety story is that it is present for every
position it holds. Pending bot orders are cancelled at close and before
shutdown. Waking after an unplanned stop, it sells any bot holding **first**,
then writes an incident.

Which market it trades is no longer assumed — P17 settles it by test.

*Enforcer:* a **flat check** — at session end and before any shutdown, zero bot
positions and zero pending bot orders. Any bot holding found overnight is an
incident and trips `STOP_NEW_TRADES`.

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

**P10 — Every trade gets a trailing stop, and the stop is run by the
ALGORITHM.** He said: *"the stop needs to come from either Trading 212 or the
algorithm."* It comes from the algorithm, because the broker cannot do it —
Trading 212 has **no trailing-stop order type and no amend endpoint**
(FACTS.md rows d1 and d2, checked 2026-09-27), so a stop held there could never
be moved up without cancelling and re-placing it, and a cancel-and-replace that
fails halfway leaves a position with no protection at all.

So: our code holds the stop level, checks prices while it is running, and sells
by **market order** when the level is crossed. Set when the position opens; the
distance is drawn from how much that instrument normally moves, so a jumpy share
gets more room than a calm one; tightened when markets are unsettled. It is
**only ever raised, never lowered**, and every open position has one.

Two limits, stated plainly rather than glossed:

- **It only watches while the machine is awake.** On a sometimes-off laptop the
  stop is checked on waking and acted on then — a gap, not a guarantee. This is
  why real money waits for the always-on home PC (S13, S14) rather than arriving
  before it.
- **For the BOT that gap is now zero**, because P4 makes it flat whenever the
  machine may be off: a stop it does not need is a stop that cannot fail. The
  gap remains real for the ADVISOR, which holds for months, and that is the part
  S13 is protecting.
- **No stop survives an overnight gap.** If a share opens far below the level,
  the sale happens down there. That is true of broker-held stops too.

*Enforcer:* a **stop ledger** — every open position must have a stop, no stop may
ever be lowered (a test tries and must fail), the catch-up on waking is logged,
and the daily sync flags any position he opened by hand that has no stop yet.

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

**P14 — The price is checked before any automatic trade — but NOT against the
broker, because it cannot tell us.** Redesigned 2026-09-27: FACTS.md row h says
Trading 212 reports a price only for an instrument we already hold, so there is
no broker quote to compare a new buy against. Three checks instead, all
*starting figures, tested first*:

- **age** — the quote must be younger than that market's normal delay plus a
  margin. London's delay is not yet measured (row o), so until it is, the margin
  is the whole rule rather than a refinement.
- **band** — the price must sit inside a sane band around recent bars. A feed
  that hands us yesterday's price, or a decimal-point error, fails here.
- **cap** — the order is small enough that a wrong price costs at most a set
  slice of the pot. This is the check that works even when the other two are
  fooled.

After the fill, the recorder compares fill against expected; a gap beyond the
*starting figure* trips `STOP_NEW_TRADES` **for that market only**, because a
bad feed is usually one market's problem.

*Enforcer:* both the pre-trade checks and the post-fill comparison, each proven
red-on-broken before being trusted.

**P15 — The bot never holds a share through its results announcement.** Earnings
days are coin-flips with a spread, which is the opposite of a small repeatable
edge. The advisor, which holds for months, instead warns him beforehand.
*Enforcer:* an earnings-date check that blocks a bot entry into the window and
raises an advisor warning before it.

**P16 — Practice account first, real ISA later, phone alerts last.** Trading 212
demo until the graduation rubric passes; then a Stocks ISA (a UK account where
gains are not taxed) at a small size. Phone alerts are built last, exactly as he
asked. *Enforcer:* the rubric in `docs/MANIFEST.md` gates the move to real money,
and phone alerts are the final stage (S15) so they cannot be built early. The order is: prove it on paper (S12), move to the always-on home PC (S13), then the ISA at a small size (S14) — he put the home-PC port at "the very end of development", and the algorithm-held stop of P10 is the reason it comes before real money rather than after it.

**P17 — Which market the bot trades is decided by test, not by preference.**
Pre-registered here, on 2026-09-27, **before any intraday result exists** — that
is the whole point of writing it down now. Three arms:

1. **US shares** — prices live enough to act on, but a 0.15% currency fee each
   way (FACTS.md row l), so 0.30% of a round trip is gone before any edge.
2. **London** — cheap to hold, and shares carry 0.5% stamp duty on the buy
   (rows m1–m3) while ETFs and AIM shares do not, so the two are costed
   separately, never lumped together. Prices arrive late; how late is not yet
   measured (row o).
3. **A mix** of both.

Every arm runs at **1× and 2× costs**, with each market's data delay built into
the test: the bot decides on the price it would really have seen, and the fill
happens at the next available price after the order, plus slippage. The
**known-null gate must first score worthless on intraday data** — a firewall
proven on daily bars has not been proven on minutes. Every variant of every arm
goes to `trials.jsonl`, and Deflated Sharpe is computed over the whole count, not
per arm, because choosing the best of three is three lottery tickets.

The bar does not move: beat the benchmark (D3) and the best single signal, after
2× costs, on unseen data. **If no arm passes, the bot stays off and we say so.**
The tests are never loosened to let it through (SCARS #21 — a loop stops on
correct or exhausted, never on profit).

*Enforcer:* the firewall, `trials.jsonl`, and a gate test asserting three arms,
two cost levels and the delay rule.

**P18 — Minute bars are only used where minute bars exist.** Agreed by the
operator on 2026-10-03, in their own words: *"GO on P18 — 'Minute bars are only
used where minute bars exist.'"* A thinly-traded share has no bar in a minute when
nothing traded, and that is data about the market, not a hole to be filled. Every
name carries a label from the 1-minute census — MINUTE_OK or FIVE_MIN_ONLY — and
asking for minute data on a FIVE_MIN_ONLY name is refused at the data layer. The
cautious label is the default; demotion is immediate, promotion needs two
consecutive passing censuses. *This changes no gate:* the census still measures
every name in the active universe, and the label is reported beside that figure,
never inside it. *Enforcer:* the access-layer test, and a test that the census
denominator is unchanged by labelling.

**P19 — The EMAs and Keltner Channels are candidates, not instructions.** Agreed
by the operator on 2026-10-03, in their own words: *"GO on P19 — 'The program
follows the EMA 9, EMA 21 and EMA 50, as well as using Keltner Channels.'"* The
requirement itself, verbatim: *"The program follows the EMA 9, EMA 21 and EMA 50,
as well as using Keltner Channels."* They enter the system the way every other
idea does. For the **bot**, each is a candidate signal, pre-registered below and
put through the firewall one at a time; **only the ones that survive feed the
confidence score** — a signal that fails is not quietly kept because it is
popular. For the **advisor**, all four are drawn on the charts from the start,
because the operator reads them, but they may only appear in a written suggestion
once they have been tested. Built in **S4**.

*Settings, fixed on 2026-10-03 before any result exists.* Keltner's middle line is
**EMA 21**, so the channel adds no parameter of its own; its bands are **± 2.0 ×
Wilder ATR(14)**, reusing the ATR already defined in the codebase so there is one
definition rather than two that drift. Bars are **5-minute for the bot** and
**daily for the advisor**.

*Pre-registered trial list.* These are the variants S4 will test, written down
**before any result is seen**, because a trial count decided afterwards is not a
trial count. **Nine rules × two bar sizes = 18 trials.** Each rule's exit is the
mirror of its entry, fixed, not a free parameter.

| # | rule | entry |
|---|---|---|
| 1 | price × EMA 9 | close crosses the EMA 9 |
| 2 | price × EMA 21 | close crosses the EMA 21 |
| 3 | price × EMA 50 | close crosses the EMA 50 |
| 4 | EMA 9 × EMA 21 | the fast EMA crosses the medium |
| 5 | EMA 9 × EMA 50 | the fast EMA crosses the slow |
| 6 | EMA 21 × EMA 50 | the medium EMA crosses the slow |
| 7 | stacked EMAs | EMA 9 > EMA 21 > EMA 50, all three aligned |
| 8 | Keltner breakout | close crosses the upper band |
| 9 | Keltner reversion | close touches the lower band and closes back inside |

Each is run on **5-minute** and on **daily** bars: 18 trials in total, long-only.
**"Close crosses the Keltner middle" is deliberately absent — it is rule 2.** The
middle line IS the EMA 21, so counting it again would be the same test wearing a
second name and would flatter the deflated score.

*Adding anything to this list later is a NEW trial and must be logged in
`trials.jsonl` before it is run* — including a second band multiplier (1.5 or 2.5
would be four more trials across the two Keltner rules and two bar sizes), a third
bar size, or a short side. Deflated Sharpe is computed over the whole count, not
per idea, because trying enough variants guarantees one looks brilliant by luck.

*Expected to be hard, said in advance:* EMA crossings on 5-minute bars fire often,
and the bot pays 0.40% a round trip on US shares and 0.70% on UK ones (measured,
S3b), so a rule that is right slightly more often than not can still lose money on
turnover alone. If none of the 18 passes, they are not used and we say so (SCARS
#21 — a loop stops on correct or exhausted, never on profit).

*Enforcer:* the firewall's pre-registration check, a test that every indicator
feeding the confidence score has a firewall result, and a trial count in
`trials.jsonl` that includes every variant tried.

**P20 — The price is cross-checked against the broker, by holding an anchor in
every name the bot may trade.** Agreed by the operator on 2026-10-04, in their own
words: *"GO on P20 — 'Compare yfinance with Trading 212 prices: hold one share of
each bot name in the practice account so Trading 212 prices all 50, and
cross-check before every trade.'"* This reverses the limitation P14 was built
around. FACTS row h is still true — Trading 212 prices only what we **hold** — so
the answer is to hold a little of everything the bot may trade, and the broker
then prices all of it. Built in **S4**. How this is handled with real money is
decided at **S14**, not before.

*The anchor is fenced.* The bot **never sells an anchor**, they are **excluded
from the bot's results and from its pot**, and flatten (P4) leaves them alone. An
anchor is measuring equipment, not a position: counting it as performance would
mean the bot's record included 50 holdings it never chose, and letting flatten
sell it would blind the very check it exists to feed.

*Units first, because this is where it would go wrong.* Trading 212 quotes London
in pence or pounds or dollars depending on the line (FACTS row r); the clean store
is in pounds. **Both sides are converted to the instrument's own quote currency
before anything is compared.** An unconverted comparison makes every pence-quoted
London name disagree by 100x, which would halt the market every morning.

*The mismatch rule — all STARTING FIGURES, tested first.* Let `gap` be the
absolute difference between the two prices as a fraction of the broker's price:

| gap | what happens | why that number |
|---|---|---|
| over **0.25%** | recorded as a warning; the trade proceeds | yfinance runs about 1.6 minutes behind (row o, one session). A liquid name can drift this far in that time, so it is worth seeing but not worth stopping for. |
| over **max(0.5%, 1 × the name's recent 5-minute ATR ÷ price)** | **that name's trade is blocked** | 0.5% is more than a large-cap usually moves in 1.6 minutes, so a bigger gap is likelier an error than a move. The ATR term exists because on a volatile name 0.5% *is* noise — a fixed threshold would block good trades and teach us to ignore the alarm. |
| over **5%** on any one name, **or** the block threshold breached by **3 or more names in the same market in one sweep** | **STOP_NEW_TRADES for that market** | One name disagreeing is a name problem — a wrong ticker, a corporate action, a stale anchor. Several at once is a *feed* problem, and a feed problem is not something to trade through. |
| **no comparison possible** — anchor missing, broker unreachable, or the broker's own price older than its age limit | **that name's trade is blocked**, naming which and why | The check existing but not running must never read the same as the check passing. |

*The obstacle, measured on 2026-10-04 rather than discovered later.* **One whole
share of each of the 50 names costs £14,032** — more than the entire £10,000 demo
account, and far more than the bot's 30% sleeve of it. So the anchor cannot be one
whole share. Trading 212 does hold **fractional** quantities (row g: a position of
12.5711224 shares), so the anchor should be the smallest quantity the broker
accepts — roughly a pound in each name, about £50 in total, which prices all 50
just as well. **The minimum order the broker accepts is NOT on record** (no FACTS
row), so it must be established before S4 builds this.

*Enforcer:* a test that the anchor list covers every bot name, a test that flatten
and the results both exclude anchors, a units test that a pence-quoted name does
not read as a 100x mismatch, and a test that a missing comparison blocks rather
than passes.

*Addendum, 2026-10-04 — the anchors are bought by the program (QT-12).* The
operator's words, verbatim: *"write the anchor-buyer box (QT-12) — P20 anchors
bought by the program, practice only, fenced; S3 close becomes QT-13"*, and from
the session before: *"Can't the algorithm do this? this is what we a building
for"*. So:

- **An anchor is the smallest practical fractional amount — a target of about £1
  — not a whole share.** Measured: whole shares of all 50 cost £14,032, more than
  the £10,000 account.
- **Anchors are bought and topped up by the program, on the practice server
  only,** through one fenced module, `qb2/execution/anchors.py`, which is not the
  bot's sender: it can only buy, it uses its own order key, it buys only while that
  name's own market is in its regular session, and it never resends an order whose
  outcome is unknown. Its caps are the £1 target, £3 per order, £100 lifetime
  (every anchor buy and top-up together) and 50 orders a day, and a cap is never
  raised without the operator's GO. It is the only order path that exists before
  S10, and the bot cannot import it.
- **The anchor reserve sits outside BOTH pots** — neither the bot's 30% nor the
  advisor's 70% — so it changes neither pot's size nor either part's results.
- **Real-money anchors are decided at S14.** Until then the module refuses the
  live server outright, before any network call is made.
- What this does not change: the cross-check rule above is still built in S4, and
  buying an anchor arms nothing — the bot's sender stays disarmed.

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
| the bot **holds days** (V3's own first P4) | replaced 2026-09-27: same day, flat overnight (new P4) |
| v1's locked "daily horizon, short horizons rejected as cost-fatal" | **reopened by the operator.** It is not overturned by preference: P17 decides it by test, at 2× costs, with every attempt counted. If the costs win, the bot stays off and we say so |
| "GBP London ETFs only" for the bot | reopened: P17 tests US shares, London (shares and ETFs costed separately) and a mix |

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

### S2a — The facts, and a read-only doorway — **DONE 2026-09-27**
Read Trading 212's documentation and write down what it actually says
([docs/t212/FACTS.md](../t212/FACTS.md)), then build a demo client that can only
**read** — no method on it can place, amend or cancel anything — with the
per-endpoint throttle those facts describe.
- Exit gate: every fact carries a source URL, the date checked and a VERIFIED / UNVERIFIED / CONTRADICTED verdict; the client refuses any HTTP method except GET, proven by a test that plants one; the live base URL appears nowhere in qb2; the throttle backs off on a rate-limited reply without crashing; no key or auth header can reach a log. **Met.**
- Enforcer: wall tests for the live URL and for key-shaped strings; a fake server that returns 429; the GET-only refusal test.
- Built/Wired/Armed: facts written and client written · wired to the demo base URL only, keys read from `.env` · armed only as far as reading — the live smoke test is off unless keys exist.

### S2b — Costs, fills, the killswitch, and pricing without a quote
The cost model, the fill recorder (expected price against actual), qb2's
killswitch, and the pre-trade price check of P14 — which now needs designing
around a hard limit: **the API cannot price a share we do not already hold**
(FACTS.md row h). `currentPrice` exists only inside a position, so a new buy has
no broker price to check against and must lean on our own data plus a staleness
rule. This stage also gives qb2 its own fingerprint, separate from v1's, now that
it holds more than a skeleton.
- Exit gate: costs are inside the backtest by construction and a test proves a zero-cost path cannot be taken; the killswitch halts a dry run; the pre-trade check has a written, tested answer for the no-quote case; qb2's fingerprint exists and v1's still covers only v1's nine folders.
- Enforcer: a wall test that no order-placing call exists outside the execution doorway; a cost-model test against a hand-computed example; the two fingerprints, checked in every later box.
- Built/Wired/Armed: cost model, recorder and killswitch written · wired into the backtester and a dry-run loop · killswitch armed and fire-drilled.

### S3 — Both universes, and the data behind them
The bot's list (proposed, then agreed before use) and the advisor's filtered list,
with the no-overlap rule enforced. Ingest for prices plus **dividends, currency
rates and earnings dates**, because P3, P13 and P15 cannot be honest without them.

**The intraday recorder is built FIRST in this stage**, before anything else,
because intraday history is short and does not wait: FACTS.md row n measured it —
minute bars come only 8 days at a time, and 5- and 15-minute bars reach back
about 60 trading days. **Every day we do not record is a day we can never test
on.** It records both markets from the first run. This stage also captures FX
rates, and **measures the quote delay that row o could not** (the markets were
shut when it was attempted).
- Exit gate: both lists agreed; the two lists provably disjoint; at least 95% of the active universe passes the data census; every instrument asserted to be the GBP line where one exists; a chart renders from clean data. **S3 is NOT complete (QT-13, 2026-10-09).** The promise this stage made, "measures the quote delay that row o could not", is now KEPT: FACTS row o is VERIFIED for both markets (US median 1.25 min, London 16.66 min, each over 5 sessions). But the census item has gone RED since it was last checked on 2026-10-03: the clean store the census reads was last fed on 2 Oct, because nothing on the schedule runs the front door (raw to clean), so on 2026-10-09 every one of the 221 names fails as stale and the census reads 0.0% against the 95% bar. The data itself is fine: rebuilt from the raw recordings into a scratch folder, the same census passes 217 of 221 (98.2%). What remains: the front door and the 5-minute census run in the recorder's after-hours step, with a loud RED when the clean store goes stale, and one fresh census on the real store at 95% or more.
- Exit check (QT-13, 2026-10-09, each item on evidence): bot list agreed GREEN · advisor list agreed (by P6's rule) GREEN · lists disjoint GREEN · census at 95% or more RED · sterling line by ISIN GREEN · chart from clean data GREEN · quote delay measured (row o) GREEN · ingest wired to the scheduler RED · census armed in the daily digest RED
- Enforcer: the front-door ingest checks, the universe test, the census meter.
- Built/Wired/Armed: universe files written · ingest wired to the scheduler with catch-up · census armed in the daily digest.

### S4 — Firewall v2
The existing firewall pointed at the new universes, plus **pre-registration** (the
candidate written down before it is tested), the benchmark (D3), and a
**survivorship mark-down**: historic lists quietly omit companies that failed, so
an untouched backtest of "today's shares" flatters itself, and the result is
marked down for it.
- Exit gate: the known-null gate re-proved — a coin-flip strategy is REJECTED and a deliberately exploitable pattern PASSES; an unregistered candidate cannot be scored; the benchmark appears in every report; **costs inside the backtest — the cost model (qb2 S2b) applied to every simulated fill, gross AND net reported, 2× stress available**. (Carried from S2b, which built the cost model before any backtest existed to put it inside.) **AND the bot's universe is AGREED, not merely proposed: the versioned bot file says AGREED and carries the operator's own words granting it, with the date.** (Carried from S3b, which proposed a list of 50 names across three tagged sleeves and deliberately left it unagreed; S3's own gate requires both lists agreed, and a backtest run on a list nobody chose would have to be thrown away.)
- Enforcer: the firewall tests, extended to the new universes, plus the pre-registration check.
- Built/Wired/Armed: pre-registration format written · wired so every scoring path refuses unregistered candidates · trial logging armed on the search path.

### S5 — The safety layer, before anything trades
**Includes the laptop phase.** The flat-on-shutdown rules of P4 are designed here
and built at S10, and they apply from the **first demo trade**, not from the move
to the home PC: shutdown, sleep, lid-close and losing AC power all flatten the
bot, and waking always reconciles against the broker before anything else. The
laptop's own battery is its UPS, which is the one advantage it has over a desktop.

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
- Exit gate: our book and the broker's record agree to a stated tolerance for five consecutive days; every open position has a stop at the broker; expected-versus-actual price recorded for every fill; **the killswitch halts a demo dry run — STOP_NEW_TRADES set mid-run, no new buy leaves the process, and flatten-bot empties the bot's holdings while leaving the advisor's alone**. (Carried from S2b, which had no dry-run loop to halt.)
- Enforcer: the daily reconciliation monitor and the stop ledger, both proven red-on-broken on doctored copies.
- Built/Wired/Armed: client upgraded to place demo orders · wired to the scheduler · armed with throttle, brakes and killswitch live. **The forward clock starts here.**

### S11 — One app
TradeScout rebuilt as the single interface: advisor screens and bot screens
together, plain words, numbers in tooltips, an age on every figure.
- Exit gate: every screen opens offscreen and closes clean; no screen can change a strategy setting; the staleness warning goes red on an old fixture and green on a fresh one.
- Enforcer: the interface smoke tests and the existing read-only wall rules.
- Built/Wired/Armed: screens written · wired to the read path and the suggestion feed · armed as the operator's default way of looking at the system.

### S12 — The forward run, then the rubric
Run both parts forward on the demo account, then judge against the graduation
rubric. No real money at this stage.
- Exit gate: every rubric condition met, including Deflated Sharpe ≥ 0.95 at the then-current trial count, and both parts ahead of the benchmark out-of-sample at 2× costs.
- Enforcer: the monthly health report and the rubric checklist in `docs/MANIFEST.md`.
- Built/Wired/Armed: forward run under way · wired to monitors and verified backups · armed on the demo account only.

### S13 — Move to the always-on home PC
He asked for this at "the very end of development", and P10 makes it a
precondition for real money rather than a convenience: our code holds the stops,
so it can only watch prices while the machine is awake. Every check is re-proved
on the new machine — a system that passed on the laptop has not passed here.

Four additions, because an always-on machine is only as honest as what happens
when it stops being on:

- **Power-off detection.** Windows gives notice of a shutdown or sleep: take it,
  flatten the bot, record the time. A power CUT gives no notice, so the program
  writes a **heartbeat file** as it runs; a gap in that file found at restart
  means it died unwatched, which triggers a reconcile, sells anything still held,
  and writes an incident.
- **A UPS for the PC and the router**, at least **10 minutes** (*starting figure,
  tested first*). Its low-battery signal flattens the bot and shuts down cleanly,
  rather than waiting to be cut off mid-order.
- **Auto-restart.** BIOS set to power on when mains returns, and the program
  starts at boot with **no login and nobody driving the desktop**.
- **An outside watchdog.** A heartbeat to a check service that is not this
  machine; silence means an email. This is the one alert that exists before S15,
  because it is safety rather than convenience — if the machine is dead, nothing
  on the machine can tell you.

- Exit gate: the full suite green on the home PC; scheduled runs fire there; the killswitch drilled there; exactly ONE machine has the scheduled tasks registered, because two writers would corrupt the journal; and **four drills, one each: unplug the mains with the UPS carrying it · let the UPS run flat · kill the program outright · drop the network** — each ending with the bot flat, the incident recorded and the watchdog having noticed.
- Enforcer: the installer's verify command run on the new machine, a single-writer check that fails if tasks exist on two machines, the heartbeat-gap reconcile, and the external watchdog.
- Built/Wired/Armed: installed on the home PC · wired to its scheduler, its backups, the UPS signal and the outside watchdog · armed only after the laptop's tasks are decommissioned.

### S14 — The Stocks ISA, at a size that does not matter
Only after S13. Real money, smallest sensible size, everything else unchanged.
- Exit gate: the rubric still passes on the home PC's own forward record; the first real order is reconciled by hand against the broker's own record; the killswitch is drilled against the live account before the first order, not after; **and FACTS.md row c is settled** — whether stop orders can be placed on a real-money account is currently UNRESOLVED, and going live on an unresolved order-type question is exactly the kind of guess this project does not make. One tiny live test, or a written answer from Trading 212 support.
- Enforcer: the daily reconciliation monitor and the stop ledger, both already proven, now watched against real fills.
- Built/Wired/Armed: live keys held only in `.env` on the home PC · wired with the live base URL enabled for the first time · armed at a size he would not mind losing entirely.

### S15 — Phone alerts
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
| A resend creates **duplicate orders** — the order endpoints are **not idempotent** in Trading 212's own words (FACTS.md row e) | S10 reads **pending orders** before any resend, and never retries a send blindly |
| A stop goes unwatched while the laptop is asleep, because our code holds it rather than the broker | the stop is checked and acted on when the machine wakes, and that gap is logged; real money waits for the always-on home PC (S13 before S14) |
| We try to price a share we do not hold, and there is no quote to be had (FACTS.md row h) | S2b designs the pre-trade check around it: age, band and size cap (P14), never a pretend broker price |
| The bot is holding something when the PC goes off | P4: flat before close, before shutdown, before sleep — and a wake-reconcile that sells anything found still held, then records an incident |
| The power is cut with no warning | a UPS that carries PC and router, a heartbeat file whose gap is noticed at restart, and an outside watchdog that emails when the machine goes silent (S13) |
| London prices arrive late and the bot acts on a stale one | the delay is measured (row o, at S3) and built into P17's test, so a strategy that only works on prices we never had cannot pass |
| Stamp duty quietly eats a same-day UK share strategy — 0.5% on every buy | costs are per instrument, not per market: UK shares carry duty, UK ETFs and AIM shares do not (rows m1–m3), and P17 costs them separately |
| Intraday history is too thin to test honestly | the recorder starts first (S3), and the trial count feeds Deflated Sharpe so a short sample cannot flatter itself |

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

- Every Trading 212 figure and behaviour now lives in
  **[docs/t212/FACTS.md](../t212/FACTS.md)**, one row each, with its source URL,
  the date checked, and a VERIFIED / UNVERIFIED / CONTRADICTED verdict. S2a did
  the first pass on 2026-09-27. Rows still open there include whether one share
  can hold two positions (strong indirect evidence, not stated), the exact
  rate-limit headers beyond `x-ratelimit-reset`, the status code returned when a
  limit is exceeded, fees and stamp duty, and whether inverse products need a
  knowledge check. Nothing above relies on an open row. The API is in beta, so
  every row is re-checked in any box that places an order.
- yfinance is treated as unreliable by design: delayed, occasionally wrong, and
  rate-limited. It is handled with a local cache, exponential back-off and a
  second-source check, not trusted.
- Repo facts cited here — the firewall, the trial log, Deflated Sharpe, the
  graduation rubric, the 1% rule, v1's frozen baseline, the fingerprint's scope —
  come from `STATE.md`, `docs/MANIFEST.md`, `docs/FRAMEWORK.md`, `docs/SCARS.md`
  and `tests/wall/` as they stood at commit `22c67f7` on 2026-09-26.
