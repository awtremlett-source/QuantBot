"""The bot's agreed universe, read for research and measurement (S4).

The anchor doorway (qb2/execution/anchors.py) has its own hash-pinned loader, but
nothing in qb2 may import the doorway (tests/wall/test_broker_readonly.py), so the
firewall, the cross-check and the freshness meter read the list here instead.

It refuses a list nobody agreed to: S4's exit gate requires the versioned bot
file to say AGREED and to carry the operator's own words and the date. A backtest
run on a list nobody chose would have to be thrown away.

QT-15 A4: P19 registers its daily trials on the ADVISOR list (171 names, DERIVED
by P6's rule: the recording list minus the bot's). It is read the same way --
each entry carries its exchange, T212 ticker, quote currency and kind, so the
firewall costs it per name (FX on both legs of every non-sterling line, stamp
duty on UK share buys) and bet_groups applies -- and :func:`for_register` hands
each register entry the universe it names.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
BOT_FILE = REPO_ROOT / "docs" / "universe" / "bot-universe-v1-2026-10-01.json"
ADVISOR_FILE = REPO_ROOT / "docs" / "universe" / "advisor-universe-v1-2026-10-01.json"
LONDON = "LSE"
US = "US"


class NotAgreed(RuntimeError):
    """The list is not the agreed one. Nothing is scored or measured on it."""


def agreement(path: Path | None = None) -> dict[str, str]:
    """Status, words and date -- or a refusal naming what is missing."""
    doc = json.loads((path or BOT_FILE).read_text(encoding="utf-8"))
    words = str(doc.get("agreed_words_verbatim", "")).strip()
    on = str(doc.get("agreed_on", "")).strip()
    if doc.get("list") != "bot" or doc.get("status") != "AGREED" or not words or not on:
        raise NotAgreed(f"{(path or BOT_FILE).name} is not AGREED with the operator's "
                        "own words and a date -- S4 refuses to score on it")
    return {"status": "AGREED", "words": words, "on": on}


def bot_entries(path: Path | None = None) -> list[dict[str, Any]]:
    """The agreed names, each with yfinance, t212_ticker, quote_currency, kind..."""
    agreement(path)
    doc = json.loads((path or BOT_FILE).read_text(encoding="utf-8"))
    entries = [e for e in doc.get("entries", []) if isinstance(e, dict)]
    if not entries:
        raise NotAgreed("the agreed bot list has no entries")
    return entries


def market_of(entry: Mapping[str, Any]) -> str:
    """LSE for a London line, US otherwise -- read from the exchange, not the suffix."""
    return LONDON if "London" in str(entry.get("exchange", "")) else US


def advisor_entries(path: Path | None = None) -> list[dict[str, Any]]:
    """The advisor's names: a list DERIVED by P6's rule, refused if it says otherwise."""
    doc = json.loads((path or ADVISOR_FILE).read_text(encoding="utf-8"))
    if doc.get("list") != "advisor" or doc.get("status") != "DERIVED":
        raise NotAgreed(f"{(path or ADVISOR_FILE).name} is not the advisor list DERIVED "
                        "by P6's rule -- nothing is scored on it")
    entries = [e for e in doc.get("entries", []) if isinstance(e, dict)]
    if not entries:
        raise NotAgreed("the advisor list has no entries")
    return entries


LOADERS: dict[str, Callable[[], list[dict[str, Any]]]] = {
    "bot-universe-v1": bot_entries, "advisor-universe-v1": advisor_entries}


def for_register(entry: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The universe a register entry names ("advisor-universe-v1: the 171 ...")."""
    name = str(entry.get("universe", "")).split(":", 1)[0].strip()
    if name not in LOADERS:
        raise NotAgreed(f"{entry.get('id')}: names no known universe ({name!r})")
    return LOADERS[name]()
