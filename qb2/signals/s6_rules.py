"""S6 batch 1's eight same-day rules, exactly as registered (QT-18 B1; register c89f2fd).

docs/research/preregistered.json is the authority, its clarifications included:

* bars are numbered from 1 within each session; a decision is taken at a bar's
  CLOSE and fills at the plan's own fill (QT-17: two bars later on 1h, same
  session only); E = the session's first bar the plan forces flat (ends after the
  P4 cut); every trade ends at E's open unless stopped earlier;
* one entry per name per day: the weight is 1 from the decision bar to the
  session's end (0 after a stop), else 0;
* a day is SKIPPED when the name has no previous session, a needed bar is
  missing, the entry would land at or after E, or P15 refuses the BUY at the
  decision bar (``plan.may_enter``) -- no retry later that day;
* XS rules (S6-06/07/08) rank BETS by the mean of their lines' returns, the
  quintile = round(0.2 x n), at least 1, ties by bet name; S6-06/07 in the Mix arm
  rank each market on its own; S6-08 ranks the whole arm;
* the stop (S6-04/05): entry - 3 x Wilder ATR(14) as of the bar before the entry;
  crossed when a held bar closes at or below it; else raised to close - 3 x ATR.

``weights(bars)`` reads only ``bars`` (a prefix of the name's bars), the plan
(calendar and P15, both known in advance) and, for XS rules, a table built from the
arm's bars at each decision moment -- the look-ahead check proves the first two.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any, Protocol

import numpy as np
import pandas as pd

from qb2.research import bet_groups, fills
from qb2.signals import indicators

ALLOWED = {
    "s6_intraday_mom": {"signal", "threshold", "entry"},
    "s6_gap_fade": {"gap", "gap_max", "decide_at_bar"},
    "s6_gap_go": {"gap", "gap_min", "first_bar_up", "decide_at_bar"},
    "s6_range_breakout": {"level", "trigger_from_bar", "trigger_before", "stop_k", "atr_period"},
    "s6_trailing_buy": {"trigger_from_bar", "atr_mult_above_running_low", "atr_period",
                        "stop_k"},
    "s6_xs_reversal": {"rank_at_bar", "rank_by", "side", "quantile"},
    "s6_xs_momentum": {"rank_at_bar", "rank_by", "side", "quantile"},
    "s6_prior_day_reversal": {"rank_by", "side", "quantile", "decide_at_bar"},
}
COMMON = {"arm", "sleeves", "stop"}
FIXED = {"decide_at_bar": 1, "trigger_from_bar": 2, "rank_at_bar": 2, "atr_period": 14,
         "stop_k": 3.0, "trigger_before": "E-1", "entry": "open of E-1", "first_bar_up": True,
         "level": "high(bar 1)", "threshold": 0.0, "atr_mult_above_running_low": 1.0,
         "quantile": 0.2, "gap_max": -0.010, "gap_min": 0.010}       # what this code implements
XS = ("s6_xs_reversal", "s6_xs_momentum", "s6_prior_day_reversal")


class Name(Protocol):                    # firewall.NameData, as much as a rule reads
    @property
    def symbol(self) -> str: ...
    @property
    def market(self) -> str: ...
    @property
    def bars(self) -> pd.DataFrame: ...
    @property
    def plan(self) -> fills.Schedule: ...


def sessions(index: pd.DatetimeIndex, market: str) -> list[tuple[int, int, date]]:
    """(first bar, one past the last bar, exchange date) of each session in ``index``."""
    days = pd.DatetimeIndex(index).tz_convert(fills.EXCHANGE_TZ[market]).date
    cuts = np.flatnonzero(np.r_[True, days[1:] != days[:-1], True])
    return [(int(a), int(b), days[a]) for a, b in zip(cuts[:-1], cuts[1:])]


def exit_bar(plan: fills.Schedule, s0: int, s1: int) -> int | None:
    """E: the session's first bar the plan forces flat (None if past the data)."""
    forced = plan.forced_flat
    if forced is None:
        return None
    hit = np.flatnonzero(forced[s0:min(s1, plan.n)])
    return s0 + int(hit[0]) if len(hit) else None


def prior_closes(bars: pd.DataFrame, spans: Sequence[tuple[int, int, date]]) -> list[float | None]:
    close = bars["close"].to_numpy(dtype=float)
    return [None] + [float(close[b - 1]) for _, b, _ in spans[:-1]]


def picks(entry: Mapping[str, Any], data: Sequence[Name]) -> set[tuple[str, date]]:
    """XS rules: the (symbol, session date) pairs chosen, from the arm's own bars."""
    p, rule = entry["parameters"], str(entry["rule"])
    groups = bet_groups.load()
    rows: list[tuple[str, str, date, float]] = []        # (group key, symbol, day, value)
    for name in data:
        close = name.bars["close"].to_numpy(dtype=float)
        spans = sessions(name.bars.index, name.market)
        prior = prior_closes(name.bars, spans)
        for i, (s0, s1, day) in enumerate(spans):
            last, before = prior[i], (prior[i - 1] if i >= 1 else None)
            value: float | None = None
            if rule == "s6_prior_day_reversal" and last is not None and before is not None:
                value = last / before - 1                 # the previous session, close to close
            elif rule != "s6_prior_day_reversal" and last is not None and s1 - s0 >= 2:
                value = float(close[s0 + 1]) / last - 1   # prior close -> bar 2's close
            if value is not None and np.isfinite(value):
                market = "" if rule == "s6_prior_day_reversal" else name.market
                rows.append((market, name.symbol, day, float(value)))
    frame = pd.DataFrame(rows, columns=["market", "symbol", "day", "value"])
    if frame.empty:
        return set()
    frame["bet"] = [bet_groups.group_of(s, groups) for s in frame["symbol"]]
    chosen: set[tuple[str, date]] = set()
    for _, group in frame.groupby(["market", "day"]):
        bets = group.groupby("bet")["value"].mean().reset_index()
        ascending = p["side"] == "bottom"
        bets = bets.assign(key=bets["value"] if ascending else -bets["value"])
        k = max(1, round(float(p["quantile"]) * len(bets)))
        top = set(bets.sort_values(["key", "bet"]).head(k)["bet"])
        chosen |= {(s, d) for s, d, b in zip(group["symbol"], group["day"], group["bet"])
                   if b in top}
    return chosen


class Rule:
    def __init__(self, entry: Mapping[str, Any], name: Name,
                 chosen: set[tuple[str, date]] | None) -> None:
        self.entry, self.rule, self.p = entry, str(entry["rule"]), entry["parameters"]
        self.symbol, self.market, self.plan = name.symbol, name.market, name.plan
        self.full_index = pd.DatetimeIndex(name.bars.index)
        self.chosen = chosen or set()
        self.name = f"{entry['id']}({self.rule})"

    def _trigger(self, s0: int, e: int, n: int, o: np.ndarray, h: np.ndarray,
                 lo: np.ndarray, c: np.ndarray, atr: np.ndarray, prior: float | None,
                 day: date) -> int | None:
        """The decision bar of the day, or None (skip)."""
        rule = self.rule
        if rule == "s6_prior_day_reversal":
            return s0 if s0 < n and (self.symbol, day) in self.chosen else None
        if prior is None:
            return None
        if rule == "s6_intraday_mom":
            hits = [j for j in range(s0, e) if self.plan.fills[j] == e - 1]
            if not hits or s0 >= n or not c[s0] / prior - 1 > self.p["threshold"]:
                return None
            return hits[0]
        if rule in ("s6_gap_fade", "s6_gap_go"):
            if s0 >= n:
                return None
            gap = o[s0] / prior - 1
            if rule == "s6_gap_fade":
                return s0 if gap <= self.p["gap_max"] else None
            return s0 if gap >= self.p["gap_min"] and c[s0] > o[s0] else None
        if rule in ("s6_xs_reversal", "s6_xs_momentum"):
            return s0 + 1 if (self.symbol, day) in self.chosen and s0 + 1 < e else None
        if rule == "s6_range_breakout":
            for k in range(s0 + 1, min(e - 1, n)):
                if c[k] > h[s0]:
                    return k
            return None
        for k in range(s0 + 1, min(e, n)):                       # s6_trailing_buy
            if np.isfinite(atr[k]) and c[k] >= lo[s0:k + 1].min() + \
                    float(self.p["atr_mult_above_running_low"]) * atr[k]:
                return k
        return None

    def weights(self, bars: pd.DataFrame) -> pd.Series:
        n = len(bars)
        if n > self.plan.n or not pd.DatetimeIndex(bars.index).equals(self.full_index[:n]):
            raise ValueError(f"{self.name}: bars are not a prefix of {self.symbol}'s own")
        o, h, lo, c = (bars[col].to_numpy(dtype=float) for col in ("open", "high", "low", "close"))
        atr = indicators.atr_wilder(bars, 14).to_numpy(dtype=float)
        out = np.zeros(n)
        spans = sessions(self.full_index, self.market)          # calendar: known in advance
        prior = prior_closes(bars.reindex(self.full_index), spans)
        for (s0, s1, day), before in zip(spans, prior):
            if s0 >= n:
                break
            e = exit_bar(self.plan, s0, s1)
            j = None if e is None else self._trigger(s0, e, n, o, h, lo, c, atr, before, day)
            if j is None or j >= n or not self.plan.usable[j] or self.plan.fills[j] >= e \
                    or (self.plan.may_enter is not None and not self.plan.may_enter[j]):
                continue
            out[j:min(s1, n)] = 1.0
            if self.p["stop"]:
                f = int(self.plan.fills[j])
                level = o[f] - float(self.p["stop_k"]) * atr[f - 1] if f < n else np.nan
                for i in range(f, min(s1, n)):
                    if c[i] <= level:
                        out[i:min(s1, n)] = 0.0
                        break
                    level = max(level, c[i] - float(self.p["stop_k"]) * atr[i])
        return pd.Series(out, index=bars.index)


def maker(entry: Mapping[str, Any], data: Sequence[Name]) -> Any:
    """``make(name) -> Strategy`` for one registered S6 trial; refuses what it does not know."""
    rule, params = str(entry["rule"]), set(entry["parameters"])
    if rule not in ALLOWED or params - COMMON != ALLOWED[rule]:
        raise ValueError(f"{entry['id']}: rule {rule!r} with parameters {sorted(params)} is "
                         "not implemented exactly as registered")
    wrong = {k: v for k, v in entry["parameters"].items() if k in FIXED and v != FIXED[k]}
    side = entry["parameters"].get("side", "bottom")
    if wrong or side not in ("bottom", "top") or bool(entry["parameters"]["stop"]) != (
            rule in ("s6_range_breakout", "s6_trailing_buy")):
        raise ValueError(f"{entry['id']}: values {wrong or side} are not what this code implements")
    chosen = picks(entry, data) if rule in XS else None
    return lambda name: Rule(entry, name, chosen)
