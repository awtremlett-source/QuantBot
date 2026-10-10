"""QT-15 A4: the firewall loads the advisor list the way it loads the bot's. Offline.

P19's nine daily trials are registered on advisor-universe-v1 (171 names); QT-14's
firewall could only load the bot list. Each register entry must now resolve to
the universe it names, costed per name, with bet groups applied.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qb2.data import universe
from qb2.execution import costs
from qb2.research import bet_groups, firewall, preregister


def test_each_of_the_18_trials_resolves_to_the_universe_it_names() -> None:
    trials = [e for e in preregister.entries().values() if e["kind"] == "trial"]
    assert len(trials) == 18
    bot = [e["yfinance"] for e in universe.bot_entries()]
    advisor = [e["yfinance"] for e in universe.advisor_entries()]
    assert len(bot) == 50 and len(advisor) == 171 and not set(bot) & set(advisor)
    for entry in trials:
        names = [e["yfinance"] for e in universe.for_register(entry)]
        wanted = advisor if entry["bar_size"] == "1d" else bot
        assert names == wanted, entry["id"]
        assert str(entry["universe"]).startswith(
            "advisor-universe-v1" if entry["bar_size"] == "1d" else "bot-universe-v1")


def test_an_unknown_universe_or_an_underived_list_is_refused(tmp_path: Path) -> None:
    with pytest.raises(universe.NotAgreed, match="no known universe"):
        universe.for_register({"id": "X", "universe": "advisor-universe-v2: later"})
    fake = tmp_path / "a.json"
    fake.write_text('{"list": "advisor", "status": "DRAFT", "entries": [{}]}',
                    encoding="utf-8")
    with pytest.raises(universe.NotAgreed, match="DERIVED"):
        universe.advisor_entries(fake)


def test_every_advisor_name_is_costed_as_itself() -> None:
    entries = universe.advisor_entries()
    seen = {"us_fx": 0, "uk_duty": 0, "london_fx": 0}
    for entry in entries:
        inst = firewall.instrument_of(entry)                # refuses an unknown kind
        buy = costs.leg_cost(inst, 300.0, "BUY")
        sell = costs.leg_cost(inst, 300.0, "SELL")
        if inst.market == "US":
            assert buy.fx_fee_gbp > 0 and sell.fx_fee_gbp > 0, inst.ticker
            seen["us_fx"] += 1
        elif inst.currency not in ("GBP", "GBX", "GBp"):
            assert buy.fx_fee_gbp > 0 and sell.fx_fee_gbp > 0, inst.ticker
            seen["london_fx"] += 1
        if inst.pays_stamp_duty_on_buy:
            assert buy.stamp_duty_gbp > 0 and sell.stamp_duty_gbp == 0, inst.ticker
            seen["uk_duty"] += 1
    assert seen["us_fx"] == 68 and seen["london_fx"] == 3 and seen["uk_duty"] > 0


def _daily(root: Path, symbol: str, zone: str) -> None:
    index = pd.bdate_range("2024-01-02", periods=300, tz=zone)
    close = 100 * np.exp(np.cumsum(np.random.default_rng(len(symbol)).normal(0, .01, 300)))
    frame = pd.DataFrame({"open": close, "high": close * 1.01, "low": close * 0.99,
                          "close": close, "volume": 1e6}, index=index)
    (root / "daily").mkdir(parents=True, exist_ok=True)
    frame.to_parquet(root / "daily" / f"{symbol}.parquet")


def test_the_firewall_loads_advisor_names_with_bet_groups(tmp_path: Path) -> None:
    entries = universe.advisor_entries()
    pick = [next(e for e in entries if universe.market_of(e) == "US"),
            next(e for e in entries if universe.market_of(e) == "LSE")]
    for e in pick:
        _daily(tmp_path, e["yfinance"], "America/New_York"
               if universe.market_of(e) == "US" else "Europe/London")
    data, skipped = firewall.load("1d", entries=pick, clean_root=tmp_path)
    assert [d.symbol for d in data] == [e["yfinance"] for e in pick] and skipped == []
    assert [d.market for d in data] == ["US", "LSE"]
    assert data[0].instrument.pays_fx_fee and not data[1].instrument.pays_fx_fee
    assert sorted(d.bet for d in data) == [0, 1]
    assert bet_groups.effective_n([e["yfinance"] for e in universe.bot_entries()]) == 48
    assert bet_groups.effective_n([e["yfinance"] for e in entries]) == 171
