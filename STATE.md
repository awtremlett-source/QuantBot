# STATE.md — resume in seconds

Phase: v2 BUILDING (the Simons direction).  Updated: 2026-10-05.
S0, S1, S2a, S2b, S3a, S3b, S3c and S3d ARE DONE. **S3 ITSELF IS STILL NOT
COMPLETE**, and the plan says exactly why. All five exit-gate items are GREEN (both
lists agreed · disjoint by test · census 98.2% on 5m against a 95% bar · sterling
line asserted by ISIN · charts from clean data) and the stage's whole ingest list is
now in: prices (intraday + daily), dividends, GBP/USD, earnings for the bot's 50 AND
the advisor's 171. **ONE thing is left: the stage promises to "measure the quote
delay that row o could not", and row o still cannot be quoted — 1 session of the 3
required for the US, and ZERO for London.** It resolves by the recorder running;
nothing to build.
NEXT BOX: let the delay accumulate (2 more sessions), then S3 closes. NOT S4.
RENUMBERED 2026-10-04: S3 close = QT-13 (QT-12 is the P20 anchor buyer).
CARRIED FLAG FOR THE S4 BOX: GOOG/GOOGL and VUAG/VUSA each count as ONE bet when
the bot trades (same company / same index fund, two lines each; both still get an
anchor, because the broker prices each line separately).

## RECORDER WEEKEND FIX — A, B, C applied before Monday 07:00 (2026-10-05)
Operator verbatim: *"GO on A, B and C (fail-first tests, red then green), applied
and pushed before the 07:00 run. ... A: hourly limit counted in weekdays ... B: an
hourly run that skips more than half the names because of the limit reports NOT
clean. C: catch-up alarm below the 180-min kill (e.g. 150), shown firing on a
planted slow run. The delay sampler must be unchanged."*
FOUND: Fri 2 Oct 20:03 took 110 min because it was the first catch-up after the
131-name fix -- 131 names had no 1h history, 31 no 5m (full 730d/60d windows).
One-off; all names now have history except GEV. BUT counting the hourly limit in
calendar days meant EVERY Monday hourly run skipped all 225 names and still
exited clean (Fri close to Mon = 3 days > limit 2).
APPLIED: (A) hourly limit = 2 WEEKDAYS behind (request still in calendar days);
(B) an hourly run with no catch-up behind it that skips more than half the names
is NOT CLEAN; (C) TASK_KILL_MINUTES 180, CATCHUP_ALARM_MINUTES 480 -> 150.
Dry-check on today's real resume points: 07:00 fetches 225, skips BA.L only (5
weekdays behind; the same run's catch-up takes it). qb2/tools/sample_delay.py
UNCHANGED (sha256 2ae3d013...c8aa3, empty diff).
TEST LEAK FIXED: the 19 "AAPL 1m lost" manifest lines (2-5 Oct, the 19th from
this session's own baseline run) came from test_recorder.py's provider-limit
test, which had no manifest of its own. tests/qb2/conftest.py now refuses ANY
write under data/, logs/, reports/ during a qb2 test (audit hook + to_parquet).
The 19 lines stay (quarantine, never delete); they are kind=lost and move no
resume point.
FOR QT-13 (not done): (1) each append to the 13 MB manifest costs 0.37 s, almost
all in closing the file (0.002 s on a small file) -- likely an antivirus rescan,
not verified; ~45 of Friday's 110 min, and it grows with the file. (2) GEV 1h:
yfinance sends GEV's listing date (2024-03-27) as the start, which Yahoo refuses
as older than 730 days -- needs an explicit start inside the window.

## QT-12 PART A DONE — the P20 anchor buyer is BUILT and DRY-RUN, NOT live (2026-10-04)
Operator verbatim: *"write the anchor-buyer box (QT-12) — P20 anchors bought by the
program, practice only, fenced; S3 close becomes QT-13"* (+ earlier: *"Can't the
algorithm do this? this is what we a building for"*). Both in PLAN_V3 P20's dated
addendum; P20's agreed text is pinned byte-identical by hash.
BUILT: qb2/execution/anchors.py (the ONE order path: practice host hard-coded,
buy-only, own key T212_ORDER_KEY/SECRET, caps £1 target · £3/order · £100 lifetime
· 50/day, regular session only by BOTH the broker's calendar and the exchange
clock, intent-before-send, unknown outcome = UNRESOLVED + run halts + never
resent until order history settles it) · anchor_ledger.py (data/anchors/
ledger.jsonl; flatten now sells at most position − anchor) · one new GET on the
read-only client (order history, for reconciling). Fences F1–F12 each watched RED
(29 deliberate breakages, all red; session log has the table).
THE WALL WAS NARROWED, NOT REMOVED: exactly one qb2 file may name the market-order
path and POST; a planted second doorway, a limit path in the doorway, a planted
order-key reader and a planted import of the doorway each turn it red.
DRY RUN (Sun, read-only key): 45 to buy when markets open, est £45.69 vs £100 cap;
5 skipped as already held (MU, SNDK, TSLA, GEV, SGLN). UNKNOWN (FACTS u, v): the
broker's minimum order (assumed £1) and quantity precision (assumed 4 dp); which
names accept fractions is unknown until a fill. FACTS j2 now VERIFIED: an order sent
while the market is shut IS queued to the next open — the fence is necessary.
NEXT FOR QT-12: operator makes a NEW practice key (Orders – Execute + Account data
only), adds T212_ORDER_KEY/SECRET to .env, says "GO QT-12 LIVE" → Part B (prove key,
live run in the overlap, reconcile from the broker, wire the weekday top-up task).

CLOCK (2026-10-04, S3e): the delay sampler now asks an internet time server
(SNTP, UDP 123, NO admin -- it asks the time, it never sets it) on every run and
records the offset; the reported age is corrected by it, and BOTH figures are
kept (age_seconds_raw = what the laptop thought, age_seconds = what it was).
Measured offset on this machine: +0.118s to +0.136s across three servers.
An unreachable server does NOT lose the reading and does NOT silently trust it:
the sample is kept, marked unverified, and EXCLUDED from the count at which row o
may be quoted. Consequence, stated plainly: the 3,106 readings taken before
2026-10-04 have no clock check, so row o now reads UNMEASURED with 0 counted --
which is more honest than the figure it replaced.

DATA NOW IN CLEAN (2026-10-03): intraday 1m/5m/1h for 226 names · DAILY bars for
221 names + GBP/USD (3 years) · DIVIDENDS for 221 names, 0 suspect · EARNINGS for
the bot's 50 and the advisor's 171. Total return in pounds (P3) is one function,
qb2/research/total_return.py: raw Close + the dividend table + the rate on each
payment's OWN ex-date. It REFUSES Adj Close, because adding dividends to a series
that already contains them counts every payout twice.

RECORDER (fixed 2026-10-02, S3c): hourly top-up **1.6–2.6 min** measured on real
task runs, against a baseline of over an hour that never finished. Hourly tops up
1m only, in batches of 40, from each name's last bar; the slow backfill and the
5m/1h top-ups run on the day's LAST trigger (20:00), because New York is open until
21:00 so "both markets shut" never happens inside the window. One lock, so two
recorders cannot write one file. Every run writes its own log to logs/recorder/
(30 days); a log with no "run finished" line is a run that was killed.
The scheduled task now runs **pythonw.exe** with absolute paths and "Start in" set
to the repo — no console window. CONFIRMED BY PROBE: with no "Start in", Task
Scheduler starts tasks in C:\Windows\system32, which is why the old relative
recorder.log never existed anywhere.

FINGERPRINTS: v1 4add56ec…743b6 (must never move, verified 2026-10-04) ·
qb2 b7698297…8682 after the weekend fix (2ba4d210…ab12 after QT-12; was 69ae0f43…a0da after S3e; 8d007b10…c85c after S3d)

## P20 AGREED — cross-check prices against the broker (2026-10-04)
Operator verbatim: *"GO on P20 — 'Compare yfinance with Trading 212 prices: hold
one share of each bot name in the practice account so Trading 212 prices all 50,
and cross-check before every trade.'"* In PLAN_V3 word for word. This reverses what
P14 was built around: FACTS row h still says T212 prices only what we HOLD, so the
answer is to hold a little of everything. Built in S4; real money decided at S14.

Anchors are FENCED: never sold by the bot, excluded from its results and its pot,
left alone by flatten. Mismatch rule (all starting figures): warn over 0.25%, block
that name over max(0.5%, 1x its 5-minute ATR/price), STOP_NEW_TRADES for the market
over 5% on one name or 3+ names breaching at once; no comparison possible = blocked,
never treated as a pass. Units converted before comparing, or every pence-quoted
London name reads as a 100x mismatch.

**OBSTACLE, MEASURED: one WHOLE share of each of the 50 costs GBP 14,032** — more
than the entire GBP 10,000 demo account, and the bot's sleeve is 30% of that. T212
does hold fractional quantities (row g: 12.5711224 shares), so the anchor should be
the smallest quantity it accepts, about GBP 1 each, roughly GBP 50 in total. **The
broker's minimum order is NOT on record** and must be established before S4 builds
this.

## P19 AGREED — the EMAs and Keltner Channels are in the plan (2026-10-03)
Operator verbatim: *"GO on P19 — 'The program follows the EMA 9, EMA 21 and EMA 50,
as well as using Keltner Channels.'"* Added to PLAN_V3 word for word, with the
requirement itself quoted inside the decision. Settings accepted as proposed:
Keltner middle = **EMA 21** (so the channel adds no parameter of its own), bands =
**± 2.0 × Wilder ATR(14)** (reusing the ATR already in the codebase), **5-minute for
the bot, daily for the advisor**.

**THE TRIAL COUNT IS NOW FIXED AT 18** — nine rules × two bar sizes, written into
the plan before any result exists: price × each of the three EMAs (3), the three
EMA-pairs crossing (3), the stacked-EMA alignment (1), Keltner breakout (1),
Keltner reversion (1). "Close crosses the Keltner middle" is deliberately NOT on
the list, because the middle line IS the EMA 21 and counting it again would be one
test wearing two names.

Adding anything later — a second multiplier, a third bar size, a short side — is a
NEW trial, logged in `trials.jsonl` before it is run. A gate test re-derives the
count from the plan's own table, so a tenth row cannot appear while the total still
says 18 (proven: planting one turns the gate red).

Nothing is built yet. S4 builds it.

## P18 AGREED — the minute-label rule is in the plan (2026-10-03)
Operator verbatim: *"GO on P18 — 'Minute bars are only used where minute bars
exist.'"* Added to PLAN_V3 word for word, with the date and those words quoted in
the decision itself, and pinned by four gate tests (all proven red when P18 is
removed). The rule changes no gate, and the plan now says so where a future box
will read it.
PLAN: docs/plan/PLAN_V3.md (gated by tests/plan/test_plan_v3.py).
PLAN_V2 is superseded and kept for history (its gate still runs, still 32).

## Settled decisions
- Repo root: c:\Users\mtrem\TRADING. Remote: github.com/awtremlett-source/QuantBot.
  LOCAL git identity: awtremlett-source <…@users.noreply.github.com>.
- Prior work: ARCHIVED to archive/ (gitignored), building fresh.
- Demo capital: £10,000 GBP. (SUPERSEDED 2026-09-26: the £100/day anchor is
  retired — "forget the £10k, we are looking for percentages". Judged in PERCENT
  after costs against a do-nothing index fund; see PLAN_V3 P3.)
- Universe (2026-10-01, built from evidence, versioned in docs/universe/):
  RECORDED 226 = 98 US (S&P 500 over $800m/day) + 100 FTSE 100 + 23 sterling London
  ETFs (over £6m/day, one line per fund) + 4 gauges + GBPUSD. BOT 50 in three tagged
  sleeves (30 US / 10 ETF / 10 UK share) — **PROPOSED, not agreed, not tradable**.
  **BOT LIST AGREED 2026-10-02, operator verbatim: "GO on bot universe v1".**
  Agreed = may be BUILT and BACK-TESTED; the sender stays disarmed and S3's gate is
  still open. A rebuild now REFUSES to overwrite an agreed list (it would otherwise
  shut the S4 gate silently).
  ADVISOR 171, disjoint from the bot by construction and by test (P6).
  Every name resolved against T212's OWN instrument list: T212's ticker is a
  HISTORICAL id (Meta is FB_US_EQ, NatWest is RBSl_EQ — and NWG_US_EQ is the New
  York ADR, so building tickers from letters trades the wrong share). 4 old names
  were WRONG: AHT.L is no longer Ashtead, IEUR.L does not exist, IGLN.L duplicated
  SGLN.L by ISIN, RXRX is far too thin. Their data is KEPT, just not updated.
- Machine: sometimes-off laptop → loops catch-up-safe.
- Data sources (locked): Price = yfinance (daily OHLCV; ~15-min delay, fine at 4h
  cadence). Sentiment = StockGeist (free 10k credits/month). Sources decoupled;
  point-in-time. Real-time feed deferred.
- Storage (locked): SQLite(WAL) system-of-record, RAW vs CLEAN. Parquet deferred.
- Cadence/budget (locked): 4h polling floor across ~100 names (~4,200 credits/mo).
  Spare credits = emergency reserve. Severity-weighted polling: calm 4h / mild ~2h /
  severe 1h+. Guardrails: global credit ceiling + optional weekly rationing.
- Regime detector (locked): emits a 0–1 severity SCORE (not just a label). Two jobs:
  pick which strategy runs + set polling cadence. Price = ground truth; sentiment =
  feature/confirmation only, never a standalone signal.
- Strategy model (locked): shared strategy TEMPLATES + one fitted CONFIG file per
  ticker (not 100 hand-written strategies). First ticker: NVDA.
- NVDA regimes (locked): 4 states — stress / calm-uptrend / choppy / calm-downtrend —
  from RV20 vs its own 1-yr median + SMA50 slope. Thresholds are walk-forward-validated
  parameters, NOT hardcoded constants. Boundary defenses: hysteresis, minimum dwell
  time, continuous severity blending, early-and-small sizing, blunt stress rules.
- Validation (locked): walk-forward + final untouched holdout; backtests simulate live
  data delay; Deflated Sharpe (penalised by number of trials).
- S3a DONE (2026-09-30, QT-08): THE INTRADAY RECORDER IS LIVE, and it had to be
  built first because the data cannot be fetched later (FACTS row n, measured).
  qb2/ingest/recorder.py captures 1-minute bars for a PROVISIONAL 119-name
  recording list (64 US shares, 30 FTSE-100 names, 20 UK ETFs, 4 gauges,
  GBPUSD), plus a one-time 5m (~60 trading days) and 1h (~2.9 years) backfill.
  Raw only: data/raw/intraday/<interval>/<ticker>/<date>.parquet (gitignored)
  with one append-only manifest line per capture (first/last bar UTC, rows,
  currency, fetch time, file hash). S3b's front door is the only thing that may
  put it in the store. WHAT IT REFUSES TO GET WRONG: the still-forming bar is
  dropped (saving it would store a high that has not happened); a bar that comes
  back CHANGED goes to quarantine and the original stands, never overwritten; a
  100x price jump is a pence/pounds unit change, not a market move; clocks are
  converted with a real timezone database, tested across the week when the UK has
  changed and the US has not (2026-10-25 vs 2026-11-01, when the gap is 4 hours
  not 5); impossible OHLC rows are quarantined and counted; a gap it cannot fill
  is written down as LOST, never interpolated. Throttling gets a patient retry
  with backoff, then an honest LOST. Freshness meter per interval, RED after 2
  weekdays (STARTING FIGURE), with its birth certificate: proven RED on a planted
  week-old manifest. SCHEDULED: QB2-Recorder registered per-user, no admin,
  MON-FRI hourly for 14 hours from 07:00 (covers London 08:00-16:30 and US
  14:30-21:00 UK). The at-logon trigger needs admin and was NOT forced — catch-up
  makes it optional; the one command is in the session log.
  DEMO KEY SMOKE TEST RUN: connected, 10 positions, 10 distinct tickers — ONE ROW
  PER TICKER, which strongly corroborates FACTS row g without settling it (the
  decisive test needs a ticker bought twice, and the key cannot read order
  history). KEY PERMISSIONS FOUND (new FACTS row p): account/summary and
  positions GRANTED; orders, instruments and exchanges all 403. A key that cannot
  READ orders cannot place one — that is the read-only proof, obtained without
  ever probing an order endpoint. The cost: T212's instrument list is unreadable,
  so the recording list is NOT verified against what T212 offers, except the 10
  tickers the live account proved. FACTS row f9 UPGRADED: 429 is the
  rate-limit status, observed live (still undocumented). The two S2b gaps were
  CARRIED, not dropped: S4's exit gate now requires the cost model inside the
  backtest, S10's requires the killswitch to halt a demo dry run.
  FIRST REAL CAPTURE (2026-09-30/10-01): 1,686,600 bars across 12,092 parquet
  files, 101.7 MiB — 1m 117 tickers/379,281 bars · 5m 117/619,535 · 1h
  116/687,784. 13 LOST gaps (all "provider returned nothing": AAPL x6 — almost
  certainly Yahoo throttling after this session's own earlier probing — plus
  AHT.L, IEUR.L, GEV; catch-up refills them on the next run). ONE bar
  quarantined for real: AGGG.L failed the OHLC sanity check on live data, so the
  guard earned its place on day one. ZERO delay samples: both markets were shut,
  so row o is still unmeasured and the recorder will take samples automatically
  during the next weekday session. A DESIGN MISTAKE WAS FOUND AND FIXED MID-RUN:
  the 1h backfill was writing one file per trading day per ticker (~59,000 tiny
  files for 2.9 years); hourly data is now partitioned BY MONTH (~36 files per
  ticker) while 1m and 5m stay per-day, and the 1,382 day-files already written
  were MOVED ASIDE to data/raw/superseded-1h-dayfiles-2026-09-30, not deleted,
  with a manifest note saying why. qb2 fingerprint now 8f291413…b1650.
- S2b DONE (2026-09-27, QT-07) — and the BOT'S HORIZON REVERSED ON OPERATOR
  INSTRUCTION. THE PLAN CHANGE: the bot now trades SAME DAY and holds nothing
  overnight (PLAN_V3 P4 replaces "holds days"): flat before each close (last sell
  15 min before the bell, STARTING FIGURE), flat before any shutdown/sleep/
  lid-close, never a buy into a shut market (a queued buy would fill unwatched),
  pending bot orders cancelled at close, and on waking from an unplanned stop it
  SELLS FIRST then writes an incident. Consequence: the laptop-off gap for the
  BOT is now zero — a stop it never needs cannot fail. v1's locked "daily horizon,
  short horizons rejected as cost-fatal" is REOPENED, and not by preference:
  P17 (new, PRE-REGISTERED before any intraday result exists) decides it by test
  — three arms (US shares · London shares+ETFs costed separately · a mix), each
  at 1× and 2× costs, each market's data delay built in, known-null re-proved on
  intraday data first, every variant into trials.jsonl with Deflated Sharpe over
  the whole count. If no arm passes, the bot stays off and we say so. S13 gained
  real power safety (power-off detection + heartbeat-gap reconcile, a UPS for PC
  and router ≥10 min, auto-restart at boot with no login, an outside watchdog
  that emails on silence — the only alert before S15 because it is safety), with
  four drills: unplug, UPS flat, kill the program, drop the network. The same
  flat-on-shutdown rules apply from the FIRST demo trade on the laptop (S5
  designs, S10 builds). FACTS ROW 2c CORRECTED to CONFLICT/UNRESOLVED: the help
  centre says Limit/Stop/Stop-Limit DO work on live accounts, the API reference
  neither confirms nor denies (its only limitation line is about account
  currency), and the page that once restricted live to market orders now 404s —
  one source asserting and one silent is not corroboration, so an earlier
  VERIFIED read from one page alone was premature. No design impact (our
  algorithm holds every stop; the bot is same-day) and it MUST be settled before
  S14, which now says so in its exit gate. NEW FACTS j–o: market orders take
  extendedHours; US pre-market 04:00–09:30 ET and after-hours 16:00–20:00 ET
  (the UK-clock conversion is DERIVED, and the offset is 4 hours for ~2 weeks a
  year, so code must use a real timezone database); no extended hours documented
  for London; FX fee 0.15% EACH leg (0.30% a round trip); UK stamp duty 0.5% on
  share BUYS only, none on ETFs or AIM; PTM levy £1.50 over £10,000 on both
  sides; yfinance intraday depth PROBED — 1m only 8 days per request, 5m/15m
  ~60 trading days, 1h ~2.9 years; quote delay UNMEASURED because it was Sunday
  night (both markets shut) → moved to S3's exit gate, and the popular
  "20 minutes" is assumed nowhere. BUILT: per-instrument cost model (UK share vs
  UK ETF vs AIM vs US all costed differently, 2× switch doubling everything),
  append-only fill recorder (INTENT before, OUTCOME after, so a crash between
  them leaves a visible unresolved intent rather than silence), killswitch
  (blocks buys, NEVER sells; flatten sells only bot-tagged quantity and leaves
  the advisor's and the operator's alone), the P14 checks (quote age, price band,
  order-size cap, post-fill gap), and a DISARMED order sender with no code path
  in qb2 that can arm it and nothing behind the door if it were. 2g still
  UNSETTLED: demo keys are absent from .env, so the one-position-per-ticker
  question could not be answered empirically. qb2 fingerprint 49ce8ea4f35e40986a7e7951467d10b8cbf31fb45e214189f3f3b243a03dff4d.
  v1 fingerprint unchanged.
- S2a DONE (2026-09-27, QT-06): Trading 212's own documentation READ and written
  down, one row per fact with source URL, date and a VERIFIED / UNVERIFIED /
  CONTRADICTED verdict -> docs/t212/FACTS.md. FOUR FINDINGS CHANGED THE PLAN:
  (1) there is NO trailing-stop order type and NO amend endpoint (only cancel),
  so P10's stop is run by OUR CODE, not parked at the broker -- which is the half
  of "the stop needs to come from either Trading 212 or the algorithm" that
  survives contact with the docs. It watches only while the machine is awake,
  which is why real money now waits for the always-on PC (S13) before the ISA
  (S14). (2) The API CANNOT price an instrument we do not hold: currentPrice
  exists only inside a position, and there is no quotes/market-data section at
  all -- so P14's pre-trade check must be designed around it at S2b. (3) Order
  endpoints are NOT IDEMPOTENT in their own words, so any future send must read
  pending orders first. (4) The believed "live = market orders only, stop types
  demo-only" split appears NOWHERE in the docs -> recorded CONTRADICTED (not
  established, rather than disproved -- absence of a statement is not proof).
  AUTH FLAG RESOLVED: Basic auth, base64 of KEY:SECRET, header
  "Authorization: Basic <credentials>" (their quickstart, checked 2026-09-27) --
  the long-standing STATE flag is closed. BUILT: qb2/execution/t212_client.py,
  read-only by construction (no method can order; the one network function
  refuses every verb but GET; the real-money hostname appears nowhere in qb2 and
  a wall test enforces that), per-endpoint throttle from the documented limits
  that also obeys x-ratelimit-reset and backs off on 429, credentials never
  logged or repr'd, instrument list landing RAW in data/raw/t212/ and entering
  the store only through S3's front door. Wall 52 -> 62. qb2 suite 18 -> 37 + 1
  honest skip (no practice keys yet: docs/t212/SETUP.md walks the operator
  through it). v1 untouched: fingerprint 4add56ec...743b6 identical.
- DIRECTION CHANGE (2026-09-26): TWO PARTS, agreed with the operator and written
  up verbatim in docs/plan/PLAN_V3.md. A BOT that trades by itself on 30% of the
  account — automatic, holds days, cheapest instruments, Simons' METHOD (many
  small patterns, one combined calibrated model, strict costs, no overriding on a
  hunch) — and an ADVISOR on 70% that ONLY EVER SUGGESTS hold / exit / new buy
  with plain-word reasons, which he then places himself. Weeks to 12 months, and
  nothing held over a year. Judged in PERCENT after costs against a do-nothing
  global index fund: "forget the £10k, we are looking for percentages." 16
  decisions P1-P16, each with a named enforcer; 14 stages S0-S13 with phone
  alerts deliberately LAST. The bot keeps its 30% even after a poor run (his
  words: it "should not get less for doing a worse job"); revisiting the split is
  a later conversation, and the stated aim is full automation. Trailing stop on
  EVERY trade, only ever raised, held at T212 so it survives the laptop being
  off. Brakes at 10% and 15% below each pot's own peak — STARTING FIGURES, to be
  tested on 2008/2020/2022 and against false alarms before they are believed.
  The honest limit is recorded in the plan: no shorting, no borrowing, delayed
  free data, so we copy Simons' method and neither his speed nor his returns.
  THREE OPEN DECISIONS: D1 the advisor's risk rule (a 25% primary with a 15% stop
  risks ~2.6% of the account, over the 1% rule), D2 how the bot sizes, D3 which
  benchmark. Defaults recommended in the plan.
- DIRECTION CHANGE (2026-09-21): v2, the Simons direction — many thin validated
  edges combined into ONE calibrated probability per instrument, searched for by
  machine under pre-registration, sized by a ladder that must first beat equal
  sizing after costs. Operator words recorded verbatim in docs/plan/PLAN_V2.md.
  v1 (NVDA regime-switcher) KEEPS RUNNING UNTOUCHED as the baseline; v2 replaces
  it only by beating it out-of-sample at 2x costs. Its clock keeps counting.
  QT-02's forward stages (MERGE_PLAN 3b/4/5/6) are SUPERSEDED by PLAN_V2 —
  marked, not deleted. QT-02's SHIPPED work (stage 3a: the Bot tab, the two
  doorways, the wall) stands and is kept.
- TWO ENVIRONMENTS — AMENDED 2026-09-21: the 2026-09-20 lock stands FOR V1 (its
  engine keeps .venv, its window keeps .venv-ui, both frozen). v2 gets ONE fresh
  pinned environment of its own for engine + interface together — that is the
  real fix for the pandas/yfinance pin conflict — and when v2 replaces v1 the
  count returns to one. The reason for the lock (never silently swap the
  libraries that produced a live record) is honoured, not overturned.
- TWO ENVIRONMENTS (locked 2026-09-20): the engine keeps .venv, the manual
  window keeps .venv-ui, permanently. manual/ never imports an engine package;
  it reaches the bot through exactly TWO doorways -- manual/bot_readonly.py
  (read-only reads) and manual/bot_governance.py (allow-listed launches).
  Their pins conflict on purpose (pandas 3.0.2 vs 2.3.3, yfinance 1.4.1 vs
  0.2.66); requirements-ui.txt must NEVER be installed into .venv. Version
  alignment is DEFERRED to the July 2027 refit, where it can ride a full
  firewall re-run -- a library version is part of what produced the record.
- Plan-review principles (locked 2026-07-08):
  - Judge strategies on RISK-ADJUSTED terms (Sharpe, max drawdown), NOT raw total return
    (buy-and-hold NVDA is a rigged benchmark long-only cannot beat on total return).
  - Prove ONE simple ALWAYS-ON strategy through the firewall BEFORE any regime-switching;
    add regime-switching only if it beats the always-on strategy out-of-sample.
  - Sentiment = v2: collect StockGeist now to build history, but OUT of v1 buy/sell decisions.
  - Emergency-polling / intraday cadence SHELVED until/unless the system goes intraday.
  - Pull NVDA history back to ~2015 before strategy work (real stress/downtrend regimes).
  - Deflate at the SWEEP level (count all ~100 tickers as trials) OR keep a final cross-ticker
    holdout tested once.
- Simons alignment (2026-07-20): breadth of thin validated edges over depth of one
  edge; daily horizon locked (costs kill short horizons at our scale — measured);
  returns anchors stay honesty-first.
- Thematic discovery (2026-07-28): REJECTED as a trading signal — innovation/narrative
  theses can't pass the firewall (no repeatable sample; survivorship stories; the
  intuition Simons dismissed). SALVAGED as candidate-DISCOVERY only: a thematic
  watchlist generator may nominate tickers for RESEARCH into Phase-6 universe
  selection, never positions; every candidate faces the full firewall.
- Autonomy (2026-07-28): operations fully automated — scheduled runs, catch-up,
  backups, digests; HUMAN RETAINED for governance only (killswitch, promotions,
  annual refit, live graduation). Near-live / 24-7 gathering REJECTED on locked
  evidence: daily bars publish daily; short horizons are cost-fatal (measured);
  credit budget. Sentiment collection stays v2.
- DEFLATED SHARPE (rubric 2) run 2026-07-28: N=481 selection trials (477
  walk-forward grid combos across 9 records + 4 standalone backtests; excluded:
  7 monte-carlo + 40 cross-ticker records), V from matched null (ann. std 0.2504,
  null mean +0.61). Champion DSR=0.898 FAIL; Challenger DSR=0.800 FAIL; Switcher
  (LIVE) DSR=0.933 FAIL (pre-committed bar 0.95; all three reruns reproduced
  exactly first: 1.1924/1.0431/1.2734; champion grid identified as
  50/100/150/200/250). Sensitivity (non-binding): 2xV -> 0.63/0.46/0.72,
  2xN -> 0.87/0.75/0.91 — no verdict flips. GOVERNANCE (pre-committed): a
  live-switcher FAIL does not pull it from paper (paper = forward test, no
  capital at risk) but is recorded, and LIVE-MONEY graduation requires
  DSR>=0.95 at then-current N. Challenger keeps spare-part status with a
  deflation flag.
- FRAMEWORK (2026-07-28): docs/FRAMEWORK.md is canonical; work follows the
  framework. 3-checks protocol adopted (correctness · language · numbers, printed
  as a "3-checks:" line before every commit). End goal: installable app on the
  always-on PC; migration rubric-gated.

## Done
- Safety rails: git init, .gitignore (verified: .env blocked, template kept),
  .env.example, docs/SCARS.md (21 laws), session log. Clock resynced by operator.
- Scaffolding: CLAUDE.md, STATE.md, GRAND_TODO.md, README.md, EDUCATION#1,
  FOUNDING_DIRECTIVE (verbatim). First commit (314ab84) pushed.
- Phase-1 env pinned (Python 3.13).
- data_store API committed + pushed (feaa00b): SQLite(WAL) RAW/CLEAN, point-in-time reads.
- Front-door ingest + quarantine table committed + pushed (3e3bd2d): one writer,
  sanity/scale checks, quarantine.
- FIRST LIGHT: live NVDA ingest = 618 daily RAW bars, 0 quarantined. Idempotency
  verified (re-run wrote 0, skipped 618). Point-in-time read mechanism verified via
  knowable_time on RAW rows.
- RAW→CLEAN reconcile brick complete (verify-and-copy; yfinance OHLC are ALREADY
  split-adjusted, so CLEAN is a validated copy, NOT re-divided — see SCARS #22).
  Committed + pushed (2f83ee7). Live NVDA rebuild = 618 CLEAN rows; continuity check
  pass (2024-06-10 10:1 split = 0.74% boundary move); max daily move 18.72% on
  2025-04-09. read_price_asof returns 618 continuous bars ($48 era → $207 latest).
  618 old double-adjusted rows archived to quarantine (superseded_by_rebuild).
- §7 VALIDATION FIREWALL COMPLETE (3/3). Backtester (8994d7a) + walk-forward (34956c4)
  + Monte-Carlo known-null gate & append-only trial log (fd7d893). BIRTH CERTIFICATE
  PASSED 2026-07-14: coin-flip REJECTED (p=0.85), FlatStrategy rejected (p=0.19),
  exploitable-pattern strategy PASSED (p=0.005) — the firewall demonstrably fails a
  worthless strategy without rejecting everything. Verdicts are RISK-ADJUSTED (Sharpe,
  not raw return); every run_backtest/walk_forward/monte_carlo run auto-appends one
  record to data/trials.jsonl (gitignored) so Deflated Sharpe counts EVERY try.
  60 tests green; ruff + mypy --strict clean.
- NVDA history extended to 2015 (live run 2026-07-14): 2,898 CLEAN bars (2015-01-02 →
  2026-07-14), both in-window splits pass continuity (2021 4:1 = 0.90%, 2024 10:1 =
  0.74%), COVID crash bar −18.4% present, max daily move 29.81% (2016-11-11 earnings
  pop, verified real). Reconcile rebuild-style supersede confirmed working as designed:
  old 618 CLEAN rows archived to quarantine (superseded_by_rebuild now 1,236 = 618+618)
  before atomic replace; summary's rows_quarantined counts validation only.
- FIRST VALIDATED STRATEGY — NVDA always-on SMA-200 accepted as Phase 2 candidate
  (2026-07-14). Walk-forward 9 folds / 45 trials, lookback 200 chosen 7/9; stitched OOS
  (2018→2026, 2,142 bars): sharpe +1.19, max DD −48.8% (vs B&H −66.4%). Firewall:
  full-series MC p=0.003; stricter matched-window MC (null mean +0.61) p=0.007,
  99.4th pct — PASSED BOTH. Trial log = 5 records. Caveats logged: single-ticker,
  Deflated Sharpe pending, paper = upper bound.
- PAPER LOOP LIVE (2026-07-14): first decision journaled — NVDA above SMA-200, pending
  buy at next open, £10k cash. Book ≡ backtester to 1e-9 (birth certificate).
  Killswitch, catch-up, crash-resume, partial-bar exclusion all test-proven.
  (execution/: frozen config law — any change = new strategy = full firewall re-run.
  69 tests green; ruff + mypy --strict clean.)
- Partial-bar fix live (2026-07-15): 07-14 bar superseded to official (close
  211.24→211.80, vol 71M→118M), bonus 07-13 volume revision caught; old rows archived
  to quarantine (never deleted). Trailing 7-day re-fetch window on every ingest;
  rows_superseded in the summary.
- FOUND+FIXED same night: loop read CLEAN as-of its PRE-sync clock, so a rebuild
  night made it silently process nothing (bars=0) — now re-reads the clock post-sync;
  fail-first test proven red on old code, green on fix.
- FIRST FILL (2026-07-15): order #1 settled at 07-14 open — sized at raw open 208.20
  → 48.030740 shares; fill 208.3041 = open × 1.0005 (the £5 is SLIPPAGE, not
  commission; commission_pct is 0). cash −£5.00 = slippage overdraft; matches
  validated backtest physics; cash-floor sizing queued as a firewall-gated
  refinement. Equity 10,167.91 at close 211.80. 76 tests green.
- CHALLENGER 1 (2026-07-15): mean-reversion (Cutler-RSI dip-buy above SMA-200 trend,
  strategies/mean_reversion.py) through the FULL firewall — VALIDATED SPARE PART,
  NOT live. Base: stitched OOS 2018→2026 sharpe +1.04, maxDD −29.6%, exposure 31.1%,
  420 trades; both MC gates passed THINLY (full-series p=0.039, matched-window
  p=0.041 vs alpha 0.05). 2× cost stress (law #15): sharpe +0.93, gate-B p=0.025
  with the null ALSO paying 2× — SURVIVED (champion at 2×: +1.19, barely moved).
  Does NOT beat the champion (+1.04 vs +1.19); value = complementary profile
  (shallower DD −29.6% vs −48.8%, 31% exposure) → regime-switcher ingredient.
  Honest trial count now 108+/walk-forward run — Deflated Sharpe pending (rubric
  #2). 91 tests green; ruff + mypy --strict clean.
- REGIME SWITCHER ADOPTED per pre-committed rules (2026-07-16). Severity-gated
  SMA-200/mean-reversion switcher (strategies/regime_switcher.py; threshold walk-forward
  tuned over {1.2,1.5,1.8}, re-entry hysteresis 0.8 FIXED). Base: beat champion OOS
  stitched 2018→2026 sharpe +1.27 vs +1.19, matched-window MC p=0.004. 2× cost stress
  (law #15, 2026-07-16): stitched sharpe +1.1999 vs champion-at-2× +1.19 — pre-committed
  bar (> +1.19) passed by a RAZOR-THIN margin (~+0.01, and the champion figure is a
  2-dp record — honesty note, not a re-litigation); matched-window null ALSO at 2×
  (n=1000, seed=0) p=0.002, 99.9th pct, null mean +0.43; maxDD at 2× −36.9% (champion
  −48.8%); base-run repro before stressing landed exactly +1.2734. VERDICT: SURVIVED →
  ADOPTED. Live swap of the paper config = separate next brick (config law: the swap
  rides THIS firewall pass; execution/ stays frozen on SMA-200 until that brick).
  Threshold instability (1.8/1.2/1.5 across folds) recorded as a known wart for the
  annual refit. Trial log now 17 records (walk-forward repro + 2× walk-forward + 2× null).
- PAPER NOW DRIVEN BY SWITCHER (2026-07-16): deployment threshold 1.5 fit on full
  history per validated process (fit_best over {1.2,1.5,1.8} on all 2,898 CLEAN bars,
  in-sample sharpe +1.3692; 3 trials logged → trials.jsonl now 20); transition
  journaled (no-op — first live decision on the 07-15 bar: calm regime → SMA-200 →
  stay long 48.030740 shares, placed=0, equity £10,201.53); drawdown warning
  re-anchored to −36.5% (switcher stitched OOS maxDD; −36.9% at 2×; warning fires at
  the shallower line). Config law intact: swap rides the switcher's firewall pass
  (be6f007/f55b738) — no loop-mechanics or research/ changes; loop tests now pin
  their small SMA fixture explicitly, and the config has its own birth-certificate
  test (tests/execution/test_config.py). 102 tests green; ruff + mypy --strict clean.
  next_refit_due unchanged: 2027-07-14.
- JOURNAL BACKUP (2026-07-17): backup mechanism live (SQLite online-backup + verify +
  14-day retention), piggybacked on the loop — every LIVE run snapshots the journal;
  backup failure warns loudly but NEVER blocks trading (scoped catch+log, law #12
  compliant). tools/backup.py + CLI: python -m tools.backup --db data/quantbot.db
  [--dest DIR] [--retain-days N]. Verify-before-trust: snapshot must open read-only,
  pass integrity_check, match all 6 table counts vs source + trials line count; a
  failed verify deletes the artifacts and raises. Dest: arg > QUANTBOT_BACKUP_DIR >
  data/backups/ (gitignored via data/). First live run: quantbot-20260717.db verified
  (6 tables, 15,737 rows) + trials-20260717.jsonl, LOCAL-ONLY warning fired as
  designed. OPERATOR ACTION REQUIRED: set QUANTBOT_BACKUP_DIR to an off-laptop folder
  (OneDrive) — rubric condition 7 counts as MET only when backups land off-laptop.
  113 tests green; ruff + mypy --strict clean.
- Rubric 1 catch-up evidence banked 2026-07-28: real 8-bar dark-gap replay via
  scheduled task, position held, digest + backup OK.
- DEFLATION BRICK (2026-07-28): research/deflation.py (moments/PSR/expected-max-
  Sharpe/DSR + count_selection_trials policy) with fail-first tests; 127 tests
  green; ruff + mypy --strict clean. Trial log 60 -> 64 records (3 wf reruns +
  1 matched null); N 481 -> 661 for the NEXT deflation (self-reference fixed by
  snapshotting N before the reruns).
- MONITORS LIVE (rubric 6, 2026-08-06): 5 meters (freshness, drawdown, invariants,
  quarantine, backup), observe-never-act; every meter unit-proven red-on-broken +
  live proof on doctored DB copies (freshness RED, -40% drawdown RED); inline
  drawdown warning replaced by the meter. The live proof caught + fixed a
  wallpaper bug (SCARS #8): quarantine meter now excludes superseded_by_rebuild
  bookkeeping (a routine rebuild archived 2,899 rows and falsely cried RED).
  Second real catch-up banked same day: 7 dark bars replayed, 2 orders settled
  at historical opens, equity 10,249.23 at new peak. 152 tests green.
- TELEGRAM DIGEST (2026-08-07): live in code — the digest + MONITORS text pushed
  to the operator's phone after every live run; token-sanitized error paths
  (leak test proves it), non-blocking (backup's contract), 10s timeout + one
  retry + 4,000-char truncation, installer-verify integrated ('telegram'
  check). DORMANT awaiting operator: BotFather bot + .env values, then
  python -m monitors.notify --get-chat-id / --test. 177 tests green.
- MONTHLY HEALTH REPORT (2026-08-07): monitors/health.py, measure-never-refit
  (SQLite opened read-only — writes impossible by construction; writes only
  data/health/health-YYYYMM.txt + optional Telegram summary). First live report:
  18 bars (LOW-CONFIDENCE), equity 10,249.23 (+2.49%), sharpe +1.13, worst dd
  -10.59% (well inside -36.5% envelope), 0% bars stressed (ref 25.8%), 3 fills /
  1 round-trip / £14.29 slippage (0.139% of equity), SHADOW RECONCILIATION OK —
  shares+cash EXACT, 8 bars differ: 07-14 supersede-explained + 7 within the
  documented inception basis-noise ceiling (<=0.03 actual vs 0.10 limit; a real
  fill error ~£5 sits 50x above). regime_series exposed from the switcher
  (decide() delegates — can never diverge; behavior proven unchanged).
  QuantBot-Monthly task registered (day 1, 07:45); run_health.bat generated;
  uninstall now decommissions all three tasks. Trials: 64 records, N=661,
  18/428 bars banked toward switcher DSR>=0.95.
- CONTROL PANEL + STATUS/DRILL (2026-08-07): tools/gui.py (stdlib Tkinter —
  observe + governance only: loop/health/backup/status runs, red-light drill,
  killswitch arm/disarm with confirm; one subprocess at a time; Controller
  tested offline behind the Runner interface, Tk = thin shell) +
  monitors/status.py (read-only status incl. tasks/config; --drill doctors two
  DB COPIES via the backup API, real DB hash-proven untouched, every line
  "DRILL — "-prefixed, never sends Telegram). Live drill: freshness RED at 22d
  + drawdown RED at -40.00% on the copies; live status OVERALL WARN (telegram,
  backup destination, logon task — the three known operator items).
  run_gui.bat generated. 198 tests green.
- First live killswitch fire-drill 2026-08-07: armed -> detected + reported
  (journal WARNING + digest "KILLSWITCH" flag), placed=0 — and it was a real
  armed decision day (bars=1, the 08-06 bar processed under the armed state);
  disarmed -> normal digest, no flag. Monthly drill cadence begins (GUI:
  Arm -> run -> Disarm).
- TRADESCOUT MERGED IN, ENGINE UNTOUCHED (2026-09-20, merge stages 0-2 of 6).
  The manual paper-trading app now lives at manual/ (copied, never moved, from
  Documents/TradeScout @ 29e8e74 "50% money ladder + friendlier GUI"; that repo
  and its GitHub remote are untouched, both tagged pre-merge-2026-09-18). Its
  131 tests run from tests/manual/; its database/cache live in data/manual/
  (gitignored); launcher = tools_ui/TradeScout.bat (NOT tools/, which is engine
  territory). THE WALL (tests/wall/, 18 tests, each with a planted-violation
  birth certificate in tests/museum/wall_violations/ and demonstrated RED on a
  sandbox copy before green): the engine never imports manual/PySide6/tools_ui
  (ast scan, dynamic imports included); manual/ may READ the engine's books
  ONLY through manual/bot_readonly.py (SQLite mode=ro URI - SQLite itself
  raises "attempt to write a readonly database", proven against the live DB
  with its hash unchanged); the engine's requirements + one-command installer
  stay headless; the banned legacy-project tokens appear nowhere in the merged
  trees. ENGINE PROVEN UNMOVED: tools/engine_fingerprint.py (new - the ONLY
  file added to an engine folder) hashes 52 files (48 engine + 4 config) ->
  25c9ec06bb13167f7cb8fde7e054251ad8243a4c9bfe84a9a1b75babbd2477ee, IDENTICAL
  before and after; engine suite still 198 green (216 with the wall). TWO
  ENVIRONMENTS ON PURPOSE: requirements-ui.txt pins CONFLICT with the engine's
  (pandas 2.3.3 vs 3.0.2, yfinance 0.2.66 vs 1.4.1) and must never be installed
  into .venv; inside .venv the manual suite is deliberately not collected and
  says so. Journal + trials backed up off-repo first and verified (10 files,
  82,320,834 bytes, every SHA-256 matching). Plan + the two-books rule:
  docs/merge/MERGE_PLAN.md (stages 3-6 are PROPOSALS only, nothing agreed).
- BOT TAB + HOUSEKEEPING (2026-09-20, merge stage 3a). The window now has a
  7th tab showing the engine in plain words, every figure carrying its age:
  last bar processed, up-to-date or not, equity, open position, forward-record
  days, trial count, last run-log entry, last digest line. Header turns RED
  when a completed trading day has gone unprocessed -- birth certificate both
  ways (old fixture RED, fresh fixture GREEN, proven through the real widget).
  On first open it reads RED and true: newest bar 2026-08-06, 31 completed
  trading days unprocessed (laptop off; the loop is catch-up-safe).
  GOVERNANCE: manual/bot_governance.py is the ONLY way the window launches
  anything -- a fixed allow-list of exactly the Tkinter panel's 6 commands
  (status/drill/loop/health/backup + telegram test) plus the killswitch FILE,
  run with the ENGINE's interpreter from the repo root, fixed argv, never
  shell=True, one at a time, every press appended to
  data/manual/governance_log.jsonl. A wall test PARSES tools/gui.py and
  bot_governance.py and fails if the two command sets ever differ. The loop
  button gained a confirmation the Tkinter panel does not have; closing the
  window during a command is BLOCKED rather than orphaning the process.
  READS: short-lived, mode=ro, 2s lock timeout -- proven not to fail or block
  a concurrent writer. HOUSEKEEPING: .venv-ui built from requirements-ui.txt
  and the launcher pointed at it (no more silent fallback to a global Python);
  old Documents/TradeScout launcher now prints where the app went and exits
  (local commit 60b7142, unpushed) so two live copies cannot both start; 16
  ruff findings fixed -- one was a REAL latent crash (NameError on `cfg` in
  _refresh_done, so the live-quote timer never started after a data refresh;
  fail-first test shipped with the fix). ENGINE UNTOUCHED: fingerprint proves
  all 48 engine code files byte-identical; pyproject.toml is the ONLY changed
  file, and only inside [tool.mypy] (the one permitted edit) -- now
  25c9ec06...2477ee -> 4add56ec...743b6. Tests: engine 198 unchanged, wall
  18 -> 44, manual 131 -> 147. ruff + mypy --strict both green repo-wide, with
  52 inherited type errors recorded in docs/merge/TYPING_DEBT.md.
  STOPPED: the old trade journal was NOT migrated -- its trades.shares is
  INTEGER where the code declares REAL (TradeScout 4e15cf4; CREATE TABLE IF
  NOT EXISTS never altered it). Verified backup taken; the rebuild needs
  PROPOSE->GO (MERGE_PLAN stage 3b).

- S1 DONE (2026-09-26, QT-04): qb2/ exists as a SKELETON — importable and empty
  of logic (data, research, signals, model, sizing, execution, ui, tools; no
  signals, no model, no orders). ONE fresh environment: requirements-qb2.txt ->
  .venv-qb2, all 13 pins resolving exactly (pandas 3.0.2 + yfinance 1.4.1 +
  PySide6 6.11.1 together — the single-environment claim in PLAN_V2 §8 is now
  proven, not asserted), 43 transitive versions recorded in
  docs/plan/ENV_QB2.md. WHAT qb2 INHERITS FROM QT-02 (nothing rebuilt that
  already works): the one-way wall and its museum of planted violations; the two
  doorways to v1's books — manual/bot_readonly.py (short-lived, mode=ro, lock
  timeout) and manual/bot_governance.py (fixed allow-list, engine interpreter,
  repo-root cwd, one at a time, every press logged); the journal, the five
  monitors and the data-layer laws; the Bot tab's habit of putting an age on
  every figure. WALL EXTENDED 44 -> 52: qb2 may not import a v1 engine package
  (relative imports inside qb2 are fine; a bare `from research import ...` would
  resolve to V1's research, which is exactly the hazard), v1 may not import qb2,
  the v1 fingerprint must not cover qb2, the three environments hold no leakage,
  and the banned-name scan now covers qb2/ tests/qb2/ docs/plan/ tests/plan/.
  THE CLOCK BUG IS FIXED: the status fixture builds on UTC like run_drill does,
  SCAR #24 written, and tests/museum/test_drill_utc_local_skew.py recreates the
  BST hour on demand — re-proved red against HEAD's own fixture, then green.
  Engine 198/0 failed. v1 UNTOUCHED: fingerprint 4add56ec...743b6 identical, and
  v1's .venv pip-freeze identical (54 packages, d0e9dd31...) with no UI package
  leaked. CLAUDE.md trimmed 3957 -> 3540 chars with all 12 law lines
  byte-identical.

## Known gap / next
- §7 VALIDATION FIREWALL: DONE (all 3 parts; birth certificate passed — see Done).
  Deferred hardening for later: purged/embargoed CPCV; sweep-level deflation + cross-ticker
  holdout before the ~100-ticker universe (GRAND_TODO "FIREWALL DESIGN follow-ups").
- NEXT ACTIONS: (a) daily MORNING loop (python -m execution.paper_loop --db
  data/quantbot.db — processes yesterday's bar; a bar counts finished once its date
  is fully past UTC, so 07-15's bar is readable after 1am UK; loop now trades the
  SWITCHER config). (b) Strategy deepening per docs/MANIFEST.md graduation rubric
  (condition 4 closed by the switcher adoption + live swap). NO export / NO ticker
  #2 until the rubric passes (all 7 conditions).

## Open flags
- FLAKY TEST — FIXED 2026-09-26 (QT-04). Kept here for the story; the scar is
  #24 and the guard is tests/museum/test_drill_utc_local_skew.py. As found:
  tests/monitors/test_status.py::test_drill_fires_both_meters_and_leaves_no_trace
  fails between 00:00 and 01:00 UK summer time. Its fixture builds bars with
  date.today() (LOCAL) while run_drill defaults to UTC; during the hour when BST
  runs a day ahead, the drill's doctored equity mark sorts BEFORE the fixture's
  healthy one, so the drawdown light cannot fire and the drill reports FAILED.
  A FIXTURE bug, not a broken monitor — the live drill is unaffected (its newest
  real mark is far older than any UTC-today insert). Fix = build the fixture on
  the UTC date. Engine suite therefore reads 197 passed / 1 failed in that hour.
- QUANTBOT_BACKUP_DIR not yet set → backups are LOCAL-ONLY (data/backups/ on the
  same laptop). Rubric condition 7 NOT met until the operator points it at an
  off-laptop folder (e.g. OneDrive).
- T212 auth scheme: RESOLVED 2026-09-27 (QT-06) -- HTTP Basic, base64 of
  KEY:SECRET, per their quickstart; see docs/t212/FACTS.md row a. NOTE:
  .env.example still carries the old "to verify" note. It is inside the
  engine fingerprint, so QT-06 could not touch it; correcting that one
  comment needs a box allowed to change engine config.
- Daily auto clock-sync task still to set up (admin).
- gh CLI not installed → use plain git for GitHub ops.
- Manual app's EXISTING trade journal STILL NOT migrated (stage 3a stopped on
  purpose): trades.shares is INTEGER in the operator's database, REAL in the
  code. Backup verified at QuantBot-premerge-backup-2026-09-20/tradescout-cache.
  Needs a one-table rebuild under PROPOSE→GO (MERGE_PLAN stage 3b).
- Bot is 31 completed trading days behind (newest bar 2026-08-06) — the laptop
  has been off; the loop is catch-up-safe, so one run should clear it. The Bot
  tab reads RED until then, correctly.
- TWO faces of governance until stage 4: tools/gui.py (Tkinter) and the Bot
  tab can both arm the killswitch. Deliberate for one stage — the panel is the
  reference the tab is tested against — but it must not stay that way.
- Typing debt: 52 mypy errors in 5 inherited modules silenced with counts in
  docs/merge/TYPING_DEBT.md; new errors in those 5 files are silenced too.
- Pre-existing Qt fault: the manual suite prints 2 "Windows fatal exception:
  access violation" lines from a worker thread and still passes. Confirmed
  pre-existing (the untouched original repo does the same). Not diagnosed.
- v1 QuantBot-Daily not run since 28 Jul; Windows refuses start (0x800710E0);
  revive-or-retire decision deferred. (Operator words, recorded 2026-10-05.
  Task Scheduler still shows it Ready with next run 05/10 07:30; last attempt
  04/10 18:37 returned 0x800710E0. No change made.)
