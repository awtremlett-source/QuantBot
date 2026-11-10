"""The anchor extras: the one name the anchor buyer may hold beside the agreed 50.

PLAN_V3 P20, addendum of 2026-11-10 (QT-31). VWRL is the ADVISOR's fund (ADV-0),
not one of the bot's 50, so it cannot join the agreed 50-name file: that file's
bytes, its hash and its exactly-50 check stay as agreed. Trading 212 prices only
what we hold (FACTS row h), so P22's second price for VWRL needs a small anchor.

The fences here, each held by a test in tests/qb2/test_qt31_vwrl_anchor.py:

* the file's bytes are pinned by hash (line endings folded to LF, as anchors.py
  pins the 50), so a changed file is refused, never read;
* it must be the AGREED anchor-extras list with exactly ONE entry, and that entry
  must be VWRL on the London Stock Exchange with its pinned ticker, ISIN and
  currency. Anything else is refused, even if the hash were moved to match it.

This module reads one file and nothing else. It cannot buy: the anchor buyer
(qb2/execution/anchors.py) reads it beside the 50 and applies every fence F1-F13
and every cap to this name unchanged. Standard library only.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
EXTRAS_FILE = REPO_ROOT / "docs" / "universe" / "anchor-extras-v1-2026-11.json"
# sha256 with CRLF folded to LF -- the file as committed in QT-31.
EXTRAS_SHA256 = "040abd435ff6cd231a437cc2599df7831ff8538c0222a5861b8fef3936cc6a11"
LIST_NAME = "anchor-extras"
AGREED = "AGREED"

# The one name, as the advisor list has it (advisor-universe-v1-2026-10-01.json).
ONLY_NAME: Mapping[str, str] = {
    "yfinance": "VWRL.L",
    "t212_ticker": "VWRLl_EQ",
    "isin": "IE00B3RBWM25",
    "exchange": "London Stock Exchange",
    "quote_currency": "GBP",
}


class ExtrasRefused(RuntimeError):
    """The extras file is not the one agreed, so nothing in it is used."""


def sha256_lf(raw: bytes) -> str:
    """Hash with CRLF folded to LF, so a Windows checkout hashes like git's copy."""
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def load(path: Path | None = None,
         expected_sha256: str = EXTRAS_SHA256) -> list[dict[str, Any]]:
    """The one agreed extra name, or a refusal. Never a name nobody agreed to."""
    target = path or EXTRAS_FILE
    try:
        raw = target.read_bytes()
    except OSError as exc:
        raise ExtrasRefused(f"{target.name} cannot be read ({type(exc).__name__}) "
                            "-- no extra anchor without the agreed file") from exc
    if sha256_lf(raw) != expected_sha256:
        raise ExtrasRefused(
            f"{target.name} is not the file agreed in QT-31 (its hash changed) "
            "-- a changed list is a new decision, not an edit")
    try:
        doc = json.loads(raw.decode("utf-8"))
    except ValueError as exc:
        raise ExtrasRefused(f"{target.name} is not readable JSON") from exc
    entries = doc.get("entries") if isinstance(doc, dict) else None
    if (not isinstance(doc, dict) or doc.get("list") != LIST_NAME
            or doc.get("status") != AGREED or not isinstance(entries, list)
            or len(entries) != 1):
        raise ExtrasRefused(f"{target.name} must be the AGREED {LIST_NAME} list "
                            "holding exactly one name")
    entry = entries[0]
    if not isinstance(entry, dict) or any(
            entry.get(key) != value for key, value in ONLY_NAME.items()):
        raise ExtrasRefused(f"{target.name} names something other than VWRL on "
                            "the London Stock Exchange -- refused")
    return [entry]
