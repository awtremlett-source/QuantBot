"""QT-18 B1: S6 batch 1's 24 trials are in the register, as designed in QT-17's box."""

from __future__ import annotations

from qb2.research import preregister

RULES = ["s6_intraday_mom", "s6_gap_fade", "s6_gap_go", "s6_range_breakout",
         "s6_trailing_buy", "s6_xs_reversal", "s6_xs_momentum", "s6_prior_day_reversal"]
ARMS = {"US": ["us_liquid"], "LON": ["uk_etf", "uk_share"],
        "MIX": ["us_liquid", "uk_etf", "uk_share"]}


def test_twenty_four_trials_eight_rules_by_three_arms_in_register_order() -> None:
    s6 = [e for e in preregister.entries().values() if str(e["id"]).startswith("S6-")]
    assert [e["id"] for e in s6] == [f"S6-{r:02d}-{a}" for r in range(1, 9) for a in ARMS]
    for e in s6:
        rule, arm = RULES[int(e["id"][3:5]) - 1], e["id"].split("-")[2]
        assert (e["kind"], e["rule"], e["bar_size"], e["side"]) == ("trial", rule, "1h", "long-only")
        assert e["parameters"]["arm"] == arm and e["parameters"]["sleeves"] == ARMS[arm]
        assert e["parameters"]["stop"] is (rule in ("s6_range_breakout", "s6_trailing_buy"))
        assert "42" in e["judged"] and "2026-07-13" in e["holdout"] and e["date"] == "2026-10-16"
