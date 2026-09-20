"""Main window. The exchange-status strip at the top is the app's signature:
regime, guidance, last refresh. Network work (refresh) and scoring (scan)
both run on worker threads so the desk never freezes."""
from __future__ import annotations

from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMainWindow, QMessageBox,
                               QProgressBar, QPushButton, QTabWidget,
                               QVBoxLayout, QWidget)

from manual.scout.hiccups import hiccup_scan
from manual.scout.live import (YFinanceLiveProvider, is_market_open,
                        tickers_of_interest)
from manual.scout.timing import EXTRA_TICKERS, timing_dial
from manual.scout.picks import record_board
from manual.scout.data import RefreshService, YFinanceProvider
from manual.scout.scan import position_verdict, scan_universe
from manual.scout.universe import INDEX_TICKERS, load_universe, universe_tickers
from .board import BoardTab
from .add_stock import AddStockDialog
from .bot_tab import BotTab
from .detail import DetailTab
from .home import HomeTab
from .journal_view import JournalTab
from .picks_view import PicksTab
from .positions import PositionsTab
from .results import ResultsTab
from .spotlight_view import SpotlightTab
from .theme import BORDER, PANEL


class RefreshWorker(QThread):
    progress = Signal(int, int, str)
    done = Signal(list)
    failed = Signal(str)

    def __init__(self, service: RefreshService, tickers: list[str],
                 force: bool):
        super().__init__()
        self.service = service
        self.tickers = tickers
        self.force = force

    def run(self):
        try:
            issues = self.service.refresh(
                self.tickers, force=self.force,
                progress_cb=lambda n, t, m: self.progress.emit(n, t, m))
            self.done.emit(issues)
        except Exception as exc:  # keep the UI alive whatever happens
            self.failed.emit(str(exc))


class LiveWorker(QThread):
    done = Signal(dict)

    def __init__(self, provider, tickers):
        super().__init__()
        self.provider = provider
        self.tickers = tickers

    def run(self):
        try:
            self.done.emit(self.provider.fetch_last(self.tickers))
        except Exception:
            self.done.emit({})


class ScanWorker(QThread):
    done = Signal(list)

    def __init__(self, store, universe_rows, cfg):
        super().__init__()
        self.store = store
        self.universe_rows = universe_rows
        self.cfg = cfg

    def run(self):
        self.done.emit(scan_universe(self.store, self.universe_rows, self.cfg))


class MainWindow(QMainWindow):
    def __init__(self, store, cfg, universe_rows,
                 provider: YFinanceProvider | None = None):
        super().__init__()
        self.store = store
        self.cfg = cfg
        self.universe_rows = universe_rows
        self.provider = provider or YFinanceProvider()
        self.refresh_service = RefreshService(store, self.provider, cfg)
        self._refresh_worker: RefreshWorker | None = None
        self._scan_worker: ScanWorker | None = None
        self._live_worker: LiveWorker | None = None
        self._rows: list[dict] = []
        self._live: dict[str, float] = {}
        self._live_provider = YFinanceLiveProvider()

        self.setWindowTitle("TradeScout \u2014 LSE paper-trading guide")
        self.resize(1280, 800)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        strip = QWidget()
        strip.setStyleSheet(f"background:{PANEL}; "
                            f"border-bottom:1px solid {BORDER};")
        srow = QHBoxLayout(strip)
        self.banner = QLabel("TRADESCOUT")
        self.banner.setObjectName("banner")
        srow.addWidget(self.banner)
        self.guidance = QLabel("")
        self.guidance.setObjectName("muted")
        srow.addWidget(self.guidance)
        srow.addStretch()
        self.last_refresh = QLabel("")
        self.last_refresh.setObjectName("muted")
        self.live_label = QLabel("")
        self.live_label.setObjectName("muted")
        srow.addWidget(self.live_label)
        srow.addWidget(self.last_refresh)
        self.refresh_btn = QPushButton("Update prices")
        self.refresh_btn.clicked.connect(lambda: self.start_refresh(False))
        srow.addWidget(self.refresh_btn)
        self.force_btn = QPushButton("Force")
        self.force_btn.setToolTip("Refresh again even if already refreshed "
                                  "today")
        self.force_btn.clicked.connect(lambda: self.start_refresh(True))
        srow.addWidget(self.force_btn)
        self.add_btn = QPushButton("Add stock\u2026")
        self.add_btn.clicked.connect(self._add_stock)
        srow.addWidget(self.add_btn)
        self.help_btn = QPushButton("How to use")
        self.help_btn.clicked.connect(self._show_help)
        srow.addWidget(self.help_btn)
        root.addWidget(strip)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setFixedHeight(14)
        root.addWidget(self.progress)

        self.tabs = QTabWidget()
        self.home_tab = HomeTab()
        self.board_tab = BoardTab()
        self.detail_tab = DetailTab(store, cfg, universe_rows)
        self.positions_tab = PositionsTab(store, cfg)
        self.picks_tab = PicksTab(store)
        self.journal_tab = JournalTab(store)
        self.results_tab = ResultsTab(self.journal_tab, self.picks_tab)
        self.tabs.addTab(self.home_tab, "🏠 Home")
        self.spotlight_tab = SpotlightTab()
        self.tabs.addTab(self.board_tab, "💡 Today's Ideas")
        self.tabs.addTab(self.spotlight_tab, "⭐ Spotlight")
        self.tabs.addTab(self.detail_tab, "🔍 Stock Detail")
        self.tabs.addTab(self.positions_tab, "💼 My Trades")
        self.tabs.addTab(self.results_tab, "📊 Results")
        # The bot's own tab: read-only figures + the governance buttons that
        # already exist headlessly. It comes last -- this app is the operator's
        # own trading; the bot is something they check on.
        self.bot_tab = BotTab()
        self.tabs.addTab(self.bot_tab, "🤖 Bot")
        root.addWidget(self.tabs, stretch=1)

        self.footer = QLabel("Guide only \u00b7 paper trading \u00b7 "
                             "not financial advice")
        self.footer.setObjectName("muted")
        self.footer.setStyleSheet(f"padding:4px 10px; background:{PANEL}; "
                                  f"border-top:1px solid {BORDER};")
        root.addWidget(self.footer)
        self.setCentralWidget(central)

        self.home_tab.update_prices.connect(
            lambda: self.start_refresh(False))
        self.home_tab.see_ideas.connect(
            lambda: self.tabs.setCurrentWidget(self.board_tab))
        self.home_tab.see_trades.connect(
            lambda: self.tabs.setCurrentWidget(self.positions_tab))
        self.home_tab.open_ticker.connect(self._open_detail)
        self.board_tab.open_ticker.connect(self._open_detail)
        self.board_tab.watch_changed.connect(self._watch_changed)
        self.spotlight_tab.open_ticker.connect(self._open_detail)
        self.spotlight_tab.watch_changed.connect(self._watch_changed)
        self.journal_tab.trades_changed.connect(
            lambda: self.positions_tab.refresh(self._rows, self._live))
        self.positions_tab.open_ticker.connect(self._open_detail)
        self.picks_tab.open_ticker.connect(self._open_detail)
        self.positions_tab.trades_changed.connect(self.journal_tab.refresh)
        self.detail_tab.trade_logged.connect(self._after_trade_logged)

        self.detail_tab.set_universe(universe_rows)
        self.home_tab.set_universe(universe_rows)
        self.positions_tab.set_universe(universe_rows)
        self.journal_tab.refresh()
        self.picks_tab.refresh()
        self._update_banner()
        self.start_scan()
        self._live_timer = QTimer(self)
        self._live_timer.setInterval(
            max(1, int(cfg.live_interval_min)) * 60_000)
        self._live_timer.timeout.connect(self._live_tick)
        self._live_timer.start()
        QTimer.singleShot(4000, self._live_tick)

    # ---------------- refresh ----------------
    def start_refresh(self, force: bool) -> None:
        if self._refresh_worker and self._refresh_worker.isRunning():
            return
        tickers = universe_tickers(self.universe_rows) \
            + list(INDEX_TICKERS) + EXTRA_TICKERS
        self.refresh_btn.setEnabled(False)
        self.force_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self._refresh_worker = RefreshWorker(self.refresh_service, tickers,
                                             force)
        self._refresh_worker.progress.connect(self._refresh_progress)
        self._refresh_worker.done.connect(self._refresh_done)
        self._refresh_worker.failed.connect(self._refresh_failed)
        self._refresh_worker.start()

    def _refresh_progress(self, n: int, total: int, msg: str) -> None:
        self.progress.setRange(0, total)
        self.progress.setValue(n)
        self.footer.setText(msg)

    def _refresh_done(self, issues: list) -> None:
        self.progress.setVisible(False)
        self.refresh_btn.setEnabled(True)
        self.force_btn.setEnabled(True)
        if issues:
            shown = " | ".join(issues[:4])
            more = f" (+{len(issues)-4} more)" if len(issues) > 4 else ""
            self.footer.setText(f"Data issues: {shown}{more}")
        else:
            self.footer.setText("Refresh complete \u2014 cache is current.")
        self._update_banner()
        self.start_scan()
        self._live_timer = QTimer(self)
        self._live_timer.setInterval(
            max(1, int(self.cfg.live_interval_min)) * 60_000)
        self._live_timer.timeout.connect(self._live_tick)
        self._live_timer.start()
        QTimer.singleShot(4000, self._live_tick)

    def _refresh_failed(self, err: str) -> None:
        self.progress.setVisible(False)
        self.refresh_btn.setEnabled(True)
        self.force_btn.setEnabled(True)
        QMessageBox.warning(self, "Refresh failed", err)

    # ---------------- scan ----------------
    def start_scan(self) -> None:
        if self._scan_worker and self._scan_worker.isRunning():
            return
        self._scan_worker = ScanWorker(self.store, self.universe_rows,
                                       self.cfg)
        self._scan_worker.done.connect(self._scan_done)
        self._scan_worker.start()

    def _scan_done(self, rows: list) -> None:
        self._rows = rows
        watching = set(self.store.watchlist())
        self.board_tab.populate(rows, self.cfg.top_n, watching)
        self.spotlight_tab.refresh(rows, watching)
        self.positions_tab.refresh(rows, self._live)
        if rows:
            record_board(self.store, rows, self.cfg)
        self.picks_tab.refresh()
        self._update_banner()
        self.home_tab.set_ideas(rows)
        lookup = {r["ticker"]: r for r in rows}
        open_trades = self.store.list_trades(open_only=True)
        n_beware = n_sell = 0
        for tr in open_trades:
            row = lookup.get(tr["ticker"])
            if not row:
                continue
            v = position_verdict(row["snap"], tr, row["sell"].score)
            if v["verdict"] == "SELL OUT":
                n_sell += 1
            elif v["verdict"] == "BEWARE":
                n_beware += 1
        self.home_tab.set_trades_summary(len(open_trades), n_beware, n_sell)
        if not rows:
            self.footer.setText("No scoreable history cached yet \u2014 "
                                "press Refresh data to pull the universe.")

    # ---------------- live quotes ----------------
    def _live_tick(self) -> None:
        if not is_market_open():
            self.live_label.setText("Live: market closed")
            return
        if self._live_worker and self._live_worker.isRunning():
            return
        from manual.ui.finders import ticker_from_label
        on_screen = ticker_from_label(self.detail_tab.picker.currentText())
        wanted = tickers_of_interest(
            self.store, [on_screen] if on_screen else None)
        self._live_worker = LiveWorker(self._live_provider, wanted)
        self._live_worker.done.connect(self._live_done)
        self._live_worker.start()

    def _live_done(self, quotes: dict) -> None:
        if not quotes:
            self.live_label.setText("Live: no quotes (delayed feed)")
            return
        self._live = quotes
        from datetime import datetime
        from manual.scout.live import LONDON
        stamp = datetime.now(LONDON).strftime("%H:%M")
        self.live_label.setText(
            f"\u25cf LIVE {stamp} \u00b7 watching {len(quotes)}")
        self.live_label.setStyleSheet("color: #3fb950;")
        self.positions_tab.refresh(self._rows, self._live)
        self.detail_tab.apply_live(self._live)

    # ---------------- plumbing ----------------
    def _update_banner(self) -> None:
        dial = timing_dial(self.store, self._rows, self.cfg)
        hic = hiccup_scan(self.store, self._rows)
        plain = {"GOOD": "GOOD", "MIXED": "MIXED",
                 "ROUGH": "ROUGH \u2014 CAREFUL"}[dial["state"]]
        self.banner.setText(f"\u25cf MARKET TODAY: {plain} "
                            f"({dial['score']}/100)")
        self.banner.setToolTip("\n".join(
            f"{c['glyph']} {c['name']}: {c['line']}"
            for c in dial["checks"]))
        self.banner.setStyleSheet(f"color: {dial['colour']};")
        guidance = dial["guidance"]
        if hic["large"]["active"]:
            guidance = "\U0001f534 " + hic["large"]["headline"]
        elif hic["small"]["active"]:
            guidance += "  \u00b7  \u26a0 " + hic["small"]["headline"]
        self.guidance.setText(guidance)
        when = self.store.get_setting("last_refresh_at")
        self.last_refresh.setText(f"Prices updated: {when}" if when
                                  else "No prices yet")
        self.home_tab.set_market(dial, hic)
        self.detail_tab.set_environment(dial["state"], hic)
        self.home_tab.set_refresh_status(
            self.refresh_service.already_refreshed_today(), when)

    def _add_stock(self) -> None:
        existing = {u["ticker"] for u in self.universe_rows}
        dlg = AddStockDialog(self.store, self.provider, self.cfg,
                             existing, self)
        if dlg.exec() and dlg.added:
            self.universe_rows = load_universe()
            self.detail_tab.set_universe(self.universe_rows)
            self.home_tab.set_universe(self.universe_rows)
            self.positions_tab.set_universe(self.universe_rows)
            self.start_scan()
            self._open_detail(dlg.added["ticker"])

    def _show_help(self) -> None:
        QMessageBox.information(self, "How to use TradeScout", (
            "Daily routine (all on the Home tab):\n\n"
            "1.  Update today's prices \u2014 once a day.\n"
            "2.  Today's Ideas \u2014 green table: strongest stocks worth a "
            "look to buy. Red table: weakest \u2014 avoid, or sell if you "
            "hold them. Hover a score to see exactly why.\n"
            "3.  Double-click any stock \u2192 Stock Detail shows the chart, "
            "the reasons, and a safe size and stop in pounds. Tick the "
            "checklist, write one honest sentence, press Log paper trade.\n"
            "4.  My Trades \u2014 every holding gets a clear verdict: HOLD, BEWARE "
            "or SELL OUT, with the reason in plain words. Close trades "
            "there and note the lesson.\n"
            "5.  Results \u2014 your scoreboard, and the app's own pick "
            "record.\n\n"
            "Also: \"Add stock\u2026\" (top) finds anything on Yahoo by "
            "name and adds it; \"Record a trade I already have\" (My "
            "Trades) logs holdings you opened elsewhere.\n\n"
            "Everything is practice (paper) money \u2014 nothing real ever "
            "moves. Guide only, not financial advice."))

    def _open_detail(self, ticker: str) -> None:
        self.tabs.setCurrentWidget(self.detail_tab)
        self.detail_tab.show_ticker(ticker)

    def _watch_changed(self, ticker: str, on: bool) -> None:
        self.store.watch(ticker, on)
        self.positions_tab.refresh(self._rows)

    def _after_trade_logged(self) -> None:
        self.positions_tab.refresh(self._rows)
        self.journal_tab.refresh()

    # ---------------- closing ----------------
    def closeEvent(self, event) -> None:
        """Failure mode (d): never close the window on top of a running command.

        The alternative -- detaching the process -- would leave an engine
        command writing to the live journal with nobody to record its exit
        code, and the governance log would end mid-sentence. Blocking is the
        honest choice: the operator waits a few seconds, or kills it from Task
        Manager knowing exactly what they are doing.
        """
        running = self.bot_tab.busy()
        if running is not None:
            QMessageBox.warning(
                self, "A bot command is still running",
                f"“{running}” is still running.\n\nWait for it to "
                f"finish before closing. Closing now would abandon a command "
                f"that is writing to the bot's journal.")
            event.ignore()
            return
        event.accept()
