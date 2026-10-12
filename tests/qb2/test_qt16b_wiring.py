"""QT-16 B6: the S5 checks wired ahead of every order and suggestion. Offline.

The sender is disarmed (ARMED False); these tests arm it by monkeypatch only, and
``place`` is a recorder -- nothing can reach Trading 212.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

import pandas as pd
import pytest

from qb2.execution import safety, sender, xcheck
from qb2.execution.fill_recorder import FillRecorder
from qb2.execution.safety import ADVISOR, BOT, MANUAL, Blocked, Holding
from qb2.execution.sender import OrderRequest
from qb2.guard import brakes, earnings_window, pots, suggestion
from qb2.guard import stops as S
from qb2.tools import clear_pause

QB2 = Path(__file__).resolve().parents[2] / "qb2"
NOW = datetime(2026, 10, 12, 15, tzinfo=timezone.utc)
BUY = OrderRequest("AAPL_US_EQ", "BUY", 1.0, "US", 200.0, 5.0, consideration_gbp=150.0)
CLEAN: dict[str, Any] = dict(
    price_check=xcheck.Rating("AAPL_US_EQ", "US", xcheck.OK, 0.0, 0.004, "planted"),
    brake=brakes.State(BOT, 3000.0, 3000.0, brakes.OK, "2026-10-12"),
    pot=pots.View(10_000.0),
    earnings=earnings_window.Verdict("AAPL_US_EQ", False, "next reports 2026-10-29"),
    stop_plan=S.plan("AAPL_US_EQ", 200.0, 4.0))
VIOLATION: dict[str, Any] = {
    "brake": brakes.State(BOT, 3000.0, 2690.0, brakes.BRAKED, "2026-10-12"),
    "pot": pots.View(10_000.0, (pots.Line("MSFT_US_EQ", BOT, 2_900.0),)),
    "earnings": earnings_window.Verdict("AAPL_US_EQ", True, "AAPL reports tomorrow"),
    "stop_plan": S.plan("MSFT_US_EQ", 200.0, 4.0)}
CALLS = {"brake": "brakes.check_buy", "pot": "pots.check",
         "earnings": "earnings_window.guard", "stop_plan": "stops.check_plan"}


def _keep(into: list[OrderRequest]) -> Callable[[OrderRequest], str]:
    def place(request: OrderRequest) -> str:
        into.append(request)
        return "ok"
    return place


def _placed(module: ModuleType = sender, **kw: Any) -> list[str]:
    seen: list[OrderRequest] = []
    module.send(BUY, market_is_open=True, place=_keep(seen), **kw)
    return [r.side for r in seen]


def _level(b: brakes.Brakes) -> str:
    state = b.state(BOT)
    return state.level if state else "no state"


# ------------------------------------------------------- the sender, buys --

def test_with_every_check_clean_a_buy_reaches_the_door(monkeypatch: pytest.MonkeyPatch,
                                                       tmp_path: Path) -> None:
    monkeypatch.setattr(sender, "ARMED", True)
    assert _placed(root=tmp_path, **CLEAN) == ["BUY"]


@pytest.mark.parametrize("name", list(VIOLATION))
def test_each_planted_violation_refuses_the_buy_and_is_recorded(
        name: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sender, "ARMED", True)
    recorder = FillRecorder(tmp_path / "fills.jsonl")
    with pytest.raises(Blocked):
        _placed(root=tmp_path, recorder=recorder, **{**CLEAN, name: VIOLATION[name]})
    assert any("REFUSED" in str(row.get("note", "")) for row in recorder.lines())


@pytest.mark.parametrize("name", list(VIOLATION))
def test_a_missing_input_is_a_refusal_never_a_pass(name: str, monkeypatch: pytest.MonkeyPatch,
                                                  tmp_path: Path) -> None:
    monkeypatch.setattr(sender, "ARMED", True)
    with pytest.raises(Blocked):
        _placed(root=tmp_path, **{**CLEAN, name: None})


def test_a_buy_with_no_pound_figure_fails_the_pot_check(monkeypatch: pytest.MonkeyPatch,
                                                        tmp_path: Path) -> None:
    monkeypatch.setattr(sender, "ARMED", True)
    bare = OrderRequest("AAPL_US_EQ", "BUY", 1.0, "US", 200.0, 5.0)
    with pytest.raises(Blocked, match="order value in pounds"):
        sender.send(bare, market_is_open=True, root=tmp_path, place=lambda r: "x", **CLEAN)


def test_a_sell_skips_every_s5_check(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sender, "ARMED", True)
    safety.arm_killswitch("test", root=tmp_path)
    sell = OrderRequest("AAPL_US_EQ", "SELL", 1.0, "US", 200.0, 5.0)
    assert sender.send(sell, market_is_open=True, root=tmp_path, place=lambda r: "sold",
                       **VIOLATION) == "sold"
    assert sender.send(sell, market_is_open=False, root=tmp_path, place=lambda r: "sold") \
        == "sold"


# --------------------------------------------- the sender calls every check --

def _calls_in_send(source: str) -> set[str]:
    tree = ast.parse(source)
    send = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "send")
    return {ast.unparse(n.func) for n in ast.walk(send) if isinstance(n, ast.Call)}


def test_the_sender_calls_every_s5_check() -> None:
    source = (QB2 / "execution" / "sender.py").read_text(encoding="utf-8")
    assert set(CALLS.values()) <= _calls_in_send(source)


def _without(call: str) -> tuple[ModuleType, str]:
    """A copy of the sender with one S5 call deleted, loaded under another name."""
    source = (QB2 / "execution" / "sender.py").read_text(encoding="utf-8")
    lines = [line for line in source.splitlines() if not line.strip().startswith(call + "(")]
    assert len(lines) == len(source.splitlines()) - 1, call
    spec = importlib.util.spec_from_loader(f"sender_without_{call}", loader=None)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    text = "\n".join(lines)
    exec(compile(text, spec.name, "exec"), module.__dict__)  # noqa: S102
    return module, text


@pytest.mark.parametrize("name", list(CALLS))
def test_removing_any_one_call_lets_its_violation_through_red(name: str,
                                                              tmp_path: Path) -> None:
    mutant, text = _without(CALLS[name])
    setattr(mutant, "ARMED", True)                          # the copy, never qb2's sender
    assert _placed(mutant, root=tmp_path, **{**CLEAN, name: VIOLATION[name]}) == ["BUY"]
    assert not set(CALLS.values()) <= _calls_in_send(text)  # the wall test sees it: RED


# ------------------------------------------------------- crossed stops --

def test_only_a_bot_crossing_becomes_a_sell(tmp_path: Path) -> None:
    acts = [S.Action(S.SELL, "b", "AAPL_US_EQ", BOT, 93.0, 94.0, "x"),
            S.Action(S.URGENT_EXIT, "a", "MSFT_US_EQ", ADVISOR, 90.0, 94.0, "x"),
            S.Action(S.URGENT_EXIT, "m", "NVDA_US_EQ", MANUAL, 90.0, 94.0, "x"),
            S.Action(S.SELL, "a2", "AMZN_US_EQ", ADVISOR, 90.0, 94.0, "planted")]
    held = [Holding("AAPL_US_EQ", 2.0, BOT), Holding("MSFT_US_EQ", 5.0, ADVISOR),
            Holding("NVDA_US_EQ", 5.0, MANUAL), Holding("AMZN_US_EQ", 5.0, ADVISOR)]
    markets = {a.ticker: "US" for a in acts}
    out = sender.sell_crossed(acts, held, market_of=markets)
    assert len(out) == 1 and "AAPL_US_EQ: SELL intent refused" in out[0]   # disarmed
    sold: list[OrderRequest] = []
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(sender, "ARMED", True)
        sender.sell_crossed(acts, held, market_of=markets,
                            place=_keep(sold))
    assert [(r.ticker, r.side, r.quantity) for r in sold] == [("AAPL_US_EQ", "SELL", 2.0)]


# ------------------------------------------------- the advisor's front door --

def _stop(opened: str) -> S.Stop:
    return S.Stop("a1", ADVISOR, "MSFT", "US", opened, 100.0, 2.0, 3.0, "1d",
                  (S.Change(opened, 94.0, "open"),))


def test_check_suggestion_runs_brake_pot_earnings_and_age() -> None:
    ok = brakes.State(ADVISOR, 7000.0, 7000.0, brakes.OK, "x")
    off = brakes.State(ADVISOR, 7000.0, 5900.0, brakes.HOLD_OFF, "x")
    view = pots.View(10_000.0, (pots.Line("VWRP", ADVISOR, 6_900.0),))
    buy = suggestion.Suggestion("MSFT", suggestion.BUY, "STOCK", "US", spend_gbp=150.0)
    soon = pd.DataFrame({"earnings_date": ["2026-10-14"],
                         "knowable_time": "2026-10-01T00:00:00+00:00"})
    a = suggestion.check_suggestion(buy, brake=ok, pot=pots.View(10_000.0), earnings=soon,
                                    now=NOW)
    assert a.allowed and any("reports on 2026-10-14" in w for w in a.warnings)
    b = suggestion.check_suggestion(buy, brake=off, pot=view, earnings=None, now=NOW)
    assert not b.allowed and len(b.refusals) == 2
    assert "hold off" in " ".join(b.warnings) and "earnings date unknown" in " ".join(b.warnings)
    hold = suggestion.Suggestion("MSFT", suggestion.HOLD, "STOCK", "US",
                                 held=_stop("2025-10-01T14:00:00+00:00"))
    assert not suggestion.check_suggestion(hold, brake=ok, pot=None, earnings=soon,
                                           now=NOW).allowed
    nearly = suggestion.Suggestion("MSFT", suggestion.HOLD, "STOCK", "US",
                                   held=_stop("2025-11-01T14:00:00+00:00"))
    c = suggestion.check_suggestion(nearly, brake=ok, pot=None, earnings=soon, now=NOW)
    assert c.allowed and any("12 months" in w for w in c.warnings)
    sell = suggestion.Suggestion("MSFT", suggestion.SELL, "STOCK", "US")
    assert suggestion.check_suggestion(sell, brake=None, pot=None, earnings=None,
                                       now=NOW).allowed


def advisor_offenders(qb2_root: Path) -> list[str]:
    """S9's wall: an advisor package that never calls check_suggestion is RED."""
    folder = qb2_root / "advisor"
    if not folder.is_dir():
        return []
    called = any("check_suggestion(" in p.read_text(encoding="utf-8")
                 for p in folder.rglob("*.py"))
    return [] if called else ["qb2/advisor/ never calls guard.suggestion.check_suggestion"]


def test_the_advisor_cannot_appear_without_the_suggestion_check(tmp_path: Path) -> None:
    assert advisor_offenders(QB2) == []                      # no advisor yet (S9)
    (tmp_path / "advisor").mkdir()
    (tmp_path / "advisor" / "engine.py").write_text("def suggest():\n    return []\n")
    assert advisor_offenders(tmp_path) != []                 # planted: RED
    (tmp_path / "advisor" / "engine.py").write_text(
        "from qb2.guard.suggestion import check_suggestion\n"
        "def suggest(s, **kw):\n    return check_suggestion(s, **kw)\n")
    assert advisor_offenders(tmp_path) == []


# ------------------------------------------------------ the pause, by hand --

def test_the_pause_tool_takes_only_his_words(tmp_path: Path) -> None:
    state = tmp_path / "brakes.jsonl"
    b = brakes.Brakes(state)
    b.update(BOT, 100.0)
    assert clear_pause.main(["--words", "GO"], state=state) == 1      # not paused
    b.update(BOT, 80.0)
    assert clear_pause.main(["--words", "  "], state=state) == 1      # empty
    assert _level(b) == brakes.PAUSED
    assert clear_pause.main(["--words", "GO: carry on"], state=state) == 0
    assert _level(b) == brakes.OK
