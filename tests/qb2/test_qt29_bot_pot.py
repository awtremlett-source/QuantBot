"""QT-29 B (P21): the bot pot -- the bot's 30% follows the index, AS IF, paper only. Offline.

His G3 choice of 2026-10-29: "(c) Follow index (Recommended)". The pot holds VWRP whenever ADV-0 holds
VWRL (its BUY or SELL issued in the run right after ADV-0's, so both fill at the same open), with its
own 15% big-fall stop (10% unsettled, only up) and the bot's brake as built; a notional GBP 3,000,
reconciled to the penny. Nothing here can build an order. Each run below is one evening's, as live.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from qb2.advisor import bot_pot, scorecard, state
from qb2.execution import sender
from qb2.execution.safety import BOT
from qb2.guard import brakes, stops
from qb2.research import names, simulate
from qb2.tools import status_push
from tests.qb2.test_qt23_advisor import ADVISOR_DIR, DAYS, ORDER_PATHS, at, frame, imports

CLOSES = [100.0, 100.0, 100.0, 110.0, 108.0, 112.0, 111.0, 115.0]


def store(tmp: Path, closes: list[float], through: date, vix: float = 15.0) -> Path:
    """A tmp clean store: VWRP.L (open = close: simple) and ^VIX, and the top-up's marker."""
    clean, days = tmp / "clean", DAYS[:len(closes)]
    (clean / "daily").mkdir(parents=True, exist_ok=True)
    frame(days, closes, closes).to_parquet(clean / "daily" / "VWRP.L.parquet")
    vdays = [days[0] - timedelta(days=7), *days]
    frame(vdays, [vix] * len(vdays), [vix] * len(vdays), "America/New_York").to_parquet(clean / "daily" / "^VIX.parquet")
    (clean / "daily_step.json").write_text(json.dumps({"fetched_through": through.isoformat()}), encoding="utf-8")
    return clean


def adv0(tmp: Path, action: str, when: datetime, kind: str = "weekly") -> None:
    """ADV-0's own suggestion, as engine.issue writes it (the bot pot only reads it)."""
    state.append(state.Paths.under(tmp).log("suggestions"), {"at": when.isoformat(timespec="seconds"),
                 "action": action, "allowed": True, "kind": kind, "ticker": "VWRL.L"})


def evening(tmp: Path, closes: list[float], k: int, *, vix: float = 15.0, minute: int = 0) -> list[str]:
    """Session k's run, after the top-up and the advisor's job (20:00 UTC plus ``minute``)."""
    adv = state.Paths.under(tmp)
    clean = store(tmp, closes[:k + 1], DAYS[k], vix)
    return bot_pot.run(at(DAYS[k], 20) + timedelta(minutes=minute), bot_pot.beside(adv), adv, clean_root=clean)


def pot(tmp: Path) -> state.Paths:
    return bot_pot.beside(state.Paths.under(tmp))


def held(tmp: Path) -> stops.Stop | None:
    return bot_pot.held_stop(stops.Ledger(pot(tmp).stops))


def days(tmp: Path) -> list[dict[str, object]]:
    return state.rows(pot(tmp).log("days"))


def signals(tmp: Path) -> list[dict[str, object]]:
    return state.rows(pot(tmp).log("signals"))


def armed(tmp: Path, closes: list[float], *, vix: float = 15.0) -> None:
    """ADV-0 bought on Monday; the deploy is Monday evening: armed from Tuesday, DAYS[1]."""
    adv0(tmp, "BUY", at(DAYS[0], 19))
    lines = evening(tmp, closes, 0, vix=vix)
    assert state.arm_date(pot(tmp)) == DAYS[1] and lines[0].startswith("armed from 2025-03-04")


# ------------------------------------------------ in and out with ADV-0, at the same open

def test_armed_on_the_first_session_after_the_deploy_it_follows_adv0_in(tmp_path: Path) -> None:
    armed(tmp_path, CLOSES)
    assert days(tmp_path) == [] and signals(tmp_path) == []                   # nothing back-filled
    evening(tmp_path, CLOSES, 1)                                              # Tue: ADV-0 holds -> BUY
    assert [(s["action"], s["kind"], s["allowed"], s["session"]) for s in signals(tmp_path)] == [
        ("BUY", "follow", True, "2025-03-04")]
    assert days(tmp_path)[0]["session"] == "2025-03-04" and not days(tmp_path)[0]["held"]
    evening(tmp_path, CLOSES, 2)                                              # filled at Wed's open
    stop = held(tmp_path)
    assert stop is not None and stop.opened_at.startswith("2025-03-05") and stop.entry == 100.0
    assert stop.pot == BOT and stop.rule == stops.FALL_RULE and stop.level == pytest.approx(85.0)


def test_a_buy_by_adv0_and_the_pots_fill_at_the_same_open(tmp_path: Path) -> None:
    adv0(tmp_path, "SELL", at(DAYS[0], 19), kind="urgent-exit")                # ADV-0 out at the arm
    evening(tmp_path, CLOSES, 0)
    evening(tmp_path, CLOSES, 1)
    assert signals(tmp_path) == [] and held(tmp_path) is None                  # out with ADV-0
    adv0(tmp_path, "BUY", at(DAYS[2], 20), kind="re-buy")                      # Wed evening: ADV-0 buys
    evening(tmp_path, CLOSES, 2, minute=1)                                     # the run right after
    evening(tmp_path, CLOSES, 3)
    adv_fill = scorecard.as_if(state.rows(state.Paths.under(tmp_path).log("suggestions")), DAYS[:4])[-1]
    stop = held(tmp_path)
    assert adv_fill.session == DAYS[3] and stop is not None and stop.opened_at.startswith(str(DAYS[3]))


def test_a_sell_by_adv0_is_followed_at_the_same_open(tmp_path: Path) -> None:
    armed(tmp_path, CLOSES)
    for k in range(1, 4):
        evening(tmp_path, CLOSES, k)
    adv0(tmp_path, "SELL", at(DAYS[4], 20), kind="urgent-exit")                # Fri evening: ADV-0 exits
    evening(tmp_path, CLOSES, 4, minute=1)
    assert signals(tmp_path)[-1]["action"] == "SELL" and signals(tmp_path)[-1]["kind"] == "follow"
    evening(tmp_path, CLOSES, 5)
    adv_fill = scorecard.as_if(state.rows(state.Paths.under(tmp_path).log("suggestions")), DAYS[:6])[-1]
    assert adv_fill == scorecard.Fill(DAYS[5], "SELL", at(DAYS[4], 20).isoformat(timespec="seconds"))
    assert held(tmp_path) is None and days(tmp_path)[-1]["held"] is False      # sold at Mon's open too


# ------------------------------------------------ its own stop: only up, 10% when unsettled

@pytest.mark.parametrize(("vix", "f"), [(15.0, 0.15), (35.0, 0.10)])
def test_the_stop_trails_the_highest_close_only_up(tmp_path: Path, vix: float, f: float) -> None:
    armed(tmp_path, CLOSES, vix=vix)
    for k in range(1, len(CLOSES)):
        evening(tmp_path, CLOSES, k, vix=vix)
    stop = held(tmp_path)
    assert stop is not None
    levels = [c.level for c in stop.history]
    assert levels == pytest.approx([x * (1 - f) for x in (100.0, 110.0, 112.0, 115.0)])
    assert levels == sorted(levels)                                            # never lowered


def test_its_own_stop_sells_at_the_next_open_and_the_rebuy_waits_for_his_words(tmp_path: Path) -> None:
    closes = [100.0, 100.0, 100.0, 110.0, 92.0, 90.0, 99.5, 100.0, 101.0]
    armed(tmp_path, closes)
    for k in range(1, 7):
        evening(tmp_path, closes, k)
    made = [(s["action"], s["kind"], s["allowed"], s["session"]) for s in signals(tmp_path)]
    assert made[1] == ("SELL", "stop", True, str(DAYS[4]))                     # 92 <= 110 x 0.85 = 93.5
    assert held(tmp_path) is None and days(tmp_path)[-2]["held"] is False      # sold at Mon's open
    assert made[2] == ("BUY", "re-buy", False, str(DAYS[6]))                   # 99.5 >= 90 x 1.10 ...
    assert "no new buys" in str(signals(tmp_path)[-1]["refusals"]) and days(tmp_path)[-1]["brake"] == brakes.PAUSED
    brakes.Brakes(pot(tmp_path).brakes).clear_pause("my words", pot=BOT)       # ... his words clear it
    evening(tmp_path, closes, 7)
    assert signals(tmp_path)[-1]["allowed"] is True and signals(tmp_path)[-1]["kind"] == "re-buy"
    evening(tmp_path, closes, 8)
    stop = held(tmp_path)
    assert stop is not None and stop.opened_at.startswith(str(DAYS[8]))


# ------------------------------------------------ the record: GBP 3,000, to the penny

def test_the_record_is_hand_worked_to_the_penny_and_reconciled(tmp_path: Path) -> None:
    armed(tmp_path, CLOSES)
    for k in range(1, 5):
        lines = evening(tmp_path, CLOSES, k)
    legs = {s: simulate.leg_fractions(names.instrument_of(bot_pot.vwrp()), s) for s in (1.0, 2.0)}
    last = days(tmp_path)[-1]                                                  # bought at 100, closed at 108
    for s in (1.0, 2.0):
        value = 3_000.0 * (1 - legs[s].buy) / 100.0 * 108.0 * (1 - legs[s].sell)   # units x close - sell cost
        assert (last[f"value_{s:g}x"], last[f"pct_{s:g}x"]) == (round(value, 2), round((value / 3_000.0 - 1) * 100, 4))
    assert "reconciled: OK" in lines and not any(x.startswith("RED") for x in lines)
    moved = [*CLOSES[:3], 111.0, *CLOSES[4:]]                                  # a revised close
    assert any(x.startswith("RED: the bot pot does not reconcile -- 2025-03-06") for x in evening(tmp_path, moved, 5))


# ------------------------------------------------ paper only, never an order; never loud on the advisor

def test_no_order_object_is_ever_built(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert sender.ARMED is False                                               # DISARMED, S10 arms it

    def refuse(*_: object, **__: object) -> None:
        raise AssertionError("an order object was built")

    monkeypatch.setattr(sender, "OrderRequest", refuse)
    monkeypatch.setattr(sender, "send", refuse)
    closes = [100.0, 100.0, 100.0, 110.0, 92.0, 90.0]
    armed(tmp_path, closes)
    for k in range(1, 6):
        evening(tmp_path, closes, k)
    assert [s["action"] for s in signals(tmp_path)] == ["BUY", "SELL"]        # bought and sold, as if
    assert not {m for m in imports(ADVISOR_DIR / "bot_pot.py") if m.startswith(ORDER_PATHS)}


def test_a_fault_is_a_red_line_never_a_raise(tmp_path: Path) -> None:
    armed(tmp_path, CLOSES)
    pot(tmp_path).log("signals").write_text("not json\n", encoding="utf-8")
    adv = state.Paths.under(tmp_path)
    line = bot_pot.step(at(DAYS[1], 20), store(tmp_path, CLOSES[:2], DAYS[1]), adv)
    assert line.startswith("Bot pot: RED: the bot pot STOPPED (Blocked: signals.jsonl line 1 is unreadable")
    assert "STOPPED" in pot(tmp_path).page.read_text(encoding="utf-8")


def test_its_block_sits_under_the_advisors_on_the_status_page(tmp_path: Path) -> None:
    armed(tmp_path, CLOSES)
    evening(tmp_path, CLOSES, 1)
    advisor_page = tmp_path / "advisor.md"
    advisor_page.write_text("# QuantBot advisor\n\nthe advisor's page\n", encoding="utf-8")
    page = status_push.advisor_page(tmp_path / "out.md", (advisor_page, pot(tmp_path).page))
    text = page.read_text(encoding="utf-8")
    assert text.index("the advisor's page") < text.index("## Bot pot (follows the index)")
    assert "in cash, a BUY waiting for the next London open" in text and "£3,000" in text
    assert status_push.secret_hits(text, {}) == []
    assert status_push.advisor_page(tmp_path / "none.md", (tmp_path / "missing.md",)) == tmp_path / "missing.md"
