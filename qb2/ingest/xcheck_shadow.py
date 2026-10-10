"""P20's cross-check in SHADOW: computed and logged every in-session run, guarding nothing.

Each recorder run inside a market's regular session takes a fresh yfinance minute
quote for every anchored name in that market, reads Trading 212's ``currentPrice``
from the positions the anchors created (FACTS row h: the broker prices only what
we hold), rates each pair with qb2/execution/xcheck.py, and appends the verdicts
to data/raw/xcheck/<day>.jsonl.

Why shadow first: it measures how often each level WOULD have fired -- the false
alarm rate -- before the check is ever allowed to stop a trade. An alarm that
fires on healthy prices teaches everyone to ignore it.

Read-only throughout: positions come from the GET-only practice client.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from qb2.data import access, universe
from qb2.execution import xcheck
from qb2.ingest import recorder, tickers
from qb2.signals import indicators

REPO_ROOT = Path(__file__).resolve().parents[2]
FOLDER = REPO_ROOT / "data" / "raw" / "xcheck"
ATR_DAYS = 7                     # calendar days of clean 5m bars for ATR(14)

Fetch = Callable[[Sequence[str], str, int], Mapping[str, pd.DataFrame]]
AtrOf = Callable[[str, datetime, str], float | None]


def broker_prices(positions: Iterable[Mapping[str, Any]]) -> dict[str, tuple[float, str]]:
    """t212 ticker -> (currentPrice, Trading 212's currency for it)."""
    out: dict[str, tuple[float, str]] = {}
    for row in positions:
        instrument = row.get("instrument")
        info = instrument if isinstance(instrument, dict) else {}
        ticker = str(info.get("ticker") or row.get("ticker") or "")
        price = row.get("currentPrice")
        if ticker and isinstance(price, (int, float)) and not isinstance(price, bool):
            out[ticker] = (float(price), str(info.get("currency") or ""))
    return out


def latest_close(frame: pd.DataFrame | None, now: datetime) -> tuple[float, float] | None:
    """(close, age in seconds) of the newest FINISHED one-minute bar, or None."""
    if frame is None or frame.empty:
        return None
    done = recorder.drop_forming_bar(frame, "1m", now)
    if done.empty:
        return None
    stamp = pd.Timestamp(done.index[-1])
    stamp = stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp
    age = (now - (stamp.to_pydatetime() + timedelta(minutes=1))).total_seconds()
    return float(done["close"].iloc[-1]), max(0.0, age)


def recent_atr(symbol: str, now: datetime, currency: str,
               clean_root: Path | None = None) -> float | None:
    """Wilder ATR(14) of the last clean 5m bars, expressed in ``currency``."""
    try:
        bars = access.bars(symbol, "5m", clean_root=clean_root,
                           since=(now - timedelta(days=ATR_DAYS)).date())
    except access.AccessRefused:
        return None
    if len(bars) < 15:
        return None
    stored = str(bars["currency"].iloc[-1]) if "currency" in bars.columns else currency
    return xcheck.to_quote(float(indicators.atr_wilder(bars).iloc[-1]), stored, currency)


def names_in(open_markets: Sequence[str],
             entries: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [e for e in entries if universe.market_of(e) in open_markets]


def quotes_for(names: Sequence[Mapping[str, Any]], fetch: Fetch) -> Mapping[str, pd.DataFrame]:
    """Fresh yfinance minute bars for these names: one batched request."""
    return fetch([str(e["yfinance"]) for e in names], "1m", 1) if names else {}


def run_sweep(now: datetime, held: Mapping[str, tuple[float, str]],
              names: Sequence[Mapping[str, Any]], quotes: Mapping[str, pd.DataFrame],
              atr_of: AtrOf = recent_atr) -> list[xcheck.Rating]:
    """One sweep over the given anchored names; the final verdicts."""
    ratings: list[xcheck.Rating] = []
    for entry in names:
        symbol = str(entry["yfinance"])
        ours_ccy = tickers.quote_currency(symbol) or str(entry["quote_currency"])
        ours = latest_close(quotes.get(symbol), now)
        broker = held.get(str(entry["t212_ticker"]))
        ratings.append(xcheck.rate(
            str(entry["t212_ticker"]), universe.market_of(entry),
            quote_currency=str(entry["quote_currency"]),
            broker_price=broker[0] if broker else None,
            broker_currency=broker[1] if broker else "",
            our_price=ours[0] if ours else None, our_currency=ours_ccy,
            our_age_seconds=ours[1] if ours else None,
            atr=atr_of(symbol, now, ours_ccy)))
    return xcheck.sweep(ratings)


def log(ratings: Sequence[xcheck.Rating], now: datetime,
        folder: Path | None = None) -> Path:
    target = (folder or FOLDER) / f"{now.astimezone(timezone.utc):%Y-%m-%d}.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    stamp = now.astimezone(timezone.utc).isoformat(timespec="seconds")
    with target.open("a", encoding="utf-8") as handle:
        for rating in ratings:
            handle.write(json.dumps({"at_utc": stamp, **rating.as_dict()}) + "\n")
    return target


def would_have_fired(folder: Path | None = None) -> dict[str, int]:
    """Every logged verdict so far, counted by level; plus the number of sweeps."""
    counts = {level: 0 for level in (xcheck.OK, xcheck.WARN, xcheck.BLOCK,
                                     xcheck.STOP, xcheck.NO_COMPARISON)}
    sweeps: set[tuple[str, str]] = set()
    for path in sorted((folder or FOLDER).glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue                       # a half-written last line
            if row.get("level") in counts:
                counts[str(row["level"])] += 1
                sweeps.add((str(row.get("at_utc")), str(row.get("market"))))
    return {**counts, "sweeps": len(sweeps)}


def status_line(folder: Path | None = None) -> str:
    c = would_have_fired(folder)
    return (f"Cross-check (shadow): warn {c[xcheck.WARN]} · block {c[xcheck.BLOCK]} · "
            f"stop {c[xcheck.STOP]} · no comparison {c[xcheck.NO_COMPARISON]} "
            f"(of {sum(v for k, v in c.items() if k != 'sweeps')} name checks "
            f"in {c['sweeps']} market sweeps)")
