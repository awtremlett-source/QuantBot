"""Premortem for the front door: every way the clean store can quietly lie.

The front door is the only writer, so a mistake here is a mistake in everything
downstream and nothing else will catch it. Each test names the specific way the
store could end up holding something that is not true.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest

from qb2.data import census as census_module
from qb2.data import front_door as fd

LONDON = "Europe/London"


def bars(rows: int = 4, start: str = "2026-09-29 08:00",
         price: float = 500.0, tz: str = LONDON) -> pd.DataFrame:
    """A small, valid frame in the recorder's own shape."""
    index = pd.date_range(start, periods=rows, freq="1min", tz=tz, name="Datetime")
    return pd.DataFrame({
        "open": [price] * rows,
        "high": [price + 1] * rows,
        "low": [price - 1] * rows,
        "close": [price + 0.5] * rows,
        "volume": [1_000] * rows,
    }, index=index)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[tuple[Path, Path]]:
    """A private raw tree and clean tree, so no test touches the real store."""
    raw = tmp_path / "data" / "raw" / "intraday"
    clean = tmp_path / "data" / "clean"
    raw.mkdir(parents=True)
    clean.mkdir(parents=True)
    yield raw, clean


def write_raw(raw: Path, symbol: str, interval: str, day: str,
              frame: pd.DataFrame) -> Path:
    folder = raw / interval / symbol
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{day}.parquet"
    frame.to_parquet(path)
    return path


def ingest(raw: Path, clean: Path, **kwargs: object) -> fd.Reconciliation:
    return fd.ingest(raw_root=raw, clean_root=clean, **kwargs)  # type: ignore[arg-type]


# ----------------------------------------------------------------- one writer

def test_a_second_writer_is_refused_while_the_first_holds_the_lock(
        tmp_path: Path) -> None:
    """Failure mode: a catch-up run firing into a run already going.

    Two writers would interleave rows inside one file. On a laptop that wakes from
    sleep this is not hypothetical -- the scheduler fires the missed run.
    """
    lock = tmp_path / "writer.lock"
    with fd.WriterLock(lock):
        with pytest.raises(fd.StoreLocked, match="another writer"):
            with fd.WriterLock(lock):
                pass
    # Released on the way out, so the next run is not blocked forever.
    assert not lock.exists()


def test_a_lock_left_behind_by_a_dead_run_is_taken_over_not_obeyed_forever(
        tmp_path: Path) -> None:
    """A laptop shut mid-run must not block every future run.

    The abandoned lock is RENAMED rather than deleted, so the evidence that a run
    died survives (quarantine, never delete).
    """
    lock = tmp_path / "writer.lock"
    lock.write_text("pid=1 from a run that died", encoding="utf-8")
    old = time.time() - 7_200
    import os
    os.utime(lock, (old, old))

    with fd.WriterLock(lock, stale_after=3_600):
        pass
    assert lock.with_suffix(".lock.abandoned").exists(), (
        "the abandoned lock must be kept as evidence, not silently removed")


# ------------------------------------------------------- the commit point

def test_a_bar_file_with_no_manifest_line_is_not_part_of_the_store(
        store: tuple[Path, Path]) -> None:
    """Failure mode: a half-written file from a power cut read as real data.

    The manifest is the commit point. A parquet file nobody recorded is treated as
    absent and re-ingested, rather than trusted because it happens to exist.
    """
    raw, clean = store
    write_raw(raw, "BP.L", "1m", "2026-09-29", bars())
    first = ingest(raw, clean, intervals=("1m",))
    assert first.files_written == 1

    # Lose the index but keep the file, exactly as a crash mid-append would.
    fd.manifest_path(clean).unlink()
    again = ingest(raw, clean, intervals=("1m",))
    assert again.files_written == 1, (
        "without its manifest line the file must be re-ingested, not assumed good")


def test_a_torn_manifest_line_does_not_poison_the_whole_index(
        store: tuple[Path, Path]) -> None:
    """A crash mid-append leaves half a line. That must cost one file, not all."""
    raw, clean = store
    write_raw(raw, "BP.L", "1m", "2026-09-29", bars())
    write_raw(raw, "AAPL", "1m", "2026-09-29", bars(price=300.0, tz="America/New_York"))
    ingest(raw, clean, intervals=("1m",))

    path = fd.manifest_path(clean)
    with path.open("a", encoding="utf-8") as fh:
        fh.write('{"event": "ingested", "source": "half a lin')
    known = fd.read_manifest(clean)
    assert len(known) == 2, "the two whole lines must still be readable"


def test_nothing_is_written_under_the_final_name_until_it_is_complete(
        store: tuple[Path, Path]) -> None:
    """No ".partial" file may survive a successful run."""
    raw, clean = store
    write_raw(raw, "BP.L", "1m", "2026-09-29", bars())
    ingest(raw, clean, intervals=("1m",))
    assert list(clean.rglob("*.partial")) == []


# --------------------------------------------------------------- idempotency

def test_running_twice_changes_nothing(store: tuple[Path, Path]) -> None:
    """Safe to run at the end of every recorder run, including catch-up runs."""
    raw, clean = store
    write_raw(raw, "BP.L", "1m", "2026-09-29", bars())
    first = ingest(raw, clean, intervals=("1m",))
    before = {p: p.read_bytes() for p in (clean / "bars").rglob("*.parquet")}

    second = ingest(raw, clean, intervals=("1m",))
    assert second.files_written == 0
    assert second.rows_already_present == first.rows_written
    after = {p: p.read_bytes() for p in (clean / "bars").rglob("*.parquet")}
    assert before == after, "a second run rewrote the data"


def test_pence_are_converted_exactly_once(store: tuple[Path, Path]) -> None:
    """The 100x bug, in its most expensive form: converting twice.

    A price converted twice is a hundredth of the truth, and it looks like a
    catastrophic crash rather than an arithmetic error.
    """
    raw, clean = store
    write_raw(raw, "BP.L", "1m", "2026-09-29", bars(price=500.0))
    ingest(raw, clean, intervals=("1m",))
    ingest(raw, clean, intervals=("1m",))

    stored = pd.read_parquet(next((clean / "bars" / "1m" / "BP.L").glob("*.parquet")))
    assert stored["open"].iloc[0] == pytest.approx(5.0)
    assert set(stored["currency"]) == {"GBP"}


def test_a_dollar_priced_name_is_left_alone(store: tuple[Path, Path]) -> None:
    raw, clean = store
    write_raw(raw, "AAPL", "1m", "2026-09-29",
              bars(price=300.0, tz="America/New_York"))
    ingest(raw, clean, intervals=("1m",))
    stored = pd.read_parquet(next((clean / "bars" / "1m" / "AAPL").glob("*.parquet")))
    assert stored["open"].iloc[0] == pytest.approx(300.0)
    assert set(stored["currency"]) == {"USD"}


# ------------------------------------------------------------- what goes in

def test_the_superseded_folder_is_never_read(store: tuple[Path, Path]) -> None:
    """The 1,382 hourly day-files moved aside on 2026-09-30 are still on disk.

    They were kept, not deleted. Reading them would double-count every hourly bar
    in the store, which is why the exclusion is at the door and not in a caller.
    """
    raw, clean = store
    write_raw(raw, "BP.L", "1h", "2026-09", bars())
    superseded = raw.parent / "superseded-1h-dayfiles-2026-09-30" / "1h" / "BP.L"
    superseded.mkdir(parents=True)
    bars().to_parquet(superseded / "2026-09-29.parquet")

    found = list(fd.raw_files("1h", root=raw))
    assert len(found) == 1
    # Checked on the path PARTS, not on the whole string: pytest's own temporary
    # directory is named after this test and contains the word "superseded".
    assert all(not any(part.startswith("superseded-") for part in path.parts)
               for path in found)


def test_a_name_that_left_the_list_keeps_its_data_but_is_not_promoted(
        store: tuple[Path, Path]) -> None:
    """AHT.L stopped being Ashtead; IEUR.L never existed on T212.

    Their recorded bars stay on disk untouched -- nothing is deleted -- but they
    must not enter the clean store, where a strategy could pick them up.
    """
    raw, clean = store
    write_raw(raw, "AHT.L", "1m", "2026-09-29", bars())
    tally = ingest(raw, clean, intervals=("1m",))
    assert tally.files_excluded == 1
    assert tally.files_written == 0
    assert list((clean / "bars").rglob("*.parquet")) == []
    assert (raw / "1m" / "AHT.L" / "2026-09-29.parquet").exists(), "raw must survive"


def test_unexpected_columns_stop_the_run_rather_than_being_guessed_at(
        store: tuple[Path, Path]) -> None:
    raw, clean = store
    frame = bars().rename(columns={"close": "closing_price"})
    write_raw(raw, "BP.L", "1m", "2026-09-29", frame)
    with pytest.raises(fd.FrontDoorError, match="unexpected columns"):
        ingest(raw, clean, intervals=("1m",))


# --------------------------------------------------------------- bad rows

def test_an_impossible_bar_is_quarantined_and_counted(
        store: tuple[Path, Path]) -> None:
    """A high below its low is not a market event. It is a broken row."""
    raw, clean = store
    frame = bars()
    frame.iloc[1, frame.columns.get_loc("high")] = 1.0     # high under the low
    write_raw(raw, "BP.L", "1m", "2026-09-29", frame)

    tally = ingest(raw, clean, intervals=("1m",))
    assert tally.rows_quarantined == 1
    assert tally.rows_written == 3
    assert list((clean / "quarantine").rglob("*.parquet")), "the row must be KEPT"
    tally.check()


def test_rows_that_vanish_are_a_failure_not_a_rounding(
        store: tuple[Path, Path]) -> None:
    """Reconciliation is exact. "About right" is how data goes missing."""
    tally = fd.Reconciliation(rows_in=100, rows_written=99)
    with pytest.raises(fd.FrontDoorError, match="reconciliation failed"):
        tally.check()
    tally.rows_dropped = 1
    tally.check()                                  # now it adds up


def test_a_duplicate_timestamp_is_dropped_and_said_so(
        store: tuple[Path, Path]) -> None:
    raw, clean = store
    frame = bars()
    doubled = pd.concat([frame, frame.iloc[[0]]])
    write_raw(raw, "BP.L", "1m", "2026-09-29", doubled)
    tally = ingest(raw, clean, intervals=("1m",))
    assert tally.rows_dropped == 1
    assert any("duplicate" in p for p in tally.problems)
    tally.check()


# -------------------------------------------------------------------- splits

def test_a_split_is_reported_and_never_applied(store: tuple[Path, Path]) -> None:
    """SCARS #22, the most expensive mistake available here.

    yfinance's prices arrive ALREADY split-adjusted. Dividing by the ratio again
    would halve a price that was never doubled, and the result looks exactly like a
    real crash -- a strategy would "learn" from it. So a jump is reported; the
    numbers are left exactly as the provider sent them.
    """
    raw, clean = store
    frame = bars(rows=4, price=500.0)
    frame.iloc[2:, :4] = 25.0                 # a 20x step, as a split would look
    write_raw(raw, "BP.L", "1m", "2026-09-29", frame)

    tally = ingest(raw, clean, intervals=("1m",))
    assert any("unexplained" in p and "NOT corrected" in p for p in tally.problems)

    stored = pd.read_parquet(next((clean / "bars" / "1m" / "BP.L").glob("*.parquet")))
    # 500 pence -> 5.00 pounds, and 25 pence -> 0.25. Converted once, never divided
    # by a split ratio.
    assert stored["open"].iloc[0] == pytest.approx(5.0)
    assert stored["open"].iloc[3] == pytest.approx(0.25)


def test_a_jump_a_known_split_explains_is_not_reported_as_a_problem(
        store: tuple[Path, Path]) -> None:
    raw, clean = store
    frame = bars(rows=4, price=500.0)
    frame.iloc[2:, :4] = 25.0
    write_raw(raw, "BP.L", "1m", "2026-09-29", frame)
    tally = ingest(raw, clean, intervals=("1m",),
                   splits={"BP.L": {"2026-09-29": 20.0}})
    assert not any("unexplained" in p for p in tally.problems)


# ------------------------------------------------------------- the calendar

def test_a_half_day_is_not_counted_as_missing_data() -> None:
    """Christmas Eve is a real session of 270 minutes, not a 240-bar hole.

    Assuming 510 minutes every London session would mark every early close as bad
    data, and the census would be wrong on exactly the days we would most want to
    trust it.
    """
    full = fd.expected_minutes("LSE", pd.Timestamp("2026-09-29"), "1m")
    half = fd.expected_minutes("LSE", pd.Timestamp("2026-12-24"), "1m")
    assert full == 510
    assert half is not None and 0 < half < full


def test_a_weekend_expects_no_bars_at_all() -> None:
    assert fd.expected_minutes("US", pd.Timestamp("2026-09-27"), "1m") == 0


def test_an_hourly_bar_counts_as_sixty_minutes() -> None:
    assert fd.expected_minutes("US", pd.Timestamp("2026-09-29"), "1h") == 390 // 60


# ---------------------------------------------------------------- the census

def test_the_census_goes_red_on_a_broken_store(tmp_path: Path) -> None:
    """The birth certificate (SCARS #9): a meter that cannot go red is decoration.

    Three stores, three verdicts. If this test ever passes while the store is
    empty, the meter is lying and every "95% pass" claim built on it is worthless.
    """
    clean = tmp_path / "clean"
    entries = [{"yfinance": "BP.L", "sleeve": "uk_share"},
               {"yfinance": "AZN.L", "sleeve": "uk_share"}]

    empty = census_module.take("1m", clean_root=clean, entries=entries)
    assert empty.verdict == "RED"
    assert empty.fraction_passing == 0.0
    assert not empty.meets_plan_gate()
    assert all("no clean bars at all" in n.reasons for n in empty.names)


def test_the_census_passes_a_name_whose_session_is_complete(
        tmp_path: Path) -> None:
    """The other half of the birth certificate: it must also be able to go green."""
    clean = tmp_path / "clean"
    folder = clean / "bars" / "1m" / "BP.L"
    folder.mkdir(parents=True)
    # A whole London session: 08:00 to 16:30 is 510 minutes.
    index = pd.date_range("2026-09-29 08:00", periods=510, freq="1min",
                          tz=LONDON, name="ts")
    pd.DataFrame({"open": 5.0, "high": 5.1, "low": 4.9, "close": 5.0,
                  "volume": 10, "currency": "GBP"}, index=index
                 ).to_parquet(folder / "2026-09-29.parquet")

    taken = census_module.take(
        "1m", clean_root=clean, today=pd.Timestamp("2026-09-30").date(),
        entries=[{"yfinance": "BP.L", "sleeve": "uk_share"}])
    assert taken.names[0].bars_present == 510
    assert taken.names[0].completeness == pytest.approx(1.0)
    assert taken.names[0].passes, taken.names[0].reasons
    assert taken.verdict == "GREEN"


def test_a_stale_name_fails_even_when_its_history_is_complete(
        tmp_path: Path) -> None:
    """Perfect data from a month ago is not data. The feed has stopped."""
    clean = tmp_path / "clean"
    folder = clean / "bars" / "1m" / "BP.L"
    folder.mkdir(parents=True)
    index = pd.date_range("2026-09-29 08:00", periods=510, freq="1min",
                          tz=LONDON, name="ts")
    pd.DataFrame({"open": 5.0, "high": 5.1, "low": 4.9, "close": 5.0,
                  "volume": 10, "currency": "GBP"}, index=index
                 ).to_parquet(folder / "2026-09-29.parquet")

    taken = census_module.take(
        "1m", clean_root=clean, today=pd.Timestamp("2026-10-20").date(),
        entries=[{"yfinance": "BP.L", "sleeve": "uk_share"}])
    assert not taken.names[0].passes
    assert any("weekdays old" in r for r in taken.names[0].reasons)


def test_the_census_report_names_the_failures_in_plain_words(
        tmp_path: Path) -> None:
    """A beginner must be able to read the verdict without decoding a percentage."""
    taken = census_module.take(
        "1m", clean_root=tmp_path / "clean",
        entries=[{"yfinance": "BP.L", "sleeve": "uk_share"}])
    text = census_module.report(taken)
    assert "RED" in text
    assert "BP.L" in text
    assert "95%" in text


# ------------------------------------------------------------- first light

def test_a_chart_refuses_to_put_two_currencies_on_one_axis() -> None:
    """The silent 100x bug, caught by the thing most likely to be looked at."""
    from qb2.tools import first_light
    mixed = pd.DataFrame({"close": [5.0, 500.0], "currency": ["GBP", "GBX"]})
    with pytest.raises(ValueError, match="more than one currency"):
        first_light.unit_of(mixed)


def test_first_light_never_reads_the_raw_store() -> None:
    """If a chart needs raw bars, the front door has failed and that is the bug.

    The CODE is inspected, not the text: the module's docstring is allowed to
    discuss the raw store, and a grep over the whole file would match its own
    explanation. So the file is parsed and every docstring removed first.
    """
    import ast

    path = (Path(__file__).resolve().parents[2]
            / "qb2" / "tools" / "first_light.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)) and ast.get_docstring(node):
            node.body = node.body[1:]
    code = ast.unparse(tree)

    assert "RAW_INTRADAY" not in code, "first light must not reach for the raw store"
    assert "data/raw" not in code and 'data", "raw' not in code
    assert "CLEAN" in code, "it must read the clean store"


def test_the_manifest_records_the_unit_it_stored_so_a_rebuild_can_be_checked(
        store: tuple[Path, Path]) -> None:
    """Without this, "was this file converted?" has no answer after the fact."""
    raw, clean = store
    write_raw(raw, "BP.L", "1m", "2026-09-29", bars(price=500.0))
    ingest(raw, clean, intervals=("1m",))
    lines = [json.loads(line) for line
             in fd.manifest_path(clean).read_text(encoding="utf-8").splitlines()
             if line.strip()]
    ingested = [row for row in lines if row.get("event") == "ingested"]
    assert ingested[0]["quote_currency"] == "GBp"
    assert ingested[0]["stored_currency"] == "GBP"
    assert ingested[0]["pence_to_pounds"] is True
    assert ingested[0]["sha256"], "the source bytes must be identified"
    runs = [row for row in lines if row.get("event") == "run"]
    assert runs and runs[-1]["rows_in"] == runs[-1]["rows_written"]


# ------------------------------------------------------------- the quote delay

def test_the_delay_says_unmeasured_when_it_has_no_samples(tmp_path: Path) -> None:
    """FACTS row o has been wrong twice by being guessed. Zero samples says so."""
    from qb2.tools import sample_delay

    empty = tmp_path / "manifest.jsonl"
    assert sample_delay.collected(empty) == {}
    text = sample_delay.verdict(empty)
    assert "UNMEASURED" in text
    assert "0 readings taken with a checked clock" in text


def test_a_handful_of_samples_is_not_allowed_to_call_itself_measured(
        tmp_path: Path) -> None:
    """The trap: quoting a median from three samples taken in one afternoon.

    A delay that varies with the time of day needs several sessions before a
    median means anything, so the thresholds are enforced rather than advisory.
    """
    from qb2.tools import sample_delay

    manifest = tmp_path / "manifest.jsonl"
    with manifest.open("w", encoding="utf-8") as fh:
        for n in range(5):
            fh.write(json.dumps({"kind": "delay_sample", "market": "US",
                                 "age_seconds": 900.0,
                                 "clock_checked": True,
                                 "at_utc": "2026-10-01T15:00:00+00:00"}) + "\n")
    text = sample_delay.verdict(manifest)
    assert "NOT YET ENOUGH" in text
    assert "5 clock-checked samples over 1 session" in text
    assert "MEASURED --" not in text


def test_enough_samples_across_enough_sessions_reads_as_measured(
        tmp_path: Path) -> None:
    from qb2.tools import sample_delay

    manifest = tmp_path / "manifest.jsonl"
    with manifest.open("w", encoding="utf-8") as fh:
        for day in ("2026-10-01", "2026-10-02", "2026-10-05"):
            for n in range(8):
                fh.write(json.dumps({
                    "kind": "delay_sample", "market": "US", "age_seconds": 900.0,
                    "clock_checked": True,
                    "at_utc": f"{day}T15:0{n}:00+00:00"}) + "\n")
    text = sample_delay.verdict(manifest)
    assert "MEASURED" in text and "NOT YET ENOUGH" not in text
    assert "15.0 min" in text


def test_no_sample_is_taken_while_the_market_is_shut(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A bar is old because the exchange is shut. That is not the feed's delay.

    This is the exact mistake row o made the first time: 2,976-minute "delays"
    recorded over a closed weekend.
    """
    from qb2.ingest import recorder
    from qb2.tools import sample_delay

    monkeypatch.setattr(recorder, "market_is_open", lambda market, now: False)
    manifest = tmp_path / "manifest.jsonl"
    assert sample_delay.take_samples(manifest=manifest) == []
    assert not manifest.exists(), "nothing may be written while the markets are shut"
