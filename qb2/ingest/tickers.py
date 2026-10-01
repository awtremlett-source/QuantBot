"""Mapping Trading 212's ticker names to yfinance's, without guessing.

T212 writes its own identifiers -- ``AAPL_US_EQ``, ``SGLNl_EQ`` -- and yfinance
wants ``AAPL`` and ``SGLN.L``. The rules below were read off a LIVE practice
account (2026-09-30), not invented:

    AAPL_US_EQ  TSLA_US_EQ  MU_US_EQ      -> SYMBOL_US_EQ  -> SYMBOL
    SGLNl_EQ                              -> SYMBOLl_EQ    -> SYMBOL.L
    SNDK1_US_EQ ALCC1_US_EQ 3LGO1l_EQ     -> a trailing DIGIT before the suffix

That last group is the honest problem. T212 appends a digit to disambiguate --
but whether ``SNDK1_US_EQ`` is yfinance's ``SNDK`` or something else is not
something this file will pretend to know. Those names are returned as
**UNCERTAIN** and listed for a human, never silently mapped.

That gap is now CLOSED for membership. The key in use since 2026-10-01 can read
T212's instrument list, so every name below is resolved against the saved copy of
it and matched on exchange and currency, not on spelling (FACTS row q, and
qb2/ingest/verify_universe.py). The lists themselves are no longer kept by hand
here: they are read from the newest versioned file in ``docs/universe/``, which
records for every name the identity it resolved to, what it measured, and why it
was included -- so the list cannot drift away from its evidence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

US_SUFFIX = "_US_EQ"
LSE_SUFFIX = "l_EQ"


@dataclass(frozen=True, slots=True)
class Mapped:
    """One instrument, with how confident we are about its yfinance name."""

    t212: str
    yfinance: str | None
    market: str
    currency: str
    certain: bool
    note: str = ""


def _has_disambiguating_digit(core: str) -> bool:
    """T212 appends a digit to separate two listings of a similar name."""
    return len(core) > 1 and core[-1].isdigit()


def map_t212_ticker(t212_ticker: str) -> Mapped:
    """Translate one T212 identifier, or say honestly that we cannot."""
    if t212_ticker.endswith(US_SUFFIX):
        core = t212_ticker[: -len(US_SUFFIX)]
        if _has_disambiguating_digit(core):
            return Mapped(t212_ticker, None, "US", "USD", False,
                          "trailing digit: T212 disambiguator, yfinance name "
                          "unknown -- needs a human")
        return Mapped(t212_ticker, core, "US", "USD", True)
    if t212_ticker.endswith(LSE_SUFFIX):
        core = t212_ticker[: -len(LSE_SUFFIX)]
        if _has_disambiguating_digit(core):
            return Mapped(t212_ticker, None, "LSE", "GBP", False,
                          "trailing digit: T212 disambiguator, yfinance name "
                          "unknown -- needs a human")
        return Mapped(t212_ticker, f"{core}.L", "LSE", "GBP", True)
    return Mapped(t212_ticker, None, "UNKNOWN", "UNKNOWN", False,
                  "suffix not recognised -- only _US_EQ and l_EQ are known")


def map_many(tickers: list[str]) -> tuple[list[Mapped], list[Mapped]]:
    """Returns (certain, uncertain). The uncertain list is for a human to read."""
    mapped = [map_t212_ticker(t) for t in tickers]
    return ([m for m in mapped if m.certain],
            [m for m in mapped if not m.certain])


# --------------------------------------------------------- the recording list --
# WHAT WE RECORD, which is not the same as what we TRADE. Recording something we
# never trade costs 23 KiB per name per weekday, measured; failing to record
# something we later want costs the data permanently, because minute bars come
# only 8 days at a time (FACTS row n). So this list is wide and the universe files
# narrow it.
#
# The v1 lists were kept by hand in this file and were wrong in ways no test could
# see: "AHT.L" had stopped being Ashtead and become Sunbelt Rentals on a US ISIN,
# "IEUR.L" does not exist on T212's London list at all, and "IGLN.L" was the same
# gold fund as "SGLN.L" under a second ISIN-sharing line. They are in git history;
# the data recorded under them is kept (quarantine, never delete) and simply no
# longer updated. Today the names come from evidence instead.
UNIVERSE_DIR = Path(__file__).resolve().parents[2] / "docs" / "universe"


def _newest_recording_file() -> Path:
    found = sorted(UNIVERSE_DIR.glob("recording-list-*.json"))
    if not found:
        raise FileNotFoundError(
            f"no recording list in {UNIVERSE_DIR}: build one with "
            "`python -m qb2.tools.build_universe` before recording anything")
    return found[-1]


@lru_cache(maxsize=1)
def _recording_file() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(
        _newest_recording_file().read_text(encoding="utf-8"))
    return loaded


def _sleeve(name: str) -> tuple[str, ...]:
    return tuple(e["yfinance"] for e in _recording_file()["entries"]
                 if e["sleeve"] == name)


def quote_currency(yfinance_symbol: str) -> str | None:
    """What currency T212 quotes this name in -- the authority, per instrument.

    None for the gauges and the exchange rate, which are not instruments.
    """
    for entry in _recording_file()["entries"]:
        if entry["yfinance"] == yfinance_symbol:
            currency = str(entry["quote_currency"])
            return "GBp" if currency == "GBX" else currency
    return None


US_SHARES: tuple[str, ...] = _sleeve("us_liquid")
UK_SHARES: tuple[str, ...] = _sleeve("uk_share")
UK_ETFS: tuple[str, ...] = _sleeve("uk_etf")

# The gauges and the exchange rate. P3 judges in pounds including the currency
# effect, so GBPUSD is not optional. These are not T212 instruments and are marked
# reference-only: we record them, we never trade them.
GAUGES: tuple[str, ...] = ("^FTSE", "^FTMC", "^GSPC", "^VIX")
FX: tuple[str, ...] = ("GBPUSD=X",)

# Confirmed present on T212 because the live practice account held them
# (2026-09-30), kept as the first independent check that the mapping rules work.
SEEN_ON_T212: tuple[str, ...] = (
    "ALCC1_US_EQ", "GEV_US_EQ", "MU_US_EQ", "RXRX_US_EQ", "SPCX_US_EQ",
    "IREN_US_EQ", "3LGO1l_EQ", "SGLNl_EQ", "SNDK1_US_EQ", "TSLA_US_EQ",
)


def recording_list() -> list[tuple[str, str, str]]:
    """(yfinance ticker, market, currency) for everything we record.

    The currency is the one Trading 212 itself quotes the instrument in, taken
    per name from the versioned universe file rather than assumed from the market. London is a
    three-way split and both T212 and yfinance agree on it name by name
    (checked 2026-10-01): most lines are pence (T212 "GBX", yfinance "GBp"),
    nine are pounds, and six are genuinely quoted in US dollars on the LSE --
    CPG.L, AGGG.L, IGLN.L and XDWD.L among them, which pay 0.15% currency
    conversion on BOTH legs. The authority for any one instrument is the
    resolved universe file built by qb2.ingest.verify_universe from Trading
    212's own list; this default exists so that the exceptions show up as
    exceptions. The recorder still fails loudly on a 100x jump.
    """
    entries: list[tuple[str, str, str]] = []
    entries += [(t, "US", quote_currency(t) or "USD") for t in US_SHARES]
    entries += [(t, "LSE", quote_currency(t) or "GBp")
                for t in (*UK_SHARES, *UK_ETFS)]
    entries += [(t, "US" if t in ("^GSPC", "^VIX") else "LSE", "INDEX")
                for t in GAUGES]
    entries += [(t, "US", "FX") for t in FX]
    seen: set[str] = set()
    unique: list[tuple[str, str, str]] = []
    for entry in entries:
        if entry[0] in seen:
            continue
        seen.add(entry[0])
        unique.append(entry)
    return unique


def counts() -> dict[str, int]:
    return {"us_shares": len(US_SHARES), "uk_shares": len(UK_SHARES),
            "uk_etfs": len(UK_ETFS), "gauges": len(GAUGES), "fx": len(FX),
            "total": len(recording_list())}
