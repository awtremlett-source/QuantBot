"""Watchlist & Positions: open paper trades with live exit flags on top,
the watchlist underneath. Close a trade with the button on its row."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox,
                               QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPushButton,
                               QSplitter, QTableWidget, QTableWidgetItem,
                               QTextEdit, QVBoxLayout, QWidget)

from manual.scout import journal
from manual.scout.indicators import to_gbp
from manual.scout.ladder import ladder_line, ladder_state
from manual.scout.playbook import manage_path
from manual.scout.scan import position_verdict
from .manual_trade import RecordTradeDialog
from .theme import AMBER, GREEN, RED, fmt_gbp, fmt_shares

POS_COLS = ["Ticker", "Opened", "Entry \u00a3", "Stop \u00a3", "Shares",
            "Last \u00a3", "Open P&L \u00a3", "Warnings", ""]
WATCH_COLS = ["Ticker", "Name", "Buy", "Sell", "Setup"]

EXIT_REASONS = ["Stop hit", "Strength faded / target", "Signal rolled over",
                "Time stop", "Thesis broken", "Other"]


class CloseTradeDialog(QDialog):
    def __init__(self, trade: dict, last_close_gbp: float | None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Close {trade['ticker']}")
        form = QFormLayout(self)
        self.price = QLineEdit()
        if last_close_gbp is not None:
            self.price.setText(f"{last_close_gbp:.4f}")
        form.addRow("Exit price (\u00a3 per share)", self.price)
        self.reason = QComboBox()
        self.reason.addItems(EXIT_REASONS)
        form.addRow("Reason", self.reason)
        self.lessons = QTextEdit()
        self.lessons.setPlaceholderText("What did this trade teach you?")
        self.lessons.setFixedHeight(60)
        form.addRow("Lessons", self.lessons)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> tuple[float, str, str]:
        return (float(self.price.text()), self.reason.currentText(),
                self.lessons.toPlainText().strip())


class PositionsTab(QWidget):
    open_ticker = Signal(str)
    trades_changed = Signal()

    def __init__(self, store, cfg=None, parent=None):
        super().__init__(parent)
        self.store = store
        self.cfg = cfg
        self.universe_rows: list[dict] = []
        self._snap_lookup: dict[str, dict] = {}
        self._name_lookup: dict[str, str] = {}

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.record_btn = QPushButton("Record a trade I already have\u2026")
        self.record_btn.clicked.connect(self._record_existing)
        top.addWidget(self.record_btn)
        self.ladder_label = QLabel("")
        self.ladder_label.setObjectName("muted")
        top.addWidget(self.ladder_label)
        top.addStretch()
        layout.addLayout(top)
        split = QSplitter(Qt.Orientation.Vertical)

        pos_box = QGroupBox("TRADES YOU\u2019RE IN (PRACTICE MONEY)")
        pv = QVBoxLayout(pos_box)
        self.pos_table = self._table(POS_COLS)
        pv.addWidget(self.pos_table)
        split.addWidget(pos_box)

        watch_box = QGroupBox("WATCHING \u2014 STOCKS YOU STARRED")
        wv = QVBoxLayout(watch_box)
        self.watch_table = self._table(WATCH_COLS)
        self.watch_table.itemDoubleClicked.connect(self._watch_opened)
        wv.addWidget(self.watch_table)
        split.addWidget(watch_box)

        layout.addWidget(split)

    def _table(self, cols: list[str]) -> QTableWidget:
        t = QTableWidget(0, len(cols))
        t.setHorizontalHeaderLabels(cols)
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        t.setAlternatingRowColors(True)
        t.verticalHeader().setVisible(False)
        return t

    def refresh(self, scan_rows: list[dict],
                live: dict[str, float] | None = None) -> None:
        self._snap_lookup = {r["ticker"]: r for r in scan_rows}
        self._name_lookup = {r["ticker"]: r["name"] for r in scan_rows}
        self._live = live or {}
        if self.cfg is not None:
            self.ladder_label.setText(
                ladder_line(ladder_state(self.store, self.cfg)))
        self._fill_positions()
        self._fill_watchlist()

    def _live_snap(self, ticker: str, snap: dict) -> dict:
        """Overlay the latest live quote (if any) onto a daily snapshot."""
        px = self._live.get(ticker)
        if px is None:
            return snap
        live_gbp = to_gbp(px, snap.get("currency", "GBp"))
        if live_gbp is None:
            return snap
        out = dict(snap)
        out["close"] = px
        out["close_gbp"] = live_gbp
        return out

    def _fill_positions(self) -> None:
        trades = self.store.list_trades(open_only=True)
        t = self.pos_table
        t.setRowCount(len(trades))
        colours = {"HOLD": GREEN, "BEWARE": AMBER, "SELL OUT": RED}
        for i, tr in enumerate(trades):
            row = self._snap_lookup.get(tr["ticker"])
            snap = self._live_snap(tr["ticker"], row["snap"]) if row else None
            last = snap["close_gbp"] if snap else None
            pnl = (last - tr["entry_px"]) * tr["shares"] - \
                (tr.get("open_costs_gbp") or 0) if last is not None else None

            t.setItem(i, 0, QTableWidgetItem(tr["ticker"]))
            if snap:
                v = position_verdict(snap, tr,
                                     row["sell"].score if row else None)
                verdict_item = QTableWidgetItem(
                    f"{v['verdict']} \u2014 {v['headline']}")
                verdict_item.setForeground(QColor(colours[v["verdict"]]))
                tooltip = [v["headline"], manage_path(snap, tr)] \
                    + v["details"]
                if pnl is not None:
                    word = "up" if pnl >= 0 else "down"
                    tooltip.insert(0, f"You are {word} "
                                      f"\u00a3{abs(pnl):,.2f} on this.")
                tooltip.append(f"\u2014 {fmt_shares(tr['shares'])} shares, "
                               f"bought {fmt_gbp(tr['entry_px'])} each, "
                               f"opened {tr['opened_at']}")
                verdict_item.setToolTip("\n".join(tooltip))
            else:
                verdict_item = QTableWidgetItem(
                    "\u2014 no price data yet (update prices, or it isn't "
                    "priced in \u00a3)")
            t.setItem(i, 1, verdict_item)

            pnl_item = QTableWidgetItem(fmt_gbp(pnl))
            if pnl is not None:
                pnl_item.setForeground(QColor(GREEN if pnl >= 0 else RED))
            t.setItem(i, 2, pnl_item)
            worth = last * tr["shares"] if last is not None else None
            t.setItem(i, 3, QTableWidgetItem(fmt_gbp(worth)))
            stop_shown = None if tr["stop_px"] == tr["entry_px"] \
                else tr["stop_px"] * tr["shares"]
            t.setItem(i, 4, QTableWidgetItem(fmt_gbp(stop_shown)))

            btn = QPushButton("Close trade")
            btn.clicked.connect(
                lambda _=False, trade=tr, price=last: self._close(trade, price))
            t.setCellWidget(i, 5, btn)
        t.resizeColumnToContents(1)

    def _fill_watchlist(self) -> None:
        tickers = self.store.watchlist()
        t = self.watch_table
        t.setRowCount(len(tickers))
        for i, tk in enumerate(tickers):
            row = self._snap_lookup.get(tk)
            t.setItem(i, 0, QTableWidgetItem(tk))
            t.setItem(i, 1, QTableWidgetItem(
                row["name"] if row else self._name_lookup.get(tk, "\u2014")))
            t.setItem(i, 2, QTableWidgetItem(
                str(row["buy"].score) if row else "\u2014"))
            t.setItem(i, 3, QTableWidgetItem(
                str(row["sell"].score) if row else "\u2014"))
            t.setItem(i, 4, QTableWidgetItem(
                row["buy"].setup if row else "\u2014"))

    def set_universe(self, rows: list[dict]) -> None:
        self.universe_rows = rows

    def _record_existing(self) -> None:
        dlg = RecordTradeDialog(self.universe_rows, self.store, self)
        while dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                dlg.save(self.store)
            except ValueError as exc:
                QMessageBox.warning(self, "Record trade", str(exc))
                continue
            self._fill_positions()
            self.trades_changed.emit()
            break

    def _watch_opened(self, item: QTableWidgetItem) -> None:
        tk = self.watch_table.item(item.row(), 0)
        if tk:
            self.open_ticker.emit(tk.text())

    def _close(self, trade: dict, last_close: float | None) -> None:
        dlg = CloseTradeDialog(trade, last_close, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            exit_px, reason, lessons = dlg.values()
        except ValueError:
            QMessageBox.warning(self, "Close trade",
                                "Exit price must be a number in pounds.")
            return
        closed = journal.close_trade(self.store, trade["id"], exit_px=exit_px,
                                     exit_reason=reason, lessons=lessons)
        r = closed.get("r_multiple")
        QMessageBox.information(
            self, "Trade closed",
            f"{closed['ticker']}: P&L {fmt_gbp(closed['pnl_gbp'])}"
            + (f", {r:+.2f}R" if r is not None else ""))
        self._fill_positions()
        self.trades_changed.emit()
