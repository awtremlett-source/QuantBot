import pandas as pd
import pytest

from manual.scout.config import Config
from manual.scout.data import DataProvider, ProviderError, RefreshService
from tests.manual.conftest import uptrend_df


class FakeProvider(DataProvider):
    def __init__(self, frames, fail_tickers=()):
        self.frames = frames
        self.fail_tickers = set(fail_tickers)
        self.calls = []

    def fetch_daily(self, tickers, start=None, period=None):
        self.calls.append({"tickers": list(tickers), "start": start,
                           "period": period})
        if self.fail_tickers & set(tickers):
            raise ProviderError("simulated 429")
        out = {}
        for t in tickers:
            df = self.frames.get(t)
            if df is None:
                continue
            if start:
                df = df[df.index >= pd.Timestamp(start)]
            out[t] = df
        return out


def make_service(store, provider, **cfg_over):
    cfg = Config(chunk_pause_s=0.0, **cfg_over)
    return RefreshService(store, provider, cfg)


def test_new_ticker_full_history_stored(tmp_store):
    prov = FakeProvider({"AAA.L": uptrend_df(120)})
    svc = make_service(tmp_store, prov)
    issues = svc.refresh(["AAA.L"])
    assert issues == []
    assert tmp_store.bar_count("AAA.L") == 120
    assert prov.calls[0]["period"] == "2y" and prov.calls[0]["start"] is None


def test_incremental_appends_only_newer_rows(tmp_store):
    full = uptrend_df(100)
    tmp_store.upsert_prices("AAA.L", full.iloc[:60])
    last = full.index[59]
    prov = FakeProvider({"AAA.L": full})
    svc = make_service(tmp_store, prov)
    svc.refresh(["AAA.L"])
    assert tmp_store.bar_count("AAA.L") == 100
    expected_start = (last + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    assert prov.calls[0]["start"] == expected_start
    # closes preserved exactly, no duplicated dates
    out = tmp_store.get_prices("AAA.L")
    assert out.index.is_unique


def test_failed_chunk_isolated(tmp_store):
    prov = FakeProvider({"AAA.L": uptrend_df(50), "BAD.L": uptrend_df(50),
                         "CCC.L": uptrend_df(50)}, fail_tickers={"BAD.L"})
    svc = make_service(tmp_store, prov, chunk_size=1)
    issues = svc.refresh(["AAA.L", "BAD.L", "CCC.L"])
    assert tmp_store.bar_count("AAA.L") == 50
    assert tmp_store.bar_count("CCC.L") == 50
    assert tmp_store.bar_count("BAD.L") == 0
    assert len(issues) == 1 and "failed" in issues[0]


def test_once_per_day_guard_and_force(tmp_store):
    prov = FakeProvider({"AAA.L": uptrend_df(30)})
    svc = make_service(tmp_store, prov)
    svc.refresh(["AAA.L"])
    n_calls = len(prov.calls)
    issues = svc.refresh(["AAA.L"])
    assert "Already refreshed" in issues[0]
    assert len(prov.calls) == n_calls          # nothing fetched
    svc.refresh(["AAA.L"], force=True)
    assert len(prov.calls) > n_calls


def test_new_ticker_with_no_data_reported(tmp_store):
    prov = FakeProvider({})
    svc = make_service(tmp_store, prov)
    issues = svc.refresh(["GHOST.L"])
    assert any("GHOST.L" in i for i in issues)


def test_progress_callback_fires(tmp_store):
    prov = FakeProvider({"AAA.L": uptrend_df(30), "BBB.L": uptrend_df(30)})
    svc = make_service(tmp_store, prov, chunk_size=1)
    seen = []
    svc.refresh(["AAA.L", "BBB.L"],
                progress_cb=lambda n, t, m: seen.append((n, t)))
    assert seen == [(1, 2), (2, 2)]
