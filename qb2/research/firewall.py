"""Firewall v2: score one pre-registered candidate across a universe (S4).

The one scoring path a candidate goes through, in order:

1. the registered token (preregister) -- an unregistered candidate stops here;
2. each name's UNSEALED bars (holdout), costed as that instrument (costs.py), its
   money in POUNDS (pounds.py, P3); on intraday bars P15's entry mask (p15.py);
3. walk-forward per name, with delay rule (c), P4 and every fill costed;
4. the names combined equal-weight per BET (bet_groups) -- gross, net, marked down;
5. Gate 1: the turnover-matched null (matched_null.py, QT-16 A1) decides p < 0.05,
   AND the net mean per bar must be positive (QT-17 A2); the coin-flip null runs the
   IDENTICAL pipeline, as a description and the Deflated Sharpe's variance input;
6. the Deflated Sharpe over qb2's whole trial count (drills excluded);
7. the benchmark (D3) through the door, same dates and bar size; the verdict; ONE
   trial-log line. Brakes (P12) are a live layer and NOT applied here (QT-17 A3):
   the report gives the maximum drawdown instead.

A held dollar bar with no GBPUSD rate (candidate or null) = INSUFFICIENT. QT-15:
``n_trials`` floors the Deflated Sharpe's N at the batch's FULL count; ``final`` is
the one holdout pass (sealed bars graded, unsealed bars only warm indicators up).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qb2.data import access, universe
from qb2.execution import costs
from qb2.research import (backtest, bet_groups, benchmark, deflation, fills, holdout,
                          matched_null, monte_carlo, p15, pounds, preregister, stats,
                          trial_log, verdict, walk_forward)
from qb2.research.strategy import Strategy

Transform = Callable[[pd.DataFrame, costs.Instrument, str], pd.DataFrame]


@dataclass(frozen=True, slots=True)
class NameData:
    symbol: str
    market: str
    instrument: costs.Instrument
    bars: pd.DataFrame
    plan: fills.Schedule
    bet: int                                  # index of its bet group
    fx: pounds.Rates | None = None            # GBPUSD on these bars (dollar lines only)
    income: np.ndarray | None = None          # QT-19: payout / previous close (P3)
    weight: pd.Series | None = None           # QT-19: its share of the pot per bar (slots)


def instrument_of(entry: Mapping[str, Any]) -> costs.Instrument:
    return costs.Instrument(str(entry["t212_ticker"]), str(entry["quote_currency"]),
                            universe.market_of(entry), str(entry["kind"]),
                            bool(entry.get("aim", False)))


def load(interval: str, *, entries: Sequence[Mapping[str, Any]] | None = None,
         transform: Transform | None = None, clean_root: Path | None = None,
         ) -> tuple[list[NameData], list[str]]:
    """Every agreed name's unsealed bars, or the reason it was left out."""
    rows = list(entries if entries is not None else universe.bot_entries())
    groups = bet_groups.load()
    bets = sorted({bet_groups.group_of(str(e["yfinance"]), groups) for e in rows})
    rates = pounds.load_fx(interval, clean_root)
    out, skipped = [], []
    for entry in rows:
        symbol, market, instrument = str(entry["yfinance"]), universe.market_of(entry),             instrument_of(entry)
        try:
            dollars = pounds.needs_rate(instrument.currency)
            bars = holdout.research_bars(symbol, interval, market, clean_root=clean_root)
        except (pounds.NoRate, access.AccessRefused) as why:
            skipped.append(f"{symbol}: {why}")
            continue
        if transform is not None and len(bars) >= 2:
            bars = transform(bars, instrument, market)
        if len(bars) < 2:
            skipped.append(f"{symbol}: no unsealed {interval} bars")
            continue
        out.append(NameData(symbol, market, instrument, bars,     # P15 mask on intraday
                            p15.schedule(symbol, instrument.kind, bars.index, interval,
                                         market, clean_root),
                            bets.index(bet_groups.group_of(symbol, groups)),
                            pounds.align(bars.index, rates, interval) if dollars else None))
    return out, skipped


@dataclass(frozen=True, slots=True)
class Portfolio:
    gross: pd.Series
    net: pd.Series
    marked: pd.Series
    trades: int
    parts: dict[str, pd.DataFrame] = field(default_factory=dict)
    graded: dict[str, matched_null.Graded] = field(default_factory=dict)

    def count(self, column: str) -> int:       # held bars flagged fx_gap / fx_stale
        return int(sum(int(f[column].sum()) for f in self.parts.values() if column in f))


def combined(parts: Mapping[str, pd.DataFrame], graded: Mapping[str, matched_null.Graded]
             | None = None, weights: Mapping[str, pd.Series] | None = None) -> Portfolio:
    combine = {col: bet_groups.combine({s: f[col].astype(float) for s, f in parts.items()},
                                       None, weights) for col in ("gross", "net", "marked")}
    trades = int(sum(int(f["entries"].sum()) for f in parts.values()))
    return Portfolio(combine["gross"], combine["net"], combine["marked"], trades,
                     dict(parts), dict(graded or {}))


def _graded(token: preregister.Registered, strategy: Strategy, name: NameData, interval: str,
            stress: float, final: holdout.HoldoutPass | None) -> matched_null.Graded | None:
    """One full run and its graded bars: the walk-forward TEST windows (contiguous and
    fixed parameters, so one slice = the folds stitched), or the sealed bars."""
    full = backtest.run(token, strategy, name.bars, instrument=name.instrument,
                        interval=interval, market=name.market, stress=stress,
                        final=final, plan=name.plan, fx=name.fx, income=name.income,
                        log_path=None)
    if final is not None:
        days = holdout.local_index(name.bars.index, name.market).date
        first = int((days < holdout.SEALED_FROM[interval]).sum())      # bars are in order
        return matched_null.Graded(full, first, len(name.bars))
    windows = walk_forward.folds(len(name.bars), *walk_forward.default_sizes(interval, name.market))
    return (matched_null.Graded(full, windows[0].test_lo, windows[-1].test_hi)
            if windows else None)


def portfolio(token: preregister.Registered, make: Callable[[NameData], Strategy],
              data: Sequence[NameData], interval: str, stress: float,
              final: holdout.HoldoutPass | None = None) -> Portfolio:
    parts, graded = {}, {}
    for name in data:
        g = _graded(token, make(name), name, interval, stress, final)
        if g is not None and g.hi > g.lo:
            graded[name.symbol] = g
            parts[name.symbol] = backtest.frame(g.full, g.lo, g.hi)
    return combined(parts, graded, _weights(data))


def _weights(data: Sequence[NameData]) -> dict[str, pd.Series] | None:     # QT-19 slots
    return {d.symbol: d.weight for d in data if d.weight is not None} or None


@dataclass(slots=True)
class FirewallResult:
    candidate_id: str
    register_commit: str
    interval: str
    stress: float
    names: int
    effective_n: int
    skipped: list[str]
    start: date | None
    end: date | None
    observed: Portfolio
    observed_1x: Portfolio | None
    p_value: float | None
    null_mean: float | None
    null_std: float | None
    deflated: dict[str, float] = field(default_factory=dict)
    benchmark: benchmark.Benchmark | None = None
    verdict: verdict.Verdict = field(default_factory=lambda: verdict.Verdict(verdict.FAIL))
    coin: tuple[float, float, float] | None = None    # coin-flip null p, mean, std (described)


def _coin(seed: int) -> Callable[[NameData], Strategy]:
    """One coin per BET: both lines of one bet flip together."""
    return lambda name: monte_carlo.RandomStrategy(
        0.5, int(np.random.SeedSequence([seed, name.bet]).generate_state(1)[0]))


def _draw(p: Portfolio, interval: str) -> tuple[float, int]:
    """A null draw kept as two numbers, not 50 frames: Sharpe per bar, FX gaps."""
    return stats.compute(p.marked, interval, "US").sharpe_per_bar, p.count("fx_gap")


def _matched(seen: Portfolio, data: Sequence[NameData], interval: str,
             seeds: Sequence[int]) -> list[tuple[float, int]]:
    """The luck test's draws: each name's own trades re-placed (matched_null.py)."""
    plans = {d.symbol: d.plan for d in data}
    ready = {s: matched_null.prepare(g.full.held, plans[s], g.lo, g.hi) for s, g in seen.graded.items()}
    bets = {d.symbol: d.bet for d in data}
    return [_draw(combined(matched_null.frames(seen.graded, ready, bets, s), None,
                           _weights(data)), interval) for s in seeds]


def score(token: preregister.Registered, make: Callable[[NameData], Strategy],
          data: Sequence[NameData], *, interval: str, stress: float = 1.0,
          skipped: Sequence[str] = (), n_null: int = monte_carlo.DEFAULT_TRIALS, seed: int = 0,
          bench: Callable[[date, date], benchmark.Benchmark] | None = None,
          log_path: Path | None = trial_log.DEFAULT_TRIAL_LOG, n_trials: int = 0,
          final: holdout.HoldoutPass | None = None) -> FirewallResult:
    registered = preregister.check(token)
    seen = portfolio(registered, make, data, interval, stress, final)
    flat = seen.marked.to_numpy(dtype=float)
    when = pd.DatetimeIndex(seen.marked.index).tz_convert("Europe/London")
    start, end = (when.min().date(), when.max().date()) if len(when) else (None, None)
    market = "US"                             # annualising basis for display only
    result = FirewallResult(
        registered.id, registered.commit, interval, stress, len(data),
        bet_groups.effective_n([d.symbol for d in data]), list(skipped), start, end, seen,
        portfolio(registered, make, data, interval, 1.0, final) if stress != 1.0 else None,
        None, None, None)
    if start and end:                         # D3 through the door, same bar size
        result.benchmark = bench(start, end) if bench else benchmark.over(
            start, end, interval=interval, final=final)
    gaps = [f"{seen.count('fx_gap')} held bar(s) of a dollar line have no GBPUSD rate, "
            "so there is no pound figure (P3)"] if seen.count("fx_gap") else []
    if not gaps and seen.trades >= verdict.MIN_OOS_TRADES and len(flat) >= verdict.MIN_OOS_BARS:
        seeds = monte_carlo.trial_seeds(seed, n_null)
        coin = [_draw(portfolio(registered, _coin(s), data, interval, stress, final), interval) for s in seeds]
        matched = _matched(seen, data, interval, seeds)
        if any(g for _, g in coin + matched):
            gaps.append("a luck-test path held a dollar line on a bar with no GBPUSD rate")
        coins, nulls = [c for c, _ in coin], [m for m, _ in matched]
        observed = stats.compute(flat, interval, market).sharpe_per_bar
        result.p_value = monte_carlo.p_value(observed, nulls)          # the luck test
        result.null_mean, result.null_std = float(np.mean(nulls)), float(np.std(nulls))
        result.coin = (monte_carlo.p_value(observed, coins), float(np.mean(coins)), float(np.std(coins)))
        counted, _ = trial_log.count_selection_trials(log_path)
        n_full = max(2, counted + (0 if registered.is_drill else 1), n_trials)
        try:
            result.deflated = deflation.deflated_sharpe(flat, n_full, float(np.var(coins)))
        except ValueError:
            result.deflated = {}              # judged INSUFFICIENT below, never PASS
    result.verdict = verdict.judge(
        oos_trades=seen.trades, oos_bars=len(flat), p_value=result.p_value,
        mean_per_bar=float(flat.mean()) if len(flat) else None,      # QT-17 A2
        dsr=result.deflated.get("dsr"), gaps=gaps,
        strategy_return=stats.compute(flat, interval, market).total_return,  # compounded
        benchmark_return=result.benchmark.total_return if result.benchmark else np.inf)
    if log_path is not None:
        trial_log.log_trial({
            "utc_time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "kind": trial_log.DRILL if registered.is_drill else trial_log.FIREWALL,
            "candidate_id": registered.id, "register_commit": registered.commit,
            "strategy_name": str(registered.entry["rule"]),
            "params": {"stress": stress, "n_null": n_null, "seed": seed,
                       "verdict": result.verdict.outcome, "p_value": result.p_value,
                       "null": "turnover-matched", "p_coin": result.coin[0] if result.coin else None,
                       "dsr": result.deflated.get("dsr"), "trades": seen.trades,
                       "benchmark": result.benchmark.symbol if result.benchmark else None},
            "metric_name": "oos_sharpe_per_bar_marked",
            "metric_value": stats.compute(flat, interval, market).sharpe_per_bar,
            "n_bars": len(flat)}, path=log_path)
    return result
