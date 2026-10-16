"""D3, the do-nothing benchmark every result is shown beside (S4).

PLAN_V3 P3: judged in percent, after costs, against doing nothing -- a global
index fund. Chosen 2026-10-10 under the STANDING GO of 2026-10-07: **Vanguard FTSE
All-World, the accumulating sterling line, VWRP** (its dividends are reinvested
inside the price, so its price IS its total return in pounds).

Verified the way S3 verified every name: resolved against Trading 212's own saved
instrument list on short name + exchange, pinned by ISIN (qb2/ingest/
verify_universe.py). If that ever fails, the distributing line VWRL is used with
its dividends added back (qb2/research/total_return.py), and the report says so.

QT-17 A1/A3: read through the holdout door like every bar in research. An
intraday trial's benchmark is VWRP's own closes at the SAME bar size over the same
dates: daily VWRP from 2025-10-10 is the DAILY sealed year, and QT-14..16's 5-minute
benchmark read it (logged, kind seal_viewed). Its price is its total return, so an
intraday figure needs the accumulating line: the distributing fallback is refused.

QT-19: VWRP's first close (in the store) was 2019-07-25; since QT-21 quarantined its five
untraded filler rows it is 2019-08-13. A daily span that starts before it is the
named fallback, VWRL with its dividends added back, up to that close, chained to
VWRP from it -- one fund, so the splice changes the line, not what is measured.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from qb2.data import access
from qb2.ingest import verify_universe
from qb2.research import holdout, total_return

D3 = "VWRP.L"
D3_FALLBACK = "VWRL.L"
D3_ISIN = "IE00BK5BQT80"

Resolver = Callable[[Sequence[tuple[str, str, str]]], list[verify_universe.Resolved]]


class MissingBenchmark(RuntimeError):
    """A result without the benchmark beside it, over the same period, is not shown."""


@dataclass(frozen=True, slots=True)
class Benchmark:
    symbol: str
    why: str
    start: date
    end: date
    total_return: float              # in pounds, dividends included


def choose(resolve: Resolver = verify_universe.resolve) -> tuple[str, str]:
    """(symbol, evidence): VWRP if T212 lists its sterling accumulating line."""
    found = resolve([(D3, "LSE", "GBP")])[0]
    if (found.ok and found.currency == "GBP" and found.isin == D3_ISIN
            and "(Acc)" in str(found.name)):
        return D3, (f"VWRP: Trading 212 {found.t212_ticker}, ISIN {found.isin}, "
                    f"{found.currency}, accumulating ({found.name})")
    return D3_FALLBACK, (f"VWRL with dividends added back -- VWRP did not resolve "
                         f"as a GBP accumulating line ({found.reason or found.currency})")


def over(start: date, end: date, *, clean_root: Path | None = None,
         chosen: tuple[str, str] | None = None, interval: str = "1d",
         final: holdout.HoldoutPass | None = None) -> Benchmark:
    """From the close BEFORE ``start`` to the close of ``end`` -- the strategy's span.
    ``final`` is the single final run's pass (dates inside the seal)."""
    symbol, why = chosen or choose()
    if interval in ("5m", "1h"):
        if symbol != D3:
            raise MissingBenchmark(f"an intraday benchmark needs the accumulating {D3}, "
                                   f"whose price is its total return; {symbol} is not it")
        bars = holdout.bars_through(symbol, interval, "LSE", through=end, final=final,
                                    clean_root=clean_root)
        days = pd.Series(bars.index.date, index=bars.index)
        before, upto = bars[(days < start).to_numpy()], bars[(days <= end).to_numpy()]
        if before.empty or upto.empty:
            raise MissingBenchmark(f"no {symbol} 1h close before {start} or by {end}")
        return Benchmark(symbol=symbol, why=f"{why} ({interval} closes)", start=start, end=end,
                         total_return=float(upto["close"].iloc[-1] / before["close"].iloc[-1]
                                            - 1.0))
    begin = start - timedelta(days=1)
    first = _first_close(symbol, clean_root=clean_root) if symbol == D3 else None
    if first is not None and begin < first:                  # QT-19: before VWRP existed
        early = total_return.holding_return(D3_FALLBACK, begin, first, clean_root=clean_root)
        late = total_return.holding_return(symbol, first, end, clean_root=clean_root, final=final)
        return Benchmark(symbol=symbol, why=f"{why}; before {first} (VWRP's first close) "
                         f"{D3_FALLBACK} with its dividends added back, chained there",
                         start=start, end=end, total_return=(1.0 + early.total_return_gross)
                         * (1.0 + late.total_return_gross) - 1.0)
    held = total_return.holding_return(symbol, begin, end, clean_root=clean_root, final=final)
    return Benchmark(symbol=symbol, why=why, start=start, end=end,
                     total_return=held.total_return_gross)


def _first_close(symbol: str, *, clean_root: Path | None = None) -> date | None:
    """The first daily close in the store (unsealed bars, through the door); None if
    there is none -- the plain path then refuses loudly, as before."""
    try:
        bars = holdout.research_bars(symbol, "1d", "LSE", clean_root=clean_root)
    except access.AccessRefused:
        return None
    return pd.Timestamp(bars.index[0]).date() if len(bars) else None
