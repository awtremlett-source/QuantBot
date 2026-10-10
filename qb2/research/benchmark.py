"""D3, the do-nothing benchmark every result is shown beside (S4).

PLAN_V3 P3: judged in percent, after costs, against doing nothing -- a global
index fund. Chosen 2026-10-10 under the STANDING GO of 2026-10-07: **Vanguard FTSE
All-World, the accumulating sterling line, VWRP** (its dividends are reinvested
inside the price, so its price IS its total return in pounds).

Verified the way S3 verified every name: resolved against Trading 212's own saved
instrument list on short name + exchange, pinned by ISIN (qb2/ingest/
verify_universe.py). If that ever fails, the distributing line VWRL is used with
its dividends added back (qb2/research/total_return.py), and the report says so.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from qb2.ingest import verify_universe
from qb2.research import total_return

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
         chosen: tuple[str, str] | None = None) -> Benchmark:
    """From the close BEFORE ``start`` to the close of ``end`` -- the strategy's span."""
    symbol, why = chosen or choose()
    held = total_return.holding_return(symbol, start - timedelta(days=1), end,
                                       clean_root=clean_root)
    return Benchmark(symbol=symbol, why=why, start=start, end=end,
                     total_return=held.total_return_gross)
