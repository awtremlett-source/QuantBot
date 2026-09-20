"""Add stock: search Yahoo Finance by company name or ticker, add the pick
to your universe, and download its history on the spot. One polite network
call per action -- never in a loop."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (QApplication, QDialog, QDialogButtonBox,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMessageBox, QPushButton,
                               QVBoxLayout)

from manual.scout.universe import UniverseError, append_ticker


class AddStockDialog(QDialog):
    """On success, self.added holds the new universe row (already appended
    to the CSV and with history cached)."""

    def __init__(self, store, provider, cfg, existing: set[str], parent=None):
        super().__init__(parent)
        self.store = store
        self.provider = provider
        self.cfg = cfg
        self.existing = existing
        self.added: dict | None = None

        self.setWindowTitle("Add a stock, ETF or fund")
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(
            "Type a company or fund name (e.g. \"gold\", \"alphabet\") or an "
            "exact ticker (e.g. SGLN.L, GOOGL), then press Search."))
        row = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setPlaceholderText("Name or ticker\u2026")
        self.query.returnPressed.connect(self._search)
        row.addWidget(self.query, stretch=1)
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._search)
        row.addWidget(search_btn)
        lay.addLayout(row)

        self.results = QListWidget()
        self.results.itemDoubleClicked.connect(lambda _: self._add())
        lay.addWidget(self.results, stretch=1)
        self.status = QLabel("")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)

        buttons = QDialogButtonBox()
        self.add_btn = buttons.addButton(
            "Add selected", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(QDialogButtonBox.StandardButton.Close)
        self.add_btn.clicked.connect(self._add)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    # ---------------- search ----------------
    def _search(self) -> None:
        q = self.query.text().strip()
        if not q:
            return
        self.results.clear()
        self.status.setText("Searching Yahoo Finance\u2026")
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            matches = self._yahoo_search(q)
        finally:
            QApplication.restoreOverrideCursor()
        if not matches:
            self.status.setText(
                "Nothing found. Check the spelling, or type the exact "
                "Yahoo ticker (London ones end in .L). If your internet is "
                "down, searching can't work.")
            return
        for m in matches:
            note = " \u00b7 already in your universe" \
                if m["symbol"] in self.existing else ""
            item = QListWidgetItem(
                f"{m['symbol']:<10} {m['name'][:44]:<45} "
                f"{m.get('exchange','')}{note}")
            item.setData(Qt.ItemDataRole.UserRole, m)
            if m["symbol"] in self.existing:
                item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.results.addItem(item)
        self.status.setText("Pick one and press Add selected "
                            "(or double-click it).")

    @staticmethod
    def _yahoo_search(q: str) -> list[dict]:
        import yfinance as yf
        out, seen = [], set()
        try:  # name search (best effort -- API shape varies by version)
            quotes = yf.Search(q, max_results=8).quotes or []
            for item in quotes:
                sym = (item.get("symbol") or "").upper()
                if not sym or sym in seen:
                    continue
                seen.add(sym)
                out.append({
                    "symbol": sym,
                    "name": item.get("shortname") or item.get("longname")
                    or sym,
                    "exchange": item.get("exchDisp")
                    or item.get("exchange") or "",
                })
        except Exception:
            pass
        candidate = q.upper()
        if candidate not in seen and (" " not in candidate):
            try:  # exact-ticker probe so SGLN.L works even if Search fails
                fi = yf.Ticker(candidate).fast_info
                if getattr(fi, "last_price", None) is not None:
                    out.insert(0, {"symbol": candidate, "name": candidate,
                                   "exchange": ""})
            except Exception:
                pass
        return out

    # ---------------- add ----------------
    def _add(self) -> None:
        item = self.results.currentItem()
        if item is None or not item.data(Qt.ItemDataRole.UserRole):
            self.status.setText("Select a result first.")
            return
        m = item.data(Qt.ItemDataRole.UserRole)
        sym = m["symbol"]
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            import yfinance as yf
            fi = yf.Ticker(sym).fast_info
            currency = getattr(fi, "currency", None) or "GBp"
            entry = {"ticker": sym, "name": m["name"],
                     "index": "Added", "sector": "Added",
                     "currency": currency,
                     "stamp_duty": "Y" if sym.endswith(".L") else "N"}
            append_ticker(entry)
            frames = self.provider.fetch_daily(
                [sym], period=self.cfg.history_period)
            df = frames.get(sym)
            if df is not None and not df.empty:
                self.store.upsert_prices(sym, df)
        except UniverseError as exc:
            QApplication.restoreOverrideCursor()
            QMessageBox.information(self, "Add stock", str(exc))
            return
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Add stock",
                                f"Couldn't add {sym}: {exc}")
            return
        QApplication.restoreOverrideCursor()
        self.added = entry
        bars = self.store.bar_count(sym)
        extra = "" if currency in ("GBp", "GBP") else (
            "\n\nNote: it isn't priced in pounds, so the app can't size a "
            "position or show \u00a3 profit for it \u2014 charts, scores and "
            "warnings still work.")
        QMessageBox.information(
            self, "Added",
            f"{sym} added to your universe with {bars} days of history."
            f"{extra}")
        self.accept()
