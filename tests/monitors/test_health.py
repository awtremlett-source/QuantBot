"""Tests for the monthly health report (measure, never refit).

The SHADOW tests are the point: the reconciliation is an ongoing birth
certificate, so a doctored journal row MUST turn the verdict RED -- if this
divergence detector cannot fire, the reconciliation is decoration.
"""

from __future__ import annotations

import hashlib
import math
import sqlite3
from pathlib import Path

import numpy as np
import pytest

from data_store import store
from data_store.store import PriceClean
from monitors.health import (
    HealthReport,
    _perf,
    build_report,
    render,
    summary,
)
from strategies.regime_switcher import (
    _HYSTERESIS,
    _SEVERITY_START,
    regime_series,
    severity_series,
)

import pandas as pd

TICKER = "NVDA"  # build_report reads the frozen CONFIG's ticker
ASOF = "2026-12-31"


def _day(i: int) -> str:
    # Consecutive UTC "days" via a simple counter inside one year.
    month = 1 + i // 28
    day = 1 + i % 28
    return f"2026-{month:02d}-{day:02d}"


def _bar(i: int, close: float) -> PriceClean:
    return PriceClean(
        ticker=TICKER,
        event_time=f"{_day(i)}T00:00:00Z",
        open=close,
        high=close + 1.0,
        low=close - 1.0,
        close=close,
        volume=1_000_000,
        adj_close=close,
        knowable_time=f"{_day(i)}T01:00:00Z",
        source="test",
    )


def _make_db(
    tmp_path: Path,
    n_clean: int = 60,
    equities: list[float] | None = None,
    shares: float = 0.0,
    cash: float = 10000.0,
) -> Path:
    """A synthetic store: flat CLEAN closes (< strategy warmup, so the shadow
    strategy stays all-cash), equity marks on the LAST len(equities) bars."""
    db = tmp_path / "health.db"
    store.init_db(db)
    conn = store.connect(db)
    try:
        store.write_price_clean(conn, [_bar(i, 100.0) for i in range(n_clean)])
        the_equities = equities if equities is not None else []
        first = n_clean - len(the_equities)
        for j, equity in enumerate(the_equities):
            conn.execute(
                "INSERT INTO paper_equity (ticker, event_time, equity, close) "
                "VALUES (?, ?, ?, 100.0)",
                (TICKER, f"{_day(first + j)}T00:00:00Z", equity),
            )
        conn.execute(
            "INSERT INTO paper_state (ticker, shares, cash, "
            "last_decided_event_time) VALUES (?, ?, ?, ?)",
            (TICKER, shares, cash, f"{_day(n_clean - 1)}T00:00:00Z"),
        )
        conn.commit()
    finally:
        conn.close()
    return db


def _report(db: Path, tmp_path: Path) -> HealthReport:
    return build_report(db, trials_path=str(tmp_path / "no-trials.jsonl"), asof=ASOF)


def _plant_supersede(db: Path, event_time: str) -> None:
    conn = store.connect(db)
    try:
        conn.execute(
            "INSERT INTO quarantine (domain, ticker, event_time, payload, "
            "reason, knowable_time) VALUES ('price_raw', ?, ?, '{}', "
            "'superseded_by_refetch', ?)",
            (TICKER, event_time, event_time),
        )
        conn.commit()
    finally:
        conn.close()


# ------------------------------------------------------------ performance


def test_sharpe_and_drawdown_hand_checked() -> None:
    marks = [
        ("t0", 10000.0), ("t1", 10100.0), ("t2", 10050.0), ("t3", 10150.0),
    ]
    block = _perf("test", marks)
    returns = np.array([10100 / 10000 - 1, 10050 / 10100 - 1, 10150 / 10050 - 1])
    expected_sharpe = returns.mean() / returns.std(ddof=1) * math.sqrt(252)
    assert block.annualized_sharpe == pytest.approx(float(expected_sharpe))
    assert block.max_drawdown == pytest.approx(10050 / 10100 - 1)
    assert block.total_return == pytest.approx(0.015)
    assert block.equity_start == 10000.0 and block.equity_end == 10150.0


def test_low_confidence_label_at_39_bars_absent_at_41() -> None:
    assert _perf("t", [(f"t{i}", 10000.0) for i in range(39)]).low_confidence
    assert not _perf("t", [(f"t{i}", 10000.0) for i in range(41)]).low_confidence


# ------------------------------------------------------------ regime_series


def test_regime_series_matches_hand_built_hysteresis_replay() -> None:
    # Calm noise long enough to define severity, then a violent stretch.
    rng = np.random.default_rng(7)
    calm = 100.0 + np.cumsum(rng.normal(0.0, 0.1, 320))
    wild = calm[-1] + np.cumsum(rng.normal(0.0, 8.0, 40))
    closes = np.concatenate([calm, wild])
    history = pd.DataFrame({"close": closes})
    threshold = 1.5

    labels = regime_series(history, threshold)

    # Independent replay of the documented hysteresis rules.
    severity = severity_series(closes).tolist()
    stressed = False
    expected = []
    for t in range(len(closes)):
        if t >= _SEVERITY_START:
            s = severity[t]
            if stressed:
                if s < _HYSTERESIS * threshold:
                    stressed = False
            elif s > threshold:
                stressed = True
        expected.append("stressed" if stressed else "calm")

    assert labels == expected
    assert len(labels) == len(closes)
    assert "stressed" in labels[-40:]  # the wild stretch must register
    assert set(labels[:_SEVERITY_START]) == {"calm"}  # warmup is calm


# ------------------------------------------------------------ costs


def test_cost_tally_from_planted_fills(tmp_path: Path) -> None:
    db = _make_db(tmp_path, equities=[10000.0] * 5)
    conn = store.connect(db)
    try:
        conn.execute(
            "INSERT INTO paper_orders (ticker, decision_event_time, "
            "target_weight, created_knowable_time, status) "
            "VALUES (?, 'd1', 1.0, 'k1', 'filled')",
            (TICKER,),
        )
        slip = 0.0005
        conn.executemany(
            "INSERT INTO paper_fills (order_id, fill_event_time, fill_price, "
            "shares_delta, cash_delta, knowable_time) VALUES (1, ?, ?, ?, ?, ?)",
            [
                ("f1", 100.0 * (1 + slip), 10.0, -1000.55, "k1"),
                ("f2", 99.0 * (1 - slip), -10.0, 989.50, "k2"),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    costs = _report(db, tmp_path).costs
    assert costs.fills == 2
    assert costs.round_trips == 1
    # Hand-checked: 10 * 100 * 0.0005 + 10 * 99 * 0.0005 = 0.5 + 0.495
    assert costs.slippage_gbp == pytest.approx(0.995)
    assert costs.slippage_pct_of_equity == pytest.approx(0.00995, rel=1e-3)


# ------------------------------------------------------------ shadow


def test_shadow_clean_fixture_is_ok(tmp_path: Path) -> None:
    db = _make_db(tmp_path, equities=[10000.0] * 10)
    shadow = _report(db, tmp_path).shadow
    assert shadow.verdict == "OK"
    assert shadow.shares_exact and shadow.cash_exact
    assert shadow.mismatches == []


def test_shadow_doctored_equity_goes_red_unless_supersede_explains(
    tmp_path: Path,
) -> None:
    # Doctor the LAST mark: the strategy is all-cash on this fixture, so the
    # shadow return is 0 and a +5 GBP jump is physics drift. This divergence
    # detector MUST fire -- otherwise the reconciliation is decoration.
    db = _make_db(tmp_path, equities=[10000.0] * 9 + [10005.0])
    shadow = _report(db, tmp_path).shadow
    assert shadow.verdict == "RED"
    assert "drifted from validated backtester" in shadow.note
    assert len(shadow.mismatches) == 1
    assert shadow.mismatches[0].diff_gbp == pytest.approx(5.0)

    # The SAME diff on a bar whose RAW row was superseded is explained: the
    # engines honestly saw different bars.
    _plant_supersede(db, shadow.mismatches[0].event_time)
    explained = _report(db, tmp_path).shadow
    assert explained.verdict == "OK"
    assert "1 superseded" in explained.note


def test_shadow_penny_diff_is_listed_as_basis_noise_not_red(
    tmp_path: Path,
) -> None:
    # Mid-history inception makes the shadow's cash/shares composition differ,
    # so pennies of drift are expected physics (measured live <= 0.03 GBP);
    # they are LISTED for the record but stay under the 0.10 verdict ceiling.
    db = _make_db(tmp_path, equities=[10000.0] * 9 + [10000.05])
    shadow = _report(db, tmp_path).shadow
    assert shadow.verdict == "OK"
    assert len(shadow.mismatches) == 1
    assert "basis-noise" in shadow.note


def test_shadow_doctored_shares_goes_red(tmp_path: Path) -> None:
    db = _make_db(tmp_path, equities=[10000.0] * 10, shares=5.0)  # no fills!
    shadow = _report(db, tmp_path).shadow
    assert shadow.verdict == "RED"
    assert not shadow.shares_exact


# ------------------------------------------------------------ rendering


def test_report_renders_and_summary_fits_telegram(tmp_path: Path) -> None:
    db = _make_db(tmp_path, equities=[10000.0] * 10)
    report = _report(db, tmp_path)
    text = render(report)
    for header in (
        "LIVE PERFORMANCE", "ENVELOPE", "REGIME", "COSTS",
        "SHADOW RECONCILIATION", "TRIALS & DSR PROGRESS",
    ):
        assert header in text
    assert "LOW-CONFIDENCE" in text  # 10 bars < 40

    brief = summary(report)
    assert len(brief.splitlines()) <= 15
    assert len(brief) < 4000  # always under the notify truncation cap


# ------------------------------------------------------------ read-only law


def test_build_report_never_writes_to_the_store(tmp_path: Path) -> None:
    db = _make_db(tmp_path, equities=[10000.0] * 10)
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    _report(db, tmp_path)
    _report(db, tmp_path)
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    # And the connection really is read-only by construction:
    from monitors.health import _connect_readonly

    conn = _connect_readonly(db)
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("INSERT INTO paper_equity VALUES ('X', 't', 1.0, 1.0)")
    finally:
        conn.close()
