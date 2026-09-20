"""Transparent scoring. Every point on the board maps to a plain-English
reason, so the operator can always answer "why is this name here?".

BUY  = Trend 30 + Momentum 25 + Setup 25 + Volume 10 + Tradeability 10 - penalties
SELL = Downtrend 30 + Momentum 25 + Breakdown 25 + Distribution 10
       + Tradeability 10 - penalties
Both clamp to 0..100. SELL means "exit or avoid" -- long-only account.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import Config

PENNY_FLOOR_GBP = 0.20


@dataclass
class ScoreResult:
    score: int = 0
    setup: str = "\u2014"
    reasons: list[str] = field(default_factory=list)


def _ok(v) -> bool:
    return v is not None


def _add(res: ScoreResult, pts: float, text: str) -> None:
    if pts > 0:
        res.score += pts
        res.reasons.append(f"+{pts:g} \u00b7 {text}")


def _penalise(res: ScoreResult, pts: float, text: str) -> None:
    res.score -= pts
    res.reasons.append(f"-{pts:g} \u00b7 {text}")


def _tradeability(res: ScoreResult, s: dict, cfg: Config) -> None:
    atr_pct = s.get("atr_pct")
    if _ok(atr_pct) and 1.5 <= atr_pct <= 5.0:
        _add(res, 5, f"Healthy volatility (ATR {atr_pct:.1f}% of price)")
    turnover = s.get("turnover_gbp")
    if _ok(turnover) and turnover >= cfg.min_turnover_gbp:
        _add(res, 5, "Liquid: \u00a31m+ average daily turnover")


def _shared_penalties(res: ScoreResult, s: dict, cfg: Config) -> None:
    turnover = s.get("turnover_gbp")
    if _ok(turnover) and turnover < cfg.min_turnover_gbp:
        _penalise(res, 15, "Thin trading \u2014 spreads will hurt")
    close_gbp = s.get("close_gbp")
    if _ok(close_gbp) and close_gbp < PENNY_FLOOR_GBP:
        _penalise(res, 10, "Below 20p \u2014 penny-stock territory")


def buy_score(s: dict, cfg: Config) -> ScoreResult:
    res = ScoreResult()
    close, sma50, sma200 = s.get("close"), s.get("sma50"), s.get("sma200")

    # Trend (30)
    trend_pts = 0
    if _ok(sma200) and _ok(close) and close > sma200:
        _add(res, 10, "Above the 200-day average")
        trend_pts += 10
    if _ok(sma50) and _ok(sma200) and sma50 > sma200:
        _add(res, 10, "50-day average above 200-day")
        trend_pts += 10
    if _ok(s.get("sma50_slope")) and s["sma50_slope"] > 0:
        _add(res, 5, "50-day average rising")
        trend_pts += 5
    if _ok(sma50) and _ok(close) and close > sma50:
        _add(res, 5, "Above the 50-day average")
        trend_pts += 5

    # Momentum (25)
    rsi = s.get("rsi")
    if _ok(rsi) and 50 <= rsi <= 70:
        pts = round(10 * (1 - abs(rsi - 60) / 10), 1)
        _add(res, pts, f"RSI {rsi:.0f} in the power zone (50\u201370)")
    if (_ok(s.get("macd_hist")) and _ok(s.get("macd_hist_delta"))
            and s["macd_hist"] > 0 and s["macd_hist_delta"] > 0):
        _add(res, 10, "MACD histogram positive and rising")
    if _ok(s.get("roc63")) and s["roc63"] > 0:
        _add(res, 5, "Positive 3-month return")

    # Setup (25) -- breakout beats pullback when both fire
    setup, setup_pts, setup_text = "\u2014", 0, ""
    d_hi, vol_ratio = s.get("dist_to_hi_pct"), s.get("vol_ratio")
    if _ok(d_hi) and d_hi <= 3.0 and _ok(vol_ratio) and vol_ratio >= 1.5:
        setup, setup_pts = "Breakout", 25
        setup_text = (f"Breakout: {d_hi:.1f}% off the 52-week high on "
                      f"{vol_ratio:.1f}\u00d7 volume")
    else:
        uptrend = (_ok(sma200) and _ok(sma50) and _ok(close)
                   and close > sma200 and sma50 > sma200)
        near50 = _ok(sma50) and _ok(close) and abs(close - sma50) / sma50 <= 0.02
        if uptrend and near50 and _ok(rsi) and 35 <= rsi <= 48:
            setup, setup_pts = "Pullback", 20
            setup_text = "Pullback: cooled to the 50-day inside an uptrend"
    if setup_pts:
        _add(res, setup_pts, setup_text)
    elif trend_pts >= 25:
        setup = "Trend-follow"

    # Volume (10)
    if _ok(vol_ratio) and vol_ratio >= 1.2 and s.get("up_day"):
        _add(res, 10, f"Up day on {vol_ratio:.1f}\u00d7 average volume")

    _tradeability(res, s, cfg)

    # Penalties
    gap = s.get("gap_pct")
    if _ok(gap) and gap > 8:
        _penalise(res, 10, f"Gapped up {gap:.1f}% today \u2014 chasing risk")
    if _ok(rsi) and rsi > 78:
        _penalise(res, 10, f"Overheated (RSI {rsi:.0f})")
    _shared_penalties(res, s, cfg)

    res.score = int(round(max(0, min(100, res.score))))
    res.setup = setup
    return res


def sell_score(s: dict, cfg: Config) -> ScoreResult:
    res = ScoreResult()
    close, sma50, sma200 = s.get("close"), s.get("sma50"), s.get("sma200")

    # Downtrend (30)
    if _ok(sma200) and _ok(close) and close < sma200:
        _add(res, 10, "Below the 200-day average")
    if _ok(sma50) and _ok(sma200) and sma50 < sma200:
        _add(res, 10, "50-day average below 200-day")
    if _ok(s.get("sma50_slope")) and s["sma50_slope"] < 0:
        _add(res, 5, "50-day average falling")
    if _ok(sma50) and _ok(close) and close < sma50:
        _add(res, 5, "Below the 50-day average")

    # Downside momentum (25)
    rsi = s.get("rsi")
    if _ok(rsi) and 30 <= rsi <= 50:
        pts = round(10 * (1 - abs(rsi - 40) / 10), 1)
        _add(res, pts, f"RSI {rsi:.0f} confirming weakness")
    if (_ok(s.get("macd_hist")) and _ok(s.get("macd_hist_delta"))
            and s["macd_hist"] < 0 and s["macd_hist_delta"] < 0):
        _add(res, 10, "MACD histogram negative and falling")
    if _ok(s.get("roc63")) and s["roc63"] < 0:
        _add(res, 5, "Negative 3-month return")

    # Breakdown (25)
    setup, bd_pts, bd_text = "\u2014", 0, ""
    d_lo, vol_ratio = s.get("dist_to_lo_pct"), s.get("vol_ratio")
    if _ok(d_lo) and d_lo <= 3.0 and _ok(vol_ratio) and vol_ratio >= 1.5:
        setup, bd_pts = "Breakdown", 25
        bd_text = (f"Breakdown: {d_lo:.1f}% off the 52-week low on "
                   f"{vol_ratio:.1f}\u00d7 volume")
    elif s.get("death_cross_recent"):
        setup, bd_pts = "Death cross", 15
        bd_text = "Death cross: 50-day fell through 200-day recently"
    if bd_pts:
        _add(res, bd_pts, bd_text)

    # Distribution (10)
    if _ok(vol_ratio) and vol_ratio >= 1.2 and s.get("down_day"):
        _add(res, 10, f"Down day on {vol_ratio:.1f}\u00d7 average volume")

    _tradeability(res, s, cfg)

    # Penalties
    gap = s.get("gap_pct")
    if _ok(gap) and gap < -8:
        _penalise(res, 10, f"Gapped down {abs(gap):.1f}% \u2014 late to sell here")
    if _ok(rsi) and rsi < 22:
        _penalise(res, 10, f"Washed out (RSI {rsi:.0f}) \u2014 bounce risk")
    _shared_penalties(res, s, cfg)

    res.score = int(round(max(0, min(100, res.score))))
    res.setup = setup
    return res
