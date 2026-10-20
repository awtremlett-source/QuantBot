"""QT-16 B1-B5: the S5 checks, each with a planted violation. Offline, tmp files only.

The premortem the box listed, one guard each: a stop lowered by any path; a
position with no stop; a check that passes on a missing input; the 15% pause
cleared by code; an earnings date used before it was knowable; an ETF blocked for
"missing" earnings; a silent 12-month roll-over; the advisor or a manual holding
sold automatically; anchors counted inside a pot.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from qb2.execution import safety
from qb2.execution.safety import ADVISOR, BOT, MANUAL, Blocked, Holding
from qb2.guard import age, brakes, earnings_window, pots
from qb2.guard import stops as S

UTC = timezone.utc


def _ledger(tmp_path: Path) -> S.Ledger:
    return S.Ledger(tmp_path / "stops.jsonl")


def _open(ledger: S.Ledger, pid: str = "p1", pot: str = BOT, ticker: str = "AAPL",
          opened: str = "2026-10-12T14:00:00+00:00") -> S.Stop:
    return ledger.open(position_id=pid, pot=pot, ticker=ticker, market="US",
                       opened_at=opened, entry=100.0, atr=2.0, reason="test",
                       unsettled=False)                 # QT-23: the advisor's stop must be told


# ------------------------------------------------------------- B1: stops --

def test_the_stop_is_set_at_entry_minus_three_atr(tmp_path: Path) -> None:
    stop = _open(_ledger(tmp_path))
    assert stop.level == pytest.approx(94.0) and stop.bar == "5m"
    assert _open(_ledger(tmp_path), "p2", ADVISOR, "MSFT").bar == "1d"


def test_every_path_that_writes_a_level_refuses_to_lower_it(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _open(ledger)
    with pytest.raises(Blocked, match="only ever raised"):
        ledger.raise_to("p1", 90.0, "recompute")                     # direct
    with pytest.raises(Blocked, match="only ever raised"):
        ledger.raise_to("p1", float("nan"), "bad maths")
    assert ledger.trail("p1", 95.0, 2.0, unsettled=False).level == 94.0   # 89 < 94: kept
    assert ledger.trail("p1", 95.0, 2.0, unsettled=True).level == 94.0    # 91 < 94: kept
    assert ledger.trail("p1", 110.0, 2.0, unsettled=False).level == 104.0  # raised
    assert ledger.trail("p1", 107.0, 2.0, unsettled=True).level == 104.0  # tighten, not lower
    with pytest.raises(Blocked, match="already has a stop"):
        _open(ledger)                                                # re-open = reset
    refused = [json.loads(x) for x in ledger.path.read_text().splitlines()
               if '"refused"' in x]
    assert len(refused) == 2                                         # both logged
    assert ledger.get("p1").level == 104.0


def test_a_ledger_file_showing_a_stop_lowered_is_not_trusted(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _open(ledger)
    with ledger.path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"event": "raise", "position_id": "p1", "level": 80.0,
                             "at": "x", "reason": "planted"}) + "\n")
    with pytest.raises(Blocked, match="LOWERED"):
        ledger.stops()


def test_no_stop_without_a_usable_entry_and_atr(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    for entry, atr in ((None, 2.0), (100.0, None), (100.0, float("nan")), (5.0, 2.0)):
        with pytest.raises(Blocked):
            ledger.open(position_id="x", pot=BOT, ticker="AAPL", market="US",
                        opened_at="2026-10-12T14:00:00+00:00", entry=entry, atr=atr,
                        reason="t")
    assert ledger.stops() == {}


def test_unsettled_means_brake_on_or_vix_over_30_or_no_vix_figure() -> None:
    assert S.unsettled(False, 18.0) is False
    assert S.unsettled(False, 31.0) and S.unsettled(True, 12.0) and S.unsettled(False, None)


def test_a_crossed_stop_sells_the_bots_and_only_alerts_his(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _open(ledger, "b", BOT, "AAPL")
    _open(ledger, "a", ADVISOR, "MSFT")
    _open(ledger, "m", MANUAL, "NVDA")
    _open(ledger, "q", ADVISOR, "AMZN")
    acts = {a.ticker: a.kind for a in
            ledger.catch_up({"AAPL": 93.0, "MSFT": 84.0, "NVDA": 94.0})}   # QT-23 R3: MSFT's stop
    # is the advisor's big fall now, 85 (100 x 0.85), so it is crossed at 84, not at 90
    assert acts == {"AAPL": S.SELL, "MSFT": S.URGENT_EXIT, "NVDA": S.URGENT_EXIT,
                    "AMZN": S.UNCHECKED}
    logged = [json.loads(x) for x in ledger.path.read_text().splitlines()]
    assert logged[-1]["event"] == "catch_up" and logged[-1]["open"] == 4


def test_the_daily_sync_lists_any_holding_with_no_stop(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _open(ledger, "a", ADVISOR, "MSFT")
    held = [Holding("MSFT", 3, ADVISOR), Holding("BP.L", 100, MANUAL), Holding("X", 0, MANUAL)]
    assert ledger.unprotected(held) == ["manual BP.L"]


# ------------------------------------------------------------- B2: brakes --

def test_brake_levels_follow_the_pots_own_peak(tmp_path: Path) -> None:
    b = brakes.Brakes(tmp_path / "brakes.jsonl")
    seen = [b.update(BOT, v).level for v in (100, 110, 100.0, 98.9, 101, 104.6, 93.4)]
    assert seen == [brakes.OK, brakes.OK, brakes.OK, brakes.BRAKED, brakes.BRAKED,
                    brakes.OK, brakes.PAUSED]
    again = brakes.Brakes(tmp_path / "brakes.jsonl").state(BOT)            # a restart
    assert again is not None and again.level == brakes.PAUSED


def test_the_bots_pause_never_clears_without_his_words(tmp_path: Path) -> None:
    b = brakes.Brakes(tmp_path / "brakes.jsonl")
    for v in (100, 84, 100, 130):
        state = b.update(BOT, v)
    assert state.level == brakes.PAUSED                      # full recovery: still paused
    for empty in ("", "   "):
        with pytest.raises(Blocked, match="empty words"):
            b.clear_pause(empty)
    words = "GO: restart the bot after the October fall"
    fresh = b.clear_pause(words)
    assert fresh.level == brakes.OK and fresh.peak == 130
    assert any(json.loads(x).get("words") == words
               for x in b.path.read_text(encoding="utf-8").splitlines())


def test_the_advisor_says_hold_off_at_15_and_no_new_buys_at_10(tmp_path: Path) -> None:
    b = brakes.Brakes(tmp_path / "brakes.jsonl")
    b.update(ADVISOR, 100)
    assert brakes.advisor_message(b.update(ADVISOR, 89)).startswith("no new buys")
    assert brakes.advisor_message(b.update(ADVISOR, 84)).startswith("hold off")
    assert b.update(ADVISOR, 90).level == brakes.HOLD_OFF   # not yet within 5%
    # QT-23, GO 2 (2026-10-19): "no code clears it" -- back within 5%, still held off until his
    # words (tests/qb2/test_qt23_advisor.py clears it with them)
    assert b.update(ADVISOR, 96).level == brakes.HOLD_OFF


def test_a_missing_brake_state_means_no_buys_and_tight_stops(tmp_path: Path) -> None:
    b = brakes.Brakes(tmp_path / "none.jsonl")
    with pytest.raises(Blocked, match="no brake state"):
        brakes.check_buy(b.state(BOT), BOT)
    assert brakes.tighten(None) is True
    with pytest.raises(Blocked):
        b.update(BOT, float("nan"))


# ------------------------------------------------------- B3: pot limits --

def test_the_bots_limit_is_30_percent_of_the_account_at_the_check() -> None:
    lines = (pots.Line("AAPL", BOT, 2_000.0), pots.Line("MSFT", ADVISOR, 6_000.0))
    pots.check(BOT, 900.0, pots.View(10_000.0, lines))                  # 2,900 <= 3,000
    with pytest.raises(Blocked, match="past its"):
        pots.check(BOT, 1_100.0, pots.View(10_000.0, lines))
    with pytest.raises(Blocked, match="past its"):
        pots.check(BOT, 900.0, pots.View(10_000.0, lines, pending_gbp=200.0))


def test_anchors_and_his_own_holdings_count_in_neither_pot() -> None:
    lines = (pots.Line("AAPL", pots.ANCHOR, 50.0), pots.Line("BP.L", MANUAL, 5_000.0),
             pots.Line("SPY", BOT, 2_900.0))
    pots.check(BOT, 100.0, pots.View(10_000.0, lines))
    assert pots.used(BOT, lines) == 2_900.0 and pots.used(ADVISOR, lines) == 0.0


def test_a_missing_pot_figure_is_a_refusal() -> None:
    for view, spend in ((None, 10.0), (pots.View(None), 10.0), (pots.View(1e4), None),
                        (pots.View(1e4, (pots.Line("AAPL", BOT, None),)), 10.0)):
        with pytest.raises(Blocked):
            pots.check(BOT, spend, view)


# ---------------------------------------------------------------- B4: age --

def test_flag_at_eleven_months_limit_at_twelve(tmp_path: Path) -> None:
    opened = "2025-10-12T14:00:00+00:00"
    assert age.status(opened, datetime(2026, 9, 11, tzinfo=UTC)) == age.OK
    assert age.status(opened, datetime(2026, 9, 13, tzinfo=UTC)) == age.FLAG
    assert age.status(opened, datetime(2026, 10, 12, 15, tzinfo=UTC)) == age.LIMIT


def test_a_silent_roll_over_is_refused_and_a_rebuy_is_a_new_record(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    old = _open(ledger, "a1", ADVISOR, "MSFT", "2025-10-01T14:00:00+00:00")
    now = datetime(2026, 10, 12, 15, tzinfo=UTC)
    with pytest.raises(Blocked, match="silent roll-over"):
        age.check_hold(old, now)
    with pytest.raises(Blocked, match="already has a stop"):
        _open(ledger, "a1", ADVISOR, "MSFT", now.isoformat())       # restart its clock
    for pid, why in (("a1", "still good"), ("a2", "  ")):
        with pytest.raises(Blocked):
            age.rebuy(ledger, "a1", new_position_id=pid, price=120.0, atr=3.0, reason=why,
                      now=now)
    new = age.rebuy(ledger, "a1", new_position_id="a2", price=120.0, atr=3.0,
                    reason="earnings up, still cheap", now=now, unsettled=False)
    # QT-23 R3/R7: the advisor's fresh stop is the big fall, 120 x 0.85 = 102 (never below the
    # old 85); manual's re-justify stays 3 x ATR (tests/qb2/test_qt23_stops.py)
    assert set(ledger.stops()) == {"a2"} and new.level == pytest.approx(102.0)
    assert age.status(new.opened_at, now) == age.OK


def test_a_bot_position_past_its_session_is_an_incident(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _open(ledger, "b1", BOT, "AAPL", "2026-10-12T14:00:00+00:00")
    during = datetime(2026, 10, 12, 19, 30, tzinfo=UTC)
    assert age.overnight(ledger.stops().values(), during, root=tmp_path) == []
    assert not safety.killswitch_armed(tmp_path)
    after = datetime(2026, 10, 12, 20, 0, 1, tzinfo=UTC)               # US close 20:00 UTC
    found = age.overnight(ledger.stops().values(), after, root=tmp_path,
                          incidents=tmp_path / "incidents.jsonl")
    assert len(found) == 1 and safety.killswitch_armed(tmp_path)
    assert "AAPL" in (tmp_path / "incidents.jsonl").read_text(encoding="utf-8")


# ----------------------------------------------------------- B5: earnings --

def _earnings(*dates: str, known: str = "2026-10-02T17:50:00+00:00") -> pd.DataFrame:
    return pd.DataFrame({"earnings_date": list(dates), "knowable_time": known})


MONDAY = datetime(2026, 10, 26, 15, tzinfo=UTC)


def test_the_bot_is_blocked_from_the_session_before_to_the_session_after() -> None:
    frame = _earnings("2026-07-30", "2026-10-27", "2027-01-28")         # 27th: a Tuesday
    for day, blocked in ((23, False), (26, True), (27, True), (28, True), (29, False)):
        moment = datetime(2026, 10, day, 15, tzinfo=UTC)
        assert earnings_window.bot_verdict("AAPL", "STOCK", "US", moment, frame).blocked \
            is blocked, day


def test_an_unknown_date_blocks_a_share_but_never_an_etf() -> None:
    for frame in (None, _earnings("2026-07-30")):                       # none / past only
        assert earnings_window.bot_verdict("AAPL", "STOCK", "US", MONDAY, frame).blocked
    etf = earnings_window.bot_verdict("ISF.L", "ETF", "LSE", MONDAY, None)
    assert not etf.blocked and "N/A" in etf.reason
    assert earnings_window.advisor_warning("ISF.L", "ETF", "LSE", MONDAY, None) is None


def test_a_date_not_yet_knowable_is_not_used() -> None:
    later = _earnings("2026-11-30", known="2026-10-27T00:00:00+00:00")  # learnt next day
    verdict = earnings_window.bot_verdict("AAPL", "STOCK", "US", MONDAY, later)
    assert verdict.blocked and "unknown" in verdict.reason
    moved = pd.concat([_earnings("2026-10-27"),
                       _earnings("2026-11-05", known="2026-10-20T00:00:00+00:00")])
    assert not earnings_window.bot_verdict("AAPL", "STOCK", "US", MONDAY, moved).blocked


def test_the_advisor_is_warned_five_trading_days_ahead() -> None:
    frame = _earnings("2026-11-02")                                     # 5 sessions on
    assert "2026-11-02" in str(earnings_window.advisor_warning(
        "MSFT", "STOCK", "US", MONDAY, frame))
    assert earnings_window.advisor_warning("MSFT", "STOCK", "US", MONDAY,
                                           _earnings("2026-11-10")) is None
    assert earnings_window.advisor_warning("MSFT", "STOCK", "US", MONDAY, None) == \
        "MSFT: earnings date unknown"
