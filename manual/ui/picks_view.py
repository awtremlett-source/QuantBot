"""Pick History: what the app recommended each day and how it aged.

Colour logic is side-aware: a BUY pick going up is green; a SELL/AVOID pick
going DOWN is green (the warning was right). Double-click any row to open
the stock."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QGroupBox, QLabel, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from manual.scout.picks import performance
from .theme import GREEN, MUTED, RED, fmt_num

COLS = ["Date", "Side", "Ticker", "Name", "% since"]


class PicksTab(QWidget):
    open_ticker = Signal(str)

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        layout = QVBoxLayout(self)

        box = QGroupBox("THE APP'S TRACK RECORD \u2014 EVERY DAILY BOARD, "
                        "MEASURED SINCE")
        bv = QVBoxLayout(box)
        self.summary = QLabel("No picks recorded yet \u2014 they save "
                              "automatically after each day's scan.")
        self.summary.setStyleSheet("font-size:15px; font-weight:bold;")
        bv.addWidget(self.summary)
        hint = QLabel("BUY picks: green when up since pick. SELL/AVOID "
                      "picks: green when down since pick (the warning was "
                      "right). Double-click a row to open the stock.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        bv.addWidget(hint)
        layout.addWidget(box)

        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.itemDoubleClicked.connect(self._row_opened)
        self.table.setColumnWidth(0, 90)
        self.table.setColumnWidth(1, 50)
        self.table.setColumnWidth(2, 30)
        self.table.setColumnWidth(3, 70)
        self.table.setColumnWidth(4, 170)
        layout.addWidget(self.table, stretch=1)

    def refresh(self) -> None:
        rows, agg = performance(self.store, self.store.list_picks())
        if agg["n"]:
            parts = []
            if agg["buy_avg_pct"] is not None:
                parts.append(f"BUY picks average since pick: "
                             f"{agg['buy_avg_pct']:+.1f}%")
            if agg["sell_avg_pct"] is not None:
                parts.append(f"SELL/AVOID picks average since pick: "
                             f"{agg['sell_avg_pct']:+.1f}%")
            self.summary.setText("   \u00b7   ".join(parts) or
                                 f"{agg['n']} picks recorded")
        t = self.table
        t.setRowCount(len(rows))
        for i, r in enumerate(rows):
            tip = (f"Rank {r['rank']} \u00b7 score {r.get('score')} \u00b7 "
                   f"{r.get('setup') or '\u2014'}\n"
                   f"Picked at {fmt_num(r.get('px'))}, now "
                   f"{fmt_num(r.get('px_now'))} "
                   f"({r.get('bars_since') or 0} trading days on)")
            date_item = QTableWidgetItem(r["date"])
            date_item.setToolTip(tip)
            t.setItem(i, 0, date_item)
            side_item = QTableWidgetItem(r["side"])
            side_item.setForeground(
                QColor(GREEN if r["side"] == "BUY" else RED))
            t.setItem(i, 1, side_item)
            t.setItem(i, 2, self._cell(r["ticker"], r["ticker"]))
            t.setItem(i, 3, self._cell(r.get("name") or "", r["ticker"]))
            pct = r.get("change_pct")
            pct_item = QTableWidgetItem(
                "\u2014" if pct is None else f"{pct:+.1f}%")
            pct_item.setToolTip(tip)
            if pct is not None:
                good = pct >= 0 if r["side"] == "BUY" else pct <= 0
                pct_item.setForeground(QColor(GREEN if good else RED))
            t.setItem(i, 4, pct_item)

    def _cell(self, text: str, ticker: str) -> QTableWidgetItem:
        item = QTableWidgetItem(str(text))
        item.setData(Qt.ItemDataRole.UserRole, ticker)
        return item

    def _row_opened(self, item: QTableWidgetItem) -> None:
        tk = self.table.item(item.row(), 2)
        if tk:
            self.open_ticker.emit(tk.text())
