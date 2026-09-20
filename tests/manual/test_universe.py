import shutil

import pytest

from manual.scout.universe import (REQUIRED_COLUMNS, UNIVERSE_PATH, UniverseError,
                            append_ticker, load_universe, row_for,
                            universe_tickers)


def test_shipped_universe_loads_and_is_large():
    rows = load_universe()
    assert len(rows) >= 200
    tickers = universe_tickers(rows)
    assert len(tickers) == len(set(tickers))
    ftse = [r for r in rows if r["index"] in ("FTSE100", "FTSE250")]
    assert all(r["ticker"].endswith(".L") for r in ftse)
    assert {"FTSE100", "FTSE250"} <= {r["index"] for r in rows}
    assert all(set(REQUIRED_COLUMNS) <= set(r) for r in rows)


def test_shipped_extras_gold_and_google():
    rows = load_universe()
    gold = row_for(rows, "SGLN.L")
    assert gold and gold["currency"] == "GBp" and gold["stamp_duty"] == "N"
    googl = row_for(rows, "GOOGL")
    assert googl and googl["currency"] == "USD"


def test_row_for_lookup():
    rows = load_universe()
    shell = row_for(rows, "SHEL.L")
    assert shell and shell["name"] == "Shell"
    assert row_for(rows, "ZZZZ.L") is None


def test_append_ticker_and_duplicate_guard(tmp_path):
    p = tmp_path / "u.csv"
    shutil.copy(UNIVERSE_PATH, p)
    before = len(load_universe(p))
    append_ticker({"ticker": "TEST.L", "name": "Test plc"}, p)
    rows = load_universe(p)
    assert len(rows) == before + 1
    assert row_for(rows, "TEST.L")["stamp_duty"] == "Y"
    with pytest.raises(UniverseError):
        append_ticker({"ticker": "TEST.L"}, p)


def test_missing_file_raises(tmp_path):
    with pytest.raises(UniverseError):
        load_universe(tmp_path / "missing.csv")
