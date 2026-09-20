"""TradeScout entry point.

A manual paper-trading guide for LSE names available on Trading 212.
Long-only framing, cache-first data, decision aid only -- it never trades.
Run: python app.py
"""
import sys

from PySide6.QtWidgets import QApplication

from manual.scout.config import load_config
from manual.scout.store import Store
from manual.scout.universe import load_universe
from manual.ui.main_window import MainWindow
from manual.ui.theme import apply_dark


def main() -> int:
    app = QApplication(sys.argv)
    apply_dark(app)
    cfg = load_config()
    store = Store()
    universe_rows = load_universe()
    win = MainWindow(store, cfg, universe_rows)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
