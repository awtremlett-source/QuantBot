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

The other gap, stated plainly: this key cannot read T212's instrument list (it
returns 403 -- docs/t212/FACTS.md, key permissions). So membership of the
recording list is **not verified against T212** except for the instruments seen
in the live account. Everything else is marked unverified rather than assumed.
"""

from __future__ import annotations

from dataclasses import dataclass

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
# PROVISIONAL and deliberately wide: this is what gets RECORDED, which is not the
# same as what gets TRADED. S3b picks the bot's universe out of this, under
# PROPOSE->GO. Recording something we never trade costs disk; failing to record
# something we later want costs the data permanently (FACTS row n).

# Liquid US names. yfinance symbols; T212 membership UNVERIFIED (403 on the
# instrument list) except where the live account proved it.
US_SHARES: tuple[str, ...] = (
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "LLY",
    "JPM", "V", "XOM", "UNH", "MA", "COST", "HD", "PG", "JNJ", "ABBV", "WMT",
    "MRK", "NFLX", "AMD", "PEP", "KO", "ADBE", "CRM", "TMO", "CSCO", "ACN",
    "MCD", "LIN", "ABT", "DHR", "INTC", "WFC", "TXN", "VZ", "QCOM", "PM",
    "CAT", "IBM", "GE", "NOW", "AMGN", "UBER", "MS", "RTX", "NEE", "SPGI",
    "ISRG", "BKNG", "GS", "PFE", "T", "LOW", "BLK", "SYK", "ELV", "PLD",
    "MU", "GEV", "IREN", "RXRX",
)

# FTSE-100 names (a representative, liquid subset) and UK-listed ETFs, all in
# pence or pounds on the LSE -- which is exactly why the unit check exists.
UK_SHARES: tuple[str, ...] = (
    "AZN.L", "SHEL.L", "HSBA.L", "ULVR.L", "RIO.L", "BP.L", "GSK.L", "REL.L",
    "BATS.L", "DGE.L", "GLEN.L", "AAL.L", "NG.L", "LSEG.L", "VOD.L", "BARC.L",
    "LLOY.L", "NWG.L", "PRU.L", "TSCO.L", "IMB.L", "CPG.L", "AHT.L", "SSE.L",
    "III.L", "ANTO.L", "SGRO.L", "STAN.L", "WTB.L", "SMIN.L",
)
UK_ETFS: tuple[str, ...] = (
    "ISF.L", "VUKE.L", "VWRL.L", "VUSA.L", "CSP1.L", "SWDA.L", "EQQQ.L",
    "IWDG.L", "VMID.L", "IUSA.L", "SGLN.L", "IGLN.L", "VFEM.L", "VJPN.L",
    "VERX.L", "IEUR.L", "XDWD.L", "AGGG.L", "VGOV.L", "IBTM.L",
)

# The gauges and the exchange rate. P3 judges in pounds including the currency
# effect, so GBPUSD is not optional.
GAUGES: tuple[str, ...] = ("^FTSE", "^FTMC", "^GSPC", "^VIX")
FX: tuple[str, ...] = ("GBPUSD=X",)

# Confirmed present on T212 because the live practice account held them
# (2026-09-30). The only T212-verified members of this list.
SEEN_ON_T212: tuple[str, ...] = (
    "ALCC1_US_EQ", "GEV_US_EQ", "MU_US_EQ", "RXRX_US_EQ", "SPCX_US_EQ",
    "IREN_US_EQ", "3LGO1l_EQ", "SGLNl_EQ", "SNDK1_US_EQ", "TSLA_US_EQ",
)


def recording_list() -> list[tuple[str, str, str]]:
    """(yfinance ticker, market, currency) for everything we record.

    Currency is the *expected* one. The recorder records what actually arrives
    and fails loudly on a 100x jump, because London prices come in pence from
    some sources and pounds from others.
    """
    entries: list[tuple[str, str, str]] = []
    entries += [(t, "US", "USD") for t in US_SHARES]
    entries += [(t, "LSE", "GBP") for t in (*UK_SHARES, *UK_ETFS)]
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
