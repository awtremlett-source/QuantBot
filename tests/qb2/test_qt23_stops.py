"""QT-23 B: the advisor's live stop is the big-fall stop (R3); bot and manual unchanged (R4); the
rule has ONE copy, shared by the live ledger and advisor_book's back-tests (R5).

Operator, 2026-10-19 (verbatim): "GO on QT-23: build the advisor with "hold the index fund" as its
default, the 15% big-fall stop (10% when markets are jumpy) as its live stop, and the rules scored
in the background on live prices only."  Offline, tmp files only. Each test was seen RED -- first
with no code, then against a planted mutant (docs/reports/QT-23_B_redfirst.py.txt).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from qb2.execution.safety import ADVISOR, BOT, MANUAL, Blocked
from qb2.guard import age
from qb2.guard import stops as S
from qb2.research import advisor_book
from tests.qb2.test_qt19b_advisor import _book, _flat, _month_end, _ranked
from tests.qb2.test_qt22_big_fall import BIG, CALM, LOUD, NAMES

OPENED = "2026-10-20T07:00:00+00:00"
NOW = datetime(2026, 10, 19, 19, 0, tzinfo=timezone.utc)


def _open(ledger: S.Ledger, pid: str, pot: str, *, entry: float = 100.0,
          unsettled: bool | None = False, opened: str = OPENED) -> S.Stop:
    return ledger.open(position_id=pid, pot=pot, ticker="VWRL.L", market="LSE", opened_at=opened,
                       entry=entry, atr=2.0, reason="test", unsettled=unsettled)


def _advisor(tmp_path: Path, *, entry: float = 100.0, opened: str = OPENED) -> S.Ledger:
    ledger = S.Ledger(tmp_path / "stops.jsonl")
    _open(ledger, "a", ADVISOR, entry=entry, opened=opened)
    return ledger


# ---------------------------------------------------------------- R3: the levels

def test_the_advisor_stop_opens_fifteen_percent_below_the_fill_ten_when_unsettled(
        tmp_path: Path) -> None:
    calm = _open(S.Ledger(tmp_path / "a.jsonl"), "a", ADVISOR)
    loud = _open(S.Ledger(tmp_path / "b.jsonl"), "b", ADVISOR, unsettled=True)
    assert (calm.level, calm.rule, calm.k, calm.bar) == (85.0, S.FALL_RULE, 0.15, "1d")
    assert (loud.level, loud.k) == (90.0, 0.10)
    assert S.FALLS == {False: 0.15, True: 0.10}
    with pytest.raises(Blocked):                                       # no figure, no stop
        _open(S.Ledger(tmp_path / "c.jsonl"), "c", ADVISOR, entry=float("nan"))


def test_the_advisor_stop_must_be_told_whether_markets_are_unsettled(tmp_path: Path) -> None:
    with pytest.raises(Blocked, match="unsettled"):
        _open(S.Ledger(tmp_path / "s.jsonl"), "a", ADVISOR, unsettled=None)
    assert not (tmp_path / "s.jsonl").exists()                          # refused, nothing written


def test_the_advisor_stop_trails_the_highest_close_by_fifteen_or_ten(tmp_path: Path) -> None:
    ledger = _advisor(tmp_path)
    assert ledger.trail("a", 120.0, None, unsettled=False).level == pytest.approx(102.0)
    assert ledger.trail("a", 118.0, None, unsettled=True).level == pytest.approx(106.2)
    assert ledger.trail("a", 119.0, None, unsettled=False).level == pytest.approx(106.2)  # kept
    assert S.fall_level(200.0, 0.15) == pytest.approx(170.0)
    assert S.fall_level(200.0, 0.15, floor=175.0) == 175.0             # never below the floor
    for price, f in ((10.12, 0.15), (10.02, 0.10)):                     # where the two forms differ
        assert price - f * price != price * (1 - f)
        assert S.fall_level(price, f) == price - f * price              # the books' arithmetic, bit for bit


# ------------------------------------------------- raise-only, on every path

def test_a_vix_flip_back_to_calm_never_lowers_the_advisor_stop(tmp_path: Path) -> None:
    ledger = _advisor(tmp_path)
    loud = ledger.trail("a", 110.0, None, unsettled=True).level        # 99.0 at 10%
    calm = ledger.trail("a", 110.0, None, unsettled=False).level       # 93.5 < 99: kept
    assert loud == pytest.approx(99.0) and calm == loud
    assert not any('"refused"' in x for x in ledger.path.read_text().splitlines())


def test_a_lowered_level_is_refused_and_logged_and_a_lowered_file_is_not_trusted(
        tmp_path: Path) -> None:
    ledger = _advisor(tmp_path)
    with pytest.raises(Blocked, match="only ever raised"):
        ledger.raise_to("a", 80.0, "recompute after restart")
    assert ledger.get("a").level == 85.0
    assert json.loads(ledger.path.read_text().splitlines()[-1])["event"] == "refused"
    with ledger.path.open("a", encoding="utf-8") as fh:               # a replayed file, lowered
        fh.write(json.dumps({"event": "raise", "position_id": "a", "level": 84.0, "at": "x",
                             "reason": "planted"}) + "\n")
    with pytest.raises(Blocked, match="LOWERED"):
        ledger.stops()


def test_a_restart_replays_the_same_levels_and_cannot_lower_them(tmp_path: Path) -> None:
    ledger = _advisor(tmp_path)
    for close in (110.0, 125.0, 120.0):
        ledger.trail("a", close, None, unsettled=False)
    again = S.Ledger(ledger.path)                                       # a fresh process
    assert again.get("a").level == pytest.approx(106.25)
    for close in (110.0, 125.0, 120.0):                                 # the same days, replayed
        again.trail("a", close, None, unsettled=False)
    assert [c.level for c in again.get("a").history] == pytest.approx([85.0, 93.5, 106.25])


def test_a_re_justified_advisor_buy_opens_no_lower_than_the_old_stop(tmp_path: Path) -> None:
    ledger = _advisor(tmp_path, opened="2025-10-01T07:00:00+00:00")
    ledger.trail("a", 130.0, None, unsettled=False)                     # 110.5
    new = age.rebuy(ledger, "a", new_position_id="a2", price=125.0, atr=None,
                    reason="12 months: the default re-justifies (R7)", now=NOW, unsettled=False)
    assert new.level == pytest.approx(110.5)                            # 125 x 0.85 = 106.25 < 110.5
    assert new.opened_at.startswith("2026-10-19") and new.rule == S.FALL_RULE
    assert set(ledger.stops()) == {"a2"}
    fresh = age.rebuy(ledger, "a2", new_position_id="a3", price=140.0, atr=None,
                      reason="and again", now=NOW, unsettled=False)
    assert fresh.level == pytest.approx(119.0)                          # 140 x 0.85 > 110.5


def test_a_re_justify_below_the_old_stop_is_refused_before_anything_closes(tmp_path: Path) -> None:
    ledger = _advisor(tmp_path)                                         # stop 85
    with pytest.raises(Blocked, match="protects nothing"):
        age.rebuy(ledger, "a", new_position_id="a2", price=84.0, atr=None, reason="late",
                  now=NOW, unsettled=False)                             # crossed: an exit, not a re-buy
    with pytest.raises(Blocked, match="unsettled"):
        age.rebuy(ledger, "a", new_position_id="a2", price=120.0, atr=None, reason="no VIX",
                  now=NOW, unsettled=None)
    assert set(ledger.stops()) == {"a"}                                 # nothing was closed


def test_a_re_justified_record_written_lower_is_not_trusted(tmp_path: Path) -> None:
    ledger = _advisor(tmp_path)
    ledger.trail("a", 130.0, None, unsettled=False)                     # 110.5
    ledger.close("a", "planted: re-justified")
    with ledger.path.open("a", encoding="utf-8") as fh:                 # a hand-made re-open, lower
        fh.write(json.dumps({"event": "open", "position_id": "a2", "pot": ADVISOR, "ticker": "VWRL.L",
                             "market": "LSE", "opened_at": OPENED, "entry": 125.0, "atr": 0.0,
                             "k": 0.15, "bar": "1d", "level": 106.25, "reason": "planted",
                             "rule": S.FALL_RULE, "replaces": "a", "at": "x"}) + "\n")
    with pytest.raises(Blocked, match="LOWER"):
        ledger.stops()


# ------------------------------------------------ crossed: an alert, never a sale

def test_a_crossed_advisor_stop_is_an_urgent_exit_never_a_sell(tmp_path: Path) -> None:
    ledger = _advisor(tmp_path)
    _open(ledger, "b", BOT)
    acts = {a.pot: a.kind for a in ledger.catch_up({"VWRL.L": 85.0})}
    assert acts[ADVISOR] == S.URGENT_EXIT                               # at the level = crossed
    assert acts[BOT] == S.SELL                                          # 85 < 94: the bot's own
    unchecked = ledger.check({})
    assert [a.kind for a in unchecked] == [S.UNCHECKED, S.UNCHECKED]
    assert "no price, stop NOT checked" in unchecked[0].message         # in plain words
    assert json.loads(ledger.path.read_text().splitlines()[-1])["event"] == "checked"


# ------------------------------------------------------- R4: bot and manual

def test_bot_and_manual_stops_are_still_three_atr_two_when_unsettled(tmp_path: Path) -> None:
    ledger = S.Ledger(tmp_path / "s.jsonl")
    bot, man = _open(ledger, "b", BOT), _open(ledger, "m", MANUAL, unsettled=None)
    assert (bot.level, bot.rule, bot.bar) == (94.0, S.ATR_RULE, "5m")
    assert (man.level, man.rule, man.bar) == (94.0, S.ATR_RULE, "1d")
    assert ledger.trail("m", 110.0, 2.0, unsettled=True).level == 106.0   # 110 - 2 x 2
    assert ledger.trail("b", 110.0, 2.0, unsettled=False).level == 104.0  # 110 - 3 x 2
    assert S.plan("AAPL", 100.0, 2.0) == S.StopPlan("AAPL", 100.0, 2.0, 3.0, 94.0)
    assert S.RULE_OF == {BOT: S.ATR_RULE, ADVISOR: S.FALL_RULE, MANUAL: S.ATR_RULE}


def test_a_manual_re_justify_is_unchanged_three_atr_at_the_new_price(tmp_path: Path) -> None:
    ledger = S.Ledger(tmp_path / "s.jsonl")
    _open(ledger, "m1", MANUAL, opened="2025-10-01T14:00:00+00:00")
    ledger.trail("m1", 130.0, 2.0, unsettled=False)                     # 124
    new = age.rebuy(ledger, "m1", new_position_id="m2", price=120.0, atr=3.0, reason="ok", now=NOW)
    assert new.level == pytest.approx(111.0)                            # R4: unchanged; flagged


def test_an_old_ledger_without_a_rule_field_replays_as_atr(tmp_path: Path) -> None:
    path = tmp_path / "s.jsonl"
    path.write_text(json.dumps({"event": "open", "position_id": "m", "pot": MANUAL, "ticker": "BP.L",
                                "market": "LSE", "opened_at": OPENED, "entry": 100.0, "atr": 2.0,
                                "k": 3.0, "bar": "1d", "level": 94.0, "reason": "QT-16",
                                "at": "x"}) + "\n", encoding="utf-8")
    assert S.Ledger(path).get("m").rule == S.ATR_RULE


# ------------------------------------------------------------ R5: one copy

def test_the_book_and_the_ledger_share_one_copy_of_the_rule(monkeypatch: pytest.MonkeyPatch,
                                                             tmp_path: Path) -> None:
    close, jan = _flat(), _month_end(2015, 1)
    close[jan + 5] = close[jan + 4] * 0.87                              # -13% from the FILL level
    risen = _flat()
    risen[jan + 3:] = 120.0                                             # up 20% after the fill, so
    risen[jan + 6] = 120.0 * 0.87                                       # the RAISED level decides
    books = {name: _book(_ranked(NAMES), {"N0": c}, s=BIG, vix=CALM)[0] for name, c in
             (("fill", close), ("raise", risen))}
    assert books["fill"].decisions["N0"][jan + 5] == books["raise"].decisions["N0"][jan + 6] == 1.0
    real = S.fall_level
    monkeypatch.setattr(S, "fall_level", lambda p, f, floor=None: real(p, f / 2, floor))
    tight = {name: _book(_ranked(NAMES), {"N0": c}, s=BIG, vix=CALM)[0] for name, c in
             (("fill", close), ("raise", risen))}                       # both paths read THE copy
    assert tight["fill"].decisions["N0"][jan + 5] == tight["raise"].decisions["N0"][jan + 6] == 0.0
    assert _open(S.Ledger(tmp_path / "x.jsonl"), "x", ADVISOR).level == pytest.approx(92.5)
    assert vars(advisor_book)["stops"] is S                             # the same module, not a copy


def test_the_book_still_tightens_to_ten_percent_when_vix_is_high() -> None:
    close, jan = _flat(), _month_end(2015, 1)
    close[jan + 5] = close[jan + 4] * 0.88
    calm, _ = _book(_ranked(NAMES), {"N0": close}, s=BIG, vix=CALM)
    loud, _ = _book(_ranked(NAMES), {"N0": close}, s=BIG, vix=LOUD)
    assert calm.decisions["N0"][jan + 5] == 1.0 and loud.decisions["N0"][jan + 5] == 0.0
