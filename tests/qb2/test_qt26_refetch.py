"""QT-26 B: a re-fetch that brings a closed session back broken never costs the store its sane row.

The cause (QT-25, live): every top-up re-fetches each name's whole history and rewrote the file
whole. VWRL.L's Fri 23 Oct row, stored sane on Friday after London's close, came back on Mon 26
Oct 06:17 UTC with no close: the door set it aside and wrote the file without Friday, and the
advisor lost the session for a day. The quarantine file was rewritten whole too, so when the bar
came back sane at 20:11 UTC the broken one vanished from it -- quarantine is never deleted.
The real rows are in tests/museum/vwrl_2026-10-23_refetch.json. The fetcher is injected: no network.
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from qb2.advisor import live
from qb2.data import daily_step
from qb2.ingest import daily, refetch
from tests.qb2.test_qt25_front_door import AAPL, VWRL, ZONES, vix_entry

MUSEUM = json.loads((Path(__file__).resolve().parents[1] / "museum" / "vwrl_2026-10-23_refetch.json")
                    .read_text(encoding="utf-8"))
SANE: dict[str, list[float]] = MUSEUM["sane"]
BROKEN: list[float | None] = MUSEUM["broken_2026-10-23"]
HISTORIC: dict[str, list[float | None]] = MUSEUM["historic_broken"]           # on every fetch, as live
FRI_1810_UK = datetime(2026, 10, 23, 17, 10, 32, tzinfo=timezone.utc)      # London closed, NY trading
FRI_1410_UK = datetime(2026, 10, 23, 13, 10, tzinfo=timezone.utc)          # London trading (BST)
MON_0617_UK = datetime(2026, 10, 26, 6, 17, 30, tzinfo=timezone.utc)       # Friday final everywhere
MON_2011_UK = datetime(2026, 10, 26, 20, 11, 6, tzinfo=timezone.utc)       # Monday final (NY 20:00 UK)
FRIDAY = "2026-10-23"


class _Provider:
    """VWRL.L's rows as given, after one older broken bar the provider sends every time (London's
    clock, as it stamps them); every other name a flat 100 every weekday to ``end``, the same on
    every fetch, so only VWRL can differ between fetches."""

    def __init__(self, vwrl: dict[str, list[float | None]], end: str) -> None:
        self.vwrl, self.end = vwrl, end

    def __call__(self, symbol: str) -> pd.DataFrame | None:
        if symbol == "VWRL.L":
            rows: dict[str, list[float | None]] = {**HISTORIC, **self.vwrl}
            index = pd.DatetimeIndex([pd.Timestamp(d).tz_localize("Europe/London") for d in rows])
            return pd.DataFrame([[math.nan if x is None else x for x in r] for r in rows.values()],
                                columns=list(daily.COLUMNS), index=index)
        index = pd.bdate_range(end=self.end, periods=30, tz=ZONES[symbol])
        return pd.DataFrame({"open": 100.0, "high": 105.0, "low": 95.0, "close": 100.0,
                             "volume": 1000.0}, index=index)


def _rows(through: str, friday: list[float | None] | None = None) -> dict[str, list[float | None]]:
    """The real sane rows to ``through``; ``friday`` replaces 23 Oct's (broken, or corrected)."""
    rows: dict[str, list[float | None]] = {d: list(r) for d, r in SANE.items() if d <= through}
    if friday is not None:
        rows[FRIDAY] = friday
    return rows


def _top_up(root: Path, now: datetime, vwrl: dict[str, list[float | None]], end: str) -> str:
    return daily_step.run_if_due(now, clean_root=root / "clean", fetch=_Provider(vwrl, end),
                                 entries=[AAPL, VWRL, vix_entry()], digest_dir=root / "digest")


def _stored(root: Path, day: str) -> list[float] | None:
    frame = daily.load("VWRL.L", root / "clean")
    assert frame is not None
    hit = frame[pd.DatetimeIndex(frame.index).date == date.fromisoformat(day)]
    return None if hit.empty else [float(x) for x in hit[list(daily.COLUMNS)].iloc[0]]


def _quarantined(root: Path, day: str) -> list[list[float]]:
    frame = pd.read_parquet(root / "clean" / "quarantine" / "daily" / "VWRL.L-impossible.parquet")
    hit = frame[pd.DatetimeIndex(frame.index).date == date.fromisoformat(day)]
    return [[float(x) for x in r] for r in hit[list(daily.COLUMNS)].to_numpy()]


def _events(root: Path, event: str) -> list[dict[str, object]]:
    lines = (root / "clean" / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
    return [r for r in map(json.loads, lines) if r.get("event") == event and r.get("table") == "daily"]


def _same(a: list[float] | None, b: list[float | None]) -> bool:
    return a is not None and all((math.isnan(x) and y is None) or x == y for x, y in zip(a, b, strict=True))


# (a) the stored sane row is kept; the broken one set aside, and named ---------------------------

def test_a_sane_stored_row_is_kept_when_its_refetch_comes_back_broken(tmp_path: Path) -> None:
    """The museum case, Fri 18:10 UK then Mon 06:17 UTC: Friday's sane row survives Monday's broken
    re-fetch, the broken bar is in the quarantine, and the door says so."""
    _top_up(tmp_path, FRI_1810_UK, _rows(FRIDAY), FRIDAY)
    line = _top_up(tmp_path, MON_0617_UK, _rows(FRIDAY, BROKEN), FRIDAY)
    assert _stored(tmp_path, FRIDAY) == SANE[FRIDAY]
    assert len(quarantined := _quarantined(tmp_path, FRIDAY)) == 1 and _same(quarantined[0], BROKEN)
    assert [(r["symbol"], r["sessions"], r["closes"], r["at"]) for r in _events(tmp_path, "kept")] == [
        ("VWRL.L", [FRIDAY], [137.0], "2026-10-26T06:17:30+00:00")]
    assert line == ("Daily store: fresh to 2026-10-23 · OK · 1 stored row kept, its re-fetch came back "
                    "broken (set aside): VWRL.L 2026-10-23")
    bars = live.bars("VWRL.L", "LSE", date(2026, 10, 23), clean_root=tmp_path / "clean")
    assert (str(live.days_of(bars.index, "LSE")[-1]), float(bars["close"].iloc[-1])) == (FRIDAY, 137.0)


# (b) stored broken, re-fetched sane: the sane one wins -----------------------------------------

def test_the_museum_sequence_ends_with_friday_sane_and_its_broken_bar_still_set_aside(tmp_path: Path) -> None:
    """Mon 06:17 broken (nothing sane stored: as live, since QT-25's door), then Mon 20:11 sane: the
    sane row is stored, and the broken bar is STILL in the quarantine (it vanished, live)."""
    line = _top_up(tmp_path, MON_0617_UK, _rows(FRIDAY, BROKEN), FRIDAY)
    assert _stored(tmp_path, FRIDAY) is None and "RED (LSE ends 2026-10-22" in line
    _top_up(tmp_path, MON_2011_UK, _rows("2026-10-26"), "2026-10-26")
    assert _stored(tmp_path, FRIDAY) == SANE[FRIDAY] and _stored(tmp_path, "2026-10-26") == SANE["2026-10-26"]
    assert len(quarantined := _quarantined(tmp_path, FRIDAY)) == 1 and _same(quarantined[0], BROKEN)


def test_a_broken_row_in_the_stored_file_gives_way_to_a_sane_refetch_and_is_never_kept(tmp_path: Path) -> None:
    """A stored file holding a broken row (written before any check): a sane re-fetch replaces it;
    a broken re-fetch does not bring the stored broken one back (only a SANE stored row is kept)."""
    for again, want in ((SANE[FRIDAY], SANE[FRIDAY]), (BROKEN, None)):
        root = tmp_path / ("sane" if want else "broken")
        clean = root / "clean"
        (clean / "daily").mkdir(parents=True)
        legacy = _Provider(_rows(FRIDAY, BROKEN), FRIDAY)("VWRL.L")
        assert legacy is not None
        legacy.assign(currency="GBP").to_parquet(clean / "daily" / "VWRL.L.parquet")
        daily.ingest([VWRL], fetch=_Provider(_rows(FRIDAY, list(again)), FRIDAY), clean_root=clean,
                     include_fx=False, now=MON_0617_UK)
        assert _stored(root, FRIDAY) == want
        assert _events(root, "kept") == []


# (c) a provider correction: the newer sane row wins, named with both figures --------------------

def test_a_provider_correction_wins_and_is_named_with_both_figures(tmp_path: Path) -> None:
    corrected = [137.0, 137.11000061035156, 136.00999450683594, 137.05, 136355]
    _top_up(tmp_path, FRI_1810_UK, _rows(FRIDAY), FRIDAY)
    line = _top_up(tmp_path, MON_0617_UK, _rows(FRIDAY, list(corrected)), FRIDAY)
    assert _stored(tmp_path, FRIDAY) == corrected
    assert [(r["symbol"], r["changes"]) for r in _events(tmp_path, "corrected")] == [
        ("VWRL.L", [[FRIDAY, 137.0, 137.05]])]
    assert line == ("Daily store: fresh to 2026-10-23 · OK · 1 close corrected by the provider (the newer "
                    "one kept): VWRL.L 2026-10-23 137.00 → 137.05")


def test_an_unchanged_refetch_reads_exactly_as_before(tmp_path: Path) -> None:
    """GUARD (green on the old code): the same sane rows again -- nothing kept, nothing corrected."""
    _top_up(tmp_path, FRI_1810_UK, _rows(FRIDAY), FRIDAY)
    line = _top_up(tmp_path, MON_0617_UK, _rows(FRIDAY), FRIDAY)
    assert line == "Daily store: fresh to 2026-10-23 · OK"
    assert _stored(tmp_path, FRIDAY) == SANE[FRIDAY]
    assert _events(tmp_path, "corrected") == [] and _events(tmp_path, "kept") == []


# (d) a session not yet closed: QT-25's refusal, unchanged ---------------------------------------

def test_a_session_still_trading_is_refused_and_no_stored_row_rescues_it(tmp_path: Path) -> None:
    """GUARD: Fri 14:10 UK, London trading. A stored 23 Oct row (a snapshot from before QT-25's door)
    is never kept for an open session -- whether the re-fetch is broken or a sane-looking snapshot."""
    for again in (BROKEN, SANE[FRIDAY]):
        root = tmp_path / ("broken" if again is BROKEN else "snapshot")
        clean = root / "clean"
        (clean / "daily").mkdir(parents=True)
        snapshot = _Provider(_rows(FRIDAY), FRIDAY)("VWRL.L")
        assert snapshot is not None
        snapshot.assign(currency="GBP").to_parquet(clean / "daily" / "VWRL.L.parquet")
        outcome = daily.ingest([VWRL], fetch=_Provider(_rows(FRIDAY, list(again)), FRIDAY),
                               clean_root=clean, include_fx=False, now=FRI_1410_UK)
        assert _stored(root, FRIDAY) is None and _stored(root, "2026-10-22") == SANE["2026-10-22"]
        assert outcome.refused == ({} if again is BROKEN else {"VWRL.L": [FRIDAY]})
        assert _events(root, "kept") == []


def test_a_stored_file_that_cannot_be_compared_is_left_to_the_refetch_as_before() -> None:
    """GUARD (written with the fix): a stored file on another clock, or without its price columns,
    keeps nothing and names nothing -- the re-fetch is stored as before QT-26."""
    fresh = _Provider(_rows(FRIDAY), FRIDAY)("VWRL.L")
    assert fresh is not None
    fresh = fresh[pd.DatetimeIndex(fresh.index).date != date(2025, 7, 29)]
    other_clock = fresh.tz_convert("America/New_York")
    no_volume = fresh.drop(columns="volume")
    for stored in (other_clock, no_volume):
        merged = refetch.merge(fresh, stored, {date(2026, 10, 22)})
        assert merged.frame is fresh and merged.kept == [] and merged.corrected == []
