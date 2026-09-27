"""S2b: what a trade costs, what gets written down, and what says no.

Offline. No network, no broker, no order: the sender is disarmed and the function
behind it raises, so there is nothing to reach even if something armed it.

Each guard is shown failing on broken behaviour before it is trusted, because a
check nobody has watched refuse is not a check (SCARS #9).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qb2.execution import costs, safety, sender
from qb2.execution.costs import Instrument
from qb2.execution.fill_recorder import FillRecorder
from qb2.execution.safety import BOT, ADVISOR, MANUAL, Blocked, Holding
from qb2.execution.sender import OrderRequest

# Instruments whose cost treatment genuinely differs (FACTS.md rows l, m1-m4).
US_SHARE = Instrument("AAPL_US_EQ", "USD", "US", "SHARE")
UK_SHARE = Instrument("VODl_EQ", "GBP", "LSE", "SHARE")
UK_ETF = Instrument("ISFl_EQ", "GBP", "LSE", "ETF")
AIM_SHARE = Instrument("ASCl_EQ", "GBP", "LSE", "SHARE", aim=True)


# ============================================================ the cost model ==

def test_a_us_round_trip_pays_the_currency_fee_twice() -> None:
    """Row l: 0.15% each leg, so 0.30% of a round trip is gone before any edge."""
    trip = costs.round_trip(US_SHARE, 1_000.0)
    assert trip.buy.fx_fee_gbp == pytest.approx(1.50)
    assert trip.sell.fx_fee_gbp == pytest.approx(1.50)
    assert trip.buy.fx_fee_gbp + trip.sell.fx_fee_gbp == pytest.approx(3.00)


def test_a_uk_share_pays_stamp_duty_on_the_buy_and_not_the_sell() -> None:
    """Row m1: 0.5% on purchases of LSE-listed shares. Never on a sale."""
    trip = costs.round_trip(UK_SHARE, 1_000.0)
    assert trip.buy.stamp_duty_gbp == pytest.approx(5.00)
    assert trip.sell.stamp_duty_gbp == 0.0


def test_a_uk_etf_pays_no_stamp_duty_at_all() -> None:
    """Row m2: "no Stamp Duty charge applied to gilts, bonds or ETFs"."""
    trip = costs.round_trip(UK_ETF, 1_000.0)
    assert trip.buy.stamp_duty_gbp == 0.0
    assert trip.sell.stamp_duty_gbp == 0.0


def test_an_aim_share_pays_no_stamp_duty() -> None:
    """Row m3: growth-market shares are excluded from chargeable securities."""
    trip = costs.round_trip(AIM_SHARE, 1_000.0)
    assert trip.buy.stamp_duty_gbp == 0.0


def test_a_uk_share_pays_no_currency_fee_and_a_us_share_pays_no_stamp_duty() -> None:
    """The two charges must never be applied to the wrong market."""
    uk = costs.round_trip(UK_SHARE, 1_000.0)
    us = costs.round_trip(US_SHARE, 1_000.0)
    assert uk.buy.fx_fee_gbp == 0.0
    assert us.buy.stamp_duty_gbp == 0.0


def test_the_ptm_levy_applies_only_over_ten_thousand_pounds() -> None:
    """Row m4: GBP 1.50 per trade over GBP 10,000, on buy and on sell."""
    small = costs.round_trip(UK_SHARE, 9_999.0)
    large = costs.round_trip(UK_SHARE, 10_001.0)
    assert small.buy.ptm_levy_gbp == 0.0
    assert large.buy.ptm_levy_gbp == pytest.approx(1.50)
    assert large.sell.ptm_levy_gbp == pytest.approx(1.50)


def test_the_itemised_parts_add_up_to_the_total() -> None:
    """A total nobody can reconcile is a total nobody should trust."""
    leg = costs.leg_cost(US_SHARE, 5_000.0, "BUY")
    assert leg.total_gbp == pytest.approx(
        leg.spread_gbp + leg.slippage_gbp + leg.fx_fee_gbp
        + leg.stamp_duty_gbp + leg.ptm_levy_gbp)


def test_doubling_the_stress_doubles_every_cost() -> None:
    """The firewall's 2x test must really be twice, not twice-ish."""
    plain = costs.round_trip(UK_SHARE, 10_500.0)
    stressed = costs.round_trip(UK_SHARE, 10_500.0, stress=2.0)
    assert stressed.total_gbp == pytest.approx(plain.total_gbp * 2)


def test_extended_hours_cost_more_than_the_regular_session() -> None:
    """Row k2 warns of wider spreads outside the regular session."""
    regular = costs.round_trip(US_SHARE, 1_000.0)
    extended = costs.round_trip(US_SHARE, 1_000.0, extended_hours=True)
    assert extended.total_gbp > regular.total_gbp


def test_an_unknown_market_is_refused_rather_than_costed_at_zero() -> None:
    """Silently costing a trade at zero is the most expensive bug available."""
    unknown = Instrument("XYZ", "EUR", "XETRA", "SHARE")
    with pytest.raises(ValueError, match="no spread figure"):
        costs.leg_cost(unknown, 1_000.0, "BUY")


def test_the_real_cost_of_a_same_day_uk_share_trade_is_stated_plainly() -> None:
    """The number that decides P17: a same-day UK share must clear ~0.7%."""
    trip = costs.round_trip(UK_SHARE, 1_000.0)
    assert trip.fraction > 0.006, (
        "stamp duty plus two spreads should cost well over half a percent")
    assert "%" in costs.describe(trip)


# ========================================================== the fill recorder ==

def test_an_intent_is_written_before_the_outcome(tmp_path: Path) -> None:
    recorder = FillRecorder(tmp_path / "fills.jsonl")
    recorder.record_intent(intent_id="a1", ticker="ISFl_EQ", side="BUY",
                           quantity=10.0, expected_price=7.12,
                           quote_age_seconds=30.0, estimated_cost_gbp=0.9)
    recorder.record_outcome(intent_id="a1", ticker="ISFl_EQ", side="BUY",
                            filled_quantity=10.0, fill_price=7.13)
    kinds = [row["kind"] for row in recorder.lines()]
    assert kinds == ["INTENT", "OUTCOME"]
    assert recorder.open_intents() == []


def test_a_crash_between_the_two_lines_leaves_a_visible_open_intent(
        tmp_path: Path) -> None:
    """The failure this file exists for: we may have ordered and do not know."""
    recorder = FillRecorder(tmp_path / "fills.jsonl")
    recorder.record_intent(intent_id="b2", ticker="AAPL_US_EQ", side="BUY",
                           quantity=1.0, expected_price=214.5,
                           quote_age_seconds=15.0, estimated_cost_gbp=1.2)
    # ... power goes here. Nothing writes an outcome.
    open_ones = recorder.open_intents()
    assert len(open_ones) == 1
    assert open_ones[0].ticker == "AAPL_US_EQ"
    assert recorder.has_open_intent("AAPL_US_EQ") is True
    assert recorder.has_open_intent("ISFl_EQ") is False


def test_a_refusal_is_recorded_so_it_cannot_look_like_a_crash(
        tmp_path: Path) -> None:
    recorder = FillRecorder(tmp_path / "fills.jsonl")
    recorder.record_intent(intent_id="c3", ticker="ISFl_EQ", side="BUY",
                           quantity=5.0, expected_price=7.0,
                           quote_age_seconds=10.0, estimated_cost_gbp=0.4)
    recorder.record_refusal(intent_id="c3", ticker="ISFl_EQ", side="BUY",
                            reason="killswitch armed")
    assert recorder.open_intents() == [], (
        "a refused order must be resolved, not left looking like a crash")


def test_no_line_is_ever_rewritten(tmp_path: Path) -> None:
    """Append-only, proven: what was there before is still there, byte for byte."""
    path = tmp_path / "fills.jsonl"
    recorder = FillRecorder(path)
    recorder.record_intent(intent_id="d4", ticker="ISFl_EQ", side="BUY",
                           quantity=1.0, expected_price=7.0,
                           quote_age_seconds=5.0, estimated_cost_gbp=0.1)
    before = path.read_bytes()
    recorder.record_outcome(intent_id="d4", ticker="ISFl_EQ", side="BUY",
                            filled_quantity=1.0, fill_price=7.05)
    after = path.read_bytes()
    assert after.startswith(before), "an earlier line was altered"
    assert len(after) > len(before)


def test_a_half_written_last_line_is_reported_not_silently_dropped(
        tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "fills.jsonl"
    recorder = FillRecorder(path)
    recorder.record_intent(intent_id="e5", ticker="ISFl_EQ", side="BUY",
                           quantity=1.0, expected_price=7.0,
                           quote_age_seconds=5.0, estimated_cost_gbp=0.1)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write('{"kind": "OUTCOME", "intent_id": "e5"')      # power cut
    rows = list(recorder.lines())
    assert len(rows) == 1
    assert "unreadable line" in capsys.readouterr().out


def test_the_fill_gap_is_measurable_for_replacing_our_guesses(
        tmp_path: Path) -> None:
    recorder = FillRecorder(tmp_path / "fills.jsonl")
    recorder.record_intent(intent_id="f6", ticker="ISFl_EQ", side="BUY",
                           quantity=1.0, expected_price=100.0,
                           quote_age_seconds=5.0, estimated_cost_gbp=0.1)
    recorder.record_outcome(intent_id="f6", ticker="ISFl_EQ", side="BUY",
                            filled_quantity=1.0, fill_price=100.5)
    assert recorder.fill_gap("f6") == pytest.approx(0.005)


# =============================================================== the killswitch ==

def test_the_killswitch_blocks_buying_and_never_selling(tmp_path: Path) -> None:
    assert safety.killswitch_armed(tmp_path) is False
    safety.check_buying_allowed(tmp_path)                    # no raise
    safety.arm_killswitch("a drill", root=tmp_path)
    assert safety.killswitch_armed(tmp_path) is True
    with pytest.raises(Blocked, match="killswitch is armed"):
        safety.check_buying_allowed(tmp_path)
    safety.disarm_killswitch(tmp_path)
    safety.check_buying_allowed(tmp_path)


def test_arming_twice_does_not_lose_the_first_reason(tmp_path: Path) -> None:
    safety.arm_killswitch("the real reason", root=tmp_path)
    safety.arm_killswitch("a later, vaguer reason", root=tmp_path)
    assert "the real reason" in safety.killswitch_path(tmp_path).read_text(
        encoding="utf-8")


def test_flatten_sells_only_the_bots_shares_never_the_operators() -> None:
    """The line that must never be crossed: P1 -- the advisor only suggests."""
    ledger = [
        Holding("ISFl_EQ", 100.0, BOT),
        Holding("VODl_EQ", 250.0, ADVISOR),
        Holding("AAPL_US_EQ", 12.0, MANUAL),
    ]
    instructions = safety.flatten_bot(ledger, "end of session")
    assert [i.ticker for i in instructions] == ["ISFl_EQ"]
    assert instructions[0].quantity == 100.0


def test_flatten_leaves_the_advisors_share_of_a_shared_ticker_alone() -> None:
    """P6's no-overlap rule should prevent this; flatten must survive it anyway."""
    ledger = [Holding("ISFl_EQ", 40.0, BOT), Holding("ISFl_EQ", 60.0, ADVISOR)]
    instructions = safety.flatten_bot(ledger, "shutdown")
    assert len(instructions) == 1
    assert instructions[0].quantity == 40.0, "it sold the advisor's shares too"


def test_the_flat_check_sees_both_holdings_and_pending_orders() -> None:
    """P4's enforcer: flat means nothing held AND nothing in flight."""
    assert safety.bot_is_flat([], []) is True
    assert safety.bot_is_flat([Holding("ISFl_EQ", 1.0, BOT)], []) is False
    assert safety.bot_is_flat([], ["ISFl_EQ"]) is False
    assert safety.bot_is_flat([Holding("VODl_EQ", 5.0, ADVISOR)], []) is True


# ============================================================== the P14 checks ==

def test_a_stale_quote_is_refused() -> None:
    safety.check_quote_age("US", 30.0)                      # fine
    with pytest.raises(Blocked, match="too stale"):
        safety.check_quote_age("US", 600.0)


def test_londons_allowance_is_wider_because_its_delay_is_unmeasured() -> None:
    """Row o could not be measured, so London gets room until it is."""
    safety.check_quote_age("LSE", 900.0)                    # fine for now
    with pytest.raises(Blocked, match="too stale"):
        safety.check_quote_age("LSE", 5_000.0)


def test_an_unknown_market_has_no_quote_allowance_and_is_refused() -> None:
    with pytest.raises(Blocked, match="no quote-age limit"):
        safety.check_quote_age("XETRA", 10.0)


def test_a_price_outside_the_sane_band_is_refused() -> None:
    recent = [100.0, 101.0, 99.5]
    safety.check_price_in_band(100.5, recent)               # fine
    with pytest.raises(Blocked, match="outside the sane band"):
        safety.check_price_in_band(10.0, recent)            # decimal point moved
    with pytest.raises(Blocked, match="outside the sane band"):
        safety.check_price_in_band(1_000.0, recent)


def test_a_price_check_with_no_history_refuses_rather_than_guesses() -> None:
    with pytest.raises(Blocked, match="refusing to trade blind"):
        safety.check_price_in_band(100.0, [])


def test_an_oversized_order_is_refused() -> None:
    safety.check_order_size(100.0, 3_000.0)                 # 3.3% of the pot
    with pytest.raises(Blocked, match="over the"):
        safety.check_order_size(1_000.0, 3_000.0)           # 33% of the pot


def test_a_fill_far_from_expectation_is_reported_for_stopping_that_market() -> None:
    assert safety.check_fill_gap(100.0, 100.5) == pytest.approx(0.005)
    with pytest.raises(Blocked, match="beyond the"):
        safety.check_fill_gap(100.0, 105.0)


# ================================================================== the sender ==

def test_the_sender_is_disarmed_and_nothing_can_arm_it() -> None:
    assert sender.ARMED is False
    request = OrderRequest("ISFl_EQ", "BUY", 10.0, "LSE", 7.0, 10.0)
    with pytest.raises(sender.NotArmed, match="Nothing was sent"):
        sender.send(request, market_is_open=True)


def test_even_armed_there_is_nothing_behind_the_door(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Belt and braces: arming it reaches a function that refuses to exist."""
    monkeypatch.setattr(sender, "ARMED", True)
    request = OrderRequest("ISFl_EQ", "BUY", 10.0, "LSE", 7.0, 10.0)
    with pytest.raises(NotImplementedError, match="S10"):
        sender.send(request, market_is_open=True)


def test_a_buy_is_refused_while_the_killswitch_is_armed(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sender, "ARMED", True)
    safety.arm_killswitch("test", root=tmp_path)
    request = OrderRequest("ISFl_EQ", "BUY", 10.0, "LSE", 7.0, 10.0)
    with pytest.raises(Blocked, match="killswitch"):
        sender.send(request, market_is_open=True, root=tmp_path)


def test_a_sell_is_still_allowed_while_the_killswitch_is_armed(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A killswitch that trapped us in a position would not be safety."""
    monkeypatch.setattr(sender, "ARMED", True)
    safety.arm_killswitch("test", root=tmp_path)
    sold: list[str] = []
    request = OrderRequest("ISFl_EQ", "SELL", 10.0, "LSE", 7.0, 10.0)
    def record(order: OrderRequest) -> str:
        sold.append(order.ticker)
        return "ok"

    sender.send(request, market_is_open=True, root=tmp_path, place=record)
    assert sold == ["ISFl_EQ"]


def test_a_buy_into_a_closed_market_is_refused(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """P4: a queued buy would fill with nothing watching it."""
    monkeypatch.setattr(sender, "ARMED", True)
    request = OrderRequest("ISFl_EQ", "BUY", 10.0, "LSE", 7.0, 10.0)
    with pytest.raises(Blocked, match="closed"):
        sender.send(request, market_is_open=False, root=tmp_path)


def test_a_sell_into_a_closed_market_is_allowed_through(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Getting out must never be blocked by the clock; P4 sells pre-market."""
    monkeypatch.setattr(sender, "ARMED", True)
    request = OrderRequest("AAPL_US_EQ", "SELL", 1.0, "US", 214.0, 10.0,
                           extended_hours=True)
    assert sender.send(request, market_is_open=False, root=tmp_path,
                       place=lambda r: "sold") == "sold"


def test_a_second_order_for_a_pending_ticker_is_refused(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Row e: the endpoints are not idempotent, so never send twice."""
    monkeypatch.setattr(sender, "ARMED", True)
    request = OrderRequest("ISFl_EQ", "BUY", 10.0, "LSE", 7.0, 10.0)
    with pytest.raises(Blocked, match="already pending"):
        sender.send(request, market_is_open=True, root=tmp_path,
                    pending_bot_tickers=["ISFl_EQ"])


def test_an_unresolved_intent_blocks_a_resend(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The crash case: we may already have ordered. Reconcile, never resend."""
    monkeypatch.setattr(sender, "ARMED", True)
    recorder = FillRecorder(tmp_path / "fills.jsonl")
    recorder.record_intent(intent_id="old", ticker="ISFl_EQ", side="BUY",
                           quantity=10.0, expected_price=7.0,
                           quote_age_seconds=5.0, estimated_cost_gbp=0.5)
    request = OrderRequest("ISFl_EQ", "BUY", 10.0, "LSE", 7.0, 10.0)
    with pytest.raises(Blocked, match="never resend"):
        sender.send(request, market_is_open=True, root=tmp_path,
                    recorder=recorder)


def test_every_refusal_is_written_down(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sender, "ARMED", True)
    recorder = FillRecorder(tmp_path / "fills.jsonl")
    request = OrderRequest("ISFl_EQ", "BUY", 10.0, "LSE", 7.0, 10.0)
    with pytest.raises(Blocked):
        sender.send(request, market_is_open=False, root=tmp_path,
                    recorder=recorder)
    notes = [row.get("note", "") for row in recorder.lines()]
    assert any("REFUSED" in str(note) for note in notes)


def test_the_sender_only_knows_market_orders() -> None:
    """Our stops are ours (rows d1/d2), so no type we cannot amend is needed."""
    source = Path(sender.__file__).read_text(encoding="utf-8")
    for unwanted in ("limit", "stop_limit"):
        assert f"orders/{unwanted}" not in source
    assert "market order" in source.lower()


# ============================================================ qb2 fingerprint ==

def test_qb2_has_its_own_fingerprint_and_it_excludes_v1() -> None:
    from qb2.tools import fingerprint as qb2_fingerprint

    combined, rows = qb2_fingerprint.fingerprint(qb2_fingerprint.REPO_ROOT)
    assert len(combined) == 64
    assert rows, "the qb2 fingerprint covered no files"
    covered = {path for path, _, _ in rows}
    assert any(path.startswith("qb2/") for path in covered)
    assert "requirements-qb2.txt" in covered
    for v1_folder in ("execution/", "monitors/", "research/", "data_store/"):
        assert not any(path.startswith(v1_folder) for path in covered), (
            f"the qb2 fingerprint has swallowed v1's {v1_folder}")


def test_the_qb2_fingerprint_is_deterministic() -> None:
    from qb2.tools import fingerprint as qb2_fingerprint

    first = qb2_fingerprint.report(qb2_fingerprint.REPO_ROOT)
    second = qb2_fingerprint.report(qb2_fingerprint.REPO_ROOT)
    assert first == second, "two runs disagreed, so it cannot be a before/after proof"
    assert "COMBINED:" in first


def test_the_ledger_default_lives_under_data_qb2() -> None:
    """qb2's own state, never mixed into v1's data/ files."""
    from qb2.execution.fill_recorder import DEFAULT_LEDGER

    assert DEFAULT_LEDGER.parent.name == "qb2"
    assert DEFAULT_LEDGER.parent.parent.name == "data"
    assert json is not None            # keep the import honest
