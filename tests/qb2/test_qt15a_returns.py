"""QT-15 A1: returns compound -- the strategy and VWRP are measured the same way. Offline.

QT-14's port added per-bar returns on a fixed stake (total = sum, equity = 1 +
cumsum) while the benchmark compounded, so a loss could read below -100% (the
coin-flip showed -369%) and drawdown was measured on a line that could go
negative. Each test here was seen RED on that summing code first.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from qb2.research import firewall, known_null, simulate, stats, verdict
from tests.qb2.test_qt14b_firewall import _bench, _data, _token, register_repo  # noqa: F401


def test_three_bars_compound_by_hand() -> None:
    """+10%, -10%, +10% is 1.1 x 0.9 x 1.1 - 1 = +8.9%, not +10%."""
    out = stats.compute(np.array([0.10, -0.10, 0.10]), "1d")
    assert out.total_return == pytest.approx(1.1 * 0.9 * 1.1 - 1)        # 0.089


def test_a_strategy_that_loses_its_slot_cannot_read_below_minus_100() -> None:
    assert stats.compute(np.array([-0.6, -0.6, -0.6]), "1d").total_return >= -1.0
    # 60 round trips, each a 2% loss plus 1% a leg: summed, this read -240%.
    opens = np.tile([100.0, 98.0], 60)
    closes = np.tile([98.0, 100.0], 60)
    held = np.tile([1.0, 0.0], 60)
    paths = simulate.run(opens, closes, held, simulate.LegFractions(0.01, 0.01))
    total = stats.compute(paths.net, "1d").total_return
    assert -1.0 <= total < -0.8


def test_each_bar_is_earned_on_the_slot_as_it_stands_then() -> None:
    """Held two bars, 100 -> 110 -> 99: +10% then -10% on the re-sized slot."""
    opens = np.array([100.0, 110.0, 99.0])
    closes = np.array([110.0, 99.0, 99.0])
    held = np.array([1.0, 1.0, 0.0])
    paths = simulate.run(opens, closes, held, simulate.LegFractions(0.001, 0.001))
    assert paths.gross[:2] == pytest.approx([0.10, -0.10])
    assert stats.compute(paths.gross, "1d").total_return == pytest.approx(99 / 100 - 1)


def test_drawdown_is_measured_on_the_compounded_line() -> None:
    """Equity 1 -> 1.5 -> 0.75 -> 0.9: the worst fall is 0.75 / 1.5 - 1 = -50%."""
    out = stats.compute(np.array([0.5, -0.5, 0.2]), "1d")
    assert out.max_drawdown == pytest.approx(-0.5)


def test_the_benchmark_check_compares_compounded_with_compounded(
        register_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    seen: dict[str, Any] = {}
    real = verdict.judge

    def spy(**kw: Any) -> verdict.Verdict:
        seen.update(kw)
        return real(**kw)

    monkeypatch.setattr(verdict, "judge", spy)
    token = _token(register_repo, "KN-PLANT-5m")
    data = known_null.with_pattern(_data("5m"), "5m", token.entry["parameters"])
    result = firewall.score(token, known_null.strategy_for(token.entry), data,
                            interval="5m", n_null=5, bench=_bench, log_path=None)
    marked = result.observed.marked.to_numpy(dtype=float)
    compounded = float(np.prod(1.0 + marked) - 1.0)
    assert abs(compounded - marked.sum()) > 1e-3          # the two bases really differ here
    assert seen["strategy_return"] == pytest.approx(compounded)
    assert result.benchmark is not None
    assert (result.benchmark.start, result.benchmark.end) == (result.start, result.end)
