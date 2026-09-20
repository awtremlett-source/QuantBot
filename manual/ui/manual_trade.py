"""Record a trade you already have -- the three-field version.

You type what your broker shows: how many shares, and the total pounds you
paid. The app does every per-share sum silently, and suggests a sell alert
sized to the stock's own recent movement (2x its average daily range below
today's price). Change the suggestion or blank it -- your call.
"""
from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox,
                               QFormLayout, QLabel, QLineEdit, QTextEdit)

from manual.scout import journal
from manual.scout.indicators import snapshot
from .finders import make_searchable, stock_labels, ticker_from_label
from .theme import AMBER, GREEN, MUTED


class RecordTradeDialog(QDialog):
    def __init__(self, universe_rows: list[dict], store=None, parent=None):
        super().__init__(parent)
        self.universe_rows = universe_rows
        self.store = store
        self._snap_cache: dict[str, dict | None] = {}
        self._alert_user_edited = False

        self.setWindowTitle("Record a trade I already have")
        self.setMinimumWidth(500)
        form = QFormLayout(self)

        self.stock = QComboBox()
        self.stock.addItems(stock_labels(universe_rows))
        make_searchable(self.stock)
        self.stock.currentTextChanged.connect(lambda _t: self._recalc())
        form.addRow("Stock (type to search)", self.stock)

        self.shares = QLineEdit()
        self.shares.setPlaceholderText("Copy from your broker \u2014 e.g. 1.64")
        self.shares.textEdited.connect(lambda _t: self._recalc())
        form.addRow("Number of shares", self.shares)

        self.total_paid = QLineEdit()
        self.total_paid.setPlaceholderText("e.g. 103.10")
        self.total_paid.textEdited.connect(lambda _t: self._recalc())
        form.addRow("Total paid (\u00a3)", self.total_paid)

        self.alert = QLineEdit()
        self.alert.setPlaceholderText(
            "Suggested automatically \u2014 or blank for none")
        self.alert.textEdited.connect(self._alert_edited)
        form.addRow("Sell alert \u2014 warn me if my holding "
                    "falls to (\u00a3)", self.alert)

        self.info = QLabel("")
        self.info.setWordWrap(True)
        self.info.setStyleSheet(f"color:{MUTED};")
        form.addRow(self.info)

        self.note = QTextEdit()
        self.note.setPlaceholderText("Optional \u2014 why you own it")
        self.note.setFixedHeight(52)
        form.addRow("Note", self.note)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    # ---------------- background maths ----------------
    def _num(self, widget) -> float | None:
        text = widget.text().strip().replace(",", "").replace("\u00a3", "")
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    def _row(self) -> dict | None:
        ticker = ticker_from_label(self.stock.currentText())
        return next((r for r in self.universe_rows
                     if r["ticker"] == ticker), None)

    def _snap(self) -> dict | None:
        row = self._row()
        if row is None or self.store is None:
            return None
        t = row["ticker"]
        if t not in self._snap_cache:
            df = self.store.get_prices(t)
            self._snap_cache[t] = snapshot(df, row.get("currency", "GBp")) \
                if not df.empty else None
        return self._snap_cache[t]

    def _alert_edited(self, _text: str) -> None:
        self._alert_user_edited = True
        self._recalc()

    def _recalc(self) -> None:
        shares = self._num(self.shares)
        snap = self._snap()
        lines, colour = [], MUTED

        # suggest an alert sized to the stock's own movement
        suggestion = None
        if (snap and shares and shares > 0
                and snap.get("close_gbp") and snap.get("atr_gbp")):
            per_share = max(0.01,
                            snap["close_gbp"] - 2.0 * snap["atr_gbp"])
            suggestion = per_share * shares
            if not self._alert_user_edited:
                self.alert.blockSignals(True)
                self.alert.setText(f"{suggestion:.2f}")
                self.alert.blockSignals(False)

        if snap and shares and snap.get("close_gbp"):
            value_now = snap["close_gbp"] * shares
            lines.append(f"Worth about \u00a3{value_now:,.2f} today.")
            alert = self._num(self.alert)
            if alert is not None and alert >= value_now:
                lines.append("\u26a0 That alert is at or above today's "
                             "value \u2014 it would go off immediately.")
                colour = AMBER
            elif alert is not None:
                drop = (1 - alert / value_now) * 100
                lines.append(f"Alert set {drop:.0f}% below today \u2014 "
                             "room for normal wobble, out if it truly "
                             "turns.")
                colour = GREEN
        elif snap is None and self._row() is not None and self.store:
            lines.append("No price history yet \u2014 update prices on "
                         "Home first, or this one isn't priced in pounds "
                         "(alerts unavailable for it, everything else "
                         "still works).")
        self.info.setText(" ".join(lines))
        self.info.setStyleSheet(f"color:{colour};")

    # ---------------- values / save ----------------
    def values(self) -> dict:
        """Raises ValueError with a friendly message if inputs don't parse."""
        row = self._row()
        if row is None:
            raise ValueError("Pick a stock from the list (type to search).")
        shares = self._num(self.shares)
        if shares is None or shares <= 0:
            raise ValueError("Number of shares must be a number above zero, "
                             "like 12 or 1.64 \u2014 copy it from your "
                             "broker.")
        total = self._num(self.total_paid)
        if total is None or total <= 0:
            raise ValueError("Total paid must be a number in pounds, "
                             "like 103.10 \u2014 the total your broker "
                             "shows you paid.")
        entry = total / shares
        stop = None
        if self.alert.text().strip():
            alert_value = self._num(self.alert)
            if alert_value is None or alert_value <= 0:
                raise ValueError("The sell alert must be a number in "
                                 "pounds, or left blank.")
            stop = alert_value / shares
        return {"ticker": row["ticker"], "name": row["name"],
                "shares": shares, "entry": entry, "stop": stop,
                "note": self.note.toPlainText().strip()}

    def save(self, store) -> int:
        v = self.values()
        stop = v["stop"] if v["stop"] is not None else v["entry"]
        risk = max(0.0, v["shares"] * (v["entry"] - stop))
        return journal.open_trade(
            store, ticker=v["ticker"], name=v["name"], entry_px=v["entry"],
            stop_px=stop, shares=v["shares"], risk_gbp=risk,
            open_costs_gbp=0.0, setup_type="Manual",
            thesis=v["note"] or "Existing holding recorded manually",
            checklist={})
