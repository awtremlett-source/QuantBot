"""PASS, FAIL or INSUFFICIENT -- and nothing in between (S4).

* INSUFFICIENT: too few out-of-sample trades (starting figure: 30) or too few
  out-of-sample bars (30, the minimum the Deflated Sharpe will accept). It is a
  third answer, never shown as PASS and never silently dropped.
* PASS needs all three, on the marked-down NET record:
  1. better than the coin-flip null on the same bars (p < 0.05);
  2. Deflated Sharpe >= 0.95 over qb2's whole trial count;
  3. a higher total return than the benchmark (D3) over the same period.
* FAIL otherwise, naming every check that failed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

PASS = "PASS"
FAIL = "FAIL"
INSUFFICIENT = "INSUFFICIENT"
MIN_OOS_TRADES = 30          # STARTING FIGURE (standing GO 2026-10-07)
MIN_OOS_BARS = 30
ALPHA = 0.05
DSR_PASS = 0.95


@dataclass(frozen=True, slots=True)
class Verdict:
    outcome: str
    reasons: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.outcome == PASS

    def line(self) -> str:
        detail = "; ".join(self.reasons) if self.reasons else "every check met"
        return f"{self.outcome} -- {detail}"


def judge(*, oos_trades: int, oos_bars: int, p_value: float | None,
          dsr: float | None, strategy_return: float, benchmark_return: float) -> Verdict:
    short = []
    if oos_trades < MIN_OOS_TRADES:
        short.append(f"only {oos_trades} out-of-sample trades (need {MIN_OOS_TRADES})")
    if oos_bars < MIN_OOS_BARS:
        short.append(f"only {oos_bars} out-of-sample bars (need {MIN_OOS_BARS})")
    if short or p_value is None or dsr is None:
        return Verdict(INSUFFICIENT, short or ["the statistics could not be computed"])
    checks = {
        f"beats the coin-flip null (p {p_value:.4f} < {ALPHA})": p_value < ALPHA,
        f"Deflated Sharpe {dsr:.3f} >= {DSR_PASS}": dsr >= DSR_PASS,
        (f"beats the benchmark ({strategy_return:+.2%} vs {benchmark_return:+.2%})"):
            strategy_return > benchmark_return,
    }
    failed = [name for name, ok in checks.items() if not ok]
    return Verdict(FAIL if failed else PASS,
                   [f"failed: {name}" for name in failed], checks)
