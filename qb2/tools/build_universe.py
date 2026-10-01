"""Build the versioned universe files from measured evidence. Run, then read.

This is the only thing that writes ``docs/universe/``. It takes three dated inputs
-- Trading 212's saved instrument list, the saved index-membership pages, and
measured traded value -- and writes out, for every name, the identity it resolved
to and the reason it is in or out. Nothing is chosen by reputation.

Why the files are versioned and dated rather than edited in place: a universe that
changes silently makes every past result unreproducible, and a renamed company
(FACTS row q) is invisible unless yesterday's identity is written down to compare
against.

The bot's list is written with ``status: PROPOSED``. PLAN_V3 S3 requires the bot's
list to be *agreed before use*, so nothing here may be traded on until the
operator says so; the S4 gate refuses to open while the status is PROPOSED.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from qb2.ingest import constituents as C
from qb2.ingest.verify_universe import (PENCE_CODES, Resolved, duplicate_isins,
                                        london_lines_by_isin, load_exchanges,
                                        load_instruments, resolve, sterling_twin)

REPO_ROOT = Path(__file__).resolve().parents[2]
UNIVERSE = REPO_ROOT / "docs" / "universe"

# --- the selection rules, each one a number we measured -----------------------
# Median daily traded value over the last 3 months (close x volume). A floor, not
# a ranking, so the list does not silently change size when the pool does.
US_FLOOR_USD = 800_000_000.0        # 98 of the 503 S&P 500 names clear this
UK_ETF_FLOOR_GBP = 6_000_000.0      # 21 of 1,090 clear it; GBP 2m let in 64
MEASURE_WINDOW = "3 months of daily bars, median of close x volume"

SLEEVES = ("us_liquid", "uk_share", "uk_etf")


def to_gbp(value: float, currency: str) -> float:
    """Pence are not pounds. Ranking without this put GBX names 100x too high."""
    return value / 100.0 if currency in PENCE_CODES else value


def _entry(r: Resolved, measured: Mapping[str, Any] | None,
           sleeve: str, reason: str, flags: Sequence[str]) -> dict[str, Any]:
    return {
        "yfinance": r.yfinance,
        "t212_ticker": r.t212_ticker,
        "isin": r.isin,
        "exchange": r.exchange,
        "quote_currency": r.currency,
        "kind": r.kind,
        "name": r.name,
        "aim": r.aim,
        "sleeve": sleeve,
        "selected_because": reason,
        "measured_daily_value": (None if measured is None
                                 else round(float(measured["median_daily_value"]), 2)),
        "measured_days": None if measured is None else measured["days"],
        "flags": list(flags),
    }


def build(us_measured: Mapping[str, Any], uk_measured: Mapping[str, Any],
          etf_measured: Mapping[str, Any],
          already_recording: Sequence[str] = ()) -> dict[str, Any]:
    instruments = load_instruments()
    exchanges = load_exchanges()
    by_isin = london_lines_by_isin(instruments, exchanges)

    kept: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    # --- US: the S&P 500 pool, cut by a measured floor ---
    us_pool = [(s, "US", "USD") for s in C.sp500()]
    for r in resolve(us_pool, instruments, exchanges):
        m = us_measured.get(r.yfinance)
        if not r.ok:
            rejected.append({"yfinance": r.yfinance, "why": r.reason})
            continue
        if m is None:
            rejected.append({"yfinance": r.yfinance,
                             "why": "no usable price history to measure"})
        elif m["median_daily_value"] >= US_FLOOR_USD:
            kept.append(_entry(r, m, "us_liquid",
                               f"S&P 500 member trading >= ${US_FLOOR_USD/1e9:.1f}bn/day",
                               []))
        else:
            rejected.append({
                "yfinance": r.yfinance,
                "why": (f"traded ${m['median_daily_value']/1e6:,.0f}m/day, under the "
                        f"${US_FLOOR_USD/1e6:,.0f}m floor")})

    # --- UK shares: the whole FTSE 100, because it IS the liquid end of London ---
    for r in resolve([(s, "LSE", "GBp") for s in C.ftse100()],
                     instruments, exchanges):
        if not r.ok:
            rejected.append({"yfinance": r.yfinance, "why": r.reason})
            continue
        flags: list[str] = []
        if r.pays_fx_fee:
            twin = sterling_twin(r, by_isin)
            flags.append(
                f"T212 quotes this in {r.currency}: 0.15% FX on BOTH legs" +
                (f"; a sterling line exists ({twin[0]}.L, {twin[1]}) and should be "
                 "compared before trading this one" if twin else
                 "; T212 lists NO sterling line for it, so the fee is unavoidable"))
        if r.aim:
            flags.append("AIM: exempt from stamp duty (FACTS m3)")
        kept.append(_entry(r, uk_measured.get(r.yfinance), "uk_share",
                           "FTSE 100 member", flags))

    # --- UK ETFs: measured, sterling-quoted, one line per fund ---
    etf_ranked = sorted(etf_measured.items(),
                        key=lambda kv: -to_gbp(kv[1]["median_daily_value"],
                                               kv[1]["currency"]))
    chosen_isins: set[str] = set()
    etf_names: list[str] = []
    for sym, m in etf_ranked:
        gbp = to_gbp(m["median_daily_value"], m["currency"])
        if gbp < UK_ETF_FLOOR_GBP:
            break
        if m["isin"] in chosen_isins:
            rejected.append({"yfinance": sym,
                             "why": f"same fund as one already chosen (ISIN {m['isin']})"})
            continue
        chosen_isins.add(str(m["isin"]))
        etf_names.append(sym)

    etf_resolved = resolve([(s, "LSE", "GBp") for s in etf_names],
                           instruments, exchanges)
    for r in etf_resolved:
        if not r.ok:
            rejected.append({"yfinance": r.yfinance, "why": r.reason})
            continue
        m = etf_measured.get(r.yfinance)
        gbp = to_gbp(float(m["median_daily_value"]), str(m["currency"])) if m else 0.0
        kept.append(_entry(r, m, "uk_etf",
                           f"sterling London ETF trading >= GBP "
                           f"{UK_ETF_FLOOR_GBP/1e6:.0f}m/day (GBP {gbp/1e6:.2f}m)",
                           ["AIM" ] if r.aim else []))

    # --- names we have already been recording, so history is not abandoned ---
    chosen = {e["yfinance"] for e in kept}
    carried = [s for s in already_recording if s not in chosen]

    return {
        "version": "v2",
        "built": date.today().isoformat(),
        "measure_window": MEASURE_WINDOW,
        "rules": {
            "us": f"S&P 500 member with median daily traded value >= ${US_FLOOR_USD:,.0f}",
            "uk_share": "FTSE 100 member, verified present on Trading 212",
            "uk_etf": (f"London ETF quoted in sterling, >= GBP {UK_ETF_FLOOR_GBP:,.0f}"
                       "/day, one line per ISIN, no leveraged or short products"),
        },
        "survivorship_caveat": C.SURVIVORSHIP_CAVEAT,
        "entries": kept,
        "rejected": rejected,
        "already_recording_not_reselected": carried,
        "duplicate_isins": duplicate_isins(
            [r for r in resolve([(e["yfinance"],
                                  "LSE" if e["sleeve"] != "us_liquid" else "US",
                                  "GBp") for e in kept], instruments, exchanges)]),
    }


# --- the two lists P6 cares about --------------------------------------------
# The bot gets the cheapest, most-traded names because it trades SAME DAY and
# pays the costs twice in one day. The advisor holds for weeks to twelve months,
# so a slightly thinner name costs it far less. The two lists must never overlap:
# if both parts held one share, the bot's stop would sell the advisor's holding
# (P6), and the advisor would be left with a position nobody decided to close.
BOT_SLEEVE_SIZES = {"us_liquid": 30, "uk_etf": 10, "uk_share": 10}


def _by_measured(entries: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    def key(e: Mapping[str, Any]) -> float:
        value = e.get("measured_daily_value")
        if value is None:
            return 0.0
        return to_gbp(float(value), str(e.get("quote_currency")))
    return sorted(entries, key=key, reverse=True)


def split_lists(recording: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Propose the bot's list; give the advisor everything else that qualifies."""
    entries: list[Mapping[str, Any]] = list(recording["entries"])
    bot: list[Mapping[str, Any]] = []
    for sleeve, size in BOT_SLEEVE_SIZES.items():
        in_sleeve = [e for e in entries if e["sleeve"] == sleeve]
        bot.extend(_by_measured(in_sleeve)[:size])

    bot_names = {e["yfinance"] for e in bot}
    advisor = [e for e in entries if e["yfinance"] not in bot_names]

    bot_doc = {
        "list": "bot",
        "version": "v1",
        "built": recording["built"],
        "status": "PROPOSED",
        "status_means": (
            "PROPOSED means NOT AGREED and NOT tradable. PLAN_V3 S3 requires the "
            "bot's list to be agreed before use, so the S4 gate stays shut while "
            "this says PROPOSED. Changing it is the operator's decision, recorded "
            "in their own words."),
        "share_of_pot": "30%",
        "horizon": "same day (P4)",
        "sleeve_sizes": dict(BOT_SLEEVE_SIZES),
        "why_these_sleeves": {
            "us_liquid": ("0.40% round trip at 1x costs, 0.80% at 2x. No stamp "
                          "duty, but 0.15% currency conversion on each leg."),
            "uk_etf": ("0.20% round trip at 1x, 0.40% at 2x -- the CHEAPEST thing "
                       "available, because ETFs pay no stamp duty (FACTS m2) and "
                       "sterling lines pay no conversion fee."),
            "uk_share": ("0.70% round trip at 1x, 1.40% at 2x -- the MOST "
                         "EXPENSIVE, because stamp duty takes 0.5% of every buy "
                         "(FACTS m1). Carried deliberately as the expensive arm so "
                         "P17 is settled by measurement rather than by preference. "
                         "A same-day signal here must clear 0.7% before it earns "
                         "anything at all."),
        },
        "entries": bot,
    }
    advisor_doc = {
        "list": "advisor",
        "version": "v1",
        "built": recording["built"],
        "status": "DERIVED",
        "status_means": ("Derived by subtraction from the recording list, so it "
                         "cannot overlap the bot's list by construction. P6 also "
                         "requires every member to pass the liquidity filter, "
                         "which it does: membership of the recording list IS the "
                         "filter."),
        "share_of_pot": "70%",
        "horizon": "weeks to 12 months; suggests only, never trades (P1)",
        "entries": advisor,
    }
    return bot_doc, advisor_doc


class AgreementWouldBeLost(RuntimeError):
    """Refusing to write a proposed list over an agreed one."""


def agreed_bot_lists() -> list[Path]:
    """Any bot list the operator has already agreed to."""
    found: list[Path] = []
    for path in sorted(UNIVERSE.glob("bot-universe-*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(doc, dict) and doc.get("status") == "AGREED":
            found.append(path)
    return found


def write_all(recording: Mapping[str, Any], *,
              supersede_agreement: bool = False) -> list[Path]:
    """Write the three files. Refuses to disarm an agreed list by accident.

    The danger this closes: ``build_universe`` always writes its bot list as
    PROPOSED, and the rest of the code reads whichever file sorts last. So a
    rebuild would quietly replace an AGREED list with a PROPOSED one -- or, on the
    same date, overwrite it outright -- and the only visible symptom would be the
    S4 gate closing again for reasons nobody could explain.

    Superseding is a decision, so it has to be asked for, and it needs a fresh
    agreement in the operator's own words afterwards.
    """
    UNIVERSE.mkdir(parents=True, exist_ok=True)
    stamp = recording["built"]
    bot_doc, advisor_doc = split_lists(recording)

    already = agreed_bot_lists()
    if already and not supersede_agreement:
        names = ", ".join(path.name for path in already)
        raise AgreementWouldBeLost(
            f"the operator has AGREED {names}, and this rebuild would write a "
            "PROPOSED list that supersedes it. Rebuilding the universe is a new "
            "decision: pass supersede_agreement=True only when the operator has "
            "asked for a new list, and record their words on the new file")
    written: list[Path] = []
    for name, doc in (("recording-list-v2", recording),
                      ("bot-universe-v1", bot_doc),
                      ("advisor-universe-v1", advisor_doc)):
        path = UNIVERSE / f"{name}-{stamp}.json"
        path.write_text(json.dumps(doc, indent=1, ensure_ascii=True) + "\n",
                        encoding="utf-8")
        written.append(path)
    return written


def main() -> None:
    liquidity = json.loads(
        (REPO_ROOT / "data" / "raw" / "reference"
         / f"liquidity-{date.today().isoformat()}.json").read_text(encoding="utf-8"))
    from qb2.ingest import tickers
    already = [t for t, _, _ in tickers.recording_list()]
    recording = build(liquidity["us"], liquidity["uk_shares"],
                      liquidity["uk_etfs"], already)
    try:
        written = write_all(recording)
    except AgreementWouldBeLost as refusal:
        print(f"REFUSED: {refusal}")
        raise SystemExit(1) from None
    for path in written:
        print(f"wrote {path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
