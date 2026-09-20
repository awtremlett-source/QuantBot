"""Journal: the scoreboard for the operator, not the stocks. Headline
expectancy, a per-setup breakdown (which setups actually pay you), and the
full trade history with lessons."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QGroupBox, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from manual.scout import journal
from .theme import GREEN, MUTED, RED, fmt_gbp, fmt_shares

TRADE_COLS = ["Opened", "Ticker", "Pattern", "R", "P&L \u00a3", "Reason",
              "Lessons", ""]
SETUP_COLS = ["Pattern", "Trades", "Win rate", "Avg R"]


class JournalTab(QWidget):
    trades_changed = Signal()

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        layout = QVBoxLayout(self)

        stats_box = QGroupBox("YOUR RESULTS SO FAR")
        srow = QHBoxLayout(stats_box)
        self.stat_labels: dict[str, QLabel] = {}
        for key, title in [("count", "Closed"), ("win_rate", "Win rate"),
                           ("expectancy_r", "Avg result"),
                           ("total_pnl_gbp", "Total P&L")]:
            col = QVBoxLayout()
            head = QLabel(title)
            head.setObjectName("muted")
            if key == "expectancy_r":
                head.setToolTip(
                    "In R = multiples of what you risked. +0.50R means a "
                    "typical trade makes half of what it risked \u2014 "
                    "above zero and rising is what you want.")
            val = QLabel("\u2014")
            val.setStyleSheet("font-size:18px; font-weight:bold;")
            col.addWidget(head)
            col.addWidget(val)
            srow.addLayout(col)
            self.stat_labels[key] = val
        srow.addStretch()
        layout.addWidget(stats_box)

        setup_box = QGroupBox("BY PATTERN \u2014 WHICH ONES PAY YOU")
        sv = QVBoxLayout(setup_box)
        self.setup_table = self._table(SETUP_COLS)
        self.setup_table.setMaximumHeight(150)
        sv.addWidget(self.setup_table)
        layout.addWidget(setup_box)

        hist_box = QGroupBox("ALL TRADES")
        hv = QVBoxLayout(hist_box)
        self.trade_table = self._table(TRADE_COLS)
        hv.addWidget(self.trade_table)
        layout.addWidget(hist_box, stretch=1)

    def _table(self, cols: list[str]) -> QTableWidget:
        t = QTableWidget(0, len(cols))
        t.setHorizontalHeaderLabels(cols)
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t.setAlternatingRowColors(True)
        t.verticalHeader().setVisible(False)
        return t

    def refresh(self) -> None:
        trades = self.store.list_trades()
        s = journal.stats(trades)
        self.stat_labels["count"].setText(str(s["count"]))
        self.stat_labels["win_rate"].setText(f"{s['win_rate']:.0f}%")
        exp = s["expectancy_r"]
        exp_label = self.stat_labels["expectancy_r"]
        exp_label.setText("\u2014" if exp is None else f"{exp:+.2f}R")
        if exp is not None:
            exp_label.setStyleSheet(
                f"font-size:18px; font-weight:bold; "
                f"color:{GREEN if exp >= 0 else RED};")
        pnl_label = self.stat_labels["total_pnl_gbp"]
        pnl_label.setText(fmt_gbp(s["total_pnl_gbp"]))
        pnl_label.setStyleSheet(
            f"font-size:18px; font-weight:bold; "
            f"color:{GREEN if s['total_pnl_gbp'] >= 0 else RED};")

        by = s["by_setup"]
        self.setup_table.setRowCount(len(by))
        for i, (setup, b) in enumerate(sorted(by.items())):
            self.setup_table.setItem(i, 0, QTableWidgetItem(setup))
            self.setup_table.setItem(i, 1, QTableWidgetItem(str(b["count"])))
            self.setup_table.setItem(i, 2, QTableWidgetItem(
                f"{b['win_rate']:.0f}%"))
            avg = b["avg_r"]
            self.setup_table.setItem(i, 3, QTableWidgetItem(
                "\u2014" if avg is None else f"{avg:+.2f}R"))

        t = self.trade_table
        t.setRowCount(len(trades))
        for i, tr in enumerate(trades):
            detail_tip = (f"{fmt_shares(tr['shares'])} shares \u00b7 "
                          f"entry {fmt_gbp(tr['entry_px'])} \u00b7 "
                          f"alert {fmt_gbp(tr['stop_px'])} \u00b7 "
                          f"exit {fmt_gbp(tr.get('exit_px'))}")
            opened = QTableWidgetItem(tr["opened_at"])
            opened.setToolTip(detail_tip)
            t.setItem(i, 0, opened)
            t.setItem(i, 1, QTableWidgetItem(tr["ticker"]))
            t.setItem(i, 2, QTableWidgetItem(tr.get("setup_type") or "\u2014"))
            r = tr.get("r_multiple")
            r_item = QTableWidgetItem("\u2014" if r is None else f"{r:+.2f}")
            if r is not None:
                r_item.setForeground(QColor(GREEN if r >= 0 else RED))
            t.setItem(i, 3, r_item)
            pnl = tr.get("pnl_gbp")
            p_item = QTableWidgetItem(fmt_gbp(pnl))
            if pnl is not None:
                p_item.setForeground(QColor(GREEN if pnl >= 0 else RED))
            t.setItem(i, 4, p_item)
            t.setItem(i, 5, QTableWidgetItem(tr.get("exit_reason") or ""))
            lessons = QTableWidgetItem(tr.get("lessons") or "")
            lessons.setForeground(QColor(MUTED))
            t.setItem(i, 6, lessons)
            btn = QPushButton("Delete")
            btn.clicked.connect(
                lambda _=False, tid=tr["id"], tk=tr["ticker"]:
                self._delete_trade(tid, tk))
            t.setCellWidget(i, 7, btn)

    def _delete_trade(self, trade_id: int, ticker: str) -> None:
        resp = QMessageBox.question(
            self, "Delete record",
            f"Permanently delete this {ticker} record? This can't be "
            f"undone \u2014 use it for mistakes, not for real history.")
        if resp != QMessageBox.StandardButton.Yes:
            return
        self.store.delete_trade(trade_id)
        self.refresh()
        self.trades_changed.emit()
