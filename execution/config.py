"""The frozen paper-trading config -- the strategy's birth certificate, not a dial.

LAW: changing ANY field of this config is a NEW strategy, and a new strategy MUST
go through the FULL §7 firewall again (backtest + walk-forward + Monte Carlo)
before it trades, even on paper. There are no "small tweaks" -- a tweaked config
has no validated track record, and running it would be trading an untested
strategy while pointing at the old strategy's evidence. That is exactly the
self-deception the firewall exists to block.

The values below are the ones that passed on 2026-07-16 (see STATE.md): the
severity-gated regime switcher on NVDA -- SMA-200 trend in calm regimes,
mean-reversion 2/20/75 in stressed ones -- adopted per pre-committed rules
(base stitched OOS sharpe +1.27 vs champion +1.19, matched-window MC p=0.004;
2x cost stress sharpe +1.1999 with the null also paying 2x, p=0.002). The
deployment threshold mirrors the validated walk-forward process: fit on ALL
history to date, then hold frozen until the next refit.
"""

from __future__ import annotations

from dataclasses import dataclass

from research.strategy import SmaTrendStrategy, Strategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.regime_switcher import RegimeSwitcherStrategy

# The worst peak-to-trough drawdown the validated OOS record ever saw. The live
# digest prints a WARNING when the paper book breaches it: beyond here the paper
# run is outside anything validation promised.
# Switcher stitched OOS maxDD: -36.5% base, -36.9% at 2x costs; the warning
# fires at the shallower (earlier) line.
VALIDATED_WORST_DRAWDOWN = -0.365


@dataclass(frozen=True, slots=True)
class PaperConfig:
    """One validated strategy fitting, frozen (see module docstring law).

    The strategy is :class:`strategies.regime_switcher.RegimeSwitcherStrategy`;
    ``threshold`` is the single fitted parameter (deployment fit on full history,
    2026-07-16) and ``lookback`` is the FROZEN trend window shared by both
    sub-strategies (part of their validated shapes, never searched). ``chosen_by``
    records where the fitting came from; ``next_refit_due`` is when it must be
    re-fitted (and thus re-firewalled) even if nothing else changed.
    """

    ticker: str = "NVDA"
    lookback: int = 200
    threshold: float = 1.5
    slippage_pct: float = 0.0005
    starting_equity: float = 10000.0
    chosen_by: str = (
        "regime-switcher firewall pass 2026-07-16 (base OOS +1.27 p=0.004; "
        "2x stress +1.1999 p=0.002) + deployment fit on full history"
    )
    next_refit_due: str = "2027-07-14"

    def build_strategy(self) -> Strategy:
        """Return the validated switcher: SMA trend when calm, dip-buyer when stressed."""
        return RegimeSwitcherStrategy(
            threshold=self.threshold,
            calm=SmaTrendStrategy([self.lookback]).build({"lookback": self.lookback}),
            stressed=MeanReversionStrategy(
                rsi_period=2,
                entry_threshold=20.0,
                exit_threshold=75.0,
                trend_lookback=self.lookback,
            ),
        )


# THE config the paper loop trades. Frozen dataclass + this single instance ==
# one place to look up what is running and why it is allowed to run.
CONFIG = PaperConfig()
