"""Firewall v2: score one pre-registered candidate across a universe (S4).

The one scoring path a candidate goes through, in order:

1. the registered token (preregister) -- an unregistered candidate stops here;
2. each name's UNSEALED bars (holdout), costed as that instrument (costs.py);
3. walk-forward per name, with delay rule (c), P4 and every fill costed;
4. the names combined equal-weight per BET (bet_groups: GOOG/GOOGL and VUAG/VUSA
   are one bet each) -- gross, net, and net after the survivorship mark-down;
5. the coin-flip null through the IDENTICAL pipeline, same bars, same costs;
6. the Deflated Sharpe over qb2's whole trial count (drills excluded);
7. the benchmark (D3) over the same period, both compounded; the verdict; ONE
   trial-log line.

QT-15: ``n_trials`` sets a floor under the Deflated Sharpe's N, so every trial of
a batch is deflated over the batch's FULL count, not the count so far; ``final``
is the single holdout pass -- each name's sealed bars are graded, its unsealed bars
only warm the indicators up; the per-name OOS frames are kept for description.
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
                          monte_carlo, preregister, stats, trial_log, verdict, walk_forward)
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


def instrument_of(entry: Mapping[str, Any]) -> costs.Instrument:
    return costs.Instrument(ticker=str(entry["t212_ticker"]),
                            currency=str(entry["quote_currency"]),
                            market=universe.market_of(entry), kind=str(entry["kind"]),
                            aim=bool(entry.get("aim", False)))


def load(interval: str, *, entries: Sequence[Mapping[str, Any]] | None = None,
         transform: Transform | None = None, clean_root: Path | None = None,
         ) -> tuple[list[NameData], list[str]]:
    """Every agreed name's unsealed bars, or the reason it was left out."""
    rows = list(entries if entries is not None else universe.bot_entries())
    groups = bet_groups.load()
    bets = sorted({bet_groups.group_of(str(e["yfinance"]), groups) for e in rows})
    out, skipped = [], []
    for entry in rows:
        symbol, market = str(entry["yfinance"]), universe.market_of(entry)
        try:
            bars = holdout.research_bars(symbol, interval, market, clean_root=clean_root)
        except access.AccessRefused as why:
            skipped.append(f"{symbol}: {why}")
            continue
        if len(bars) < 2:
            skipped.append(f"{symbol}: no unsealed {interval} bars")
            continue
        instrument = instrument_of(entry)
        if transform is not None:
            bars = transform(bars, instrument, market)
        out.append(NameData(symbol, market, instrument, bars,
                            fills.schedule(bars.index, interval, market),
                            bets.index(bet_groups.group_of(symbol, groups))))
    return out, skipped


@dataclass(frozen=True, slots=True)
class Portfolio:
    gross: pd.Series
    net: pd.Series
    marked: pd.Series
    trades: int
    parts: dict[str, pd.DataFrame] = field(default_factory=dict)


def _sealed(token: preregister.Registered, strategy: Strategy, name: NameData,
            interval: str, stress: float, final: holdout.HoldoutPass) -> pd.DataFrame:
    """The holdout run for one name: one full run, graded on the sealed bars only."""
    full = backtest.run(token, strategy, name.bars, instrument=name.instrument,
                        interval=interval, market=name.market, stress=stress,
                        final=final, plan=name.plan, log_path=None)
    days = holdout.local_index(name.bars.index, name.market).date
    first = int((days < holdout.SEALED_FROM[interval]).sum())      # bars are in order
    return walk_forward._frame(full, first, len(name.bars))       # noqa: SLF001


def portfolio(token: preregister.Registered, make: Callable[[NameData], Strategy],
              data: Sequence[NameData], interval: str, stress: float,
              final: holdout.HoldoutPass | None = None) -> Portfolio:
    parts: dict[str, pd.DataFrame] = {}
    for name in data:
        if final is not None:
            oos = _sealed(token, make(name), name, interval, stress, final)
        else:
            oos = walk_forward.walk_forward(
                token, walk_forward.Fixed(make(name)), name.bars,
                instrument=name.instrument, interval=interval, market=name.market,
                stress=stress, plan=name.plan, log_path=None).oos
        if len(oos):
            parts[name.symbol] = oos
    combine = {col: bet_groups.combine({s: f[col].astype(float) for s, f in parts.items()})
               for col in ("gross", "net", "marked")}
    trades = int(sum(int(f["entries"].sum()) for f in parts.values()))
    return Portfolio(combine["gross"], combine["net"], combine["marked"], trades, parts)


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


def _coin(seed: int) -> Callable[[NameData], Strategy]:
    """One coin per BET: both lines of one bet flip together."""
    return lambda name: monte_carlo.RandomStrategy(
        0.5, int(np.random.SeedSequence([seed, name.bet]).generate_state(1)[0]))


def score(token: preregister.Registered, make: Callable[[NameData], Strategy],
          data: Sequence[NameData], *, interval: str, stress: float = 1.0,
          skipped: Sequence[str] = (), n_null: int = monte_carlo.DEFAULT_TRIALS,
          seed: int = 0,
          bench: Callable[[date, date], benchmark.Benchmark] = benchmark.over,
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
    if start and end:
        result.benchmark = bench(start, end)
    if seen.trades >= verdict.MIN_OOS_TRADES and len(flat) >= verdict.MIN_OOS_BARS:
        nulls = [stats.compute(portfolio(registered, _coin(s), data, interval, stress, final)
                               .marked, interval, market).sharpe_per_bar
                 for s in monte_carlo.trial_seeds(seed, n_null)]
        observed = stats.compute(flat, interval, market).sharpe_per_bar
        result.p_value = monte_carlo.p_value(observed, nulls)
        result.null_mean, result.null_std = float(np.mean(nulls)), float(np.std(nulls))
        counted, _ = trial_log.count_selection_trials(log_path)
        n_full = max(2, counted + (0 if registered.is_drill else 1), n_trials)
        try:
            result.deflated = deflation.deflated_sharpe(flat, n_full, float(np.var(nulls)))
        except ValueError:
            result.deflated = {}              # judged INSUFFICIENT below, never PASS
    result.verdict = verdict.judge(
        oos_trades=seen.trades, oos_bars=len(flat), p_value=result.p_value,
        dsr=result.deflated.get("dsr"),
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
                       "dsr": result.deflated.get("dsr"), "trades": seen.trades,
                       "benchmark": result.benchmark.symbol if result.benchmark else None},
            "metric_name": "oos_sharpe_per_bar_marked",
            "metric_value": stats.compute(flat, interval, market).sharpe_per_bar,
            "n_bars": len(flat)}, path=log_path)
    return result
