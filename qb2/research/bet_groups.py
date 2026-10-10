"""Names that are one bet, counted once wherever breadth is counted (S4).

GOOG/GOOGL (two share classes of one company) and VUAG/VUSA (two lines of one
index fund) move together, so counting each pair as two names would claim
breadth that does not exist and flatter every cross-name test. The list is a
versioned file, docs/research/bet_groups.json; changing it is a new version.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
GROUPS_FILE = REPO_ROOT / "docs" / "research" / "bet_groups.json"


def load(path: Path | None = None) -> dict[str, str]:
    """symbol -> its group's name (only names that share a group appear)."""
    doc = json.loads((path or GROUPS_FILE).read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for group in doc["groups"]:
        for member in group["members"]:
            if member in out:
                raise ValueError(f"{member} is in two bet groups")
            out[str(member)] = str(group["name"])
    return out


def group_of(symbol: str, groups: Mapping[str, str] | None = None) -> str:
    known = load() if groups is None else groups
    return known.get(symbol, symbol)


def effective_n(symbols: Iterable[str], groups: Mapping[str, str] | None = None) -> int:
    """How many independent bets these names really are."""
    known = load() if groups is None else groups
    return len({group_of(s, known) for s in symbols})


def combine(returns: Mapping[str, pd.Series],
            groups: Mapping[str, str] | None = None) -> pd.Series:
    """Equal weight per BET: members averaged first, then bets averaged.

    Aligned on the union of timestamps; a name with no bar at a moment holds no
    position then, so it contributes a zero return.
    """
    known = load() if groups is None else groups
    if not returns:
        return pd.Series(dtype=float)
    frame = pd.DataFrame(dict(returns)).fillna(0.0)
    by_bet: dict[str, list[str]] = {}
    for symbol in frame.columns:
        by_bet.setdefault(group_of(str(symbol), known), []).append(str(symbol))
    bets = pd.DataFrame({bet: frame[members].mean(axis=1)
                         for bet, members in by_bet.items()})
    return bets.mean(axis=1)
