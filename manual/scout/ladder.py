"""The 50% money ladder: where to split your money.

Each successive open position gets half the allocation of the one before:
position #1 may use up to 50% of the bankroll, #2 up to 25%, #3 up to
12.5%, and so on. Two nice properties for a beginner: you are never fully
invested (there is always reserve), and each additional idea must be
smaller than the last -- conviction first, dabbling later.

The ladder is a CEILING on position value. The risk rule (1% of bankroll
per trade via the stop) still sizes the trade; the ladder just refuses to
let any one position swallow the pot.
"""
from __future__ import annotations

from .config import Config
from .store import Store

LADDER_FLOOR_GBP = 100.0   # below this the ladder is effectively full


def ladder_state(store: Store, cfg: Config) -> dict:
    open_trades = store.list_trades(open_only=True)
    deployed = sum((t.get("entry_px") or 0.0) * (t.get("shares") or 0.0)
                   for t in open_trades)
    slot = len(open_trades) + 1
    fraction = 0.5 ** slot
    cap = cfg.bankroll_gbp * fraction
    return {
        "n_open": len(open_trades),
        "deployed": deployed,
        "reserve": max(0.0, cfg.bankroll_gbp - deployed),
        "next_slot": slot,
        "next_fraction": fraction,
        "next_cap": cap,
        "bankroll": cfg.bankroll_gbp,
        "full": cap < LADDER_FLOOR_GBP,
    }


def ladder_line(st: dict) -> str:
    if st["full"]:
        return (f"Money ladder: \u00a3{st['deployed']:,.0f} of "
                f"\u00a3{st['bankroll']:,.0f} deployed across "
                f"{st['n_open']} positions \u2014 the ladder is full; "
                f"bank something before adding.")
    return (f"Money ladder: \u00a3{st['deployed']:,.0f} of "
            f"\u00a3{st['bankroll']:,.0f} deployed \u00b7 next is position "
            f"#{st['next_slot']} \u2192 up to \u00a3{st['next_cap']:,.0f} "
            f"({st['next_fraction'] * 100:g}% of the pot).")
