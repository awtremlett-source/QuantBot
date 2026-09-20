"""Spotlight tab: durable climbers given the stage. Star to track,
double-click to open."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QLabel, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from manual.scout.spotlight import spotlight_rows
from .theme import GREEN, fmt_px

COLS = ["\u2605", "Ticker", "Name", "Sector", "Steadiness", "1-year", "Last"]


class SpotlightTab(QWidget):
    open_ticker = Signal(str)
    watch_changed = Signal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Large, liquid names that have spent at least 80% of the last "
            "six months above their 200-day average and are up over the "
            "year \u2014 durable climbers, not this week's excitement. "
            "Refreshes itself every scan. Star one to track it; "
            "double-click to open.")
        intro.setObjectName("muted")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.itemDoubleClicked.connect(self._opened)
        self.table.itemChanged.connect(self._starred)
        self.table.setColumnWidth(0, 28)
        self.table.setColumnWidth(2, 200)
        layout.addWidget(self.table, stretch=1)

    def refresh(self, scan_rows: list[dict], watching: set[str]) -> None:
        rows = spotlight_rows(scan_rows)
        t = self.table
        t.blockSignals(True)
        t.setRowCount(len(rows))
        for i, r in enumerate(rows):
            star = QTableWidgetItem()
            star.setFlags(Qt.ItemFlag.ItemIsUserCheckable
                          | Qt.ItemFlag.ItemIsEnabled)
            star.setCheckState(Qt.CheckState.Checked
                               if r["ticker"] in watching
                               else Qt.CheckState.Unchecked)
            star.setData(Qt.ItemDataRole.UserRole, r["ticker"])
            t.setItem(i, 0, star)
            t.setItem(i, 1, self._cell(r["ticker"], r["ticker"]))
            t.setItem(i, 2, self._cell(r["name"], r["ticker"]))
            t.setItem(i, 3, self._cell(r["sector"], r["ticker"]))
            steady = self._cell(f"{r['steady_pct']:.0f}% of 6 months",
                                r["ticker"])
            steady.setForeground(QColor(GREEN))
            t.setItem(i, 4, steady)
            year = r["year_pct"]
            t.setItem(i, 5, self._cell(
                "\u2014" if year is None else f"{year:+.0f}%", r["ticker"]))
            t.setItem(i, 6, self._cell(
                fmt_px(r["close"], r["currency"]), r["ticker"]))
        t.blockSignals(False)

    def _cell(self, text, ticker):
        item = QTableWidgetItem(str(text))
        item.setData(Qt.ItemDataRole.UserRole, ticker)
        return item

    def _opened(self, item):
        ticker = item.data(Qt.ItemDataRole.UserRole)
        if ticker:
            self.open_ticker.emit(ticker)

    def _starred(self, item):
        if item.column() == 0:
            ticker = item.data(Qt.ItemDataRole.UserRole)
            if ticker:
                self.watch_changed.emit(
                    ticker, item.checkState() == Qt.CheckState.Checked)
