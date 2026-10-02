"""The recorder: does it lose a day, corrupt a bar, or lie about a gap?

All offline. Every fetch is a fixture, so the default run touches no network.

The interesting tests are the refusals: a forming bar dropped, a changed bar
quarantined instead of overwritten, pence-vs-pounds caught, the clock-change week
handled, and a gap it cannot fill written down as LOST rather than filled in.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from qb2.ingest import recorder, tickers

UTC = timezone.utc


def bars_frame(start: datetime, count: int, interval_minutes: int = 1,
               close: float = 100.0, step: float = 0.1) -> pd.DataFrame:
    """A well-formed frame of closed bars, indexed in UTC."""
    index = pd.date_range(start=start, periods=count,
                          freq=f"{interval_minutes}min", tz="UTC")
    closes = [close + step * n for n in range(count)]
    return pd.DataFrame(
        {"open": [c - step / 2 for c in closes],
         "high": [c + step for c in closes],
         "low": [c - step for c in closes],
         "close": closes,
         "volume": [1_000.0] * count},
        index=index)


# ========================================================== the clock ==========

def test_the_exchange_clock_uses_a_real_timezone_database() -> None:
    """Not a fixed offset: the whole point is the changeover dates."""
    summer = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    assert recorder.utc_offset_hours("LSE", summer) == 1.0        # BST
    assert recorder.utc_offset_hours("US", summer) == -4.0        # EDT


def test_the_week_when_the_gap_is_four_hours_not_five() -> None:
    """UK clocks go back 2026-10-25; the US waits until 2026-11-01.

    For that one week London is UTC+0 while New York is still UTC-4, so the gap
    is 4 hours. Code that adds a fixed 5 would put every US bar in the wrong
    place for a week -- and it would look like a market move, not a bug.
    """
    between = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
    london = recorder.utc_offset_hours("LSE", between)
    new_york = recorder.utc_offset_hours("US", between)
    assert london == 0.0, "the UK should have left BST by 28 October"
    assert new_york == -4.0, "the US should still be on EDT on 28 October"
    assert london - new_york == 4.0

    after = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
    assert (recorder.utc_offset_hours("LSE", after)
            - recorder.utc_offset_hours("US", after)) == 5.0


def test_market_hours_know_about_weekends_and_the_clock() -> None:
    # Wednesday 2026-09-30, 14:00 UTC = 15:00 London (open), 10:00 New York (open)
    midday = datetime(2026, 9, 30, 14, 0, tzinfo=UTC)
    assert recorder.market_is_open("LSE", midday) is True
    assert recorder.market_is_open("US", midday) is True
    # 23:29 UTC on the same day: both shut.
    late = datetime(2026, 9, 30, 23, 29, tzinfo=UTC)
    assert recorder.market_is_open("LSE", late) is False
    assert recorder.market_is_open("US", late) is False
    # Sunday.
    sunday = datetime(2026, 9, 27, 14, 0, tzinfo=UTC)
    assert recorder.market_is_open("US", sunday) is False


# ================================================= correctness at the edge =====

def test_the_still_forming_bar_is_dropped() -> None:
    """A bar whose minute has not finished is not a bar."""
    now = datetime(2026, 9, 30, 14, 30, 30, tzinfo=UTC)
    frame = bars_frame(datetime(2026, 9, 30, 14, 26, tzinfo=UTC), 5)
    # last bar is stamped 14:30, which completes at 14:31 -- after `now`.
    kept = recorder.drop_forming_bar(frame, "1m", now)
    assert len(kept) == 4
    assert kept.index[-1] == pd.Timestamp("2026-09-30 14:29", tz="UTC")


def test_a_completed_last_bar_is_kept() -> None:
    now = datetime(2026, 9, 30, 14, 35, tzinfo=UTC)
    frame = bars_frame(datetime(2026, 9, 30, 14, 26, tzinfo=UTC), 5)
    assert len(recorder.drop_forming_bar(frame, "1m", now)) == 5


def test_an_impossible_bar_is_spotted() -> None:
    frame = bars_frame(datetime(2026, 9, 30, 14, 0, tzinfo=UTC), 3)
    frame.loc[frame.index[1], "high"] = 1.0      # high below open and close
    problems = recorder.ohlc_problems(frame)
    assert list(problems) == [False, True, False]


def test_a_negative_or_missing_price_is_spotted() -> None:
    frame = bars_frame(datetime(2026, 9, 30, 14, 0, tzinfo=UTC), 3)
    frame.loc[frame.index[0], "close"] = 0.0
    frame.loc[frame.index[2], "low"] = None
    problems = recorder.ohlc_problems(frame)
    assert bool(problems.iloc[0]) and bool(problems.iloc[2])


def test_pence_meeting_pounds_is_caught_as_a_unit_change() -> None:
    """A UK price that jumps 100x is a unit change, never a market move."""
    assert recorder.unit_jump(7.12, 712.0) is not None       # pounds -> pence
    assert recorder.unit_jump(712.0, 7.12) is not None       # pence -> pounds
    assert recorder.unit_jump(712.0, 715.0) is None          # an actual move
    assert recorder.unit_jump(None, 712.0) is None           # nothing to compare


# ========================================================= saving and gaps =====

def test_a_capture_is_written_with_a_manifest_line(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    bars = recorder.Bars("ISF.L", "1m", "LSE", "GBp",
                         bars_frame(datetime(2026, 9, 30, 8, 0, tzinfo=UTC), 10))
    records = recorder.save_bars(bars, root=tmp_path, manifest=manifest)
    assert len(records) == 1
    assert records[0]["rows"] == 10
    assert records[0]["currency"] == "GBp"
    assert records[0]["file_hash"]
    assert Path(str(records[0]["file"])).is_file()
    lines = [json.loads(line) for line in
             manifest.read_text(encoding="utf-8").splitlines()]
    assert lines[0]["kind"] == "capture"


def test_re_running_the_same_capture_adds_nothing(tmp_path: Path) -> None:
    """Catch-up safety: running twice must not duplicate a single bar."""
    manifest = tmp_path / "manifest.jsonl"
    bars = recorder.Bars("ISF.L", "1m", "LSE", "GBp",
                         bars_frame(datetime(2026, 9, 30, 8, 0, tzinfo=UTC), 10))
    recorder.save_bars(bars, root=tmp_path, manifest=manifest)
    second = recorder.save_bars(bars, root=tmp_path, manifest=manifest)
    assert second == [], "the same bars were saved twice"


def test_an_overlapping_run_adds_only_the_new_bars(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    start = datetime(2026, 9, 30, 8, 0, tzinfo=UTC)
    recorder.save_bars(
        recorder.Bars("ISF.L", "1m", "LSE", "GBp", bars_frame(start, 10)),
        root=tmp_path, manifest=manifest)
    later = recorder.save_bars(
        recorder.Bars("ISF.L", "1m", "LSE", "GBp", bars_frame(start, 15)),
        root=tmp_path, manifest=manifest)
    assert later[0]["rows"] == 15, "the file should now hold all 15 bars"
    saved = pd.read_parquet(Path(str(later[0]["file"])))
    assert len(saved) == 15
    assert not saved.index.duplicated().any()


def test_a_changed_bar_is_quarantined_and_the_original_stands(
        tmp_path: Path) -> None:
    """Never overwrite. Which version is right is a human's question."""
    manifest = tmp_path / "manifest.jsonl"
    start = datetime(2026, 9, 30, 8, 0, tzinfo=UTC)
    first = bars_frame(start, 5)
    recorder.save_bars(recorder.Bars("ISF.L", "1m", "LSE", "GBp", first),
                       root=tmp_path, manifest=manifest)

    # A revised bar that is still a POSSIBLE bar -- shift the whole row a little.
    # (A wild close would trip the OHLC sanity check first, which is correct but
    # would test the wrong guard.)
    altered = first.copy()
    for column in ("open", "high", "low", "close"):
        altered.loc[altered.index[2], column] *= 1.002
    recorder.save_bars(recorder.Bars("ISF.L", "1m", "LSE", "GBp", altered),
                       root=tmp_path, manifest=manifest)

    rows = [json.loads(line) for line in
            manifest.read_text(encoding="utf-8").splitlines()]
    reasons = [r.get("reason") for r in rows if r.get("kind") == "quarantine"]
    assert "value_changed" in reasons, f"a changed bar was accepted: {reasons}"

    saved = pd.read_parquet(next((tmp_path / "1m" / "ISF.L").glob("*.parquet")))
    assert saved.loc[first.index[2], "close"] == first.loc[first.index[2], "close"], (
        "the original bar was overwritten")


def test_a_broken_bar_is_quarantined_and_the_good_ones_are_kept(
        tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    frame = bars_frame(datetime(2026, 9, 30, 8, 0, tzinfo=UTC), 5)
    frame.loc[frame.index[1], "high"] = 0.5          # impossible
    records = recorder.save_bars(
        recorder.Bars("ISF.L", "1m", "LSE", "GBp", frame),
        root=tmp_path, manifest=manifest)
    # save_bars now hands back what it QUARANTINED as well as what it saved, so
    # the caller can count both without re-reading the manifest. The two are told
    # apart by "kind", never by position in the list.
    saved_records = [r for r in records if r.get("kind") != "quarantine"]
    quarantine_records = [r for r in records if r.get("kind") == "quarantine"]
    assert [r["rows"] for r in saved_records] == [4], "the broken bar was saved"
    assert [r["rows"] for r in quarantine_records] == [1], "the bad row was lost"
    rows = [json.loads(line) for line in
            manifest.read_text(encoding="utf-8").splitlines()]
    assert any(r.get("reason") == "ohlc_sanity" for r in rows)


def test_a_gap_that_cannot_be_filled_is_recorded_as_lost(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    record = recorder.record_lost("ISF.L", "1m", "provider gave nothing", manifest)
    assert record["status"] == "LOST"
    assert recorder.last_saved_bar("ISF.L", "1m", manifest) is None, (
        "a LOST gap must not count as a saved bar")


def test_the_recorder_knows_where_to_carry_on_from(tmp_path: Path) -> None:
    """This is what makes a missed run harmless."""
    manifest = tmp_path / "manifest.jsonl"
    start = datetime(2026, 9, 30, 8, 0, tzinfo=UTC)
    recorder.save_bars(
        recorder.Bars("ISF.L", "1m", "LSE", "GBp", bars_frame(start, 10)),
        root=tmp_path, manifest=manifest)
    resume = recorder.last_saved_bar("ISF.L", "1m", manifest)
    assert resume is not None
    assert resume.hour == 8 and resume.minute == 9


# ============================================================ the delay ========

def test_a_delay_sample_is_only_taken_while_the_market_is_open() -> None:
    """The trap FACTS row o fell into: a shut market is not a delayed feed."""
    open_moment = datetime(2026, 9, 30, 14, 0, tzinfo=UTC)
    last_bar = open_moment - timedelta(minutes=17)
    sample = recorder.delay_sample("US", last_bar, open_moment)
    assert sample is not None
    assert sample["age_seconds"] == pytest.approx(1020.0)

    shut = datetime(2026, 9, 30, 23, 30, tzinfo=UTC)
    assert recorder.delay_sample("US", shut - timedelta(hours=3), shut) is None


# ======================================================= the freshness meter ===

def test_the_freshness_meter_is_green_after_a_fresh_capture(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    now = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    recorder.save_bars(
        recorder.Bars("ISF.L", "1m", "LSE", "GBp",
                      bars_frame(datetime(2026, 9, 30, 8, 0, tzinfo=UTC), 10)),
        root=tmp_path, manifest=manifest, now=now)
    meters = {m["interval"]: m for m in recorder.freshness(manifest, now)}
    assert meters["1m"]["status"] == "OK"


def test_the_freshness_meter_goes_red_on_a_stale_manifest(tmp_path: Path) -> None:
    """Birth certificate (SCARS #9): watch it fire before trusting it.

    A planted capture from a week ago must turn the light red, or the meter is
    decoration and a dead recorder would look healthy.
    """
    manifest = tmp_path / "manifest.jsonl"
    stale = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)          # a Monday
    recorder.save_bars(
        recorder.Bars("ISF.L", "1m", "LSE", "GBp",
                      bars_frame(datetime(2026, 9, 21, 8, 0, tzinfo=UTC), 5)),
        root=tmp_path, manifest=manifest, now=stale)
    now = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)            # 7 weekdays later
    meters = {m["interval"]: m for m in recorder.freshness(manifest, now)}
    assert meters["1m"]["status"] == "RED"
    assert int(str(meters["1m"]["weekdays_since"])) >= 3


def test_a_never_recorded_interval_is_red_not_silent(tmp_path: Path) -> None:
    meters = {m["interval"]: m for m in
              recorder.freshness(tmp_path / "absent.jsonl")}
    assert all(m["status"] == "RED" for m in meters.values())
    assert "never" in str(meters["1m"]["detail"])


# ============================================================== the run ========

def test_one_dead_symbol_does_not_lose_everybody_elses_day(
        tmp_path: Path) -> None:
    """Handled and logged, never fatal (SCARS #12)."""
    manifest = tmp_path / "manifest.jsonl"
    now = datetime(2026, 9, 30, 14, 0, tzinfo=UTC)

    def fetch(ticker: str, interval: str, days: int) -> pd.DataFrame:
        if ticker == "BROKEN":
            raise RuntimeError("provider exploded")
        return bars_frame(datetime(2026, 9, 30, 8, 0, tzinfo=UTC), 10)

    outcome = recorder.capture(
        [("BROKEN", "US", "USD"), ("ISF.L", "LSE", "GBP")], "1m",
        fetch=fetch, root=tmp_path, manifest=manifest, now=now)
    assert outcome.rows_saved == 10, "the healthy ticker was not saved"
    assert len(outcome.errors) == 1
    assert any(g["status"] == "LOST" for g in outcome.lost)


def test_an_empty_provider_reply_is_a_lost_gap_not_a_silent_skip(
        tmp_path: Path) -> None:
    outcome = recorder.capture(
        [("ISF.L", "LSE", "GBP")], "1m",
        fetch=lambda t, i, d: pd.DataFrame(), root=tmp_path,
        manifest=tmp_path / "m.jsonl", now=datetime(2026, 9, 30, 14, 0, tzinfo=UTC))
    assert outcome.rows_saved == 0
    assert outcome.lost and outcome.lost[0]["reason"] == "provider returned nothing"


def test_the_run_takes_a_delay_sample_during_market_hours(tmp_path: Path) -> None:
    now = datetime(2026, 9, 30, 14, 0, tzinfo=UTC)
    outcome = recorder.capture(
        [("ISF.L", "LSE", "GBP")], "1m",
        fetch=lambda t, i, d: bars_frame(
            now - timedelta(minutes=20), 10), root=tmp_path,
        manifest=tmp_path / "m.jsonl", now=now)
    assert outcome.delay_samples, "no delay sample was taken while open"
    assert outcome.delay_samples[0]["market"] == "LSE"


def test_the_provider_limit_from_the_facts_file_is_respected() -> None:
    """Row n: 1m is 8 days per request. Asking for more returns nothing."""
    asked: list[int] = []

    def fetch(ticker: str, interval: str, days: int) -> pd.DataFrame:
        asked.append(days)
        return pd.DataFrame()

    recorder.capture([("AAPL", "US", "USD")], "1m", fetch=fetch)
    assert asked == [8], f"asked for {asked} days of 1m data; the limit is 8"


# ====================================================== the ticker mapping =====

def test_a_plain_us_ticker_maps_cleanly() -> None:
    mapped = tickers.map_t212_ticker("AAPL_US_EQ")
    assert mapped.yfinance == "AAPL"
    assert mapped.market == "US" and mapped.currency == "USD"
    assert mapped.certain is True


def test_a_plain_london_ticker_gets_the_dot_l_suffix() -> None:
    mapped = tickers.map_t212_ticker("SGLNl_EQ")
    assert mapped.yfinance == "SGLN.L"
    assert mapped.market == "LSE" and mapped.currency == "GBP"
    assert mapped.certain is True


def test_a_disambiguating_digit_is_never_guessed() -> None:
    """SNDK1_US_EQ might be SNDK, or it might not. We do not pretend."""
    for awkward in ("SNDK1_US_EQ", "ALCC1_US_EQ", "3LGO1l_EQ"):
        mapped = tickers.map_t212_ticker(awkward)
        assert mapped.certain is False
        assert mapped.yfinance is None
        assert "human" in mapped.note


def test_an_unrecognised_suffix_is_refused_not_invented() -> None:
    mapped = tickers.map_t212_ticker("SOMETHING_DE_EQ")
    assert mapped.certain is False
    assert mapped.market == "UNKNOWN"


def test_the_live_account_tickers_split_into_certain_and_uncertain() -> None:
    certain, uncertain = tickers.map_many(list(tickers.SEEN_ON_T212))
    assert len(certain) + len(uncertain) == 10
    # Only the names carrying T212's disambiguating digit are uncertain.
    assert {m.t212 for m in uncertain} == {"ALCC1_US_EQ", "SNDK1_US_EQ",
                                           "3LGO1l_EQ"}
    assert {m.yfinance for m in certain} == {"GEV", "MU", "RXRX", "IREN",
                                             "TSLA", "SGLN.L", "SPCX"}


def test_the_recording_list_is_wide_and_has_no_duplicates() -> None:
    entries = tickers.recording_list()
    names = [t for t, _, _ in entries]
    assert len(names) == len(set(names)), "the recording list repeats a ticker"
    assert len(entries) > 100
    counts = tickers.counts()
    assert counts["total"] == len(entries)
    assert counts["uk_etfs"] >= 20


def test_every_london_entry_defaults_to_pence_and_every_us_entry_to_dollars() -> None:
    """London's default is PENCE, which is what both our sources actually say.

    This test used to assert "GBP" for every London name and passed for a week,
    because the list and the test shared one wrong assumption. Trading 212 quotes
    2,420 London instruments in GBX and yfinance spells the same unit GBp
    (FACTS row r), so pence is the common case and pounds is the exception. The
    default here only has to be the USUAL unit; the authority for any single
    instrument is the resolved universe file, and the front door carries the
    currency per row.
    """
    for ticker, market, currency in tickers.recording_list():
        if ticker.startswith("^") or ticker.endswith("=X"):
            assert currency in ("INDEX", "FX"), ticker
            continue
        assert market == ("LSE" if ticker.endswith(".L") else "US"), ticker
        # Not a default: this is what T212 says about this one instrument.
        assert currency == tickers.quote_currency(ticker), ticker
        if market == "LSE":
            assert currency in ("GBp", "GBP", "USD", "EUR"), ticker
        else:
            assert currency == "USD", ticker
    # The London split is real and must not quietly collapse to one currency.
    london = {tickers.quote_currency(t) for t, m, _ in tickers.recording_list()
              if m == "LSE"}
    assert {"GBp", "GBP"} <= london, (
        f"London should span pence AND pounds (FACTS row r); got {london}")


def test_the_exchange_rate_is_recorded_because_p3_needs_it() -> None:
    """P3 judges in pounds including the currency effect."""
    names = [t for t, _, _ in tickers.recording_list()]
    assert "GBPUSD=X" in names
    for gauge in ("^FTSE", "^GSPC", "^VIX"):
        assert gauge in names


# ============================================ politeness and staying offline ===

def test_a_throttled_fetch_is_retried_with_a_pause_then_succeeds() -> None:
    """Free data throttles without saying so, so a failure means 'slow down'."""
    attempts = {"n": 0}
    waited: list[float] = []

    def flaky(ticker: str, interval: str, days: int) -> pd.DataFrame:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("429-ish: too many requests")
        return bars_frame(datetime(2026, 9, 30, 8, 0, tzinfo=UTC), 5)

    frame = recorder.fetch_with_backoff(flaky, "ISF.L", "1m", 8,
                                        sleeper=waited.append)
    assert len(frame) == 5
    assert attempts["n"] == 3
    assert waited == [2.0, 8.0], f"backoff pauses were {waited}"


def test_it_gives_up_rather_than_hammering_forever() -> None:
    waited: list[float] = []

    def always_fails(ticker: str, interval: str, days: int) -> pd.DataFrame:
        raise RuntimeError("still throttled")

    with pytest.raises(RuntimeError, match="still throttled"):
        recorder.fetch_with_backoff(always_fails, "ISF.L", "1m", 8,
                                    sleeper=waited.append)
    assert len(waited) == recorder.FETCH_ATTEMPTS - 1


def test_the_raw_capture_folder_is_gitignored() -> None:
    """Thousands of parquet files must never reach the repository."""
    patterns = [line.strip() for line in
                (Path(__file__).resolve().parents[2] / ".gitignore"
                 ).read_text(encoding="utf-8").splitlines()]
    assert "/data/" in patterns, (
        "the anchored /data/ rule is what keeps data/raw/intraday out of git")


def test_these_tests_never_touch_the_network() -> None:
    """Every fetch in this file is injected; the real one is never called.

    Checked by reading this file's own syntax rather than searching its text --
    a substring search would trip over the name written in this very docstring.
    """
    import ast

    source = Path(__file__).read_text(encoding="utf-8")
    real_fetcher = "yfinance" + "_fetch"
    called: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        name = (target.attr if isinstance(target, ast.Attribute)
                else target.id if isinstance(target, ast.Name) else "")
        if name == real_fetcher:
            called.append(f"line {node.lineno}")
    assert called == [], (
        f"a test calls the real provider at {called} -- inject a fixture instead")
    assert "fetch=" in source, "the tests should be injecting a fetcher"


def test_hourly_data_is_partitioned_by_month_not_by_day(tmp_path: Path) -> None:
    """Otherwise a 2.9-year hourly backfill is ~59,000 near-empty files.

    Minute data stays day-partitioned, because one day of minutes is a real
    file. This is the difference between a directory you can read and one the
    filesystem chokes on.
    """
    start = datetime(2026, 8, 28, 13, 0, tzinfo=UTC)          # spans into September
    frame = bars_frame(start, 120, interval_minutes=60)
    records = recorder.save_bars(
        recorder.Bars("AAPL", "1h", "US", "USD", frame),
        root=tmp_path, manifest=tmp_path / "m.jsonl")
    names = sorted(Path(str(r["file"])).name for r in records)
    assert names == ["2026-08.parquet", "2026-09.parquet"], names

    minute = recorder.save_bars(
        recorder.Bars("AAPL", "1m", "US", "USD",
                      bars_frame(datetime(2026, 9, 30, 14, 0, tzinfo=UTC), 30)),
        root=tmp_path, manifest=tmp_path / "m.jsonl")
    assert Path(str(minute[0]["file"])).name == "2026-09-30.parquet"


def test_a_month_file_still_refuses_to_overwrite_a_changed_bar(
        tmp_path: Path) -> None:
    """Month partitioning must not weaken the never-overwrite rule."""
    manifest = tmp_path / "m.jsonl"
    frame = bars_frame(datetime(2026, 9, 1, 13, 0, tzinfo=UTC), 24,
                       interval_minutes=60)
    recorder.save_bars(recorder.Bars("AAPL", "1h", "US", "USD", frame),
                       root=tmp_path, manifest=manifest)
    altered = frame.copy()
    for column in ("open", "high", "low", "close"):
        altered.loc[altered.index[3], column] *= 1.003
    recorder.save_bars(recorder.Bars("AAPL", "1h", "US", "USD", altered),
                       root=tmp_path, manifest=manifest)
    reasons = [json.loads(line).get("reason") for line
               in manifest.read_text(encoding="utf-8").splitlines()]
    assert "value_changed" in reasons
