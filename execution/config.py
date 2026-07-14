"""The frozen paper-trading config -- the strategy's birth certificate, not a dial.

LAW: changing ANY field of this config is a NEW strategy, and a new strategy MUST
go through the FULL §7 firewall again (backtest + walk-forward + Monte Carlo)
before it trades, even on paper. There are no "small tweaks" -- a tweaked config
has no validated track record, and running it would be trading an untested
strategy while pointing at the old strategy's evidence. That is exactly the
self-deception the firewall exists to block.

The values below are the ones that passed on 2026-07-14 (see STATE.md):
SMA-200 long-only on NVDA, stitched OOS sharpe +1.19, both Monte-Carlo gates
passed (full-series p=0.003; matched-window p=0.007).
"""

from __future__ import annotations

from dataclasses import dataclass

from research.strategy import SmaTrendStrategy, Strategy

# The worst peak-to-trough drawdown the validated OOS record ever saw. The live
# digest prints a WARNING when the paper book breaches it: beyond here the paper
# run is outside anything validation promised.
VALIDATED_WORST_DRAWDOWN = -0.488


@dataclass(frozen=True, slots=True)
class PaperConfig:
    """One validated strategy fitting, frozen (see module docstring law).

    The strategy family is :class:`research.strategy.SmaTrendStrategy`;
    ``lookback`` is the single fitted parameter. ``chosen_by`` records where the
    fitting came from; ``next_refit_due`` is when it must be re-fitted (and thus
    re-firewalled) even if nothing else changed.
    """

    ticker: str = "NVDA"
    lookback: int = 200
    slippage_pct: float = 0.0005
    starting_equity: float = 10000.0
    chosen_by: str = "walk_forward 2026-07-14 (7/9 folds)"
    next_refit_due: str = "2027-07-14"

    def build_strategy(self) -> Strategy:
        """Return the concrete validated strategy (SMA trend rule, long-only)."""
        return SmaTrendStrategy([self.lookback]).build({"lookback": self.lookback})


# THE config the paper loop trades. Frozen dataclass + this single instance ==
# one place to look up what is running and why it is allowed to run.
CONFIG = PaperConfig()
