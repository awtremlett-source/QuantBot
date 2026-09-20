"""Home: the first thing you see. Three numbered steps, big buttons, plain
words. Everything else in the app is reachable from here, in the order you
should use it."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QPushButton,
                               QVBoxLayout, QWidget)

from .finders import make_line_completer, stock_labels, ticker_from_label

from .theme import AMBER, GREEN, MUTED, RED

PLAIN_MARKET = {
    "GOOD": ("GOOD for buying", GREEN),
    "MIXED": ("MIXED \u2014 be picky", AMBER),
    "ROUGH": ("ROUGH \u2014 be careful", RED),
}


class HomeTab(QWidget):
    update_prices = Signal()
    see_ideas = Signal()
    see_trades = Signal()
    open_ticker = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 18)
        root.setSpacing(14)

        title = QLabel("Your daily routine \u2014 three steps, in order")
        title.setStyleSheet("font-size:20px; font-weight:bold;")
        root.addWidget(title)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("\U0001f50d Find any stock:"))
        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Type a name or ticker \u2014 e.g. gold, shell, GOOGL\u2026")
        self.search.returnPressed.connect(self._search_go)
        search_row.addWidget(self.search, stretch=1)
        root.addLayout(search_row)

        # Step 1 -- update prices
        self.refresh_btn = QPushButton("Update today's prices")
        self.refresh_btn.setObjectName("primary")
        self.refresh_btn.setMinimumHeight(36)
        self.refresh_btn.clicked.connect(self.update_prices.emit)
        self.refresh_status = QLabel("")
        row1, box1 = self._step(
            "1", "Update today's prices",
            "Once a day. Takes seconds after the first time.",
            self.refresh_btn, self.refresh_status)
        root.addWidget(box1)

        # Step 2 -- read the ideas
        ideas_btn = QPushButton("Open Today's Ideas")
        ideas_btn.setMinimumHeight(36)
        ideas_btn.clicked.connect(self.see_ideas.emit)
        self.ideas_status = QLabel("")
        _, box2 = self._step(
            "2", "Read today's ideas",
            "Green table = strongest stocks worth a look to buy. "
            "Red table = weakest \u2014 avoid, or think about selling if you "
            "own them. Hover any score to see exactly why.",
            ideas_btn, self.ideas_status)
        root.addWidget(box2)

        # Step 3 -- check your trades
        trades_btn = QPushButton("Open My Trades")
        trades_btn.setMinimumHeight(36)
        trades_btn.clicked.connect(self.see_trades.emit)
        self.trades_status = QLabel("")
        _, box3 = self._step(
            "3", "Check the trades you're in",
            "Warnings appear when a trade of yours looks like it should be "
            "closed. Practice money only \u2014 nothing real ever moves.",
            trades_btn, self.trades_status)
        root.addWidget(box3)

        # Market conditions
        market_box = QGroupBox("MARKET CONDITIONS TODAY")
        mv = QVBoxLayout(market_box)
        self.market_label = QLabel("Update prices to find out.")
        self.market_label.setStyleSheet("font-size:15px; font-weight:bold;")
        mv.addWidget(self.market_label)
        self.market_detail = QLabel("")
        self.market_detail.setObjectName("muted")
        self.market_detail.setWordWrap(True)
        mv.addWidget(self.market_detail)
        root.addWidget(market_box)

        # Quick glance lists
        glance = QHBoxLayout()
        self.buy_list = QListWidget()
        self.sell_list = QListWidget()
        for lst, heading in ((self.buy_list, "TOP 5 WORTH A LOOK"),
                             (self.sell_list, "TOP 5 TO AVOID / SELL")):
            box = QGroupBox(heading)
            v = QVBoxLayout(box)
            lst.itemDoubleClicked.connect(self._item_opened)
            v.addWidget(lst)
            glance.addWidget(box)
        root.addLayout(glance, stretch=1)

        tip = QLabel("Double-click any stock above to see its full story. "
                     "Stuck? Press the \"How to use\" button at the top.")
        tip.setObjectName("muted")
        root.addWidget(tip)

    def _step(self, number: str, heading: str, sub: str,
              button: QPushButton, status: QLabel):
        box = QGroupBox()
        row = QHBoxLayout(box)
        badge = QLabel(number)
        badge.setFixedWidth(34)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(f"font-size:22px; font-weight:bold; "
                            f"color:{AMBER};")
        row.addWidget(badge)
        text_col = QVBoxLayout()
        head = QLabel(heading)
        head.setStyleSheet("font-size:15px; font-weight:bold;")
        subl = QLabel(sub)
        subl.setObjectName("muted")
        subl.setWordWrap(True)
        text_col.addWidget(head)
        text_col.addWidget(subl)
        row.addLayout(text_col, stretch=1)
        status.setObjectName("muted")
        row.addWidget(status)
        row.addWidget(button)
        return row, box

    # ---------------- updates from the main window ----------------
    def set_refresh_status(self, done_today: bool, when: str | None) -> None:
        if done_today:
            self.refresh_status.setText("Done today \u2713")
            self.refresh_status.setStyleSheet(f"color:{GREEN}; "
                                              "font-weight:bold;")
        elif when:
            self.refresh_status.setText(f"Not done today (last: {when})")
            self.refresh_status.setStyleSheet(f"color:{AMBER};")
        else:
            self.refresh_status.setText("Never run \u2014 start here")
            self.refresh_status.setStyleSheet(f"color:{AMBER}; "
                                              "font-weight:bold;")

    def set_market(self, dial: dict, hiccups: dict | None = None) -> None:
        plain, colour = PLAIN_MARKET[dial["state"]]
        self.market_label.setText(f"{plain}  \u00b7  "
                                  f"{dial['score']}/100")
        self.market_label.setStyleSheet(
            f"font-size:15px; font-weight:bold; color:{colour};")
        lines = [dial["guidance"]] + [
            f"{c['glyph']} {c['name']}: {c['line']}"
            for c in dial["checks"]]
        if hiccups:
            for key, icon in (("large", "\U0001f534"), ("small", "\u26a0")):
                h = hiccups[key]
                if h["active"]:
                    lines.append(f"{icon} {h['headline']}")
                    lines += [f"    \u2022 {e}" for e in h["evidence"]]
        self.market_detail.setText("\n".join(lines))

    def set_ideas(self, rows: list[dict]) -> None:
        buys = sorted(rows, key=lambda r: r["buy"].score, reverse=True)[:5]
        sells = sorted(rows, key=lambda r: r["sell"].score, reverse=True)[:5]
        self._fill(self.buy_list, buys, "buy")
        self._fill(self.sell_list, sells, "sell")
        self.ideas_status.setText(f"{len(rows)} stocks scored today"
                                  if rows else "")

    def set_trades_summary(self, n_open: int, n_beware: int,
                           n_sell: int) -> None:
        if n_open == 0:
            self.trades_status.setText("No open trades yet")
            self.trades_status.setStyleSheet(f"color:{MUTED};")
        elif n_sell:
            self.trades_status.setText(
                f"{n_open} open \u00b7 \U0001f534 {n_sell} say SELL OUT")
            self.trades_status.setStyleSheet(f"color:{RED}; "
                                             "font-weight:bold;")
        elif n_beware:
            self.trades_status.setText(
                f"{n_open} open \u00b7 \u26a0 {n_beware} say beware")
            self.trades_status.setStyleSheet(f"color:{AMBER}; "
                                             "font-weight:bold;")
        else:
            self.trades_status.setText(
                f"{n_open} open \u00b7 all say HOLD")
            self.trades_status.setStyleSheet(f"color:{GREEN};")

    def _fill(self, lst: QListWidget, rows: list[dict], side: str) -> None:
        lst.clear()
        for r in rows:
            res = r[side]
            if res.score <= 0:
                continue
            item = QListWidgetItem(
                f"{r['ticker']:<8} {r['name'][:26]:<27} "
                f"score {res.score:>3}   {res.setup}")
            item.setData(Qt.ItemDataRole.UserRole, r["ticker"])
            item.setToolTip("\n".join(res.reasons))
            lst.addItem(item)
        if lst.count() == 0:
            placeholder = QListWidgetItem(
                "Nothing here yet \u2014 update prices first.")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            lst.addItem(placeholder)

    def set_universe(self, rows: list[dict]) -> None:
        self._tickers = {r["ticker"] for r in rows}
        completer = make_line_completer(stock_labels(rows))
        completer.activated.connect(self._search_picked)
        self.search.setCompleter(completer)

    def _search_picked(self, label: str) -> None:
        self.search.clear()
        self.open_ticker.emit(ticker_from_label(label))

    def _search_go(self) -> None:
        ticker = ticker_from_label(self.search.text())
        if ticker in getattr(self, "_tickers", set()):
            self.search.clear()
            self.open_ticker.emit(ticker)

    def _item_opened(self, item: QListWidgetItem) -> None:
        ticker = item.data(Qt.ItemDataRole.UserRole)
        if ticker:
            self.open_ticker.emit(ticker)
