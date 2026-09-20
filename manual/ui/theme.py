"""Visual identity: a quiet UK dealing-desk terminal.

One idea, executed with restraint: charcoal panels, tabular monospace
numbers, and exactly three signal colours that always mean the same thing
-- green = long/buy, red = exit/avoid, amber = caution. The signature
element is the exchange-status regime strip across the top.
"""
from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

BG = "#0d1117"
PANEL = "#161b22"
BORDER = "#30363d"
TEXT = "#e6edf3"
MUTED = "#8b949e"
GREEN = "#3fb950"
RED = "#f85149"
AMBER = "#d29922"
MONO = "Cascadia Mono, Consolas, DejaVu Sans Mono, monospace"

STYLESHEET = f"""
QWidget {{ background: {BG}; color: {TEXT}; font-size: 13px; }}
QTabWidget::pane {{ border: 1px solid {BORDER}; top: -1px; }}
QTabBar::tab {{ background: {PANEL}; color: {MUTED}; padding: 7px 16px;
    border: 1px solid {BORDER}; border-bottom: none; }}
QTabBar::tab:selected {{ color: {TEXT}; background: {BG};
    border-bottom: 2px solid {AMBER}; }}
QGroupBox {{ border: 1px solid {BORDER}; margin-top: 12px; padding-top: 6px;
    font-weight: bold; color: {MUTED}; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 4px;
    letter-spacing: 1px; }}
QTableWidget {{ background: {PANEL}; gridline-color: {BORDER};
    font-family: {MONO}; alternate-background-color: #11151c; }}
QHeaderView::section {{ background: {BG}; color: {MUTED}; border: none;
    border-bottom: 1px solid {BORDER}; padding: 5px; font-weight: bold; }}
QPushButton {{ background: {PANEL}; border: 1px solid {BORDER};
    padding: 6px 14px; border-radius: 3px; }}
QPushButton:hover {{ border-color: {MUTED}; }}
QPushButton#primary {{ border-color: {GREEN}; color: {GREEN};
    font-weight: bold; }}
QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {PANEL}; border: 1px solid {BORDER}; padding: 4px;
    font-family: {MONO}; }}
QProgressBar {{ background: {PANEL}; border: 1px solid {BORDER};
    text-align: center; }}
QProgressBar::chunk {{ background: {AMBER}; }}
QCheckBox {{ spacing: 6px; }}
QToolTip {{ background: {PANEL}; color: {TEXT}; border: 1px solid {BORDER}; }}
QScrollArea {{ border: none; }}
QLabel#banner {{ font-family: {MONO}; font-weight: bold; font-size: 14px;
    padding: 8px 12px; letter-spacing: 1px; }}
QLabel#muted {{ color: {MUTED}; }}
"""


def apply_dark(app: QApplication) -> None:
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(BG))
    pal.setColor(QPalette.ColorRole.Base, QColor(PANEL))
    pal.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Button, QColor(PANEL))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(AMBER))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(BG))
    app.setPalette(pal)
    app.setStyleSheet(STYLESHEET)


def fmt_gbp(v: float | None, dp: int = 2) -> str:
    return "\u2014" if v is None else f"\u00a3{v:,.{dp}f}"


def fmt_px(snap_close: float | None, currency: str = "GBp") -> str:
    """Show the quote the way the LSE shows it (pence for GBp lines)."""
    if snap_close is None:
        return "\u2014"
    if currency == "GBp":
        return f"{snap_close:,.1f}p"
    return f"{snap_close:,.2f} {currency}"


def fmt_num(v: float | None, dp: int = 1) -> str:
    return "\u2014" if v is None else f"{v:,.{dp}f}"


def fmt_shares(v: float | None) -> str:
    if v is None:
        return "\u2014"
    f = float(v)
    if f == int(f):
        return f"{int(f):,}"
    return f"{f:,.4f}".rstrip("0").rstrip(".")
