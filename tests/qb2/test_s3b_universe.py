"""Premortem for the universe: every way a list of names can be quietly wrong.

These tests are written against the failures we actually found on 2026-10-01 while
resolving our own list against Trading 212's, not against imagined ones. Each one
names the mistake it prevents.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from qb2.ingest import constituents, verify_universe as vu

# A miniature instrument list in T212's own shape, holding exactly the traps.
INSTRUMENTS: list[dict[str, object]] = [
    # The rename trap: Meta's T212 ticker is still Facebook's.
    {"ticker": "FB_US_EQ", "shortName": "META", "currencyCode": "USD",
     "type": "STOCK", "isin": "US30303M1027", "name": "Meta Platforms",
     "workingScheduleId": 1},
    # The wrong-share trap: NatWest exists in London AND as a New York ADR.
    {"ticker": "RBSl_EQ", "shortName": "NWG", "currencyCode": "GBX",
     "type": "STOCK", "isin": "GB00BM8PJY71", "name": "NatWest",
     "workingScheduleId": 3},
    {"ticker": "NWG_US_EQ", "shortName": "NWG", "currencyCode": "USD",
     "type": "STOCK", "isin": "US6390572070", "name": "NatWest",
     "workingScheduleId": 2},
    # The OTC trap: a thin ADR wearing a familiar name.
    {"ticker": "LNSTY_US_EQ", "shortName": "LSEGY", "currencyCode": "USD",
     "type": "STOCK", "isin": "US54211Y1073",
     "name": "London Stock Exchange Group", "workingScheduleId": 4},
    # Share classes, spelled three different ways by three sources.
    {"ticker": "BRK_B_US_EQ", "shortName": "BRK.B", "currencyCode": "USD",
     "type": "STOCK", "isin": "US0846707026",
     "name": "Berkshire Hathaway (Class B)", "workingScheduleId": 2},
    {"ticker": "BTl_EQ", "shortName": "BT/A", "currencyCode": "GBX",
     "type": "STOCK", "isin": "GB0030913577", "name": "BT Group",
     "workingScheduleId": 3},
    # One fund, two London lines, one ISIN: holding both is holding it twice.
    {"ticker": "IGLNl_EQ", "shortName": "IGLN", "currencyCode": "USD",
     "type": "ETF", "isin": "IE00B4ND3602", "name": "iShares Physical Gold",
     "workingScheduleId": 3},
    {"ticker": "SGLNl_EQ", "shortName": "SGLN", "currencyCode": "GBX",
     "type": "ETF", "isin": "IE00B4ND3602", "name": "iShares Physical Gold",
     "workingScheduleId": 3},
    # A London share T212 prices in dollars, with no sterling line anywhere.
    {"ticker": "CPGl1_EQ", "shortName": "CPG", "currencyCode": "USD",
     "type": "STOCK", "isin": "GB00BD6K4575", "name": "Compass",
     "workingScheduleId": 3},
    # Two US lines of one name, to force the ambiguity path.
    {"ticker": "DUPE_US_EQ", "shortName": "DUPE", "currencyCode": "USD",
     "type": "STOCK", "isin": "US1", "name": "Duplicated One",
     "workingScheduleId": 1},
    {"ticker": "DUPE2_US_EQ", "shortName": "DUPE", "currencyCode": "USD",
     "type": "STOCK", "isin": "US2", "name": "Duplicated Two",
     "workingScheduleId": 2},
]
EXCHANGES = {1: "NASDAQ", 2: "NYSE", 3: "London Stock Exchange",
             4: "OTC Markets", 5: "London Stock Exchange AIM"}


def resolve_one(symbol: str, market: str, currency: str = "USD") -> vu.Resolved:
    return vu.resolve([(symbol, market, currency)], INSTRUMENTS, EXCHANGES)[0]


def test_a_renamed_company_resolves_to_t212s_old_ticker() -> None:
    """Failure mode: building "META_US_EQ", which T212 has never heard of.

    T212 keeps the ticker a company had when it was listed, so Meta is still
    FB_US_EQ. A constructed ticker would simply 404 -- or worse, hit something.
    """
    meta = resolve_one("META", "US")
    assert meta.ok and meta.t212_ticker == "FB_US_EQ"
    assert meta.isin == "US30303M1027"


def test_a_london_share_never_resolves_to_its_new_york_adr() -> None:
    """The expensive failure: trading NatWest's dollar ADR instead of the share.

    Both lines answer to "NWG". Only the exchange tells them apart, and getting
    it wrong means the wrong currency, the wrong fees and a position nobody
    intended -- at prices that look perfectly plausible.
    """
    london = resolve_one("NWG.L", "LSE", "GBp")
    assert london.ok
    assert london.t212_ticker == "RBSl_EQ"
    assert london.exchange == "London Stock Exchange"
    assert london.currency == "GBX"
    assert london.isin == "GB00BM8PJY71"      # the GB line, not US6390572070

    new_york = resolve_one("NWG", "US")
    assert new_york.ok and new_york.t212_ticker == "NWG_US_EQ"
    assert new_york.isin != london.isin, "these must never resolve to one instrument"


def test_an_otc_line_is_never_chosen() -> None:
    """OTC is where the thin look-alikes live; it is never the line we mean."""
    assert not resolve_one("LSEGY", "US").ok


def test_two_candidates_are_refused_rather_than_guessed_between() -> None:
    """A coin-flip between two real instruments is the worst possible answer."""
    ambiguous = resolve_one("DUPE", "US")
    assert not ambiguous.ok
    assert "ambiguous" in ambiguous.reason
    assert "never by guessing" in ambiguous.reason
    assert "DUPE_US_EQ" in ambiguous.reason and "DUPE2_US_EQ" in ambiguous.reason


@pytest.mark.parametrize(("symbol", "expected"), [
    ("BRK-B", "BRK_B_US_EQ"),      # yfinance spelling
    ("BRK.B", "BRK_B_US_EQ"),      # Wikipedia spelling
])
def test_share_classes_match_whichever_way_they_are_spelled(
        symbol: str, expected: str) -> None:
    """Three sources, three separators, one share. The separator means nothing."""
    assert resolve_one(symbol, "US").t212_ticker == expected


def test_bt_group_matches_t212s_slash_spelling() -> None:
    """T212 writes BT's A shares "BT/A"; yfinance writes "BT-A.L"."""
    result = resolve_one("BT-A.L", "LSE", "GBp")
    assert result.ok and result.t212_ticker == "BTl_EQ"


def test_the_sterling_line_of_a_fund_is_found_by_isin() -> None:
    """The plan's rule: prefer the GBP line where one exists."""
    by_isin = vu.london_lines_by_isin(INSTRUMENTS, EXCHANGES)
    gold = resolve_one("IGLN.L", "LSE", "GBp")
    assert gold.pays_fx_fee, "a USD line held from a GBP account pays the fee"
    twin = vu.sterling_twin(gold, by_isin)
    assert twin == ("SGLN", "GBX")


def test_a_name_with_no_sterling_line_says_so_instead_of_pretending() -> None:
    """CPG.L is a FTSE 100 member T212 prices only in dollars.

    The honest answer is "there is no sterling line and the fee is real", not a
    quiet substitution of some other instrument.
    """
    by_isin = vu.london_lines_by_isin(INSTRUMENTS, EXCHANGES)
    compass = resolve_one("CPG.L", "LSE", "GBp")
    assert compass.ok and compass.pays_fx_fee
    assert vu.sterling_twin(compass, by_isin) is None


def test_two_names_that_are_one_fund_are_reported() -> None:
    """Holding IGLN and SGLN looks like two holdings and behaves like one."""
    results = vu.resolve([("IGLN.L", "LSE", "GBp"), ("SGLN.L", "LSE", "GBp")],
                         INSTRUMENTS, EXCHANGES)
    duplicates = vu.duplicate_isins(results)
    assert duplicates == {"IE00B4ND3602": ["IGLN.L", "SGLN.L"]}


def test_a_company_that_became_a_different_company_is_caught() -> None:
    """AHT.L stopped being Ashtead and became Sunbelt Rentals, on a US ISIN.

    A rename is invisible in prices: the series carries on, the strategy carries
    on, and it is now trading something else. Only a pinned identity catches it.
    """
    results = vu.resolve([("NWG.L", "LSE", "GBp")], INSTRUMENTS, EXCHANGES)
    pinned = vu.pin_identities(results)
    assert pinned["NWG.L"]["isin"] == "GB00BM8PJY71"

    # Same symbol, different company underneath.
    stale = {"NWG.L": {**pinned["NWG.L"], "isin": "GB00SOMETHINGELSE"}}
    changes = vu.compare_to_pinned(results, stale)
    assert changes and "isin changed" in changes[0][1]
    assert vu.compare_to_pinned(results, pinned) == [], "no change must be silent"


def test_a_gauge_is_marked_reference_only_and_never_tradable() -> None:
    for symbol in ("^FTSE", "GBPUSD=X"):
        result = resolve_one(symbol, "US")
        assert result.ok and not result.tradable
        assert result.reason == vu.REFERENCE_ONLY
        assert result.t212_ticker is None


def test_aim_is_recognised_so_stamp_duty_is_not_overcharged() -> None:
    aim = [{"ticker": "ASCl_EQ", "shortName": "ASC", "currencyCode": "GBX",
            "type": "STOCK", "isin": "GB00B07CF030", "name": "ASOS",
            "workingScheduleId": 5}]
    result = vu.resolve([("ASC.L", "LSE", "GBp")], aim, EXCHANGES)[0]
    assert result.ok and result.aim
    assert "AIM" in result.note


# --------------------------------------------------------- the membership parse

def test_the_constituent_parser_does_not_invent_symbols() -> None:
    """A summarising model invented several hundred tickers; a parser cannot.

    This is the reason membership is parsed mechanically. The regex must accept
    real tickers and reject prose, so a table cell containing a sentence can
    never become a holding.
    """
    assert constituents.TICKER.match("AAPL")
    assert constituents.TICKER.match("BRK.B")
    assert constituents.TICKER.match("BT.A")
    for junk in ("Apple Inc.", "the", "", "Information Technology",
                 "TOO-LONG-FOR-A-TICKER", "lower"):
        assert not constituents.TICKER.match(junk), junk


def test_a_table_is_read_by_column_name_not_by_position(tmp_path: Path) -> None:
    """Columns move. Reading the third cell because it was third once is a bug."""
    page = tmp_path / "ftse100-2026-01-01.html"
    page.write_text(
        "<table><tr><th>Company</th><th>FTSE Industry</th><th>Ticker</th></tr>"
        "<tr><td>AstraZeneca</td><td>Health Care</td><td>AZN</td></tr>"
        "<tr><td>BT Group</td><td>Telecoms</td><td>BT.A</td></tr></table>",
        encoding="utf-8")
    assert constituents.ftse100(tmp_path) == ["AZN.L", "BT-A.L"]


def test_the_survivorship_caveat_is_stated_and_says_which_way_it_is_wrong() -> None:
    """A caveat that does not say the direction of the error is decoration."""
    caveat = constituents.SURVIVORSHIP_CAVEAT
    assert "TODAY" in caveat
    assert "biased upward" in caveat or "OPTIMISTIC" in caveat


# ------------------------------------------------------- the built universe files

UNIVERSE = Path(__file__).resolve().parents[2] / "docs" / "universe"


def _newest(prefix: str) -> dict[str, Any]:
    found = sorted(UNIVERSE.glob(f"{prefix}-*.json"))
    if not found:
        pytest.skip(f"no {prefix} file built yet")
    loaded: dict[str, Any] = json.loads(found[-1].read_text(encoding="utf-8"))
    return loaded


def test_the_bot_and_advisor_lists_cannot_overlap() -> None:
    """P6: if both parts held one share, one part's stop would sell the other's."""
    bot = {e["yfinance"] for e in _newest("bot-universe")["entries"]}
    advisor = {e["yfinance"] for e in _newest("advisor-universe")["entries"]}
    assert bot and advisor
    assert not (bot & advisor), f"both lists hold {sorted(bot & advisor)}"


def test_every_traded_name_carries_the_identity_it_was_resolved_to() -> None:
    """A universe entry without an ISIN cannot be checked for a rename later."""
    for which in ("bot-universe", "advisor-universe"):
        for entry in _newest(which)["entries"]:
            assert entry["t212_ticker"], f"{which}: {entry['yfinance']} has no ticker"
            assert entry["isin"], f"{which}: {entry['yfinance']} has no ISIN"
            assert entry["quote_currency"], f"{which}: {entry['yfinance']} has no unit"


def test_the_bot_list_is_agreed_in_the_operators_own_words() -> None:
    """PLAN_V3 S3 requires the bot's list to be AGREED before use.

    Agreed on 2026-10-02. The S4 exit gate asks for three things and this checks
    all three, because "AGREED" on its own is just a word somebody typed: the
    status, the operator's words exactly as they were given, and the date they
    were given on (FRAMEWORK requirements-verbatim).
    """
    bot = _newest("bot-universe")
    assert bot["status"] == "AGREED"
    assert bot["agreed_words_verbatim"] == "GO on bot universe v1"
    assert bot["agreed_on"] == "2026-10-02"
    assert len(bot["entries"]) == 50, "agreement covers exactly the list shown"


def test_being_agreed_does_not_mean_anything_trades() -> None:
    """The dangerous misreading. AGREED is permission to BUILD, not to trade.

    The sender is disarmed in code and S3's own gate is still open; agreeing a
    list changes neither.
    """
    bot = _newest("bot-universe")
    assert "does NOT mean anything trades" in bot["status_means"]

    from qb2.execution import sender
    assert sender.ARMED is False, "a list being agreed must never arm the sender"


def test_a_rebuild_cannot_quietly_cancel_the_agreement(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The silent disarm: a rebuild writes PROPOSED and the S4 gate shuts again.

    Everything reads whichever universe file sorts last, so a newer PROPOSED file
    would override an agreed one with no error and no obvious cause.
    """
    from qb2.tools import build_universe

    monkeypatch.setattr(build_universe, "UNIVERSE", tmp_path)
    (tmp_path / "bot-universe-v1-2026-10-01.json").write_text(
        json.dumps({"status": "AGREED", "agreed_words_verbatim": "GO"}),
        encoding="utf-8")

    recording = {"built": "2026-11-01", "entries": []}
    with pytest.raises(build_universe.AgreementWouldBeLost, match="AGREED"):
        build_universe.write_all(recording)

    # Superseding is allowed, but only when it is asked for out loud.
    written = build_universe.write_all(recording, supersede_agreement=True)
    assert any("bot-universe" in path.name for path in written)


def test_the_bot_sleeves_are_tagged_and_their_costs_written_down() -> None:
    """A sleeve without its cost is a sleeve whose trades cannot be judged."""
    bot = _newest("bot-universe")
    sleeves = {e["sleeve"] for e in bot["entries"]}
    assert sleeves == {"us_liquid", "uk_share", "uk_etf"}
    for sleeve in sleeves:
        assert "%" in bot["why_these_sleeves"][sleeve], sleeve
    # The expensive arm must be labelled as such, or it will be mistaken for a
    # recommendation rather than a measurement.
    assert "MOST" in bot["why_these_sleeves"]["uk_share"].upper()


def test_the_recording_list_records_why_each_name_was_rejected() -> None:
    """"It is not on the list" is not a reason. Every exclusion names itself."""
    recording = _newest("recording-list")
    assert recording["rejected"], "nothing was rejected, which cannot be right"
    for rejection in recording["rejected"]:
        assert rejection["why"].strip(), rejection
    assert recording["survivorship_caveat"]
