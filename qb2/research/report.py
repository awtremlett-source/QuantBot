"""The firewall's report, in plain words -- and it will not render without D3 (S4).

PLAN_V3 P3: every result is shown beside the do-nothing benchmark over the SAME
period. A report missing the benchmark, or with the benchmark over a different
period, raises :class:`benchmark.MissingBenchmark` instead of printing a number
that cannot be judged.

Every report shows gross and net (net = after the cost model; the stress level is
stated), the survivorship mark-down before and after, the trades, the effective
number of bets, the null, the Deflated Sharpe, and the verdict.
"""

from __future__ import annotations

from qb2.research import backtest, stats
from qb2.research.benchmark import MissingBenchmark
from qb2.research.firewall import FirewallResult


def _pct(value: float) -> str:
    return f"{value:+.2%}"


def render(result: FirewallResult) -> str:
    mark = result.benchmark
    if mark is None:
        raise MissingBenchmark(f"{result.candidate_id}: no benchmark -- refusing to render")
    if (mark.start, mark.end) != (result.start, result.end):
        raise MissingBenchmark(f"{result.candidate_id}: benchmark covers {mark.start}.."
                               f"{mark.end}, the strategy {result.start}..{result.end}")
    seen = result.observed
    figures = {k: stats.compute(getattr(seen, k), result.interval)
               for k in ("gross", "net", "marked")}
    lines = [
        f"### {result.candidate_id} -- {result.verdict.outcome}",
        "",
        f"- Registered in commit `{result.register_commit[:12]}`; bars: {result.interval}; "
        f"costs at {result.stress:g}x; out-of-sample {result.start} to {result.end}",
        f"- Names: {result.names} ({result.effective_n} independent bets; "
        f"{len(result.skipped)} left out)",
        "",
        "| | total return | Sharpe / bar | annualised | max drawdown |",
        "|---|---|---|---|---|",
    ]
    labels = {"gross": "strategy, gross (no costs)",
              "net": f"strategy, net at {result.stress:g}x costs",
              "marked": "strategy, net after survivorship mark-down"}
    for key, label in labels.items():
        s = figures[key]
        lines.append(f"| {label} | {_pct(s.total_return)} | {s.sharpe_per_bar:.4f} | "
                     f"{s.sharpe_annualised:.2f} | {s.max_drawdown:.2%} |")
    if result.observed_1x is not None:
        one = stats.compute(result.observed_1x.net, result.interval)
        lines.append(f"| strategy, net at 1x costs | {_pct(one.total_return)} | "
                     f"{one.sharpe_per_bar:.4f} | {one.sharpe_annualised:.2f} | "
                     f"{one.max_drawdown:.2%} |")
    lines += [f"| **benchmark {mark.symbol}** (same period) | **{_pct(mark.total_return)}** "
              "| | | |", "",
              f"- Benchmark: {mark.why}",
              f"- Mark-down: before {_pct(figures['net'].total_return)}, after "
              f"{_pct(figures['marked'].total_return)} ({backtest.SURVIVORSHIP_LABEL})",
              f"- Out-of-sample trades: {seen.trades}; bars: {figures['marked'].bars}"]
    if result.p_value is not None:
        lines.append(f"- Coin-flip null: p = {result.p_value:.4f} (null Sharpe/bar "
                     f"{result.null_mean:.4f} ± {result.null_std:.4f})")
    if result.deflated:
        d = result.deflated
        lines.append(f"- Deflated Sharpe: {d['dsr']:.3f} over {d['n_trials']:.0f} trials "
                     f"(luck ceiling {d['sr0']:.4f} per bar)")
    lines.append(f"- Verdict: {result.verdict.line()}")
    return "\n".join(lines) + "\n"
