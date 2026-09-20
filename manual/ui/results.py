"""Results: one place for both scoreboards -- your trading results and the
app's own pick record -- as two inner tabs."""
from __future__ import annotations

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget


class ResultsTab(QWidget):
    def __init__(self, journal_tab: QWidget, picks_tab: QWidget, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 0)
        self.inner = QTabWidget()
        self.inner.addTab(journal_tab, "My trading results")
        self.inner.addTab(picks_tab, "The app's pick record")
        layout.addWidget(self.inner)
