"""QT-23 C: the advisor -- ADV-0 (the default) live, its scorecard, the six shadows, the walls.

Operator, 2026-10-19 (verbatim): "GO on QT-23: build the advisor with "hold the index fund" as its
default, the 15% big-fall stop (10% when markets are jumpy) as its live stop, and the rules scored
in the background on live prices only."  And: "GO on the advisor's brake: after an urgent exit, my
own words clear the advisor's hold-off and restart its peak from that day, as for the bot's pause;
no code clears it."
Offline: a tmp clean store (VWRL.L, ^VIX) and tmp advisor files. Each test was seen RED -- first
with no code, then against a planted mutant (docs/reports/QT-23_C_redfirst.py.txt).
"""

from __future__ import annotations

import ast
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qb2.advisor import daily, engine, live, scorecard, shadow, state
from qb2.data import universe
from qb2.execution import costs
from qb2.execution.safety import ADVISOR, BOT, Blocked
from qb2.guard import brakes, stops
from qb2.research import advisor_book, advisor_data, firewall, fills
from qb2.tools import clear_pause, status_push
from tests.qb2.test_qt19b_advisor import _bars

ROOT = Path(__file__).resolve().parents[2]
UTC = timezone.utc
VWRL = costs.Instrument("VWRLl_EQ", "GBP", "LSE", "ETF", False)
WEEK = [date(2025, 3, d) for d in (3, 4, 5, 6, 7)]                     # five London sessions
OPENS = [100.00, 101.50, 101.00, 99.50, 100.00]
CLOSES = [101.00, 102.00, 99.00, 100.50, 103.00]


def frame(days: list[date], opens: list[float], closes: list[float], tz: str = "Europe/London") -> pd.DataFrame:
    idx = pd.DatetimeIndex([pd.Timestamp(d).tz_localize(tz) for d in days]).as_unit("ms")
    return pd.DataFrame({"open": opens, "high": np.maximum(opens, closes), "low": np.minimum(opens, closes),
                         "close": closes, "volume": 1.0, "currency": "GBP"}, index=idx)


def store(tmp: Path, days: list[date], opens: list[float], closes: list[float], *,
          through: date, vix: float = 15.0) -> Path:
    """A tmp clean store: VWRL.L and ^VIX daily bars, and the top-up's marker."""
    clean = tmp / "clean"
    (clean / "daily").mkdir(parents=True, exist_ok=True)
    frame(days, opens, closes).to_parquet(clean / "daily" / "VWRL.L.parquet")
    vdays = [days[0] - timedelta(days=7)] + list(days)
    frame(vdays, [vix] * len(vdays), [vix] * len(vdays), "America/New_York").to_parquet(clean / "daily" / "^VIX.parquet")
    (clean / "daily_step.json").write_text(json.dumps({"fetched_through": through.isoformat()}), encoding="utf-8")
    return clean


def at(day: date, hour: int) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=UTC)


# ------------------------------------------------- the scorecard, hand-worked

def test_a_hand_worked_week_reproduces_to_the_penny() -> None:
    """BUY filled at Monday's open of 100.00; 10 bp a leg at 1x (spread 8 + slippage 2), 20 at 2x.
    Each day = 7000 x close_k / 100 x (1 - leg) x (1 - leg): bought, and marked as if sold that close.
    Friday 1x: 7000 x 1.03 x 0.999 x 0.999 = 7195.587 -> £7,195.59. The dividend run adds 0.50 on
    Wednesday, paid on Tuesday's close of 102.00: Wednesday's gap becomes (101.00 + 0.50) / 102.00."""
    bars, book = frame(WEEK, OPENS, CLOSES), [scorecard.Fill(WEEK[0], scorecard.BUY, "x")]
    plain = scorecard.record(bars, WEEK, book, np.zeros(5), VWRL)
    assert [round(d.value[1.0], 2) for d in plain] == [7055.87, 7125.73, 6916.15, 7020.94, 7195.59]
    assert [round(d.value[2.0], 2) for d in plain] == [7041.75, 7111.47, 6902.31, 7006.89, 7181.19]
    paid = np.zeros(5)
    paid[2] = 0.50 / 102.00                                             # P3: payout / previous close
    div = scorecard.record(bars, WEEK, book, paid, VWRL)
    assert [round(d.value[1.0], 2) for d in div] == [7055.87, 7125.73, 6950.39, 7055.69, 7231.21]
    assert round(div[-1].value[2.0], 2) == 7216.74
    assert all(d.held for d in div) and div[-1].pct() == pytest.approx(7231.21 / 7000 - 1, abs=1e-6)


def test_an_allowed_suggestion_fills_at_the_first_open_after_it() -> None:
    opens = scorecard.xlon_open
    assert scorecard.fill_session(at(WEEK[4], 7), WEEK + [date(2025, 3, 10)], opens) == WEEK[4]  # 07:00 < 08:00
    assert scorecard.fill_session(at(WEEK[4], 9), WEEK + [date(2025, 3, 10)], opens) == date(2025, 3, 10)
    rows = [{"at": at(WEEK[0], 6).isoformat(), "action": "BUY", "allowed": False},     # refused: not followed
            {"at": at(WEEK[0], 7).isoformat(), "action": "SELL", "allowed": True},     # out: nothing to sell
            {"at": at(WEEK[1], 7).isoformat(), "action": "BUY", "allowed": True},
            {"at": at(WEEK[2], 7).isoformat(), "action": "BUY", "allowed": True},      # held: ignored
            {"at": at(WEEK[3], 7).isoformat(), "action": "SELL", "allowed": True}]
    assert [(f.session, f.side) for f in scorecard.as_if(rows, WEEK)] == [(WEEK[1], "BUY"), (WEEK[3], "SELL")]
    held = scorecard.held_path(WEEK, scorecard.as_if(rows, WEEK))
    assert held.tolist() == [0, 1, 1, 0, 0]                            # sold at Thursday's open


def test_a_written_day_that_moves_is_red_and_named() -> None:
    bars, book = frame(WEEK, OPENS, CLOSES), [scorecard.Fill(WEEK[0], scorecard.BUY, "x")]
    fresh = scorecard.record(bars, WEEK, book, np.zeros(5), VWRL)
    lines = [scorecard.line(d) for d in fresh]
    assert scorecard.reconcile(lines, fresh) == []
    lines[2] = {**lines[2], "value_1x": 6916.16}
    assert scorecard.reconcile(lines, fresh) == [
        "2025-03-05: £6,916.16 at 1x written, £6,916.15 now (a revised price or dividend)"]


# ---------------------------------------------------------- the engine

def _ctx(close: float = 100.0, held: stops.Stop | None = None, brake: brakes.State | None = None,
         value: float = 7000.0) -> engine.Context:
    return engine.Context(WEEK[0], close, False, brake, value, held)


def _brake(level: str = brakes.OK) -> brakes.State:
    return brakes.State(ADVISOR, 7000.0, 7000.0 if level == brakes.OK else 5900.0, level, "x")


def test_every_suggestion_is_checked_and_written_refused_or_not(tmp_path: Path) -> None:
    paths = state.Paths.under(tmp_path)
    ok = engine.issue(paths, _ctx(brake=_brake()), action="BUY", kind="weekly", reason="r", stop=85.0,
                      now=at(WEEK[0], 19))
    no = engine.issue(paths, _ctx(brake=None), action="BUY", kind="weekly", reason="r", stop=85.0,
                      now=at(WEEK[0], 19))
    off = engine.issue(paths, _ctx(brake=_brake(brakes.HOLD_OFF)), action="BUY", kind="re-buy", reason="r",
                       stop=85.0, now=at(WEEK[0], 19))
    assert ok["allowed"] and not no["allowed"] and not off["allowed"]
    assert "no buys until it is measured" in no["refusals"][0] and "no new buys" in off["refusals"][0]
    assert any("hold off" in w for w in off["warnings"])
    assert [r["allowed"] for r in state.rows(paths.log("suggestions"))] == [True, False, False]


def test_the_weekly_review_buys_first_then_holds_with_its_stop(tmp_path: Path) -> None:
    paths, ledger = state.Paths.under(tmp_path), stops.Ledger(tmp_path / "stops.jsonl")
    first = engine.weekly_review(paths, _ctx(brake=_brake()), ledger, at(WEEK[0], 19))
    assert [r["action"] for r in first] == ["BUY"] and "safety stop 15%" in first[0]["reason"]
    assert first[0]["stop"] == pytest.approx(85.0)
    assert engine.weekly_review(paths, _ctx(brake=_brake()), ledger, at(WEEK[1], 19)) == []   # still to fill
    held = ledger.open(position_id="ADV-0-x", pot=ADVISOR, ticker="VWRL.L", market="LSE",
                       opened_at=at(WEEK[1], 8).isoformat(), entry=100.0, atr=None, reason="t", unsettled=False)
    hold = engine.weekly_review(paths, _ctx(close=110.0, held=held, brake=_brake()), ledger, at(WEEK[4], 7))
    assert hold[0]["action"] == "HOLD" and hold[0]["allowed"] and "£85.00" in hold[0]["reason"]


def test_at_twelve_months_the_default_is_re_justified_never_lower(tmp_path: Path) -> None:
    paths, ledger = state.Paths.under(tmp_path), stops.Ledger(tmp_path / "stops.jsonl")
    engine.issue(paths, _ctx(brake=_brake()), action="BUY", kind="weekly", reason="r", stop=85.0,
                 now=at(WEEK[0], 19))
    old = ledger.open(position_id="ADV-0-a", pot=ADVISOR, ticker="VWRL.L", market="LSE",
                      opened_at="2024-03-04T08:00:00+00:00", entry=100.0, atr=None, reason="t", unsettled=False)
    ledger.trail("ADV-0-a", 130.0, None, unsettled=False)                # 110.5
    made = engine.weekly_review(paths, _ctx(close=125.0, held=ledger.get("ADV-0-a"), brake=_brake()),
                                ledger, at(WEEK[4], 7))
    assert made[0]["kind"] == "re-justify" and made[0]["action"] == "HOLD" and made[0]["allowed"]
    assert made[0]["stop"] == pytest.approx(110.5) and old.position_id not in ledger.stops()


# -------------------------------------------------- the daily job, end to end

DAYS: list[date] = list(pd.DatetimeIndex(advisor_book.sessions("LSE", date(2025, 3, 3), date(2025, 4, 30))).date)


def _run(tmp: Path, closes: list[float], through: date, now: datetime, *, first: bool = False,
         vix: float = 15.0) -> list[str]:
    days = DAYS[:len(closes)]
    clean = store(tmp, days, closes, closes, through=through, vix=vix)       # open = close: simple
    paths = state.Paths.under(tmp)
    if state.arm_date(paths) is None:
        state.arm(paths, days[0], now, "test")
        brakes.Brakes(paths.brakes).update(ADVISOR, scorecard.POT_GBP, at=now)
    return daily.run(now, paths, clean_root=clean, first_review=first, shadows=False)


def test_a_buy_fills_at_the_next_open_and_the_stop_trails_the_highest_close(tmp_path: Path) -> None:
    closes = [100.0, 100.0, 104.0, 110.0, 108.0]
    _run(tmp_path, closes[:1], DAYS[0], at(DAYS[0], 19), first=True)          # BUY, issued after Monday
    lines = _run(tmp_path, closes, DAYS[4], at(DAYS[4], 19))
    paths = state.Paths.under(tmp_path)
    held = daily.advisor_stop(stops.Ledger(paths.stops))
    assert held is not None and held.entry == 100.0 and held.opened_at.startswith(str(DAYS[1]))
    assert [c.level for c in held.history] == pytest.approx([85.0, 88.4, 93.5])   # 100, 104, 110 x 0.85
    days = state.rows(paths.log("days"))
    assert [d["session"] for d in days] == [str(d) for d in DAYS[:5]] and not days[0]["held"]
    assert "reconciled: OK" in lines and not any(x.startswith("RED") for x in lines)


def test_a_crossed_stop_says_sell_never_sells_and_the_rebuy_waits_behind_the_brake(tmp_path: Path) -> None:
    closes = [100.0, 100.0, 120.0, 101.0, 99.0, 95.0, 104.6, 105.0]
    _run(tmp_path, closes[:1], DAYS[0], at(DAYS[0], 19), first=True)
    _run(tmp_path, closes[:4], DAYS[3], at(DAYS[3], 19))                 # stop 102 (120 x 0.85); 101 crosses
    paths = state.Paths.under(tmp_path)
    urgent = [s for s in state.rows(paths.log("suggestions")) if s["kind"] == "urgent-exit"]
    assert [(s["action"], s["allowed"], s["session"]) for s in urgent] == [("SELL", True, str(DAYS[3]))]
    assert daily.advisor_stop(stops.Ledger(paths.stops)) is not None     # an alert: nothing was sold
    lines = _run(tmp_path, closes, DAYS[7], at(DAYS[7], 19))
    assert daily.advisor_stop(stops.Ledger(paths.stops)) is None         # as if sold at Friday's open
    rebuy = [s for s in state.rows(paths.log("suggestions")) if s["kind"] == "re-buy"]
    assert rebuy and rebuy[0]["session"] == str(DAYS[6])                 # 104.6 >= 95 x 1.10
    assert not rebuy[0]["allowed"] and "no new buys" in rebuy[0]["refusals"][0]   # the pot is braked
    assert "REFUSED" in paths.page.read_text(encoding="utf-8")
    assert not any(x.startswith("RED") for x in lines)


def test_a_week_away_is_caught_up_and_an_older_friday_shows_missed(tmp_path: Path) -> None:
    closes = [100.0] * 15                                                # Mon 3 Mar .. Fri 21 Mar
    _run(tmp_path, closes[:1], DAYS[0], at(DAYS[0], 19), first=True)
    lines = _run(tmp_path, closes, DAYS[14], at(DAYS[14] + timedelta(days=3), 19))   # Monday 24th
    reviews = [r for r in state.rows(state.Paths.under(tmp_path).log("runs")) if r.get("job") == "weekly"]
    assert [(r.get("friday"), r.get("missed", False), r.get("late", False)) for r in reviews] == [
        (None, False, False), ("2025-03-07", True, False), ("2025-03-14", True, False),
        ("2025-03-21", False, True)]
    assert any("MISSED" in x for x in lines) and any("woke after" in x for x in lines)


def test_a_stale_close_leaves_the_stop_unchecked_and_says_so(tmp_path: Path) -> None:
    closes = [100.0, 100.0, 101.0]
    _run(tmp_path, closes[:1], DAYS[0], at(DAYS[0], 19), first=True)
    lines = _run(tmp_path, closes, DAYS[2], at(DAYS[6], 19))             # the store stopped on day 2
    assert any(x.startswith("UNCHECKED") for x in lines)
    assert "UNCHECKED" in state.Paths.under(tmp_path).page.read_text(encoding="utf-8")


def test_vwrl_must_resolve_to_its_isin_gbp_and_london(monkeypatch: pytest.MonkeyPatch) -> None:
    assert daily.vwrl()["isin"] == daily.ISIN
    monkeypatch.setattr(universe, "advisor_entries", lambda: [
        {"yfinance": "VWRL.L", "isin": daily.ISIN, "quote_currency": "USD", "exchange": "London Stock Exchange"}])
    with pytest.raises(Blocked, match="R1"):
        daily.vwrl()


def test_the_page_passes_the_status_push_secret_scan(tmp_path: Path) -> None:
    closes = [100.0, 100.0, 104.0]
    _run(tmp_path, closes[:1], DAYS[0], at(DAYS[0], 19), first=True)
    _run(tmp_path, closes, DAYS[2], at(DAYS[2], 19))
    text = state.Paths.under(tmp_path).page.read_text(encoding="utf-8")
    assert "hold the whole-world index fund" in text and "as-if record" in text
    assert status_push.secret_hits(text, {}) == []


# --------------------------------------------------- the brake: GO 2

def test_only_his_words_clear_the_advisors_hold_off_and_restart_its_peak(tmp_path: Path) -> None:
    b = brakes.Brakes(tmp_path / "brakes.jsonl")
    for v in (7000.0, 5900.0, 6900.0):                                   # -15.7%, then back within 5%
        state_ = b.update(ADVISOR, v)
    assert state_.level == brakes.HOLD_OFF                               # no code clears it (GO 2)
    for words in ("", "   "):
        assert clear_pause.main(["--words", words, "--pot", "advisor"], state=b.path) == 1
    said = "GO: clear the advisor's hold-off -- the stop did its job"
    assert clear_pause.main(["--words", said, "--pot", "advisor"], state=b.path) == 0
    now = b.state(ADVISOR)
    assert now is not None and (now.level, now.peak) == (brakes.OK, 6900.0)   # restarted that day
    rows = [json.loads(x) for x in b.path.read_text(encoding="utf-8").splitlines()]
    assert {"event": "cleared", "pot": ADVISOR, "words": said}.items() <= rows[-2].items()
    assert clear_pause.main(["--words", said, "--pot", "advisor"], state=b.path) == 1   # not held off now


def test_the_bots_pause_is_unchanged_and_the_advisors_ten_percent_still_clears_itself(tmp_path: Path) -> None:
    b = brakes.Brakes(tmp_path / "brakes.jsonl")
    assert [b.update(ADVISOR, v).level for v in (100.0, 89.0, 96.0)] == [brakes.OK, brakes.BRAKED, brakes.OK]
    assert [b.update(BOT, v).level for v in (100.0, 84.0, 100.0)] == [brakes.OK, brakes.PAUSED, brakes.PAUSED]
    assert clear_pause.main(["--words", "GO: clear the bot"], state=b.path) == 0


# ------------------------------------------------------------- the shadows

def _names(n: int = 10) -> list[firewall.NameData]:
    idx = pd.DatetimeIndex(advisor_book.sessions("US", date(2015, 1, 1), date(2016, 12, 31))).tz_localize(
        "America/New_York")
    out = []
    for j in range(n):
        bars = _bars(100.0 * np.cumprod(np.full(len(idx), 1.0 + 0.0005 * (j + 1))), days=idx)
        out.append(firewall.NameData(f"N{j}", "US", costs.Instrument(f"N{j}", "GBP", "US", "ETF", False),
                                     bars, fills.schedule(bars.index, "1d", "US"), j,
                                     None, np.zeros(len(bars))))
    return out


def test_no_shadow_return_is_scored_before_the_arm_date() -> None:
    from qb2.research import preregister
    names, arm = _names(), date(2016, 3, 16)
    vix = pd.Series(15.0, index=names[0].bars.index)
    by = shadow.score(preregister.require("S-01").entry, names, vix, arm, {})
    for series in by.values():
        assert len(series) and min(live.days_of(series.index, "US")) >= arm
    b = shadow.book(preregister.require("S-01").entry, names, vix, arm, {})
    early = live.days_of(names[0].bars.index, "US") < arm
    assert not any(np.asarray(b.decisions[n.symbol])[early].any() for n in names)
    assert b.buys and min(names[0].bars.index[t].date() for _, t in b.buys) >= arm


def test_the_filter_rule_is_one_copy_shared_by_research_and_the_shadows() -> None:
    idx = pd.DatetimeIndex(advisor_book.sessions("LSE", date(2014, 1, 1), date(2015, 12, 31))).tz_localize(
        "Europe/London")
    up = pd.Series(np.linspace(50, 80, len(idx)), index=idx)
    on = advisor_data.filter_of(up, up)
    assert on and all(on.values())                                       # rising: above its 200-day mean


# --------------------------------------------------------------- the walls

ADVISOR_DIR = ROOT / "qb2" / "advisor"
ORDER_PATHS = ("qb2.execution.sender", "qb2.execution.anchors", "qb2.execution.anchor_ledger",
               "qb2.execution.t212_client", "qb2.execution.fill_recorder", "qb2.execution.xcheck")


def imports(path: Path) -> set[str]:
    tree, out = ast.parse(path.read_text(encoding="utf-8")), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            out |= {node.module} | {f"{node.module}.{a.name}" for a in node.names}
    return out


def test_the_advisor_imports_no_order_path() -> None:
    found = {p.name: sorted(m for m in imports(p) if m.startswith(ORDER_PATHS)) for p in ADVISOR_DIR.glob("*.py")}
    assert {k: v for k, v in found.items() if v} == {}
    assert len(found) >= 7


def test_only_engine_issue_writes_a_suggestion() -> None:
    writers = {p.name for p in ADVISOR_DIR.glob("*.py") if '"suggestions"' in p.read_text(encoding="utf-8")
               and "state.append(" in p.read_text(encoding="utf-8")
               and 'append(paths.log("suggestions")' in p.read_text(encoding="utf-8")}
    assert writers == {"engine.py"}
    src = (ADVISOR_DIR / "engine.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "issue")
    line = {ast.unparse(c.func): c.lineno for c in ast.walk(fn) if isinstance(c, ast.Call)}
    assert line["suggestion.check_suggestion"] < line["state.append"]   # checked FIRST, then written


def test_the_advisor_reads_bars_only_through_its_live_door() -> None:
    raw = ("daily.load", "access.bars", "read_parquet", "research_bars", "bars_through")
    found = {p.name: [r for r in raw if r in p.read_text(encoding="utf-8")]
             for p in ADVISOR_DIR.glob("*.py") if p.name != "live.py"}
    assert {k: v for k, v in found.items() if v} == {}
