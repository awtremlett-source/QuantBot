"""The advisor's monthly book: what is held, bar by bar, exactly as registered (QT-19 B1).

docs/research/preregistered.json (register 6332880), field "book" of A-01..A-06 and the
KN-A drills, is the authority. In brief, at each month's last close:

1. stops first (every close): a name stopped at its decision bar is not bought then;
2. P13: held 12+ months -> kept only if in the top k (a re-justified buy: fresh stop,
   no trade), else sold;
3. other held names kept if eligible and in the top 30% (the buffer), else sold;
4. more than k kept -> the lowest-ranked beyond k sold;
5. free slots filled with the best-ranked eligible names not held (none while A-06's
   market filter is off: then everything is sold).

A name's decision bar is its bar on its exchange's LAST session of the month; the
arm decides once both markets have closed that month (a London decision bar can be
a day earlier than New York's -- it still fills at London's next open, after the
decision). No bar there: a held name is sold, decided at its next bar.

Pure logic: bars, values, VIX and the A-06 filter are handed in. The output is each
name's 0/1 target at every close (``decisions``, the firewall's Strategy weights) and
its share of the pot at every bar (``weights``: 1/k, capped by the 1% rule).
:func:`causal` rebuilds on data cut at mid-month dates and refuses a book whose past
changed -- the look-ahead check the per-name Strategy contract cannot make here.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Protocol

import exchange_calendars as xcals  # type: ignore[import-untyped]
import numpy as np
import pandas as pd

from qb2.research import fills
from qb2.research.strategy import LookAhead
from qb2.signals import indicators


class Name(Protocol):                    # firewall.NameData, as much as the book reads
    @property
    def symbol(self) -> str: ...
    @property
    def market(self) -> str: ...
    @property
    def bars(self) -> pd.DataFrame: ...
    @property
    def bet(self) -> int: ...


@dataclass(frozen=True, slots=True)
class Settings:
    lookback: int
    ascending: bool
    top: float = 0.2
    buffer: float = 0.3
    age_months: int = 12
    stop_k: float = 3.0
    stop_k_unsettled: float = 2.0
    vix_unsettled: float = 30.0
    coverage: float = 0.9
    risk_per_trade: float = 0.01
    advisor_share: float = 0.7

    @classmethod
    def of(cls, p: Mapping[str, Any], lookback: int, ascending: bool) -> Settings:
        return cls(lookback, ascending, float(p["top"]), float(p["buffer"]), int(p["age_months"]),
                   float(p["stop_k"]), float(p["stop_k_unsettled"]), float(p["vix_unsettled"]),
                   float(p["coverage"]), float(p["risk_per_trade"]), float(p["advisor_share"]))


@dataclass(slots=True)
class Book:
    decisions: dict[str, np.ndarray]
    weights: dict[str, pd.Series]
    buys: list[tuple[str, int]] = field(default_factory=list)     # (symbol, decision bar)
    requalified: int = 0
    stopped: int = 0
    filter_off_months: int = 0
    capped: dict[str, np.ndarray] = field(default_factory=dict)   # the 1% rule binds here


def month_of(day: date) -> int:
    return day.year * 12 + day.month - 1


def sessions(market: str, first: date, last: date) -> np.ndarray:
    cal = xcals.get_calendar(fills.CALENDARS[market], start=str(first), end=str(last))
    return np.asarray(cal.sessions.values.astype("datetime64[D]"))


def last_sessions(days: np.ndarray) -> dict[int, date]:
    out: dict[int, date] = {}
    for d in pd.DatetimeIndex(days).date:
        out[month_of(d)] = d                 # in order, so the month's last one wins
    return out


def build(s: Settings, data: Sequence[Name], values: Mapping[str, np.ndarray], *,
          vix: pd.Series | None = None, market_on: Mapping[int, bool] | None = None) -> Book:
    names = list(data)
    if len({n.bet for n in names}) != len(names):
        raise ValueError("a bet with two lines in the advisor arm: not implemented")
    dates = [pd.DatetimeIndex(n.bars.index).date for n in names]
    first, last = min(d[0] for d in dates), max(d[-1] for d in dates)
    ahead = date.fromordinal(last.toordinal() + 45)      # the real month ends, not the data's
    cal = {m: sessions(m, first, ahead) for m in {n.market for n in names}}
    ends = {m: last_sessions(days) for m, days in cal.items()}
    o = [n.bars["open"].to_numpy(dtype=float) for n in names]
    c = [n.bars["close"].to_numpy(dtype=float) for n in names]
    atr = [indicators.atr_wilder(n.bars, 14).to_numpy(dtype=float) for n in names]
    vix_days = np.asarray([] if vix is None else pd.DatetimeIndex(vix.index).date)
    vix_close = np.asarray([] if vix is None else vix.to_numpy(dtype=float))

    def k_at(day: date) -> float:            # P10: 2 when unsettled (VIX before the day > 30)
        j = int(np.searchsorted(vix_days, np.asarray(day), side="left")) - 1
        calm = j >= 0 and bool(np.isfinite(vix_close[j])) and vix_close[j] <= s.vix_unsettled
        return s.stop_k if calm else s.stop_k_unsettled

    timeline: dict[date, list[tuple[int, int]]] = {}
    decbar: list[dict[int, int]] = []
    for i, (n, d) in enumerate(zip(names, dates, strict=True)):
        mine: dict[int, int] = {}
        for t, day in enumerate(d):
            timeline.setdefault(day, []).append((i, t))
            if ends[n.market].get(month_of(day)) == day:
                mine[month_of(day)] = t
        decbar.append(mine)
    months = set().union(*(e.keys() for e in ends.values()))
    decide_on = {m: max(e[m] for e in ends.values() if m in e) for m in months}
    out = Book({n.symbol: np.zeros(len(n.bars)) for n in names}, {})
    target = np.zeros(len(names))
    held: set[int] = set()
    level = np.full(len(names), np.nan)
    pending: dict[int, float] = {}           # name -> the decision bar's ATR (stop at fill)
    bought: dict[int, int] = {}              # name -> month its buy was decided
    sell_next: set[int] = set()
    stopped_on: dict[int, date] = {}
    k_by_month: dict[int, int] = {}

    def decide(m: int) -> None:
        now = {i: b[m] for i, b in enumerate(decbar) if m in b}
        for i in sorted(held - set(now)):                 # no month-end bar: sold next bar
            held.discard(i)
            sell_next.add(i)
        ok = []
        for i, t in now.items():
            v = values[names[i].symbol][t]
            if t < s.lookback or not np.isfinite(v):
                continue
            span = cal[names[i].market]
            lo = int(np.searchsorted(span, np.datetime64(dates[i][t - s.lookback]), "left"))
            hi = int(np.searchsorted(span, np.datetime64(dates[i][t]), "right"))
            if (s.lookback + 1) / max(hi - lo, 1) >= s.coverage:
                ok.append((float(v) if s.ascending else -float(v), names[i].symbol, i))
        rank = [i for _, _, i in sorted(ok)]
        k = max(1, round(s.top * len(rank))) if rank else 0
        b = max(k, round(s.buffer * len(rank)))
        k_by_month[m] = k
        top_k, top_b = set(rank[:k]), set(rank[:b])
        place = {i: r for r, i in enumerate(rank)}
        due = {i for i in held if m - bought[i] >= s.age_months}       # P13: re-qualify
        off = market_on is not None and not market_on.get(m, False)
        keep: list[int] = []
        if off:                                           # A-06: cash, nothing bought
            out.filter_off_months += 1
        else:
            keep = [i for i in sorted(held) if (i in top_k if i in due else i in top_b)]
            keep = sorted(keep, key=lambda i: place[i])[:k]
        for i in sorted(due & set(keep)):                 # a re-justified buy: fresh stop
            bought[i], pending[i] = m, float(atr[i][now[i]])
            out.requalified += 1
        new = [i for i in rank if i not in held and stopped_on.get(i) != dates[i][now[i]]]
        for i in sorted(held - set(keep)):
            held.discard(i)
            target[i] = 0.0
            out.decisions[names[i].symbol][now[i]] = 0.0
        for i in new[:0 if off else max(k - len(keep), 0)]:
            held.add(i)
            target[i], bought[i], pending[i] = 1.0, m, float(atr[i][now[i]])
            out.decisions[names[i].symbol][now[i]] = 1.0
            out.buys.append((names[i].symbol, now[i]))

    for day in sorted(timeline):
        for i, t in timeline[day]:
            if i in sell_next:
                sell_next.discard(i)
                target[i] = 0.0
                continue
            if i not in held or target[i] == 0.0:
                continue
            if i in pending:                              # the fill bar: the stop is set
                level[i] = o[i][t] - k_at(day) * pending.pop(i)
            if c[i][t] <= level[i]:                       # P10: crossed -> sold next open
                held.discard(i)
                target[i] = 0.0
                stopped_on[i] = day
                out.stopped += 1
            elif np.isfinite(atr[i][t]):
                level[i] = max(level[i], c[i][t] - k_at(day) * atr[i][t])
        if decide_on.get(month_of(day)) == day:
            decide(month_of(day))
        for i, t in timeline[day]:
            out.decisions[names[i].symbol][t] = target[i]
    for i, n in enumerate(names):
        slot = np.array([1.0 / k_by_month[m - 1] if k_by_month.get(m - 1) else 0.0
                         for m in (month_of(d) for d in dates[i])])
        risk = np.r_[np.nan, s.stop_k * atr[i][:-1] / c[i][:-1]]
        with np.errstate(divide="ignore", invalid="ignore"):
            cap = np.where(np.isfinite(risk) & (risk > 0),
                           s.risk_per_trade / s.advisor_share / risk, np.inf)
        out.weights[n.symbol] = pd.Series(np.minimum(slot, cap), index=n.bars.index)
        out.capped[n.symbol] = cap < slot
    return out


def causal(make: Callable[[Sequence[Any]], Book], data: Sequence[Any], full: Book,
           cuts: Sequence[date]) -> None:
    """Rebuild on every name's bars dated before each cut (mid-month dates); a decision
    before the cut that changes means the book read the future: refused."""
    for cut in cuts:
        early = [replace(n, bars=n.bars[pd.DatetimeIndex(n.bars.index).date < cut])
                 for n in data]
        early = [n for n in early if len(n.bars) >= 2]
        again = make(early)
        for n in early:
            if not np.array_equal(again.decisions[n.symbol],
                                  full.decisions[n.symbol][:len(n.bars)]):
                raise LookAhead(f"advisor book: {n.symbol}'s decisions before {cut} changed "
                                "when later bars were removed -- it reads the future")
