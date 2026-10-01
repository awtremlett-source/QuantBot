"""Resolve our names against Trading 212's own instrument list, and keep the proof.

WHY THIS FILE EXISTS. We write down a share as "NWG.L" and assume everyone means
the same thing. Trading 212 does not. Its ``ticker`` field is a *historical*
identifier that it never updates when a company renames itself, so the real list
says:

    Meta Platforms      -> FB_US_EQ     (Facebook)
    RTX                 -> UTX_US_EQ    (United Technologies)
    Booking             -> PCLN_US_EQ   (Priceline)
    Elevance Health     -> ANTM_US_EQ   (Anthem)
    NatWest (London)    -> RBSl_EQ      (Royal Bank of Scotland)

and at the same time it *does* have an instrument whose ticker is ``NWG_US_EQ``:
NatWest's New York listing, priced in dollars. So a program that builds a T212
ticker out of the letters it knows will send an order for the wrong share, in the
wrong currency, on the wrong continent, and nothing downstream will notice --
the prices will look plausible because they are real prices of something else.

So nothing here is constructed. Every name is looked up in the list T212 actually
served, matched on ``shortName`` *and* exchange, and the answer is recorded with
its ISIN. The ISIN is the identity that survives a rename, and comparing it
against a pinned copy is how we find out that a name has become a different
company (see :func:`compare_to_pinned` -- AHT.L is the live example: it is no
longer Ashtead, it is Sunbelt Rentals, on a US ISIN).

Two more things the real list settled:

* **Pence.** T212 quotes 2,420 London instruments in ``GBX`` -- pence -- against
  557 in ``GBP`` and 1,323 in ``USD``. A series that mixes them has a 100x step
  in it, which is why the currency T212 reports is recorded per instrument and
  never inferred from the ".L" suffix.
* **AIM.** T212 names "London Stock Exchange AIM" as a separate exchange, so the
  stamp-duty exemption for AIM shares (docs/t212/FACTS.md row m3) can be read off
  the data instead of guessed.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
T212_RAW = REPO_ROOT / "data" / "raw" / "t212"

LONDON_MAIN = "London Stock Exchange"
LONDON_AIM = "London Stock Exchange AIM"
US_EXCHANGES = frozenset({"NASDAQ", "NYSE"})
# OTC is where the ADRs and the thin names live (LNSTY is "London Stock Exchange
# Group" and ASHTY is Sunbelt). It is never the line we mean, so it is excluded
# rather than ranked.
EXCLUDED_EXCHANGES = frozenset({"OTC Markets"})

PENCE_CODES = frozenset({"GBX", "GBp"})
POUND_CODES = frozenset({"GBP"})
# T212 writes pence "GBX"; yfinance writes the same thing "GBp". One spelling wins
# so the two sources can be compared at all.
SPELLING: Mapping[str, str] = {"GBX": "GBp"}
# The line we want, in order of preference, per market.
PREFERRED_CURRENCY: Mapping[str, tuple[str, ...]] = {
    "LSE": ("GBX", "GBP"),
    "US": ("USD",),
}

REFERENCE_ONLY = "reference only, not tradable"


@dataclass(frozen=True, slots=True)
class Resolved:
    """One of our names, looked up. ``ok`` false always carries a reason."""

    yfinance: str
    market: str
    t212_ticker: str | None = None
    isin: str | None = None
    exchange: str | None = None
    currency: str | None = None
    kind: str | None = None
    name: str | None = None
    aim: bool = False
    ok: bool = True
    reason: str = ""
    note: str = ""

    @property
    def tradable(self) -> bool:
        return self.reason != REFERENCE_ONLY

    @property
    def is_pence(self) -> bool:
        return self.currency in PENCE_CODES

    @property
    def pays_fx_fee(self) -> bool:
        """A London share T212 quotes in dollars costs 0.15% FX on *both* legs."""
        return (self.market == "LSE" and self.currency is not None
                and self.currency not in (PENCE_CODES | POUND_CODES))


def newest_raw(what: str, folder: Path | None = None) -> Path:
    """The most recent saved copy of a T212 list."""
    base = folder or T212_RAW
    candidates = sorted(base.glob(f"{what}-*.json"))
    if not candidates:
        raise FileNotFoundError(
            f"no saved T212 {what} list in {base} -- save one before verifying")
    return candidates[-1]


def load_instruments(folder: Path | None = None) -> list[dict[str, object]]:
    rows = json.loads(newest_raw("instruments", folder).read_text(encoding="utf-8"))
    return [r for r in rows if isinstance(r, dict)]


def load_exchanges(folder: Path | None = None) -> dict[int, str]:
    """workingScheduleId -> exchange name, so an instrument can name its market."""
    rows = json.loads(newest_raw("exchanges", folder).read_text(encoding="utf-8"))
    mapping: dict[int, str] = {}
    for exchange in rows:
        if not isinstance(exchange, dict):
            continue
        label = str(exchange.get("name", "?"))
        for schedule in exchange.get("workingSchedules", []) or []:
            if isinstance(schedule, dict) and "id" in schedule:
                try:
                    mapping[int(schedule["id"])] = label
                except (TypeError, ValueError):
                    continue
    return mapping


def market_symbol(yfinance_symbol: str) -> str:
    """"VOD.L" -> "VOD". The letters a human would read off a screen."""
    return (yfinance_symbol[:-2] if yfinance_symbol.endswith(".L")
            else yfinance_symbol)


def class_key(symbol: str) -> str:
    """One spelling for a share class, because the three sources disagree.

    Berkshire's B shares are "BRK-B" to yfinance, "BRK.B" on Wikipedia and in
    T212's shortName, and "BRK_B_US_EQ" in T212's ticker. BT Group's A shares are
    "BT-A.L", "BT.A" and T212's "BT/A". The separator carries no information, so
    it is flattened before anything is compared.
    """
    return symbol.upper().replace("-", ".").replace("/", ".").replace("_", ".")


def _exchange_of(row: Mapping[str, object],
                 exchanges: Mapping[int, str]) -> str | None:
    schedule = row.get("workingScheduleId")
    if isinstance(schedule, bool) or not isinstance(schedule, (int, float)):
        return None
    return exchanges.get(int(schedule))


def _on_market(exchange: str | None, market: str) -> bool:
    if exchange is None or exchange in EXCLUDED_EXCHANGES:
        return False
    if market == "LSE":
        return exchange in (LONDON_MAIN, LONDON_AIM)
    return exchange in US_EXCHANGES


def resolve_one(yfinance_symbol: str, market: str,
                expected_currency: str,
                by_short: Mapping[str, Sequence[Mapping[str, object]]],
                exchanges: Mapping[int, str]) -> Resolved:
    """Find the one instrument we mean, or say why we cannot. Never guesses."""
    if yfinance_symbol.startswith("^") or yfinance_symbol.endswith("=X"):
        return Resolved(yfinance_symbol, market, ok=True, reason=REFERENCE_ONLY)

    short = class_key(market_symbol(yfinance_symbol))
    candidates = [r for r in by_short.get(short, ())
                  if _on_market(_exchange_of(r, exchanges), market)]
    if not candidates:
        return Resolved(yfinance_symbol, market, ok=False,
                        reason=f"no instrument on {market} with shortName {short!r}")

    if len(candidates) > 1:
        # Prefer the home-currency line; that is the whole point of the rule
        # "the GBP line where one exists".
        for code in PREFERRED_CURRENCY.get(market, ()):
            narrowed = [r for r in candidates
                        if str(r.get("currencyCode")) == code]
            if len(narrowed) == 1:
                candidates = narrowed
                break
        else:
            shown = ", ".join(
                f"{r.get('ticker')}({r.get('currencyCode')})" for r in candidates)
            return Resolved(yfinance_symbol, market, ok=False,
                            reason=f"ambiguous on {market}: {shown} "
                                   "-- resolve by hand, never by guessing")

    found = candidates[0]
    exchange = _exchange_of(found, exchanges)
    currency = str(found.get("currencyCode") or "")
    resolved = Resolved(
        yfinance=yfinance_symbol,
        market=market,
        t212_ticker=str(found.get("ticker")),
        isin=str(found.get("isin") or "") or None,
        exchange=exchange,
        currency=currency,
        kind=str(found.get("type") or "") or None,
        name=str(found.get("name") or "") or None,
        aim=exchange == LONDON_AIM,
        ok=True,
    )

    notes: list[str] = []
    if resolved.pays_fx_fee:
        notes.append(f"T212 quotes this London line in {currency}, not GBP/GBX: "
                     "0.15% FX conversion on BOTH legs (FACTS row l)")
    spelled = SPELLING.get(currency, currency)
    if spelled != expected_currency and not resolved.pays_fx_fee:
        notes.append(f"we expected {expected_currency}, T212 says {currency}")
    if resolved.aim:
        notes.append("AIM: no stamp duty on the buy (FACTS row m3)")
    return (resolved if not notes
            else Resolved(**{**asdict(resolved), "note": "; ".join(notes)}))


def resolve(entries: Sequence[tuple[str, str, str]],
            instruments: Sequence[Mapping[str, object]] | None = None,
            exchanges: Mapping[int, str] | None = None,
            folder: Path | None = None) -> list[Resolved]:
    rows = list(instruments if instruments is not None else load_instruments(folder))
    schedule_names = dict(exchanges if exchanges is not None
                          else load_exchanges(folder))
    by_short: dict[str, list[Mapping[str, object]]] = {}
    for row in rows:
        by_short.setdefault(class_key(str(row.get("shortName"))), []).append(row)
    return [resolve_one(sym, market, currency, by_short, schedule_names)
            for sym, market, currency in entries]


def summarise(results: Sequence[Resolved]) -> dict[str, object]:
    tradable = [r for r in results if r.tradable]
    failed = [r for r in tradable if not r.ok]
    return {
        "checked": len(results),
        "tradable": len(tradable),
        "reference_only": len(results) - len(tradable),
        "resolved": len(tradable) - len(failed),
        "failed": len(failed),
        "pence_quoted": sum(1 for r in tradable if r.is_pence),
        "pound_quoted": sum(1 for r in tradable if r.currency in POUND_CODES),
        "pays_fx_fee": sum(1 for r in tradable if r.pays_fx_fee),
        "aim": sum(1 for r in tradable if r.aim),
        "renamed_by_t212": sum(
            1 for r in tradable
            if r.ok and r.t212_ticker is not None
            and not class_key(str(r.t212_ticker)).startswith(
                class_key(market_symbol(r.yfinance)))),
        "failures": [(r.yfinance, r.reason) for r in failed],
    }


# --- identity, pinned ------------------------------------------------------
# A rename is invisible in prices. The only way we find out that "AHT.L" stopped
# being Ashtead and became Sunbelt Rentals is to write down the ISIN today and
# compare tomorrow. That is what this pair of functions is for.

def pin_identities(results: Sequence[Resolved]) -> dict[str, dict[str, object]]:
    return {r.yfinance: {"t212_ticker": r.t212_ticker, "isin": r.isin,
                         "currency": r.currency, "exchange": r.exchange,
                         "name": r.name}
            for r in results if r.ok and r.tradable}


def compare_to_pinned(results: Sequence[Resolved],
                      pinned: Mapping[str, Mapping[str, object]],
                      ) -> list[tuple[str, str]]:
    """Differences that mean "this is not the share it was". Empty is good."""
    changes: list[tuple[str, str]] = []
    for r in results:
        if not (r.ok and r.tradable):
            continue
        was = pinned.get(r.yfinance)
        if was is None:
            changes.append((r.yfinance, "new name, not in the pinned identities"))
            continue
        for field in ("isin", "t212_ticker", "currency"):
            before, now = was.get(field), getattr(r, field)
            if before != now:
                changes.append(
                    (r.yfinance, f"{field} changed: {before!r} -> {now!r}"
                                 f" (T212 now calls it {r.name!r})"))
    return changes


# --- the plan's rule: "the GBP line where one exists" ----------------------
# A fund often has several London lines that are the SAME fund -- same ISIN,
# different quote currency. Holding the dollar line of a fund costs 0.15% on
# each leg for nothing, and holding two lines of one ISIN is holding the same
# thing twice while believing the risk is spread.

def london_lines_by_isin(
        instruments: Sequence[Mapping[str, object]],
        exchanges: Mapping[int, str]) -> dict[str, list[Mapping[str, object]]]:
    grouped: dict[str, list[Mapping[str, object]]] = {}
    for row in instruments:
        if _exchange_of(row, exchanges) in (LONDON_MAIN, LONDON_AIM):
            grouped.setdefault(str(row.get("isin")), []).append(row)
    return grouped


def sterling_twin(result: Resolved,
                  by_isin: Mapping[str, Sequence[Mapping[str, object]]],
                  ) -> tuple[str, str] | None:
    """The same fund's sterling line, if T212 lists one. (shortName, currency).

    Returns None when there genuinely is no sterling line -- CPG.L, a FTSE 100
    member, is the live example -- in which case the FX fee is simply a real cost
    of owning that name and must be carried, not wished away.
    """
    if not result.pays_fx_fee or result.isin is None:
        return None
    for row in by_isin.get(result.isin, ()):
        code = str(row.get("currencyCode"))
        if code in (PENCE_CODES | POUND_CODES):
            return str(row.get("shortName")), code
    return None


def duplicate_isins(results: Sequence[Resolved]) -> dict[str, list[str]]:
    """Names that are secretly the same instrument. Empty is good.

    IGLN.L and SGLN.L are both iShares Physical Gold, ISIN IE00B4ND3602, one
    quoted in dollars and one in pence. A list holding both looks like two
    holdings and behaves like one.
    """
    seen: dict[str, list[str]] = {}
    for r in results:
        if r.ok and r.tradable and r.isin:
            seen.setdefault(r.isin, []).append(r.yfinance)
    return {isin: names for isin, names in seen.items() if len(names) > 1}
