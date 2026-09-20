"""Today's Board: two ranked tables. Double-click a row to open the stock;
tick the star column to watch it. Score cells carry their full reason list
as a tooltip -- no black boxes."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QGroupBox, QHBoxLayout, QLabel, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from .theme import GREEN, MUTED, RED, fmt_px

COLS = ["\u2605", "Ticker", "Name", "Score", "Pattern", "Last", "Why"]


class BoardTab(QWidget):
    open_ticker = Signal(str)
    watch_changed = Signal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        self.buy_table = self._make_table()
        self.sell_table = self._make_table()
        layout.addWidget(self._boxed("STRONGEST TODAY \u2014 WORTH A LOOK TO BUY",
                                     self.buy_table))
        layout.addWidget(self._boxed("WEAKEST TODAY \u2014 AVOID, OR SELL IF YOU HOLD THEM",
                                     self.sell_table))
        self.hint = QLabel("No data yet. Press Refresh data to pull the "
                           "universe from Yahoo Finance.")
        self.hint.setObjectName("muted")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _boxed(self, title: str, table: QTableWidget) -> QGroupBox:
        box = QGroupBox(title)
        lay = QVBoxLayout(box)
        lay.addWidget(table)
        return box

    def _make_table(self) -> QTableWidget:
        t = QTableWidget(0, len(COLS))
        t.setHorizontalHeaderLabels(COLS)
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        t.setAlternatingRowColors(True)
        t.verticalHeader().setVisible(False)
        t.setSortingEnabled(False)
        t.itemDoubleClicked.connect(self._row_opened)
        t.itemChanged.connect(self._star_changed)
        t.setColumnWidth(0, 28)
        t.setColumnWidth(1, 70)
        t.setColumnWidth(2, 170)
        t.setColumnWidth(3, 52)
        t.setColumnWidth(4, 92)
        t.setColumnWidth(5, 78)
        tips = {3: "0\u2013100. Hover any score to see exactly why.",
                4: "The kind of opportunity spotted (Breakout, Pullback...)",
                5: "Latest price. p = pence.",
                6: "The top reasons in plain English. Hover for all of them."}
        for col, tip in tips.items():
            t.horizontalHeaderItem(col).setToolTip(tip)
        return t

    def populate(self, rows: list[dict], top_n: int, watching: set[str]) -> None:
        buys = sorted(rows, key=lambda r: r["buy"].score, reverse=True)[:top_n]
        sells = sorted(rows, key=lambda r: r["sell"].score, reverse=True)[:top_n]
        self._fill(self.buy_table, buys, "buy", GREEN, watching)
        self._fill(self.sell_table, sells, "sell", RED, watching)

    def _fill(self, table: QTableWidget, rows: list[dict], side: str,
              colour: str, watching: set[str]) -> None:
        table.blockSignals(True)
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        base = QColor(colour)
        for i, r in enumerate(rows):
            res = r[side]
            snap = r["snap"]
            star = QTableWidgetItem()
            star.setFlags(Qt.ItemFlag.ItemIsUserCheckable
                          | Qt.ItemFlag.ItemIsEnabled)
            star.setCheckState(Qt.CheckState.Checked if r["ticker"] in watching
                               else Qt.CheckState.Unchecked)
            star.setData(Qt.ItemDataRole.UserRole, r["ticker"])
            table.setItem(i, 0, star)

            table.setItem(i, 1, self._cell(r["ticker"], r["ticker"]))
            table.setItem(i, 2, self._cell(r["name"], r["ticker"]))

            score_item = self._cell("", r["ticker"])
            score_item.setData(Qt.ItemDataRole.EditRole, res.score)
            shade = QColor(base)
            shade.setAlpha(40 + int(res.score * 1.6))
            score_item.setBackground(shade)
            score_item.setToolTip("\n".join(res.reasons) or "No points scored")
            score_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(i, 3, score_item)

            table.setItem(i, 4, self._cell(res.setup, r["ticker"]))
            table.setItem(i, 5, self._cell(
                fmt_px(snap["close"], snap["currency"]), r["ticker"]))
            why = "; ".join(x.split("\u00b7 ", 1)[-1] for x in res.reasons[:3])
            why_item = self._cell(why, r["ticker"])
            why_item.setToolTip("\n".join(res.reasons))
            why_item.setForeground(QColor(MUTED))
            table.setItem(i, 6, why_item)
        table.setSortingEnabled(True)
        table.sortItems(3, Qt.SortOrder.DescendingOrder)
        table.blockSignals(False)

    def _cell(self, text: str, ticker: str) -> QTableWidgetItem:
        item = QTableWidgetItem(str(text))
        item.setData(Qt.ItemDataRole.UserRole, ticker)
        return item

    def _row_opened(self, item: QTableWidgetItem) -> None:
        ticker = item.data(Qt.ItemDataRole.UserRole)
        if ticker:
            self.open_ticker.emit(ticker)

    def _star_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        ticker = item.data(Qt.ItemDataRole.UserRole)
        if ticker:
            self.watch_changed.emit(
                ticker, item.checkState() == Qt.CheckState.Checked)
