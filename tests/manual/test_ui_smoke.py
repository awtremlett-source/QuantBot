"""Offscreen Qt smoke tests: the app builds and the core flows run without a
display or network. QT_QPA_PLATFORM=offscreen is set in the root conftest."""
import numpy as np
import pytest

from manual.scout.config import Config
from manual.scout.scan import scan_universe
from manual.scout.store import Store
from tests.manual.conftest import downtrend_df, make_ohlcv, uptrend_df

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication  # noqa: E402

UNIVERSE = [
    {"ticker": "UP.L", "name": "Uptrend plc", "index": "FTSE100",
     "sector": "Test", "currency": "GBp", "stamp_duty": "Y"},
    {"ticker": "DOWN.L", "name": "Downtrend plc", "index": "FTSE250",
     "sector": "Test", "currency": "GBp", "stamp_duty": "Y"},
]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def seeded_store(tmp_path):
    store = Store(tmp_path / "ui.db")
    store.upsert_prices("UP.L", uptrend_df(300))
    store.upsert_prices("DOWN.L", downtrend_df(300))
    # index history so the regime banner has something to chew on
    idx = make_ohlcv(7000 + 5 * np.arange(300))
    store.upsert_prices("^FTSE", idx)
    store.upsert_prices("^FTMC", idx)
    store.upsert_prices("^VIX", make_ohlcv(np.full(60, 15.0)))
    yield store
    store.close()


def make_window(app, seeded_store):
    from manual.ui.main_window import MainWindow
    win = MainWindow(seeded_store, Config(), UNIVERSE, provider=None)
    if win._scan_worker:
        win._scan_worker.wait(15000)
    app.processEvents()
    return win


def test_window_builds_with_six_tabs_home_first(app, seeded_store):
    win = make_window(app, seeded_store)
    assert win.tabs.count() == 6
    assert win.tabs.currentIndex() == 0
    assert "Home" in win.tabs.tabText(0)
    assert "GOOD" in win.banner.text()
    assert "/100" in win.banner.text()
    assert "Breadth" in win.banner.toolTip()


def test_boards_populate_and_rank_correctly(app, seeded_store):
    win = make_window(app, seeded_store)
    assert win.board_tab.buy_table.rowCount() == 2
    top_buy = win.board_tab.buy_table.item(0, 1).text()
    top_sell = win.board_tab.sell_table.item(0, 1).text()
    assert top_buy == "UP.L"
    assert top_sell == "DOWN.L"
    score_item = win.board_tab.buy_table.item(0, 3)
    assert score_item.toolTip()  # reasons attached


def test_detail_renders_chart_and_scores(app, seeded_store):
    win = make_window(app, seeded_store)
    win._open_detail("UP.L")
    assert win.tabs.currentWidget() is win.detail_tab
    assert "Uptrend plc" in win.detail_tab.title.text()
    assert win.detail_tab._canvas is not None
    assert win.detail_tab._current["plan"]["ok"]
    path = win.detail_tab.path_label.text()
    assert "Stage-2" in path or "Breakout" in path or "Golden" in path


def test_log_and_close_paper_trade_flow(app, seeded_store, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    win = make_window(app, seeded_store)
    win._open_detail("UP.L")
    for cb in win.detail_tab.checks:
        cb.setChecked(True)
    win.detail_tab.thesis.setPlainText("Strong uptrend, breakout on volume.")
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: None))
    win.detail_tab._log_trade()
    open_trades = seeded_store.list_trades(open_only=True)
    assert len(open_trades) == 1
    assert open_trades[0]["ticker"] == "UP.L"
    assert open_trades[0]["thesis"]
    win.positions_tab.refresh(scan_universe(seeded_store, UNIVERSE, Config()))
    assert win.positions_tab.pos_table.rowCount() == 1


def test_picks_recorded_and_tab_populated(app, seeded_store):
    win = make_window(app, seeded_store)
    assert seeded_store.list_picks()          # auto-recorded by the scan
    assert win.picks_tab.table.rowCount() >= 2
    assert "%" in win.picks_tab.summary.text()


def test_home_tab_guides_after_scan(app, seeded_store):
    win = make_window(app, seeded_store)
    assert win.home_tab.buy_list.count() >= 1
    assert "scored today" in win.home_tab.ideas_status.text()
    assert win.home_tab.refresh_status.text()      # some status shown
    win.home_tab.open_ticker.emit("UP.L")
    assert win.tabs.currentWidget() is win.detail_tab


def test_detail_shows_manage_path_when_held(app, seeded_store):
    from manual.scout import journal
    journal.open_trade(seeded_store, ticker="UP.L", name="Uptrend plc",
                       entry_px=1.0, stop_px=0.9, shares=10, risk_gbp=1.0,
                       open_costs_gbp=0.0, setup_type="Manual",
                       thesis="held", checklist={})
    win = make_window(app, seeded_store)
    win._open_detail("UP.L")
    assert "You hold this" in win.detail_tab.path_label.text()


def test_spotlight_lists_durable_climber(app, seeded_store):
    win = make_window(app, seeded_store)
    t = win.spotlight_tab.table
    tickers = [t.item(i, 1).text() for i in range(t.rowCount())]
    assert "UP.L" in tickers and "DOWN.L" not in tickers


def test_delete_trade_removes_record(app, seeded_store, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from manual.scout import journal
    tid = journal.open_trade(seeded_store, ticker="UP.L", name="Uptrend plc",
                             entry_px=1.0, stop_px=0.9, shares=10,
                             risk_gbp=1.0, open_costs_gbp=0.0,
                             setup_type="Manual", thesis="oops",
                             checklist={})
    win = make_window(app, seeded_store)
    monkeypatch.setattr(QMessageBox, "question", staticmethod(
        lambda *a, **k: QMessageBox.StandardButton.Yes))
    win.journal_tab._delete_trade(tid, "UP.L")
    assert seeded_store.get_trade(tid) is None
    assert seeded_store.list_trades() == []


def test_ladder_line_shows_in_my_trades(app, seeded_store):
    win = make_window(app, seeded_store)
    line = win.positions_tab.ladder_label.text()
    assert "position #1" in line and "\u00a35,000" in line


def test_path_panel_includes_money_split(app, seeded_store):
    win = make_window(app, seeded_store)
    win._open_detail("UP.L")
    assert "Money split" in win.detail_tab.path_label.text()


def test_watch_toggle_persists(app, seeded_store):
    win = make_window(app, seeded_store)
    win._watch_changed("UP.L", True)
    assert seeded_store.watchlist() == ["UP.L"]
    assert win.positions_tab.watch_table.rowCount() == 1


def test_record_existing_trade_dialog(app, seeded_store):
    from manual.ui.manual_trade import RecordTradeDialog
    dlg = RecordTradeDialog(UNIVERSE)
    dlg.stock.setCurrentText("UP.L \u2014 Uptrend plc")
    dlg.shares.setText("10")
    dlg.total_paid.setText("250.00")
    v = dlg.values()
    assert v["ticker"] == "UP.L" and v["entry"] == pytest.approx(25.0)
    tid = dlg.save(seeded_store)
    trade = seeded_store.get_trade(tid)
    assert trade["shares"] == 10 and trade["setup_type"] == "Manual"
    assert trade["stop_px"] == pytest.approx(25.0)   # no stop -> stop=entry


def test_record_fractional_shares(app, seeded_store):
    from manual.ui.manual_trade import RecordTradeDialog
    dlg = RecordTradeDialog(UNIVERSE)
    dlg.stock.setCurrentText("UP.L \u2014 Uptrend plc")
    dlg.shares.setText("0.1523")
    dlg.total_paid.setText("250.00")
    v = dlg.values()
    assert v["shares"] == pytest.approx(0.1523)
    assert v["entry"] == pytest.approx(250.0 / 0.1523)
    tid = dlg.save(seeded_store)
    trade = seeded_store.get_trade(tid)
    assert trade["shares"] == pytest.approx(0.1523)


def test_record_dialog_friendly_errors(app):
    from manual.ui.manual_trade import RecordTradeDialog
    dlg = RecordTradeDialog(UNIVERSE)
    dlg.stock.setCurrentText("UP.L \u2014 Uptrend plc")
    dlg.shares.setText("ten")
    dlg.total_paid.setText("250")
    with pytest.raises(ValueError):
        dlg.values()
    dlg.shares.setText("0")
    with pytest.raises(ValueError):
        dlg.values()
    dlg.shares.setText("10")
    dlg.shares.setText("10")
    dlg.alert.setText("abc")
    with pytest.raises(ValueError):
        dlg.values()
    dlg.alert.setText("-5")
    with pytest.raises(ValueError):
        dlg.values()


def test_alert_is_whole_holding_value(app, seeded_store):
    from manual.ui.manual_trade import RecordTradeDialog
    dlg = RecordTradeDialog(UNIVERSE, seeded_store)
    dlg.stock.setCurrentText("UP.L \u2014 Uptrend plc")
    dlg.shares.setText("1.64")
    dlg.total_paid.setText("103.10")
    dlg.alert.setText("154.57")           # whole-holding pounds
    v = dlg.values()
    assert v["entry"] == pytest.approx(103.10 / 1.64)
    assert v["stop"] == pytest.approx(154.57 / 1.64)   # per-share, hidden
    tid = dlg.save(seeded_store)
    trade = seeded_store.get_trade(tid)
    assert trade["stop_px"] == pytest.approx(94.25, abs=0.01)
    assert trade["risk_gbp"] == 0.0       # alert above entry: profit lock


def test_alert_suggested_automatically(app, seeded_store):
    from manual.ui.manual_trade import RecordTradeDialog
    dlg = RecordTradeDialog(UNIVERSE, seeded_store)
    dlg.stock.setCurrentText("UP.L \u2014 Uptrend plc")
    dlg.shares.setText("2")
    dlg._recalc()
    suggested = float(dlg.alert.text())
    assert suggested > 0
    assert "Worth about" in dlg.info.text()


def test_detail_picker_search_by_label(app, seeded_store):
    win = make_window(app, seeded_store)
    assert win.detail_tab.picker.isEditable()
    win.detail_tab._picker_changed("DOWN.L \u2014 Downtrend plc")
    assert "Downtrend plc" in win.detail_tab.title.text()


def test_home_search_opens_detail(app, seeded_store):
    win = make_window(app, seeded_store)
    win.home_tab.search.setText("UP.L \u2014 Uptrend plc")
    win.home_tab._search_go()
    assert win.tabs.currentWidget() is win.detail_tab
    assert "Uptrend plc" in win.detail_tab.title.text()
