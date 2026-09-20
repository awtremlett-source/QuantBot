from tests.manual.conftest import uptrend_df


def test_upsert_idempotent_and_last_date(tmp_store):
    df = uptrend_df(50)
    assert tmp_store.upsert_prices("AAA.L", df) == 50
    assert tmp_store.upsert_prices("AAA.L", df) == 50  # replace, not duplicate
    assert tmp_store.bar_count("AAA.L") == 50
    assert tmp_store.last_date("AAA.L") == df.index[-1].strftime("%Y-%m-%d")


def test_get_prices_roundtrip_sorted(tmp_store):
    df = uptrend_df(30)
    tmp_store.upsert_prices("BBB.L", df.iloc[::-1])  # insert reversed
    out = tmp_store.get_prices("BBB.L")
    assert list(out.columns) == ["open", "high", "low", "close", "volume"]
    assert out.index.is_monotonic_increasing
    assert len(out) == 30
    assert out["close"].iloc[-1] == df["close"].iloc[-1]


def test_missing_ticker_empty_frame(tmp_store):
    out = tmp_store.get_prices("NOPE.L")
    assert out.empty
    assert tmp_store.last_date("NOPE.L") is None


def test_watchlist_toggle(tmp_store):
    tmp_store.watch("AAA.L", True)
    tmp_store.watch("BBB.L", True)
    tmp_store.watch("AAA.L", True)   # idempotent
    assert tmp_store.watchlist() == ["AAA.L", "BBB.L"]
    tmp_store.watch("AAA.L", False)
    assert tmp_store.watchlist() == ["BBB.L"]


def test_meta_merges(tmp_store):
    tmp_store.set_meta("AAA.L", currency="GBp")
    tmp_store.set_meta("AAA.L", note="hello")
    assert tmp_store.get_meta("AAA.L") == {"currency": "GBp", "note": "hello"}


def test_settings_roundtrip(tmp_store):
    assert tmp_store.get_setting("x") is None
    tmp_store.set_setting("x", "1")
    tmp_store.set_setting("x", "2")
    assert tmp_store.get_setting("x") == "2"


def test_delete_trade(tmp_store):
    tid = tmp_store.insert_trade(opened_at="2026-08-20 10:00",
                                 ticker="OOPS.L", entry_px=1.0,
                                 stop_px=0.9, shares=1)
    assert tmp_store.get_trade(tid) is not None
    tmp_store.delete_trade(tid)
    assert tmp_store.get_trade(tid) is None
