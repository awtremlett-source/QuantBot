"""Playbook: turn signals into a recommended path.

recommend_new(...)  -- for a stock you're considering: picks the best-fit
play for THIS stock in TODAY'S environment and lays out enter / manage /
exit as numbered steps with pound numbers where possible.

manage_path(...)    -- for a position you already hold: one concrete line
on how to run it from here (trail levels, the exit tripwire).

Plays are the long-only playbook: stage-2 trend ride, golden cross,
52-week breakout, pullback-in-uptrend, oversold snap-back, and cash.
"""
from __future__ import annotations


def _fmt(v: float | None) -> str:
    return "\u2014" if v is None else f"\u00a3{v:,.2f}"


def _ladder_step(ladder: dict | None, plan: dict) -> tuple | None:
    if not ladder:
        return None
    if ladder["full"]:
        return ("Money split", "Your 50% ladder is full \u2014 bank a "
                               "position before adding a new one.")
    pct = ladder["next_fraction"] * 100
    text = (f"This would be position #{ladder['next_slot']} \u2014 the 50% "
            f"ladder allows up to {_fmt(ladder['next_cap'])} "
            f"({pct:g}% of the pot).")
    if plan.get("ok"):
        if any("money ladder" in w for w in plan.get("warnings", [])):
            text += " Your size was trimmed to fit."
        else:
            text += (f" Your plan uses {_fmt(plan['value_gbp'])} "
                     f"\u2014 fits comfortably.")
    return ("Money split", text)


def with_money_split(rec: dict, ladder: dict | None,
                     plan: dict) -> dict:
    """Insert the Money split step after Enter for tradeable plays."""
    if rec.get("tradeable"):
        step = _ladder_step(ladder, plan)
        if step:
            rec["steps"] = [rec["steps"][0], step] + rec["steps"][1:]
    return rec


def recommend_new(snap: dict, buy_res, sell_res, plan: dict,
                  dial_state: str = "MIXED",
                  hiccups: dict | None = None) -> dict:
    """Returns {play, why, steps: [(label, text)...], tradeable: bool}."""
    hic = hiccups or {}
    small = hic.get("small", {}).get("active", False)
    large = hic.get("large", {}).get("active", False)
    entry = plan.get("entry_gbp") if plan.get("ok") else None
    stop = plan.get("stop_gbp") if plan.get("ok") else None
    atr = snap.get("atr_gbp")
    close = snap.get("close_gbp")

    # ---- environment veto first ----
    if dial_state == "ROUGH" or large:
        return {
            "play": "Cash is a position", "tradeable": False,
            "why": ("Conditions are hostile \u2014 most new buys lose money "
                    "in this weather regardless of the stock."),
            "steps": [
                ("Don't enter", "Stand aside on this one for now."),
                ("Keep it warm", "Star it \u2014 the watchlist tracks it "
                                 "for the turn."),
                ("The door reopens", "when the dial climbs out of ROUGH "
                                     "and no large hiccup is active."),
            ]}

    setup = buy_res.setup
    sizing = "half your normal size" if dial_state == "MIXED" \
        else "normal size"

    if setup == "Breakout":
        steps = [
            ("Enter", f"Buy near {_fmt(entry)} at {sizing} \u2014 "
                      "breakouts want strength, not haggling."),
            ("Protect", f"Sell alert at {_fmt(stop)} from day one."),
            ("Manage", "Each week it rises, raise the alert to about "
                       "2\u00d7 its daily range below price"
                       + (f" (today: {_fmt(close - 2 * atr)})"
                          if close and atr else "") + "."),
            ("Exit", "Alert hit, or a close below the 50-day average "
                     "\u2014 whichever comes first."),
        ]
        return {"play": "52-week breakout", "tradeable": True,
                "why": "It's pressing its yearly high on heavy volume "
                       "\u2014 momentum's strongest signature.",
                "steps": steps}

    if setup == "Pullback":
        why = "An uptrending stock cooling to its 50-day \u2014 buying " \
              "strength at a discount."
        if small:
            why += " A small market hiccup is active: prime window for " \
                   "exactly this play."
        target = snap.get("dist_to_hi_pct")
        steps = [
            ("Enter", f"Buy near {_fmt(entry)} at {sizing}."),
            ("Protect", f"Sell alert at {_fmt(stop)} \u2014 just under "
                        "the pullback low."),
            ("First target", "the old high"
             + (f", about {target:.1f}% above" if target else "") + "."),
            ("Exit", "If the bounce fails \u2014 a close below the 20-day "
                     "average \u2014 take the small loss and move on."),
        ]
        return {"play": "Pullback in uptrend", "tradeable": True,
                "why": why, "steps": steps}

    if snap.get("golden_cross_recent") and close is not None \
            and snap.get("sma200") and snap["close"] > snap["sma200"]:
        return {"play": "Golden cross", "tradeable": True,
                "why": "Its 50-day just crossed above its 200-day \u2014 "
                       "the classic start-of-trend signal.",
                "steps": [
                    ("Enter", f"Buy near {_fmt(entry)} at {sizing}."),
                    ("Protect", f"Sell alert at {_fmt(stop)}."),
                    ("Hold", "while the 50-day stays above the 200-day "
                             "\u2014 these runs take months, let it work."),
                    ("Exit", "the reverse cross, or your alert."),
                ]}

    if setup == "Trend-follow" and buy_res.score >= 30:
        rsi = snap.get("rsi")
        if rsi is not None and rsi > 78:
            enter = (f"It's overheated right now (RSI {rsi:.0f}) \u2014 "
                     "don't chase today; wait for a few quiet days or a "
                     "dip toward the 20-day, then buy at " + sizing + ".")
        else:
            enter = (f"Buy near {_fmt(entry)} at {sizing} \u2014 "
                     "no need to chase a perfect day.")
        return {"play": "Stage-2 trend ride", "tradeable": True,
                "why": "A steady climber above a rising 200-day \u2014 "
                       "the slow-and-boring play that builds accounts.",
                "steps": [
                    ("Enter", enter),
                    ("Protect", f"Sell alert at {_fmt(stop)}, then forget "
                                "the daily noise."),
                    ("Hold", "for months while it closes above its "
                             "200-day average."),
                    ("Exit", "a decisive close below the 200-day \u2014 "
                             "the trend is over when it says so."),
                ]}

    if sell_res.score >= 45:
        return {"play": "No path \u2014 avoid", "tradeable": False,
                "why": "This one belongs on the weak board, not in your "
                       "account.",
                "steps": [("Skip it", "Plenty of stronger fish today.")]}

    return {"play": "No clean play yet", "tradeable": False,
            "why": "Nothing here fits a play today \u2014 forcing trades "
                   "is how accounts leak.",
            "steps": [
                ("Wait for", "a breakout near the yearly high on volume, "
                             "or a pullback to the 50-day in an uptrend."),
                ("Meanwhile", "star it and the app will keep watch."),
            ]}


def manage_path(snap: dict, trade: dict) -> str:
    """One line: how to run a position you already hold from here."""
    close = snap.get("close_gbp")
    stop = trade.get("stop_px")
    atr = snap.get("atr_gbp")
    trail = (close - 2 * atr) if (close and atr) else None
    raise_bit = ""
    if trail and stop is not None and trail > stop:
        raise_bit = f" Raise your sell alert to {_fmt(trail)}."

    sma50, sma200 = snap.get("sma50"), snap.get("sma200")
    c = snap.get("close")
    if close is not None and stop is not None and close <= stop:
        return "Path: sell today \u2014 the alert did its job. Log the lesson."
    if c and sma200 and sma50 and c > sma200 and sma50 > sma200 \
            and c > sma50:
        return ("Path: trend-ride \u2014 hold while it closes above its "
                "200-day." + raise_bit)
    if c and sma50 and c > sma50:
        return ("Path: swing \u2014 hold above the 50-day; sell on a close "
                "below it." + raise_bit)
    return ("Path: tighten \u2014 it's below its 50-day; sell into "
            "strength or on any further weakness." + raise_bit)
