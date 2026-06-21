# SCARS REGISTER — twenty-two laws from the desk

> #1–21 verbatim from §13 of the founding directive (QUANTBOT KICKSTART, 2026-06-15); #22+ earned in-session, same force.
> Read once, obey forever. Each row is a real failure and the law it produced.
> `CLAUDE.md` points here; these laws are binding on every session and every loop.

| # | War story | Law it produced |
|---|---|---|
| 1 | I audited a system whose live API token had been pasted into 197 report files | Secrets in env from day zero; .gitignore before first commit; names-only in any output |
| 2 | A pence-vs-pounds unit slip sized orders **100× too small** for weeks — and fixing it unmasked a second bug sizing 6× too big | Front-door ingest with unit checks; one writer; verify every fix with a fail-first test on the old code |
| 3 | A cross-timeframe scale mismatch was invisible to within-series checks | Per-ticker scale authority at the boundary; cross-TF consistency in the census |
| 4 | Ingest manifests logged "success" for 42 quarantined writes | Manifest truth: record what was STORED, post-write verified |
| 5 | Reverse-split tickers cycled write→purge→rewrite daily, forever | Corporate-action authority; refuse stale-scale rows up front |
| 6 | A bulk extractor died partway; 2,945 tickers were silently never staged | Reconcile counts after every bulk job; gaps page |
| 7 | The bulk zip was a snapshot; un-staged tickers never refreshed | Snapshot-vs-refresh distinction; coverage checked, never assumed |
| 8 | A data-quality meter was RED 93 consecutive days — trailing whitespace in a loader | Wallpaper rule; chronic-red audits the METER; strip/validate at source |
| 9 | A pipeline canary was red 70/70 from birth — it tested a wire that never existed | Birth-certificate law for every monitor and test |
| 10 | A process stayed "alive" 3 days while wedged; its heartbeat self-refreshed | Progress-stamps, not liveness-stamps |
| 11 | A background job was killed hourly at a default 30-min budget; looked like random failure | Explicit per-process budgets; killed-by-watchdog is loud, never silent |
| 12 | Backtest phases failed for days; the error text was never captured | Capture stderr separately; a breaker that can't say WHY is wallpaper |
| 13 | Two promotion frameworks grew in parallel; a stale whitelist starved the order flow | One promotion authority; locked lists refresh on evidence |
| 14 | Strategies judged on all-regime Sharpe culled the specialists exactly when out-of-regime | Evaluate per-regime; a chop specialist dormant in a trend is healthy |
| 15 | Backtest Sharpes of +6.9 got celebrated — later exposed as cost-model and sizing artifacts | Calibration line: real ≈ 0.7–1.2 net deflated; bigger = red flag; costs inside the backtest |
| 16 | Same-bar-close fills flattered every result | Fill at next-bar open minus slippage, always |
| 17 | A paper book assumed perfect fills | Paper = upper bound; pessimistic fills; demo fills are optimistic by construction |
| 18 | "Random historical months" testing over-sampled bull markets | Stratify replays across stress, chop, and trend episodes |
| 19 | An exit upgrade sat in a queue while winners round-tripped to losers | Ratchet + free-roll exits are core risk plumbing, not an enhancement |
| 20 | The OS clock drifted +31.6s; timestamps and bar alignment were quietly wrong | NTP sync at setup + daily task; verify with stripchart |
| 21 | A team set an optimizer to "keep searching until the backtest turned profitable" — it succeeded, shipped, and lost money live; the green was the optimizer fitting noise it was told to chase | A loop's stop-condition is *correct / exhausted*, NEVER *profitable*; optimize process, observe outcome; P&L is a thermometer, not a thermostat (§2c) |
| 22 | The RAW→CLEAN brick divided pre-split bars by the split ratio, but Yahoo/yfinance already split-adjusts OHLC (even with auto_adjust=False) — double-adjusting collapsed NVDA's pre-split bars ~10× (a fake ~907% jump) and read_price_asof served ÷10 garbage (~$4.80 not ~$48); caught by the live read-back before any strategy used it, RAW (system of record) was never wrong | CLEAN = validated COPY of RAW; never re-adjust splits — the split/corporate-actions logic is a CONTINUITY CHECK only: a ~split-ratio cliff at a split date means the source failed to pre-adjust → quarantine + raise. Dividend adjustment (via Yahoo Adj Close) is a separate later refinement |
