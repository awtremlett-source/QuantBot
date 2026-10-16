"""S9 advisor batch 1's six ranking values, exactly as registered (QT-19 B1; register 6332880).

docs/research/preregistered.json is the authority (entries A-01..A-06, and the drills
KN-A-RANDOM / GAP / PLANT-1d). Each rule is only a VALUE per name per bar; the monthly
book that turns values into holdings -- eligibility, ranking, buffer, P13, stops,
slots -- is qb2/research/advisor_book.py, the same for all six.

Bar t is the decision bar; every value uses bars t and earlier only (rolling windows
end at t), so a value never reads the future. NaN = not enough bars.

* momentum L-1: close[t-21] / close[t-L] - 1 (L = 252 for 12-1, 126 for 6-1);
* risk-adjusted: the 12-1 return / the std (ddof 1) of the 252 close-to-close
  returns ending at t;
* near the high: close[t] / the highest HIGH of bars t-251..t (252 bars);
* low volatility: that std, ranked lowest first;
* drills: a seeded uniform draw per (bet, month) -- or 1.0 where the decision bar
  carries the planted marker (volume 777,777,777), else 0.0.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

SENTINEL_VOLUME = 777_777_777.0          # the planted marker; no real bar has it
SKIP = 21                                # "skipping the latest month"
VOL_BARS = 252
STD = "std(the 252 close-to-close returns to t, ddof=1)"
MOM12 = "close[t-21] / close[t-252] - 1"
TEXT = {                                 # (rule, registered value) -> lookback, order
    ("a_momentum", MOM12): (252, "highest first"),
    ("a_momentum", "close[t-21] / close[t-126] - 1"): (126, "highest first"),
    ("a_risk_adjusted_momentum", f"({MOM12}) / {STD}"): (252, "highest first"),
    ("a_near_high", "close[t] / max(high[t-251..t])"): (252, "highest first"),
    ("a_low_volatility", STD): (252, "lowest first"),
    ("a_random", "uniform draw seeded by (0, bet index, month)"): (252, "highest first"),
    ("a_marker", "1.0 if the decision bar carries the marker else 0.0"): (252, "highest first"),
}
FILTER_START = "VWRP's close on or before the month's last XLON session > the mean of its last 200 closes"


@dataclass(frozen=True, slots=True)
class Rule:
    rule: str
    lookback: int
    ascending: bool                      # True: lowest value ranks first
    market_filter: bool                  # A-06: VWRP above its 200-day average

    def values(self, bars: pd.DataFrame, bet: int, months: np.ndarray) -> np.ndarray:
        """The value at every bar of one name (``months``: each bar's month number)."""
        close = bars["close"].astype(float)
        if self.rule in ("a_momentum", "a_risk_adjusted_momentum"):
            out = close.shift(SKIP) / close.shift(self.lookback) - 1.0
            if self.rule == "a_risk_adjusted_momentum":
                out = out / _vol(close)
            return np.asarray(out, dtype=float)
        if self.rule == "a_near_high":
            high = bars["high"].astype(float).rolling(VOL_BARS, min_periods=VOL_BARS).max()
            return np.asarray(close / high, dtype=float)
        if self.rule == "a_low_volatility":
            return np.asarray(_vol(close), dtype=float)
        if self.rule == "a_random":
            return np.array([np.random.default_rng(np.random.SeedSequence([0, bet, int(m)])).random()
                             for m in months])
        if self.rule == "a_marker":
            return np.asarray(bars["volume"].to_numpy(dtype=float) == SENTINEL_VOLUME, dtype=float)
        raise ValueError(f"no value for rule {self.rule!r}")


def _vol(close: pd.Series) -> pd.Series:
    return close.pct_change().rolling(VOL_BARS, min_periods=VOL_BARS).std(ddof=1)


def of(entry: Mapping[str, Any]) -> Rule:
    """The rule for one registered entry; refuses anything it does not implement exactly."""
    p, rule = entry["parameters"], str(entry["rule"])
    known = TEXT.get((rule, str(p.get("value"))))
    if known is None or (int(p["lookback"]), str(p["order"])) != known:
        raise ValueError(f"{entry['id']}: {rule!r} with value {p.get('value')!r}, lookback "
                         f"{p.get('lookback')!r}, order {p.get('order')!r} is not implemented "
                         "exactly as registered")
    flt = p.get("filter")
    if flt is not None and (rule != "a_momentum" or not str(flt).startswith(FILTER_START)):
        raise ValueError(f"{entry['id']}: filter {flt!r} is not the one this code implements")
    return Rule(rule, known[0], known[1] == "lowest first", flt is not None)
