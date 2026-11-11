"""QT-30 B (P22): a second price on every closing price that drives a stop. Offline.

His words, 2026-11-08: "cant you find the closing price to confirm it elsewhere?". CONFIRMED raises
the stop; anything else does not; a hit is never suppressed; pence never read 100x off. Every run below
goes through the live jobs (daily.run, bot_pot.run) on planted second prices. Seen RED first on the
old jobs (the stop rose on every close, and only a store close could fire it).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from qb2.advisor import daily, price_check, state
from qb2.guard import stops
from qb2.ingest import close_feeds, fresh_run, recorder
from tests.qb2.test_qt23_advisor import DAYS, at
from tests.qb2.test_qt29_bot_pot import CLOSES, armed, evening, held, pot, signals

SESSION = date(2025, 3, 6)
T = "VWRP.L"


def plant(tmp: Path, *rows: dict[str, Any]) -> None:
    for row in rows:
        state.append(tmp / "price_check" / "observations.jsonl", row)


def t212(day: date, price: float, *, hour: int = 19, currency: str = "GBP", ticker: str = T) -> dict[str, Any]:
    return {"kind": "t212", "ticker": ticker, "price": price, "currency": currency,
            "fetched_at": at(day, hour).isoformat()}


def backup(day: date, close: float, *, ticker: str = T, currency: str = "GBP") -> dict[str, Any]:
    return {"kind": "backup", "ticker": ticker, "session": day.isoformat(), "close": close, "currency": currency,
            "fetched_at": at(day, 19).isoformat()}


def journal(tmp: Path) -> list[dict[str, Any]]:
    return state.rows(tmp / "price_check" / "journal.jsonl")


def sells(tmp: Path) -> list[dict[str, Any]]:
    return [dict(s) for s in signals(tmp) if s["action"] == "SELL"]


def held_at(tmp: Path, closes: list[float], *rows: dict[str, Any]) -> stops.Stop:
    """ADV-0 in; the pot's BUY fills at DAYS[2]'s open (stop 85); then DAYS[3] with these second prices."""
    armed(tmp, closes)
    evening(tmp, closes, 1)
    plant(tmp, backup(DAYS[2], closes[2]))
    evening(tmp, closes, 2)
    plant(tmp, *rows)
    evening(tmp, closes, 3)
    stop = held(tmp)
    assert stop is not None
    return stop


# ----------------------------------------------------- the bot pot: raise only when CONFIRMED

def test_a_confirmed_close_raises_the_stop(tmp_path: Path) -> None:
    stop = held_at(tmp_path, CLOSES, t212(DAYS[3], 110.2))                   # 0.18% away
    assert stop.level == pytest.approx(93.5)                                 # 110 x 0.85
    row = journal(tmp_path)[-1]
    assert (row["status"], row["source"], row["t212"], row["session"]) == ("CONFIRMED", "Trading 212", 110.2, str(DAYS[3]))
    assert row["gap_pct"] == pytest.approx(0.1815, abs=1e-3) and row["fetched_at"] and row["store"] == 110.0


def test_an_unconfirmed_close_does_not_raise_the_stop(tmp_path: Path) -> None:
    stop = held_at(tmp_path, CLOSES)                                         # no second price at all
    assert stop.level == pytest.approx(85.0)
    assert journal(tmp_path)[-1]["status"] == "UNCONFIRMED"


def test_a_disagreeing_close_does_not_raise_the_stop(tmp_path: Path) -> None:
    stop = held_at(tmp_path, CLOSES, t212(DAYS[3], 112.0))                   # 1.8% away
    assert stop.level == pytest.approx(85.0) and journal(tmp_path)[-1]["status"] == "DISAGREE"


# ----------------------------------------------------- a hit is never suppressed

def test_a_hit_on_an_unconfirmed_close_still_sells_flagged(tmp_path: Path) -> None:
    closes = [100.0, 100.0, 100.0, 80.0, 80.0]
    held_at(tmp_path, closes)
    sold = sells(tmp_path)
    assert [s["kind"] for s in sold] == ["stop"] and sold[0]["allowed"]
    assert "UNCONFIRMED — check the price yourself" in sold[0]["reason"]
    assert "closed at £80.00" in sold[0]["reason"]


def test_a_hit_on_a_confirmed_close_sells_unflagged(tmp_path: Path) -> None:
    closes = [100.0, 100.0, 100.0, 80.0, 80.0]
    held_at(tmp_path, closes, t212(DAYS[3], 80.0))
    sold = sells(tmp_path)
    assert [s["kind"] for s in sold] == ["stop"] and "UNCONFIRMED" not in sold[0]["reason"]


def test_disagree_with_one_source_at_or_below_the_stop_sells_flagged(tmp_path: Path) -> None:
    closes = [100.0, 100.0, 100.0, 90.0, 90.0]                               # the store says 90, above the 85 stop
    stop = held_at(tmp_path, closes, t212(DAYS[3], 84.0))
    sold = sells(tmp_path)
    assert [s["kind"] for s in sold] == ["stop"]
    assert "UNCONFIRMED — check the price yourself" in sold[0]["reason"] and "Trading 212" in sold[0]["reason"]
    assert "£84" not in sold[0]["reason"] and stop.level == pytest.approx(85.0)


def test_a_disagreeing_second_price_above_the_stop_fires_nothing(tmp_path: Path) -> None:
    closes = [100.0, 100.0, 100.0, 90.0, 90.0]
    held_at(tmp_path, closes, t212(DAYS[3], 95.0))
    assert sells(tmp_path) == []


# ----------------------------------------------------- the advisor's job, the same rule

def _advisor(tmp: Path, closes: list[float], *rows: dict[str, Any]) -> state.Paths:
    from tests.qb2.test_qt23_advisor import _run

    _run(tmp, closes[:1], DAYS[0], at(DAYS[0], 19), first=True)              # BUY, fills at DAYS[1]'s open
    plant(tmp, *rows)
    _run(tmp, closes, DAYS[len(closes) - 1], at(DAYS[len(closes) - 1], 19))
    return state.Paths.under(tmp)


def test_the_advisor_raises_only_on_a_confirmed_close(tmp_path: Path) -> None:
    closes = [100.0, 100.0, 104.0, 110.0]
    paths = _advisor(tmp_path, closes, backup(DAYS[1], 100.0, ticker="VWRL.L"), backup(DAYS[3], 110.0, ticker="VWRL.L"))
    stop = daily.advisor_stop(stops.Ledger(paths.stops))
    assert stop is not None and [c.level for c in stop.history] == pytest.approx([85.0, 93.5])       # DAYS[2] unconfirmed
    assert [r["status"] for r in journal(tmp_path)] == ["CONFIRMED", "UNCONFIRMED", "CONFIRMED"]


def test_the_advisors_urgent_exit_is_never_suppressed(tmp_path: Path) -> None:
    paths = _advisor(tmp_path, [100.0, 100.0, 80.0])
    urgent = [s for s in state.rows(paths.log("suggestions")) if s["kind"] == "urgent-exit"]
    assert [s["action"] for s in urgent] == ["SELL"] and "UNCONFIRMED — check the price yourself" in urgent[0]["reason"]


def test_the_advisor_fires_on_a_second_source_at_the_stop(tmp_path: Path) -> None:
    paths = _advisor(tmp_path, [100.0, 100.0, 90.0], backup(DAYS[2], 84.0, ticker="VWRL.L"))
    urgent = [s for s in state.rows(paths.log("suggestions")) if s["kind"] == "urgent-exit"]
    assert len(urgent) == 1 and "the backup feed" in urgent[0]["reason"] and "£84" not in urgent[0]["reason"]


# ----------------------------------------------------- the rule, edge by edge

@pytest.mark.parametrize(("store_close", "second", "status"), [
    (100.5, 100.0, price_check.CONFIRMED),                                   # exactly 0.5% above
    (99.5, 100.0, price_check.CONFIRMED),                                    # exactly 0.5% below
    (100.51, 100.0, price_check.DISAGREE),
    (99.49, 100.0, price_check.DISAGREE),
    (100.0, 100.0, price_check.CONFIRMED)])
def test_the_half_percent_edge_on_both_sides(store_close: float, second: float, status: str) -> None:
    assert price_check.judge(T, SESSION, store_close, backup=(second, "t")).status == status


def test_a_missing_feed_is_never_confirmed() -> None:
    check = price_check.judge(T, SESSION, 100.0)
    assert check.status == price_check.UNCONFIRMED and not check.may_raise and check.gap is None


def test_trading_212_comes_first_and_the_backup_only_if_it_has_no_close() -> None:
    both = price_check.judge(T, SESSION, 100.0, t212=(103.0, "a"), backup=(100.0, "b"))
    assert (both.source, both.status) == (price_check.T212, price_check.DISAGREE)
    only = price_check.judge(T, SESSION, 100.0, backup=(100.0, "b"))
    assert (only.source, only.status) == (price_check.BACKUP, price_check.CONFIRMED)


@pytest.mark.parametrize("currency", ["GBX", "GBp"])
def test_pence_do_not_read_a_hundred_times_off(tmp_path: Path, currency: str) -> None:
    """A pence price from Trading 212, gathered and then judged: the whole path."""
    def pence() -> list[dict[str, Any]]:
        return [{"instrument": {"ticker": "VWRPl_EQ", "currency": currency}, "currentPrice": 10_010.0}]

    target = tmp_path / "price_check" / "observations.jsonl"
    close_feeds.gather(NOW, pence, print, fetch=fetch, path=target)
    check = price_check.check_of(state.Paths.under(tmp_path), T, date(2026, 11, 6), 100.0)
    assert check.status == price_check.CONFIRMED and check.second == pytest.approx(100.10)
    assert check.source == price_check.T212


def test_a_row_not_in_pounds_is_no_price_at_all(tmp_path: Path) -> None:
    plant(tmp_path, t212(SESSION, 10_010.0, currency="GBX"))
    assert price_check.check_of(state.Paths.under(tmp_path), T, SESSION, 100.0).status == price_check.UNCONFIRMED


def test_a_dollar_price_is_no_confirmation(tmp_path: Path) -> None:
    plant(tmp_path, t212(SESSION, 100.0, currency="USD"))
    assert price_check.check_of(state.Paths.under(tmp_path), T, SESSION, 100.0).status == price_check.UNCONFIRMED


@pytest.mark.parametrize("hour", [15, 16])                                   # before the close and auction are over
def test_a_broker_read_before_that_close_does_not_count(tmp_path: Path, hour: int) -> None:
    plant(tmp_path, t212(SESSION, 100.0, hour=hour))
    assert price_check.check_of(state.Paths.under(tmp_path), T, SESSION, 100.0).status == price_check.UNCONFIRMED


def test_a_broker_read_after_the_next_open_does_not_count(tmp_path: Path) -> None:
    plant(tmp_path, t212(SESSION + timedelta(days=1), 100.0, hour=9))
    assert price_check.check_of(state.Paths.under(tmp_path), T, SESSION, 100.0).status == price_check.UNCONFIRMED


def test_a_read_at_seven_next_morning_counts_and_the_newest_wins(tmp_path: Path) -> None:
    plant(tmp_path, t212(SESSION, 90.0), t212(SESSION + timedelta(days=1), 100.0, hour=7))
    check = price_check.check_of(state.Paths.under(tmp_path), T, SESSION, 100.0)
    assert (check.status, check.second) == (price_check.CONFIRMED, 100.0)


def test_an_unreadable_file_is_unconfirmed_and_said_never_a_crash(tmp_path: Path) -> None:
    target = tmp_path / "price_check" / "observations.jsonl"
    target.parent.mkdir(parents=True)
    target.write_text("{half a line\n", encoding="utf-8")
    check = price_check.check_of(state.Paths.under(tmp_path), T, SESSION, 100.0)
    assert check.status == price_check.UNCONFIRMED and "unreadable" in check.note


def test_the_journal_only_appends_one_line_per_name_and_session(tmp_path: Path) -> None:
    held_at(tmp_path, CLOSES, t212(DAYS[3], 110.0))
    target = tmp_path / "price_check" / "journal.jsonl"
    before = target.read_text(encoding="utf-8")
    evening(tmp_path, CLOSES, 3, minute=30)                                  # the same session again
    assert target.read_text(encoding="utf-8") == before
    plant(tmp_path, t212(DAYS[4], 108.0))
    evening(tmp_path, CLOSES, 4)
    after = target.read_text(encoding="utf-8")
    assert after.startswith(before) and len(after.splitlines()) == len(before.splitlines()) + 1


def test_a_repeat_of_a_journalled_session_changes_nothing_at_all(tmp_path: Path) -> None:
    """Earlier lines stay: a repeat neither rewrites the file nor adds a line."""
    paths, stop = state.Paths.under(tmp_path), stops.Ledger(tmp_path / "s.jsonl").open(
        position_id="P", pot="advisor", ticker="VWRL.L", market="LSE", opened_at="2025-03-04T08:00:00+00:00",
        entry=100.0, atr=None, reason="test", unsettled=False)
    now = datetime(2025, 3, 7, 7, 0, tzinfo=UTC)
    for session in (date(2025, 3, 4), date(2025, 3, 5)):
        price_check.day(paths, "VWRL.L", session, 100.0, now, stop)
    target = tmp_path / "price_check" / "journal.jsonl"
    before = target.read_text(encoding="utf-8")
    assert len(before.splitlines()) == 2
    price_check.day(paths, "VWRL.L", date(2025, 3, 4), 100.0, now, stop)
    assert target.read_text(encoding="utf-8") == before


# ----------------------------------------------------- the status page

def test_the_page_says_green_or_red_with_both_prices(tmp_path: Path) -> None:
    lines = [] if held_at(tmp_path, CLOSES, t212(DAYS[3], 110.0)) is None else price_check.page_lines(pot(tmp_path), T)
    assert lines == [f"Price check: 🟢 VWRP close of {DAYS[3]} CONFIRMED — our store £110.00, Trading 212 £110.00, gap 0.00%"]
    assert any("Price check: 🟢" in x for x in (pot(tmp_path).page.read_text(encoding="utf-8").splitlines()))


def test_the_page_is_red_when_not_confirmed_and_names_the_pending_anchor(tmp_path: Path) -> None:
    paths = _advisor(tmp_path, [100.0, 100.0, 104.0], backup(DAYS[2], 104.0, ticker="VWRL.L"))
    page = paths.page.read_text(encoding="utf-8")
    assert "Price check: 🔴" not in page.split(f"close of {DAYS[2]}")[1][:10]
    assert f"VWRL close of {DAYS[2]} CONFIRMED — our store £104.00, the backup feed, gap 0.00%; backup feed only — " \
           "Trading 212 anchor pending" in page
    assert "VWRL anchor: not set up — see the QT-32 report" in page


def test_vwrp_is_never_called_anchor_pending_it_already_has_one(tmp_path: Path) -> None:
    held_at(tmp_path, CLOSES, backup(DAYS[3], 110.0))
    line = price_check.page_lines(pot(tmp_path), T)[0]
    assert "CONFIRMED" in line and "the backup feed" in line and "anchor pending" not in line


def test_the_backup_feeds_figure_is_never_printed_on_the_public_page(tmp_path: Path) -> None:
    paths = _advisor(tmp_path, [100.0, 100.0, 104.0], backup(DAYS[2], 104.33, ticker="VWRL.L"))
    assert "104.33" not in paths.page.read_text(encoding="utf-8")
    assert journal(tmp_path)[-1]["backup"] == 104.33                         # the journal keeps it


# ----------------------------------------------------- gathering the second prices

NOW = datetime(2026, 11, 9, 7, 0, tzinfo=UTC)                                # a Monday, London shut
QUOTE = {"FormattedQuoteResult": {"FormattedQuote": [{"symbol": "VWRL-GB", "currencyCode": "GBP"}]}}
BARS = {"barData": {"priceBars": [{"close": "133.6900", "tradeTime": "20261106000000"}]}}


def fetch(url: str, currency: str = "GBP") -> Any:
    symbol = "VWRP-GB" if "VWRP-GB" in url else "VWRL-GB"
    if "quote.cnbc.com" in url:
        return {"FormattedQuoteResult": {"FormattedQuote": [{"symbol": symbol, "currencyCode": currency}]}}
    return BARS


def positions() -> list[dict[str, Any]]:
    return [{"instrument": {"ticker": "VWRPl_EQ", "currency": "GBP"}, "currentPrice": 138.4}]


def test_both_sources_are_saved_with_their_fetch_time(tmp_path: Path) -> None:
    said: list[str] = []
    close_feeds.gather(NOW, positions, said.append, fetch=fetch, path=tmp_path / "o.jsonl")
    rows = state.rows(tmp_path / "o.jsonl")
    assert [(r["kind"], r["ticker"]) for r in rows] == [("t212", "VWRP.L"), ("backup", "VWRL.L"), ("backup", "VWRP.L")]
    assert {r["fetched_at"] for r in rows} == {NOW.isoformat(timespec="seconds")}
    assert rows[1]["session"] == "2026-11-06" and rows[1]["close"] == 133.69


def test_a_pence_feed_is_stored_in_pounds(tmp_path: Path) -> None:
    close_feeds.gather(NOW, positions, print, fetch=lambda u: fetch(u, "GBX"), path=tmp_path / "o.jsonl")
    assert state.rows(tmp_path / "o.jsonl")[1]["close"] == pytest.approx(1.3369)     # 133.69 pence


def test_the_same_close_is_not_saved_twice_and_a_correction_is(tmp_path: Path) -> None:
    target = tmp_path / "o.jsonl"
    close_feeds.gather(NOW, positions, print, fetch=fetch, path=target)
    close_feeds.gather(NOW, positions, print, fetch=fetch, path=target)
    assert sum(r["kind"] == "backup" for r in state.rows(target)) == 2
    corrected = {"barData": {"priceBars": [{"close": "133.7000", "tradeTime": "20261106000000"}]}}
    close_feeds.gather(NOW, positions, print, fetch=lambda u: corrected if "bars" in u else fetch(u), path=target)
    assert sum(r["kind"] == "backup" for r in state.rows(target)) == 4       # added, nothing rewritten


def test_one_source_failing_never_stops_the_other_or_the_run(tmp_path: Path) -> None:
    def broken(url: str) -> Any:
        raise OSError("no route")

    said: list[str] = []
    close_feeds.gather(NOW, positions, said.append, fetch=broken, path=tmp_path / "o.jsonl")
    assert len(state.rows(tmp_path / "o.jsonl")) == 1 and any("backup feed failed (OSError" in x for x in said)


def test_nothing_is_read_while_london_is_open(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(recorder, "market_is_open", lambda market, now: True)
    close_feeds.gather(NOW, positions, print, fetch=fetch, path=tmp_path / "o.jsonl")
    assert not (tmp_path / "o.jsonl").exists()


def test_the_recorders_hook_gathers_first_and_survives_a_fault(monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[str] = []
    def boom(*a: object, **k: object) -> None:
        order.append("gather")
        raise RuntimeError("no")

    monkeypatch.setattr(close_feeds, "gather", boom)
    monkeypatch.setattr(fresh_run, "before_clean", lambda say: order.append("before"))
    monkeypatch.setattr(fresh_run, "after_clean", lambda say: order.append("after"))
    said: list[str] = []
    assert fresh_run.around_clean(lambda after_hours: [], after_hours=False, say=said.append) == []
    assert order == ["gather", "before", "after"] and any("Price check failed" in x for x in said)


def test_the_two_daily_jobs_are_the_only_callers_of_the_rule() -> None:
    root = Path(__file__).resolve().parents[2] / "qb2"
    users = {p.relative_to(root).as_posix() for p in root.rglob("*.py")
             if "price_check.day(" in p.read_text(encoding="utf-8") and p.name != "price_check.py"}
    assert users == {"advisor/daily.py", "advisor/bot_pot.py"}
