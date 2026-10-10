"""QT-14A: the T212 freshness meter and the P20 cross-check in shadow. Offline.

P20's enforcers: a pence-quoted name never reads as a 100x mismatch; a missing
comparison BLOCKS; 3 blocked names in one sweep stop that market; London's lines
are wider than the US ones by the square-root rule. The freshness meter: a
planted 4-minute lag is recovered as 4; a flat series does not count; an API
failure is logged and skipped. And the order inside a run: live sampling first,
then these polls, then the after-hours step.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from qb2.data import access, clean_step, universe
from qb2.execution import safety, sender, xcheck
from qb2.execution.sender import OrderRequest
from qb2.ingest import fresh_run, recorder, t212_fresh, xcheck_shadow
from qb2.tools import record_now, sample_delay, status_push

LSE_BP = dict(quote_currency="GBX", broker_currency="GBX", our_currency="GBP",
              our_age_seconds=60.0)


def _rate(ticker: str, broker: float | None, ours: float | None, market: str = "LSE",
          **kw: Any) -> xcheck.Rating:
    args = {**LSE_BP, **kw} if market == "LSE" else {
        "quote_currency": "USD", "broker_currency": "USD", "our_currency": "USD",
        "our_age_seconds": 60.0, **kw}
    return xcheck.rate(ticker, market, broker_price=broker, our_price=ours, **args)


# ----------------------------------------------------------- P20, the rule --

def test_a_pence_quoted_name_does_not_read_as_a_100x_mismatch() -> None:
    rating = _rate("BPl_EQ", 586.40, 5.8640)            # GBX broker, GBP clean store
    assert rating.level == xcheck.OK and rating.gap == pytest.approx(0.0)
    assert xcheck.to_quote(5.864, "GBP", "GBX") == pytest.approx(586.4)
    assert xcheck.to_quote(586.4, "GBp", "GBX") == pytest.approx(586.4)


def test_a_missing_comparison_blocks_and_says_why() -> None:
    for rating in (_rate("BPl_EQ", None, 5.86), _rate("BPl_EQ", 586.0, None),
                   _rate("CPGl_EQ", 30.0, 25.0, quote_currency="USD",
                         broker_currency="USD", our_currency="GBP")):
        assert rating.level == xcheck.NO_COMPARISON and rating.blocks
        assert rating.reason
    with pytest.raises(safety.Blocked, match="no comparison possible"):
        xcheck.guard("BPl_EQ", None)


def test_a_stale_price_of_ours_is_no_comparison() -> None:
    assert _rate("AAPL_US_EQ", 200.0, 200.0, market="US",
                 our_age_seconds=600.0).level == xcheck.NO_COMPARISON


def test_three_blocked_names_in_one_sweep_stop_that_market_only() -> None:
    lse = [_rate(f"N{i}l_EQ", 100.0, 1.03) for i in range(3)]         # 3% gaps
    assert {r.level for r in lse} == {xcheck.BLOCK}
    us = [_rate("AAPL_US_EQ", 200.0, 200.1, market="US")]
    final = xcheck.sweep([*lse, *us])
    assert [r.level for r in final[:3]] == [xcheck.STOP] * 3
    assert final[3].level == xcheck.OK
    two = xcheck.sweep(lse[:2] + [_rate("OKl_EQ", 100.0, 1.0)])
    assert [r.level for r in two] == [xcheck.BLOCK, xcheck.BLOCK, xcheck.OK]


def test_one_name_over_five_percent_stops_the_market() -> None:
    final = xcheck.sweep([_rate("Xl_EQ", 100.0, 1.06), _rate("Yl_EQ", 100.0, 1.0)])
    assert [r.level for r in final] == [xcheck.STOP, xcheck.STOP]


def test_london_lines_are_wider_than_the_us_by_the_square_root_rule() -> None:
    us, lse = xcheck.thresholds("US"), xcheck.thresholds("LSE")
    assert us.warn == pytest.approx(0.0025 * math.sqrt(1.25 / 1.6))
    assert lse.warn == pytest.approx(0.0025 * math.sqrt(16.66 / 1.6))
    assert lse.block_floor / us.block_floor == pytest.approx(math.sqrt(16.66 / 1.25))
    assert lse.warn > us.warn and lse.block_floor > us.block_floor
    assert lse.stop_one_name == us.stop_one_name == 0.05      # not scaled (strict side)
    # the figures written into PLAN_V3 P20
    assert (round(us.warn * 100, 3), round(us.block_floor * 100, 3)) == (0.221, 0.442)
    assert (round(lse.warn * 100, 3), round(lse.block_floor * 100, 3)) == (0.807, 1.613)


def test_the_atr_term_widens_the_block_line_with_the_same_scaling() -> None:
    quiet = _rate("Al_EQ", 100.0, 1.02)
    loud = _rate("Al_EQ", 100.0, 1.02, atr=0.01)           # ATR 1p on a GBP1 line
    assert quiet.level == xcheck.BLOCK
    assert loud.block_at == pytest.approx(0.01 / 1.0 * xcheck.scale("LSE"))
    assert loud.level == xcheck.WARN


# ------------------------------------------------- the sender's chain (S10) --

def test_the_sender_still_refuses_everything() -> None:
    assert sender.ARMED is False
    clean = xcheck.Rating("ISFl_EQ", "LSE", xcheck.OK, 0.0, 0.016, "planted")
    for check in (None, clean):
        for side in ("BUY", "SELL"):
            with pytest.raises(sender.NotArmed):
                sender.send(OrderRequest("ISFl_EQ", side, 1.0, "LSE", 7.0, 10.0),
                            market_is_open=True, price_check=check)


def test_armed_the_cross_check_is_a_step_in_the_chain(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sender, "ARMED", True)
    buy = OrderRequest("ISFl_EQ", "BUY", 1.0, "LSE", 7.0, 10.0)
    with pytest.raises(safety.Blocked, match="no comparison possible"):
        sender.send(buy, market_is_open=True, root=tmp_path)
    bad = xcheck.Rating("ISFl_EQ", "LSE", xcheck.BLOCK, 0.03, 0.016, "planted")
    with pytest.raises(safety.Blocked, match="BLOCK"):
        sender.send(buy, market_is_open=True, root=tmp_path, price_check=bad)
    sell = OrderRequest("ISFl_EQ", "SELL", 1.0, "LSE", 7.0, 10.0)
    assert sender.send(sell, market_is_open=True, root=tmp_path,
                       place=lambda r: "sold") == "sold"      # getting out never blocks


# ------------------------------------------------------ the freshness meter --

T0 = datetime(2026, 10, 12, 10, 5, 7, tzinfo=UTC)


def _minute_closes(start: datetime, minutes: int, seed: int = 1) -> pd.Series:
    rng = np.random.default_rng(seed)
    index = pd.date_range(start, periods=minutes, freq="1min", tz="UTC")
    return pd.Series(5.0 * np.exp(np.cumsum(rng.normal(0, 0.0008, minutes))), index=index)


def _polls_at_lag(closes: pd.Series, lag: int) -> list[tuple[datetime, float]]:
    out = []
    for i in range(10):
        at = T0 + timedelta(seconds=30 * i)
        cutoff = at - timedelta(minutes=lag)
        done = closes[closes.index + pd.Timedelta(minutes=1) <= cutoff]
        out.append((at, float(done.iloc[-1])))
    return out


def test_a_planted_four_minute_lag_is_recovered_as_four() -> None:
    closes = _minute_closes(T0 - timedelta(minutes=45), 60)
    result = t212_fresh.fit(_polls_at_lag(closes, 4), closes)
    assert result.best_lag == 4 and result.counted, result.reason


def test_a_flat_series_does_not_count() -> None:
    closes = _minute_closes(T0 - timedelta(minutes=45), 60)
    flat = [(T0 + timedelta(seconds=30 * i), 5.0) for i in range(10)]
    result = t212_fresh.fit(flat, closes)
    assert not result.counted and "flat" in result.reason


def test_no_bars_for_the_long_lags_is_not_counted() -> None:
    closes = _minute_closes(T0 - timedelta(minutes=8), 20)      # just after the open
    result = t212_fresh.fit(_polls_at_lag(closes, 2), closes)
    assert not result.counted and "no bars" in result.reason


class _Clock:
    def __init__(self) -> None:
        self.t = T0

    def now(self) -> datetime:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += timedelta(seconds=seconds)


def _position(ticker: str, price: float, currency: str = "GBX") -> dict[str, Any]:
    return {"instrument": {"ticker": ticker, "currency": currency},
            "currentPrice": price, "quantity": 0.2}


def test_ten_polls_thirty_seconds_apart_inside_five_minutes() -> None:
    clock = _Clock()
    polls = t212_fresh.poll_series(lambda: [_position("BPl_EQ", 586.0)],
                                   still_open=lambda m: True, say=lambda s: None,
                                   sleep=clock.sleep, now=clock.now)
    assert len(polls) == 10
    span = (polls[-1].at - polls[0].at).total_seconds()
    assert span == 270.0 <= t212_fresh.CAP_SECONDS
    assert polls[0].prices == {"BPl_EQ": (586.0, "GBX")}


def test_an_api_failure_is_logged_and_skipped_never_fatal() -> None:
    clock, calls = _Clock(), [0]
    said: list[str] = []

    def flaky() -> list[dict[str, Any]]:
        calls[0] += 1
        if calls[0] % 3 == 0:
            raise ConnectionError("planted")
        return [_position("BPl_EQ", 586.0)]

    polls = t212_fresh.poll_series(flaky, still_open=lambda m: True, say=said.append,
                                   sleep=clock.sleep, now=clock.now)
    assert len(polls) == 7 and calls[0] == 10
    assert sum("poll failed (ConnectionError)" in s for s in said) == 3


def test_polling_stops_when_london_closes() -> None:
    clock = _Clock()
    polls = t212_fresh.poll_series(lambda: [], still_open=lambda m: m < T0 + timedelta(
        seconds=100), say=lambda s: None, sleep=clock.sleep, now=clock.now)
    assert len(polls) == 4


ENTRY = {"yfinance": "BP.L", "t212_ticker": "BPl_EQ", "quote_currency": "GBX",
         "exchange": "London Stock Exchange", "kind": "STOCK"}


def _poll_file(folder: Path, closes: pd.Series, lag: int, run: str = "R1") -> None:
    polls = [t212_fresh.Poll(at, {"BPl_EQ": (p * 100.0, "GBX")})       # pence
             for at, p in _polls_at_lag(closes, lag)]
    t212_fresh.save_polls(polls, run, folder)


def _bars(closes: pd.Series) -> pd.DataFrame:
    return pd.DataFrame({"close": closes.to_numpy(), "currency": "GBP"},
                        index=closes.index.tz_convert("Europe/London"))


def test_measuring_a_day_converts_units_and_counts(tmp_path: Path) -> None:
    closes = _minute_closes(T0 - timedelta(minutes=45), 60)
    _poll_file(tmp_path, closes, lag=15)
    rows = t212_fresh.measure_day(T0.date(), tmp_path, entries=[ENTRY],
                                  bars_of=lambda s, d: _bars(closes))
    assert [(r["best_lag"], r["counted"]) for r in rows] == [(15, True)]


def test_a_name_that_is_not_minute_ok_is_not_counted(tmp_path: Path) -> None:
    closes = _minute_closes(T0 - timedelta(minutes=45), 60)
    _poll_file(tmp_path, closes, lag=15)

    def refused(symbol: str, day: date) -> pd.DataFrame:
        raise access.AccessRefused("BP.L is FIVE_MIN_ONLY: ...")
    rows = t212_fresh.measure_day(T0.date(), tmp_path, entries=[ENTRY], bars_of=refused)
    assert rows[0]["counted"] is False and rows[0]["reason"] == "name is not MINUTE_OK"


def test_pending_days_are_measured_once_and_only_when_clean(tmp_path: Path) -> None:
    closes = _minute_closes(T0 - timedelta(minutes=45), 60)
    _poll_file(tmp_path / "raw", closes, lag=15)
    out = tmp_path / "samples.jsonl"
    kw: dict[str, Any] = dict(entries=[ENTRY], bars_of=lambda s, d: _bars(closes))
    day = T0.date()
    assert t212_fresh.measure_pending(day - timedelta(days=1), tmp_path / "raw", out, **kw) == 0
    assert t212_fresh.measure_pending(day, tmp_path / "raw", out, **kw) == 1
    assert t212_fresh.measure_pending(day, tmp_path / "raw", out, **kw) == 0
    line = t212_fresh.status_line(out)
    assert line.startswith("T212 London freshness: 1 counted / 1 sessions · median 15 min")
    assert "UNVERIFIED" in line


def test_the_status_page_carries_both_s4_lines(tmp_path: Path) -> None:
    xcheck_shadow.log([_rate("BPl_EQ", 586.0, 5.86), _rate("Xl_EQ", 100.0, 1.006)],
                      T0, tmp_path / "x")
    text = status_push.build_status(tmp_path / "none.jsonl", tmp_path, T0,
                                    clean_root=tmp_path,
                                    fresh_samples=tmp_path / "s.jsonl",
                                    xcheck_folder=tmp_path / "x")
    assert "- T212 London freshness: 0 counted / 0 sessions · median — min" in text
    assert "- Cross-check (shadow): warn 0 · block 0 · stop 0" in text or \
        "- Cross-check (shadow): warn 1 · block 0 · stop 0" in text


# ------------------------------------------- the order inside a run (A1, A3) --

def test_live_sampling_first_then_polls_then_clean_then_measure(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[str] = []
    clock = _Clock()

    def tap(tag: str, value: Any = None) -> Any:
        calls.append(tag)
        return value
    monkeypatch.setattr(sample_delay, "take_samples", lambda: tap("sample", []))
    monkeypatch.setattr(recorder, "capture_incremental",
                        lambda e, interval, **kw: tap(f"fetch {interval}",
                                                      recorder.Outcome()))
    monkeypatch.setattr(recorder, "market_is_open", lambda m, now=None: m == "LSE")
    monkeypatch.setattr(universe, "bot_entries", lambda path=None: [ENTRY])
    monkeypatch.setattr(recorder, "batched_yfinance_fetch",
                        lambda names, i, d: tap("quote", {}))
    monkeypatch.setattr(fresh_run, "_positions",
                        lambda: tap("poll", [_position("BPl_EQ", 586.0)]))
    monkeypatch.setattr(fresh_run, "_utcnow", clock.now)
    monkeypatch.setattr(time, "sleep", clock.sleep)
    monkeypatch.setattr(xcheck_shadow, "FOLDER", tmp_path / "xcheck")
    monkeypatch.setattr(t212_fresh, "FOLDER", tmp_path / "fresh")
    monkeypatch.setattr(t212_fresh, "SAMPLES", tmp_path / "samples.jsonl")
    monkeypatch.setattr(t212_fresh, "measure_pending",
                        lambda through, **kw: tap("measure", 0))
    monkeypatch.setattr(clean_step, "run_if_due",
                        lambda now, after_hours: tap("clean", "planted"))
    monkeypatch.setattr(clean_step, "status_verdict",
                        lambda now: clean_step.Verdict(True, None, None))
    monkeypatch.setattr(recorder, "freshness", lambda: [])
    monkeypatch.setattr(sample_delay, "verdict", lambda: "planted")
    monkeypatch.setattr(record_now, "rotate_logs", lambda: [])
    said: list[str] = []
    monkeypatch.setattr(record_now, "say", said.append)
    code = record_now._run(argparse.Namespace(interval="1m", full=False), [], T0,
                           time.monotonic(), False)
    assert calls[:3] == ["sample", "fetch 1m", "quote"]
    assert calls[3:13] == ["poll"] * 10
    assert calls[13] == "clean"
    assert code == 0, said
    assert any("polls saved for London" in s for s in said)
    saved = (tmp_path / "fresh" / "2026-10-12.jsonl").read_text().splitlines()
    assert len(saved) == 10 and json.loads(saved[0])["prices"]["BPl_EQ"] == [586.0, "GBX"]


def test_with_markets_shut_the_run_says_freshness_skipped(
        monkeypatch: pytest.MonkeyPatch) -> None:
    said: list[str] = []
    monkeypatch.setattr(recorder, "market_is_open", lambda m, now=None: False)
    monkeypatch.setattr(fresh_run, "_positions", lambda: pytest.fail("polled while shut"))
    fresh_run.before_clean(said.append)
    assert "  T212 freshness: market closed, freshness skipped" in said


def test_a_broken_measurement_never_fails_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    said: list[str] = []

    def boom(say: object) -> None:
        raise RuntimeError("planted")
    monkeypatch.setattr(fresh_run, "before_clean", boom)
    monkeypatch.setattr(fresh_run, "after_clean", boom)
    assert fresh_run.around_clean(lambda after_hours: [], after_hours=False,
                                  say=said.append) == []
    assert sum("planted" in s for s in said) == 2
