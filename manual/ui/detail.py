"""Stock Detail: the pre-trade page. Chart on the left; on the right the
scores with every reason, the risk box in pounds, a five-point checklist and
the Log paper trade button. Logging requires a written thesis -- the journal
is the point of the whole app."""
from __future__ import annotations

import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
import mplfinance as mpf
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QGroupBox, QHBoxLayout,
                               QLabel, QMessageBox, QPushButton, QScrollArea,
                               QTextEdit, QVBoxLayout, QWidget)

from manual.scout import journal, risk
from manual.scout.ladder import ladder_state
from manual.scout.playbook import manage_path, recommend_new, with_money_split
from manual.scout.indicators import snapshot
from manual.scout.scoring import buy_score, sell_score
from .finders import make_searchable, stock_labels, ticker_from_label
from .theme import (AMBER, BG, BORDER, GREEN, MUTED, PANEL, RED, TEXT,
                    fmt_gbp, fmt_num, fmt_px, fmt_shares)

CHECKLIST = [
    "Market regime supports new longs",
    "Buy score \u2265 60 with a named setup",
    "Stop level and share count accepted",
    "Checked news / earnings date \u2014 no landmine",
    "Not chasing a large gap",
]

_MC = mpf.make_marketcolors(up=GREEN, down=RED, edge="inherit",
                            wick="inherit", volume="in")
_STYLE = mpf.make_mpf_style(
    marketcolors=_MC, facecolor=BG, figcolor=BG, edgecolor=BORDER,
    gridcolor="#21262d", gridstyle=":",
    rc={"axes.labelcolor": MUTED, "xtick.color": MUTED,
        "ytick.color": MUTED, "text.color": TEXT, "font.size": 8})


class DetailTab(QWidget):
    trade_logged = Signal()

    def __init__(self, store, cfg, universe_rows, parent=None):
        super().__init__(parent)
        self.store = store
        self.cfg = cfg
        self.universe_rows = universe_rows
        self._canvas: FigureCanvasQTAgg | None = None
        self._current: dict | None = None  # {ticker, snap, buy, plan, urow}
        self._dial_state: str = "MIXED"
        self._hiccups: dict | None = None
        self._live_line: str = ""

        root = QHBoxLayout(self)

        left = QVBoxLayout()
        picker_row = QHBoxLayout()
        picker_row.addWidget(QLabel("Find a stock"))
        self.picker = QComboBox()
        self.picker.setMinimumWidth(340)
        make_searchable(self.picker)
        self._label_by_ticker: dict[str, str] = {}
        self.picker.activated.connect(
            lambda _i: self._picker_changed(self.picker.currentText()))
        self.picker.currentTextChanged.connect(self._picker_changed)
        picker_row.addWidget(self.picker)
        picker_row.addStretch()
        left.addLayout(picker_row)
        self.chart_holder = QVBoxLayout()
        left.addLayout(self.chart_holder, stretch=1)
        root.addLayout(left, stretch=3)

        panel = QWidget()
        pv = QVBoxLayout(panel)
        self.title = QLabel("Pick a ticker")
        self.title.setStyleSheet("font-size:16px; font-weight:bold;")
        pv.addWidget(self.title)
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("muted")
        pv.addWidget(self.subtitle)

        self.buy_box = QGroupBox("SHOULD YOU BUY IT? (SCORE OUT OF 100)")
        self.buy_label = QLabel("\u2014")
        self.buy_label.setWordWrap(True)
        QVBoxLayout(self.buy_box).addWidget(self.buy_label)
        pv.addWidget(self.buy_box)

        self.sell_box = QGroupBox("SHOULD YOU AVOID OR SELL IT? (SCORE OUT OF 100)")
        self.sell_label = QLabel("\u2014")
        self.sell_label.setWordWrap(True)
        QVBoxLayout(self.sell_box).addWidget(self.sell_label)
        pv.addWidget(self.sell_box)

        self.risk_box = QGroupBox("IF YOU BOUGHT TODAY \u2014 SIZE, STOP AND COSTS")
        self.risk_label = QLabel("\u2014")
        self.risk_label.setWordWrap(True)
        QVBoxLayout(self.risk_box).addWidget(self.risk_label)
        pv.addWidget(self.risk_box)

        self.path_box = QGroupBox("RECOMMENDED PATH")
        self.path_label = QLabel("\u2014")
        self.path_label.setWordWrap(True)
        QVBoxLayout(self.path_box).addWidget(self.path_label)
        pv.addWidget(self.path_box)

        check_box = QGroupBox("BEFORE YOU LOG IT \u2014 QUICK CHECKLIST")
        cb_lay = QVBoxLayout(check_box)
        self.checks: list[QCheckBox] = []
        for text in CHECKLIST:
            cb = QCheckBox(text)
            self.checks.append(cb)
            cb_lay.addWidget(cb)
        pv.addWidget(check_box)

        pv.addWidget(QLabel("In your own words \u2014 why this trade? (required)"))
        self.thesis = QTextEdit()
        self.thesis.setPlaceholderText(
            "One or two honest sentences. Required before logging.")
        self.thesis.setFixedHeight(70)
        pv.addWidget(self.thesis)

        self.log_btn = QPushButton("Log paper trade")
        self.log_btn.setObjectName("primary")
        self.log_btn.clicked.connect(self._log_trade)
        pv.addWidget(self.log_btn)
        pv.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(panel)
        scroll.setMinimumWidth(360)
        root.addWidget(scroll, stretch=2)

    # ---------------- population ----------------
    def set_universe(self, rows: list[dict]) -> None:
        self.universe_rows = rows
        labels = stock_labels(rows)
        self._label_by_ticker = {r["ticker"]: lab
                                 for r, lab in zip(rows, labels)}
        current = self.picker.currentText()
        self.picker.blockSignals(True)
        self.picker.clear()
        self.picker.addItems(labels)
        if current in labels:
            self.picker.setCurrentText(current)
        self.picker.blockSignals(False)

    def show_ticker(self, ticker: str) -> None:
        label = self._label_by_ticker.get(ticker, ticker)
        if self.picker.currentText() != label:
            self.picker.blockSignals(True)
            self.picker.setCurrentText(label)
            self.picker.blockSignals(False)
        self._render(ticker)

    def _picker_changed(self, text: str) -> None:
        if not text:
            return
        ticker = ticker_from_label(text)
        if ticker in self._label_by_ticker:
            self._render(ticker)

    def set_environment(self, dial_state: str, hiccups: dict | None) -> None:
        self._dial_state = dial_state
        self._hiccups = hiccups
        if self._current:
            self._render(self._current["ticker"])

    def apply_live(self, quotes: dict[str, float]) -> None:
        cur = self._current
        if not cur or cur["ticker"] not in quotes:
            return
        from datetime import datetime
        px = quotes[cur["ticker"]]
        self._live_line = (f"  \u00b7  \u25cf LIVE "
                           f"{datetime.now().strftime('%H:%M')}: "
                           f"{fmt_px(px, cur['snap']['currency'])}")
        base = self.subtitle.text().split("  \u00b7  \u25cf LIVE")[0]
        self.subtitle.setText(base + self._live_line)

    # ---------------- rendering ----------------
    def _render(self, ticker: str) -> None:
        df = self.store.get_prices(ticker)
        urow = next((u for u in self.universe_rows if u["ticker"] == ticker),
                    {"ticker": ticker, "name": ticker, "sector": "",
                     "currency": "GBp", "stamp_duty": "Y"})
        snap = snapshot(df, urow.get("currency", "GBp"))
        if snap is None:
            self.title.setText(ticker)
            self.subtitle.setText("Not enough history cached to score "
                                  "(needs ~220 daily bars).")
            self._current = None
            return

        buy = buy_score(snap, self.cfg)
        sell = sell_score(snap, self.cfg)
        ladder = ladder_state(self.store, self.cfg)
        plan = risk.plan(snap, self.cfg, urow.get("stamp_duty", "Y"),
                         max_value_gbp=ladder["next_cap"])
        self._ladder = ladder
        self._current = {"ticker": ticker, "snap": snap, "buy": buy,
                         "plan": plan, "urow": urow}

        self.title.setText(f"{urow['name']}  ({ticker})")
        self.subtitle.setText(
            f"{urow.get('sector','')}  \u00b7  {urow.get('index','')}  \u00b7  "
            f"Last {fmt_px(snap['close'], snap['currency'])}  \u00b7  "
            f"RSI {fmt_num(snap['rsi'],0)}  \u00b7  "
            f"ATR {fmt_num(snap['atr_pct'],1)}%")

        self.buy_label.setText(self._score_text(buy, GREEN))
        self.buy_label.setToolTip("\n".join(buy.reasons))
        self.sell_label.setText(self._score_text(sell, RED))
        self.sell_label.setToolTip("\n".join(sell.reasons))
        self.risk_label.setText(self._risk_text(plan))
        self.path_label.setText(self._path_text(snap, buy, sell, plan,
                                                ticker))
        self._draw_chart(df, ticker)

    def _score_text(self, res, colour: str) -> str:
        lines = [f"<span style='color:{colour}; font-size:20px; "
                 f"font-weight:bold'>{res.score}</span>"
                 f"<span style='color:{MUTED}'> /100 \u00b7 {res.setup}</span>"]
        lines += [f"<div style='color:{TEXT}'>\u2022 "
                  f"{r.split('\u00b7 ', 1)[-1]}</div>"
                  for r in res.reasons[:4]]
        extra = len(res.reasons) - 4
        if extra > 0:
            lines.append(f"<div style='color:{MUTED}'>\u2026and {extra} "
                         f"more \u2014 hover for the full breakdown.</div>")
        if not res.reasons:
            lines.append(f"<div style='color:{MUTED}'>No points scored.</div>")
        return "".join(lines)

    def _path_text(self, snap, buy, sell, plan, ticker) -> str:
        open_here = [t for t in self.store.list_trades(open_only=True)
                     if t["ticker"] == ticker]
        if open_here:
            line = manage_path(snap, open_here[0])
            return (f"<b style='color:{AMBER}'>You hold this.</b> "
                    f"<div>{line}</div>")
        rec = with_money_split(
            recommend_new(snap, buy, sell, plan,
                          self._dial_state, self._hiccups),
            getattr(self, "_ladder", None), plan)
        colour = GREEN if rec["tradeable"] else MUTED
        html = [f"<b style='color:{colour}; font-size:14px'>"
                f"{rec['play']}</b>",
                f"<div style='color:{MUTED}'>{rec['why']}</div>"]
        for n, (label, text) in enumerate(rec["steps"], start=1):
            html.append(f"<div><b>{n}. {label}:</b> {text}</div>")
        return "".join(html)

    def _risk_text(self, plan: dict) -> str:
        if not plan.get("ok"):
            return f"<span style='color:{AMBER}'>{plan.get('why','')}</span>"
        rows = [
            ("Buy at", fmt_gbp(plan["entry_gbp"])),
            ("Sell alert", fmt_gbp(plan["stop_gbp"])),
            ("Shares", fmt_shares(plan["shares"])),
            ("Cash at risk", fmt_gbp(plan["risk_gbp"])),
        ]
        html = "".join(
            f"<div><span style='color:{MUTED}'>{k}:</span> {v}</div>"
            for k, v in rows)
        for w in plan.get("warnings", []):
            html += f"<div style='color:{AMBER}'>\u26a0 {w}</div>"
        html += (f"<div style='color:{MUTED}'>Hover for costs and "
                 f"details.</div>")
        self.risk_label.setToolTip(
            f"Position value: {fmt_gbp(plan['value_gbp'])}\n"
            f"Risk per share: {fmt_gbp(plan['risk_per_share_gbp'])}\n"
            f"Stamp duty: {fmt_gbp(plan['stamp_gbp'])}\n"
            f"PTM levy: {fmt_gbp(plan['ptm_gbp'])}\n"
            f"Breakeven move: {plan['breakeven_pct']:.2f}%\n"
            f"% of bankroll: {plan['pct_bankroll']:.1f}%")
        return html

    def _draw_chart(self, df, ticker: str) -> None:
        while self.chart_holder.count():
            item = self.chart_holder.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        if self._canvas is not None:
            plt.close(self._canvas.figure)
            self._canvas = None
        plot_df = df.tail(130).rename(columns={
            "open": "Open", "high": "High", "low": "Low",
            "close": "Close", "volume": "Volume"})
        fig, _ = mpf.plot(plot_df, type="candle", mav=(20, 50),
                          volume=True, style=_STYLE, returnfig=True,
                          figsize=(7.2, 5.2), tight_layout=True,
                          datetime_format="%b %y", xrotation=0)
        self._canvas = FigureCanvasQTAgg(fig)
        self.chart_holder.addWidget(self._canvas)

    # ---------------- trade logging ----------------
    def _log_trade(self) -> None:
        cur = self._current
        if not cur:
            QMessageBox.information(self, "Log paper trade",
                                    "Pick a ticker with enough history first.")
            return
        plan = cur["plan"]
        if not plan.get("ok"):
            QMessageBox.warning(self, "Log paper trade",
                                f"Cannot size this trade: {plan.get('why')}")
            return
        thesis = self.thesis.toPlainText().strip()
        if not thesis:
            QMessageBox.warning(self, "Log paper trade",
                                "Write the thesis first \u2014 that's the "
                                "discipline this app exists for.")
            return
        unchecked = [c.text() for c in self.checks if not c.isChecked()]
        if unchecked:
            resp = QMessageBox.question(
                self, "Checklist incomplete",
                "Unticked:\n\u2022 " + "\n\u2022 ".join(unchecked)
                + "\n\nLog the paper trade anyway?")
            if resp != QMessageBox.StandardButton.Yes:
                return
        checklist = {c.text(): c.isChecked() for c in self.checks}
        journal.open_trade(
            self.store, ticker=cur["ticker"], name=cur["urow"]["name"],
            entry_px=plan["entry_gbp"], stop_px=plan["stop_gbp"],
            shares=plan["shares"], risk_gbp=plan["risk_gbp"],
            open_costs_gbp=plan["costs_gbp"],
            setup_type=cur["buy"].setup, thesis=thesis, checklist=checklist)
        self.thesis.clear()
        for c in self.checks:
            c.setChecked(False)
        QMessageBox.information(
            self, "Logged",
            f"Paper trade logged: {fmt_shares(plan['shares'])} \u00d7 {cur['ticker']} "
            f"at {fmt_gbp(plan['entry_gbp'])}, stop {fmt_gbp(plan['stop_gbp'])}.")
        self.trade_logged.emit()
