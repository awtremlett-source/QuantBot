"""Premortem for dividends, total return in pounds, and the minute-label rule.

Three kinds of mistake are possible here and all three are silent:

* a **units** error, where a pence dividend meets a pound price and a normal
  quarter looks like a 112% yield -- or, worse, the other way round;
* a **double count**, where dividends are added to a price series that already
  includes them, flattering every back-test by the yield;
* a **look-ahead**, where a payout that had not gone ex yet is handed to a
  strategy pretending to stand in the past.

The fourth is new in this box: a usage rule quietly becoming a way to make a gate
pass. The labels must never shrink the census's denominator.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from qb2.data import access
from qb2.ingest import daily, dividends
from qb2.research import total_return as tr

UTC = timezone.utc
REPO_ROOT = Path(__file__).resolve().parents[2]


def daily_frame(start: str, closes: list[float], currency: str = "USD",
                ) -> pd.DataFrame:
    index = pd.date_range(start, periods=len(closes), freq="D", name="date")
    return pd.DataFrame({
        "open": closes, "high": [c * 1.01 for c in closes],
        "low": [c * 0.99 for c in closes], "close": closes,
        "volume": [1_000] * len(closes), "currency": currency}, index=index)


def payout_table(symbol: str, rows: list[tuple[str, float]], currency: str = "USD",
                 verdict: str = "OK",
                 knowable: str = "2000-01-01T00:00:00+00:00") -> pd.DataFrame:
    return pd.DataFrame([{
        "symbol": symbol, "ex_date": when, "amount": amount, "currency": currency,
        "verdict": verdict, "when": "past", "knowable_time": knowable,
    } for when, amount in rows])


# ======================================================== units at the boundary

def test_a_pence_dividend_is_converted_like_the_price_it_came_from(
        tmp_path: Path) -> None:
    """BP pays 6.2 PENCE against a share quoted at 557 PENCE -- a 1.1% quarter.

    Convert the price to pounds and leave the dividend alone and the same payment
    reads as 112% of the share price, every quarter, for every London payer. The
    conversion has to happen to both or neither.
    """
    clean = tmp_path / "clean"
    (clean / "daily").mkdir(parents=True)
    # The clean store already holds the PRICE in pounds: 557.80p -> 5.578.
    daily_frame("2026-08-10", [5.578] * 5, "GBP").to_parquet(
        clean / "daily" / "BP.L.parquet")

    series = pd.Series([6.226], index=pd.DatetimeIndex(["2026-08-13"]))
    rows = dividends.to_rows("BP.L", "LSE", "GBp", series,
                             datetime(2026, 10, 3, tzinfo=UTC), clean_root=clean)

    assert rows["amount"].iloc[0] == pytest.approx(0.06226)
    assert rows["currency"].iloc[0] == "GBP"
    assert rows["yield_of_price"].iloc[0] == pytest.approx(0.06226 / 5.578, rel=1e-6)
    assert rows["verdict"].iloc[0] == "OK"


def test_a_pence_dividend_left_unconverted_is_caught(tmp_path: Path) -> None:
    """The planted error: the price converted, the dividend not.

    This is the 100x mistake, and the yield check is what stands between it and
    the store. 6.226 against a GBP 5.578 share is 112% -- impossible for a
    quarterly payout, and flagged.
    """
    clean = tmp_path / "clean"
    (clean / "daily").mkdir(parents=True)
    daily_frame("2026-08-10", [5.578] * 5, "GBP").to_parquet(
        clean / "daily" / "BP.L.parquet")

    series = pd.Series([6.226], index=pd.DatetimeIndex(["2026-08-13"]))
    # "USD" here stands for "nobody converted this": the pence value goes in raw.
    rows = dividends.to_rows("BP.L", "LSE", "USD", series,
                             datetime(2026, 10, 3, tzinfo=UTC), clean_root=clean)

    assert rows["verdict"].iloc[0] == "SUSPECT"
    assert rows["yield_of_price"].iloc[0] > 1.0
    assert "units error" in rows["why"].iloc[0]


def test_a_special_dividend_is_flagged_and_kept_not_dropped(
        tmp_path: Path) -> None:
    """A real 20% special payout trips the same check, and that is correct.

    The honest response is to mark it SUSPECT and keep it for a human, not to
    silently keep it (hiding a possible units error) and not to drop it (losing a
    real payment).
    """
    clean = tmp_path / "clean"
    (clean / "daily").mkdir(parents=True)
    daily_frame("2026-08-10", [100.0] * 5).to_parquet(
        clean / "daily" / "XYZ.parquet")

    series = pd.Series([20.0], index=pd.DatetimeIndex(["2026-08-13"]))
    rows = dividends.to_rows("XYZ", "US", "USD", series,
                             datetime(2026, 10, 3, tzinfo=UTC), clean_root=clean)

    assert rows["verdict"].iloc[0] == "SUSPECT"
    assert len(rows) == 1, "it is kept, not dropped"
    assert "special dividend" in rows["why"].iloc[0]
    assert rows["amount"].iloc[0] == 20.0, "and it is not 'corrected'"


def test_a_payout_with_no_price_to_check_against_says_so(tmp_path: Path) -> None:
    """Silence is not a pass. With no close, the verdict is UNCHECKED."""
    clean = tmp_path / "clean"
    (clean / "daily").mkdir(parents=True)
    series = pd.Series([0.26], index=pd.DatetimeIndex(["2020-01-02"]))
    rows = dividends.to_rows("NOPRICE", "US", "USD", series,
                             datetime(2026, 10, 3, tzinfo=UTC), clean_root=clean)
    assert rows["verdict"].iloc[0] == "UNCHECKED"


# ============================================================== knowable time

def test_a_future_dividend_cannot_leak_into_a_backtest(tmp_path: Path) -> None:
    """Earnings dates move and so do dividends. A payout is knowable when it goes
    ex, not when we happened to download it."""
    clean = tmp_path / "clean"
    (clean / "daily").mkdir(parents=True)
    daily_frame("2026-09-01", [100.0] * 40).to_parquet(
        clean / "daily" / "XYZ.parquet")

    fetched = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)
    series = pd.Series([1.0, 1.0],
                       index=pd.DatetimeIndex(["2026-09-10", "2026-12-10"]))
    rows = dividends.to_rows("XYZ", "US", "USD", series, fetched,
                             clean_root=clean, now=fetched)

    assert list(rows["when"]) == ["past", "announced"]
    # The past one became knowable at the opening bell on its ex-date...
    assert rows["knowable_time"].iloc[0].startswith("2026-09-10")
    # ...and the future one only when we fetched it.
    assert rows["knowable_time"].iloc[1] == fetched.isoformat()

    standing_in_august = fetched - timedelta(days=60)
    assert len(dividends.knowable_at(rows, standing_in_august)) == 0
    assert len(dividends.knowable_at(rows, fetched)) == 2


def test_a_past_dividend_is_not_knowable_the_morning_before(
        tmp_path: Path) -> None:
    """The ex-date's OPENING bell, not midnight: a backtest standing at the
    previous close must not see it."""
    clean = tmp_path / "clean"
    (clean / "daily").mkdir(parents=True)
    daily_frame("2026-09-01", [100.0] * 40).to_parquet(
        clean / "daily" / "XYZ.parquet")
    fetched = datetime(2026, 10, 3, tzinfo=UTC)
    series = pd.Series([1.0], index=pd.DatetimeIndex(["2026-09-10"]))
    rows = dividends.to_rows("XYZ", "US", "USD", series, fetched,
                             clean_root=clean, now=fetched)

    night_before = datetime(2026, 9, 10, 4, 0, tzinfo=UTC)   # before 09:30 ET
    assert len(dividends.knowable_at(rows, night_before)) == 0
    after_the_bell = datetime(2026, 9, 10, 14, 0, tzinfo=UTC)
    assert len(dividends.knowable_at(rows, after_the_bell)) == 1


# ======================================================== accumulating ETFs

def test_an_accumulating_etf_is_marked_from_evidence_not_assumption() -> None:
    """Two things must agree: no payouts in the whole history AND the fund's own
    name saying it accumulates. One without the other is UNKNOWN."""
    assert access is not None       # module imports cleanly
    assert dividends.looks_accumulating("Vanguard FTSE All-World (Acc)")
    assert dividends.looks_accumulating("iShares Core MSCI World Accumulating")
    assert not dividends.looks_accumulating("iShares Core FTSE 100 (Dist)")
    assert not dividends.looks_accumulating("Vanguard S&P 500")


def test_an_etf_with_no_payouts_and_no_acc_in_its_name_is_unknown(
        tmp_path: Path) -> None:
    clean = tmp_path / "clean"
    entries = [
        {"yfinance": "ACCFUND.L", "sleeve": "uk_etf", "kind": "ETF",
         "name": "Vanguard FTSE All-World (Acc)", "quote_currency": "GBP"},
        {"yfinance": "MYSTERY.L", "sleeve": "uk_etf", "kind": "ETF",
         "name": "Some Fund", "quote_currency": "GBP"},
    ]
    out = dividends.collect(entries, fetch=lambda s: None, clean_root=clean)
    statuses = {c.symbol: c.status for c in out.coverage}
    assert statuses["ACCFUND.L"] == "ACC: N/A"
    assert statuses["MYSTERY.L"] == "UNKNOWN"

    text = dividends.report(out)
    assert "UNKNOWN" in text and "MYSTERY.L" in text
    assert "MISSING" not in text, "an accumulating ETF is not missing data"


def test_a_throttled_fetch_is_recorded_not_faked(tmp_path: Path) -> None:
    """Yahoo throttles without saying so. A gap is a gap, by name."""
    def throttled(symbol: str) -> pd.Series:
        raise RuntimeError("429 Too Many Requests")

    out = dividends.collect(
        [{"yfinance": "AAA", "sleeve": "us_liquid", "kind": "STOCK",
          "name": "A", "quote_currency": "USD"}],
        fetch=throttled, clean_root=tmp_path / "clean")
    assert out.coverage[0].status == "MISSING"
    assert "429" in out.coverage[0].reason
    assert list((tmp_path / "clean").rglob("*.parquet")) == []


# ========================================================== total return (P3)

def test_a_us_payer_total_return_matches_a_hand_calculation() -> None:
    """Birth certificate 1 of 3, computed by hand.

    Buy at $100 when a pound buys $1.25, so the holding costs GBP 80.00.
    It ends at $110 when a pound buys $1.10, so the shares are worth GBP 100.00.
    One dividend of $2.00 goes ex when the rate is $1.20, worth GBP 1.666667.
    Gross = (100.00 + 1.666667) / 80.00 - 1 = +27.0833%.
    Net of 15% US withholding: dividend GBP 1.416667,
    (100.00 + 1.416667) / 80.00 - 1 = +26.7708%.
    """
    prices = daily_frame("2026-01-01", [100.0] + [105.0] * 29 + [110.0])
    fx = pd.DataFrame(
        {"close": [1.25] + [1.20] * 29 + [1.10]},
        index=pd.date_range("2026-01-01", periods=31, freq="D"))
    payouts = payout_table("AAA", [("2026-01-15", 2.0)])

    held = tr.holding_return("AAA", "2026-01-01", "2026-01-31",
                             prices=prices, payouts=payouts, fx=fx)

    assert held.start_value_gbp == pytest.approx(80.0)
    assert held.dividends_gbp_gross == pytest.approx(2.0 / 1.20)
    assert held.total_return_gross == pytest.approx(0.2708333, abs=1e-6)
    assert held.total_return_net == pytest.approx(0.2677083, abs=1e-6)
    # The share rose 10% in dollars but the pound figure is far higher, because
    # the dollar strengthened against the pound. That IS the currency effect.
    assert held.price_return_local == pytest.approx(0.10)


def test_a_uk_payer_in_pence_total_return_matches_a_hand_calculation() -> None:
    """Birth certificate 2 of 3. No currency effect, and no withholding.

    The clean store holds pounds: 500p is GBP 5.00, rising to GBP 5.50.
    One dividend of 6.25p is GBP 0.0625.
    Gross = (5.50 + 0.0625) / 5.00 - 1 = +11.25%, and net is the same, because
    the UK withholds nothing at source.
    """
    prices = daily_frame("2026-01-01", [5.00] * 30 + [5.50], currency="GBP")
    payouts = payout_table("BP.L", [("2026-01-15", 0.0625)], currency="GBP")

    held = tr.holding_return("BP.L", "2026-01-01", "2026-01-31",
                             prices=prices, payouts=payouts, fx=None)

    assert held.rate_start == 1.0 and held.rate_end == 1.0
    assert held.total_return_gross == pytest.approx(0.1125, abs=1e-9)
    assert held.total_return_net == pytest.approx(0.1125, abs=1e-9), (
        "the UK withholds nothing at source")
    assert held.currency_effect == pytest.approx(0.0)


def test_a_non_payer_total_return_is_just_the_price() -> None:
    """Birth certificate 3 of 3: no dividends, so nothing may be added."""
    prices = daily_frame("2026-01-01", [200.0] * 30 + [220.0], currency="GBP")
    held = tr.holding_return("NVDA.L", "2026-01-01", "2026-01-31",
                             prices=prices, payouts=None, fx=None)
    assert held.payments == 0
    assert held.dividends_gbp_gross == 0.0
    assert held.total_return_gross == pytest.approx(0.10)
    assert held.total_return_gross == held.total_return_net


def test_the_birth_certificate_goes_red_on_a_pence_pounds_error() -> None:
    """Prove the hand-calculation would CATCH the units mistake.

    If the dividend were left in pence (6.25) beside a GBP 5.00 price, the total
    return would read +135% instead of +11.25%. A test that cannot tell those
    apart is not checking anything.
    """
    prices = daily_frame("2026-01-01", [5.00] * 30 + [5.50], currency="GBP")
    planted = payout_table("BP.L", [("2026-01-15", 6.25)], currency="GBP")

    held = tr.holding_return("BP.L", "2026-01-01", "2026-01-31",
                             prices=prices, payouts=planted, fx=None)

    assert held.total_return_gross > 1.0
    assert held.total_return_gross != pytest.approx(0.1125, abs=1e-3)


def test_adding_dividends_to_an_adjusted_close_is_refused() -> None:
    """Double counting, the mistake that makes every back-test look better.

    Adj Close already has dividends reinvested. Adding our table to it counts
    them twice, and the result looks perfectly reasonable -- just wrong, always in
    the same direction.
    """
    frame = daily_frame("2026-01-01", [100.0] * 31)
    frame["Adj Close"] = frame["close"] * 1.02
    with pytest.raises(tr.TotalReturnError, match="count every payout twice"):
        tr.refuse_adjusted_close(frame)
    with pytest.raises(tr.TotalReturnError):
        tr.holding_return("AAA", "2026-01-01", "2026-01-31", prices=frame,
                          payouts=None, fx=None)


def test_the_clean_daily_store_never_holds_an_adjusted_close() -> None:
    """The structural half of the guard: the column is never saved at all."""
    assert "adj close" not in [c.lower() for c in daily.COLUMNS]
    stored = sorted((REPO_ROOT / "data" / "clean" / "daily").glob("*.parquet"))
    if not stored:
        pytest.skip("no daily store yet")
    columns = [c.lower() for c in pd.read_parquet(stored[0]).columns]
    assert not any("adj" in c for c in columns), columns


def test_withholding_is_a_named_assumption_not_a_buried_number() -> None:
    """Whoever reads a net figure must be able to see what was assumed."""
    assert tr.WITHHOLDING["US"] == 0.15
    assert tr.WITHHOLDING["LSE"] == 0.0
    assert "W-8BEN" in tr.WITHHOLDING_BASIS
    assert "NEITHER IS CONFIRMED" in tr.WITHHOLDING_BASIS


def test_a_dividend_is_converted_at_its_own_dates_rate() -> None:
    """Payments months apart met different rates; today's rate is not theirs."""
    prices = daily_frame("2026-01-01", [100.0] * 31)
    fx = pd.DataFrame({"close": [1.00] * 10 + [2.00] * 21},
                      index=pd.date_range("2026-01-01", periods=31, freq="D"))
    payouts = payout_table("AAA", [("2026-01-05", 1.0), ("2026-01-25", 1.0)])

    held = tr.holding_return("AAA", "2026-01-01", "2026-01-31",
                             prices=prices, payouts=payouts, fx=fx)
    # One pound at a rate of 1.00, one at 2.00: 1.0 + 0.5, not 2 x either.
    assert held.dividends_gbp_gross == pytest.approx(1.5)


def test_a_dollar_holding_cannot_be_priced_in_pounds_without_a_rate() -> None:
    prices = daily_frame("2026-01-01", [100.0] * 31)
    with pytest.raises(tr.TotalReturnError, match="no GBP/USD"):
        tr.holding_return("AAA", "2026-01-01", "2026-01-31", prices=prices,
                          payouts=None, fx=pd.DataFrame())


# ========================================================= the minute label

def test_the_default_label_is_the_cautious_one() -> None:
    """A name nobody has judged is FIVE_MIN_ONLY, not MINUTE_OK."""
    assert access.label_for("NEVER-SEEN", labels={}) == access.FIVE_MIN_ONLY


class FakeName:
    def __init__(self, symbol: str, passes: bool, sessions: int,
                 reasons: tuple[str, ...] = (), last_bar: str | None = None) -> None:
        self.last_bar = last_bar        # QT-13b: a pass counts only on newer bars
        self.symbol = symbol
        self.passes = passes
        self.sessions_present = sessions
        self.reasons = reasons


class FakeCensus:
    def __init__(self, names: list[FakeName], taken: str) -> None:
        self.names = names
        self.taken = taken


def test_promotion_needs_two_passes_so_a_label_does_not_flip_on_noise() -> None:
    """One quiet day must not promote a name, and one busy day must not either."""
    first = access.update_labels(
        FakeCensus([FakeName("AAA", True, 30, last_bar="2026-10-01 19:59")],
                   "2026-10-01T20:00:00"))
    assert first["AAA"].label == access.FIVE_MIN_ONLY
    assert first["AAA"].consecutive_passes == 1

    second = access.update_labels(
        FakeCensus([FakeName("AAA", True, 30, last_bar="2026-10-02 19:59")],
                   "2026-10-02T20:00:00"), first)
    assert second["AAA"].label == access.MINUTE_OK
    assert second["AAA"].consecutive_passes == 2
    assert second["AAA"].census_date == "2026-10-02"


def test_demotion_is_immediate_because_the_data_already_changed() -> None:
    promoted = {"AAA": access.Label("AAA", access.MINUTE_OK, "", "x", "x", 5, 30)}
    after = access.update_labels(
        FakeCensus([FakeName("AAA", False, 30, ("only 55% of the bars",))],
                   "2026-10-03T20:00:00"), promoted)
    assert after["AAA"].label == access.FIVE_MIN_ONLY
    assert after["AAA"].consecutive_passes == 0
    assert "55%" in after["AAA"].reason


def test_too_little_history_stays_cautious_however_well_it_scores() -> None:
    """A name with three days of minute data has not earned a promotion."""
    labels = access.update_labels(
        FakeCensus([FakeName("NEW", True, 3)], "2026-10-02T20:00:00"))
    assert labels["NEW"].label == access.FIVE_MIN_ONLY
    assert "fewer than the" in labels["NEW"].reason


def test_the_label_records_which_census_it_came_from() -> None:
    labels = access.update_labels(
        FakeCensus([FakeName("AAA", True, 30)], "2026-10-02T20:00:00"))
    assert labels["AAA"].census_taken == "2026-10-02T20:00:00"
    assert labels["AAA"].census_date == "2026-10-02"


def test_a_label_can_never_shrink_the_gate(tmp_path: Path) -> None:
    """THE thing this rule must never become: a back door around the 95% bar.

    PLAN_V3 measures the census over every name in the active universe. If
    labelling could remove names from that count, a gate could be made to pass by
    relabelling rather than by fixing the data.
    """
    names = [FakeName("AAA", True, 30), FakeName("BBB", False, 30),
             FakeName("CCC", True, 2)]
    census = FakeCensus(names, "2026-10-02T20:00:00")
    labels = access.update_labels(census)

    assert access.census_unchanged_by_labels(census)
    assert len(census.names) == 3, "the census still counts every name"
    assert sum(1 for v in labels.values() if v.label == access.MINUTE_OK) == 0
    # The label file is separate from the census: one cannot edit the other.
    saved = access.save_labels(labels, tmp_path / "labels.json")
    body = json.loads(saved.read_text(encoding="utf-8"))
    assert "changes no gate" in body["rule"]


def test_asking_for_minute_bars_on_a_five_min_only_name_is_refused(
        tmp_path: Path) -> None:
    """The enforcement. A series full of real gaps must not reach a strategy."""
    clean = tmp_path / "clean"
    for interval in ("1m", "5m"):
        folder = clean / "bars" / interval / "THIN.L"
        folder.mkdir(parents=True)
        index = pd.date_range("2026-10-01 08:00", periods=10, freq="1min",
                              tz="Europe/London", name="ts")
        pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
                      "volume": 1, "currency": "GBP"}, index=index
                     ).to_parquet(folder / "2026-10-01.parquet")

    labels = {"THIN.L": access.Label("THIN.L", access.FIVE_MIN_ONLY,
                                     "failed the minute census", "x", "x", 0, 30)}
    with pytest.raises(access.AccessRefused, match="FIVE_MIN_ONLY"):
        access.bars("THIN.L", "1m", clean_root=clean, labels=labels)

    # The same name at five minutes is fine -- that is the point of the label.
    frame = access.bars("THIN.L", "5m", clean_root=clean, labels=labels)
    assert len(frame) == 10


def test_a_minute_ok_name_can_be_read_at_one_minute(tmp_path: Path) -> None:
    """The other half: the rule must not block everything."""
    clean = tmp_path / "clean"
    folder = clean / "bars" / "1m" / "LIQUID"
    folder.mkdir(parents=True)
    index = pd.date_range("2026-10-01 14:30", periods=10, freq="1min",
                          tz="UTC", name="ts")
    pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
                  "volume": 1, "currency": "USD"}, index=index
                 ).to_parquet(folder / "2026-10-01.parquet")

    labels = {"LIQUID": access.Label("LIQUID", access.MINUTE_OK, "passed twice",
                                     "x", "x", 2, 30)}
    assert len(access.bars("LIQUID", "1m", clean_root=clean, labels=labels)) == 10


def test_nothing_outside_the_access_layer_reads_minute_bars_directly() -> None:
    """A reader that skips the check is a hole in the rule.

    Scanned over qb2's own code: only the access layer, the front door (which
    WRITES them) and the tools that measure the store may touch the bar files.
    """
    import ast

    # The rule is about BAR files specifically. daily.py, dividends.py and
    # earnings.py read their own tables, which carry no minute-level gaps and no
    # label; flagging those would be flagging the wrong thing.
    allowed = {"access.py", "front_door.py", "census.py", "first_light.py",
               "recorder.py"}
    offenders: list[str] = []
    for path in sorted((REPO_ROOT / "qb2").rglob("*.py")):
        if path.name in allowed or "__pycache__" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        if '"bars"' not in source and "/ 'bars'" not in source:
            continue                     # it never goes near the bar tree
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "read_parquet":
                offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == [], (
        f"these read bar files without going through the access layer: {offenders}")

    # And the doorway really is the only one that knows about the label.
    doorway = (REPO_ROOT / "qb2" / "data" / "access.py").read_text(encoding="utf-8")
    assert "AccessRefused" in doorway and "MINUTE_OK" in doorway


# ============================================================ one writer only

def test_only_the_front_door_writes_to_the_clean_store() -> None:
    """Dividends, daily bars and FX are new tables. They use the same door.

    A second writer means two processes can interleave, and it means the checks
    live in two places and drift apart.
    """
    import ast

    # front_door.py IS the door. recorder.py writes the RAW store, which is its
    # own domain with its own manifest and its own lock -- the front door's rule
    # is about what may enter CLEAN.
    writers = {"front_door.py", "recorder.py"}
    offenders: list[str] = []
    for path in sorted((REPO_ROOT / "qb2").rglob("*.py")):
        if path.name in writers or "__pycache__" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "to_parquet":
                offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == [], (
        "these write parquet directly instead of going through the front door's "
        f"atomic write: {offenders}")

    # The new tables go through the same door as the bars did.
    for module in ("daily.py", "dividends.py", "earnings.py"):
        source = (REPO_ROOT / "qb2" / "ingest" / module).read_text(encoding="utf-8")
        assert "_write_parquet_atomically" in source, module
        assert "_append_manifest" in source, module
        assert "WriterLock" in source, module


def test_the_census_cannot_be_made_red_by_an_ex_date_price_drop(
        tmp_path: Path) -> None:
    """Every payer drops on its ex-date. That must never read as broken data.

    The census counts BARS, not price continuity, so a 5% ex-date gap cannot make
    a name fail. This test pins that, because a census that flagged ex-dates would
    turn every dividend payer red four times a year.
    """
    from qb2.data import census as census_module

    clean = tmp_path / "clean"
    folder = clean / "bars" / "5m" / "PAYER.L"
    folder.mkdir(parents=True)
    index = pd.date_range("2026-09-29 08:00", periods=102, freq="5min",
                          tz="Europe/London", name="ts")
    closes = [10.0] * 50 + [9.5] * 52           # a 5% ex-date gap
    pd.DataFrame({"open": closes, "high": closes, "low": closes, "close": closes,
                  "volume": 10, "currency": "GBP"}, index=index
                 ).to_parquet(folder / "2026-09-29.parquet")

    taken = census_module.take(
        "5m", clean_root=clean, today=pd.Timestamp("2026-09-30").date(),
        entries=[{"yfinance": "PAYER.L", "sleeve": "uk_share"}])
    assert taken.names[0].passes, taken.names[0].reasons


def test_the_default_test_run_stays_offline() -> None:
    import ast

    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "yfinance" not in imported and "requests" not in imported


def test_the_sender_is_still_disarmed() -> None:
    from qb2.execution import sender
    assert sender.ARMED is False


def test_the_provider_already_split_adjusted_the_dividends() -> None:
    """The data contract (CLAUDE.md, scar #22), proven on a known split.

    NVIDIA split 10-for-1 in June 2024. A holder of one pre-split share was paid
    $0.04 in March 2024. If the series were NOT adjusted, that is what we would
    see; adjusting it ourselves afterwards would divide a payout that had already
    been divided, and understate every pre-split dividend tenfold.

    The stored value is 0.004 -- a tenth -- so the provider has already done it
    and we must not do it again.
    """
    stored = dividends.load("NVDA", REPO_ROOT / "data" / "clean")
    if stored is None:
        pytest.skip("NVDA dividends not ingested on this machine")

    before = stored[(stored["ex_date"] > "2024-01-01")
                    & (stored["ex_date"] < "2024-06-01")]
    after = stored[(stored["ex_date"] > "2024-06-01")
                   & (stored["ex_date"] < "2025-01-01")]
    if before.empty or after.empty:
        pytest.skip("the split window is not in the stored history")

    pre = float(before["amount"].iloc[-1])
    post = float(after["amount"].iloc[0])
    assert pre == pytest.approx(0.004, abs=1e-6), (
        f"pre-split payment stored as {pre}; 0.04 would mean it was NOT adjusted")
    assert post / pre < 10, "a 10x step across the split would mean a double adjust"
    assert bool(stored["split_adjusted_by_provider"].iloc[0]) is True
