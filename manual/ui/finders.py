"""Shared helpers for finding stocks by name or ticker.

Every picker in the app shows "TICKER \u2014 Company Name" and lets you type
any part of either: "gold", "shel", "google" all work.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QCompleter

SEP = " \u2014 "


def stock_label(row: dict) -> str:
    return f"{row['ticker']}{SEP}{row['name']}"


def stock_labels(rows: list[dict]) -> list[str]:
    return [stock_label(r) for r in rows]


def ticker_from_label(text: str) -> str:
    return text.split(SEP)[0].strip().upper()


def make_searchable(combo: QComboBox) -> None:
    """Turn a combo into a type-to-search box matching anywhere in the text."""
    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    completer = combo.completer()
    completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
    completer.setFilterMode(Qt.MatchFlag.MatchContains)
    completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)


def make_line_completer(labels: list[str]) -> QCompleter:
    completer = QCompleter(labels)
    completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
    completer.setFilterMode(Qt.MatchFlag.MatchContains)
    completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    return completer
