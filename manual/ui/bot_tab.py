"""The Bot tab -- what the trading engine is doing, in plain words.

READ-ONLY about the bot's books, and ALLOW-LISTED about its commands. Every
number here comes through manual/bot_readonly.py; every button goes through
manual/bot_governance.py. This file holds no engine paths, no SQL and no
commands of its own.

It deliberately does NOT offer: any strategy setting, any parameter, any way to
edit a position, and no "copy the bot's trade" button. The bot's edge was
validated as a whole; a human reaching in to adjust it mid-flight would break
the thing that makes its record worth having. So this tab watches and governs,
exactly like the Tkinter control panel it mirrors -- nothing more.

AGE IS SHOWN ON EVERYTHING. A figure without an age quietly becomes a lie: the
laptop is off much of the time, so "equity £10,238" means nothing until you
know whether that was this morning or five weeks ago.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (QGroupBox, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QTextEdit, QVBoxLayout, QWidget)

from manual import bot_governance, bot_readonly
from manual.bot_readonly import TRACK_RECORD_TARGET_DAYS, BotSnapshot

from .theme import AMBER, BORDER, GREEN, MONO, MUTED, PANEL, RED, fmt_gbp

# label, action, confirmation question (None = press straight through).
# The labels and the order MIRROR tools/gui.py. The confirmations are equal or
# stronger: the panel guards only the killswitch, and we also guard the loop,
# because that button writes to the live forward track record.
BUTTONS: list[tuple[str, str, str | None]] = [
    ("Refresh Status", "status", None),
    ("Run Loop Now", "loop",
     "Run the paper loop now?\n\nIt processes every unprocessed bar and writes "
     "to the bot's live journal -- the forward track record. Safe, but it is "
     "the real thing, not a rehearsal."),
    ("Health Report Now", "health", None),
    ("Backup Now", "backup", None),
    ("Test the Lights (drill)", "drill", None),
    ("Arm/Disarm Killswitch", "killswitch", None),   # asks its own question
    ("Send Test Telegram", "telegram_test", None),
]

UNKNOWN = "—"          # em dash: "nothing to show", never a zero


def _money(value: float | None) -> str:
    """Pounds, with the minus OUTSIDE the sign: -£4.64, not £-4.64.

    A negative cash balance is a real thing here -- slippage can overdraw the
    book by a few pounds -- so it has to read clearly rather than oddly.
    """
    if value is None:
        return UNKNOWN
    return f"-{fmt_gbp(abs(value))}" if value < 0 else fmt_gbp(value)


def _age(days: int | None) -> str:
    if days is None:
        return ""
    if days == 0:
        return " (today)"
    return f" ({days} day{'s' if days != 1 else ''} ago)"


def header_line(snapshot: BotSnapshot) -> tuple[str, bool]:
    """The tab's headline and whether it should be RED.

    Pure function of the snapshot, so the red can be proven on a fixture
    without a window (SCARS #9 -- a warning nobody has watched fire is not a
    warning).
    """
    if snapshot.latest_bar is None:
        return ("Bot data is stale — the bot has no journal yet", True)
    if snapshot.stale:
        behind = snapshot.trading_days_behind
        return (f"Bot data is stale — {behind} completed trading "
                f"day{'s' if behind != 1 else ''} not processed", True)
    return ("The bot is up to date", False)


def describe(snapshot: BotSnapshot) -> list[tuple[str, str]]:
    """The tab's rows, in plain words, each carrying its own age."""
    bar = (snapshot.latest_bar[:10] if snapshot.latest_bar else UNKNOWN)
    rows = [
        ("Last bar it processed", f"{bar}{_age(snapshot.bar_age_days)}"),
        ("Up to date?", "yes" if not snapshot.stale
         else f"NO — {snapshot.trading_days_behind} trading days behind"),
        ("Money (equity)", UNKNOWN if snapshot.equity is None
         else f"{_money(snapshot.equity)} as at that bar"),
    ]
    if snapshot.shares:
        holding = (f"{snapshot.shares:.6f} {snapshot.ticker or ''} shares"
                   f" + {_money(snapshot.cash)} cash")
    else:
        holding = f"none — all cash ({_money(snapshot.cash)})"
    rows.append(("Open position", holding))
    rows += [
        ("Forward record so far",
         f"{snapshot.track_record_days} of {TRACK_RECORD_TARGET_DAYS} days"
         f" — {snapshot.marks} bars marked"),
        ("Trials logged (honesty tally)", str(snapshot.trials)),
        ("Last entry in its run log",
         f"{snapshot.last_log_time or UNKNOWN}"
         f"{' — errors in the log' if snapshot.log_has_errors else ''}"),
        ("Its last digest line", snapshot.last_digest or UNKNOWN),
    ]
    return rows


class _ActionWorker(QThread):
    """Runs ONE allow-listed action off the UI thread."""

    finished_with = Signal(str, int, str)   # action, exit code, output

    def __init__(self, action: str) -> None:
        super().__init__()
        self._action = action

    def run(self) -> None:                  # pragma: no cover -- thread body
        try:
            outcome = bot_governance.run(self._action)
            self.finished_with.emit(self._action, outcome.returncode,
                                    outcome.output.strip() or "(no output)")
        except (bot_governance.Busy, bot_governance.UnknownAction) as exc:
            self.finished_with.emit(self._action, -1, f"REFUSED: {exc}")


class BotTab(QWidget):
    """Observe the bot; govern it through the two doorways. Nothing else."""

    def __init__(self) -> None:
        super().__init__()
        self._worker: _ActionWorker | None = None
        self._buttons: dict[str, QPushButton] = {}

        self.header = QLabel("")
        self.header.setStyleSheet(
            f"font-size: 15px; font-weight: 600; padding: 6px;"
            f" border: 1px solid {BORDER}; background: {PANEL};")

        self.facts = QLabel("")
        self.facts.setTextInteractionFlags(self.facts.textInteractionFlags())
        self.facts.setStyleSheet(f"font-family: {MONO}; padding: 6px;")

        self.killswitch = QLabel("")
        self.killswitch.setStyleSheet("padding: 2px 6px;")

        row = QHBoxLayout()
        for label, action, confirm in BUTTONS:
            button = QPushButton(label)
            button.clicked.connect(
                lambda _checked=False, a=action, q=confirm: self._press(a, q))
            self._buttons[action] = button
            row.addWidget(button)
        row.addStretch(1)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setStyleSheet(f"font-family: {MONO};")
        self.output.setPlaceholderText(
            "Output from the bot's own commands appears here. Nothing has been "
            "run from this window yet.")

        meters = QGroupBox("The bot's own status check")
        meters_layout = QVBoxLayout(meters)
        self.meters_hint = QLabel(
            "Press “Refresh Status” to run the bot's meters. They are "
            "not run automatically: this window never starts an engine command "
            "on its own.")
        self.meters_hint.setWordWrap(True)
        self.meters_hint.setStyleSheet(f"color: {MUTED};")
        meters_layout.addWidget(self.meters_hint)
        meters_layout.addWidget(self.output, stretch=1)

        layout = QVBoxLayout(self)
        layout.addWidget(self.header)
        layout.addWidget(self.killswitch)
        layout.addWidget(self.facts)
        layout.addLayout(row)
        layout.addWidget(meters, stretch=1)

        self.refresh()

    # ------------------------------------------------------------- reading ---

    def refresh(self) -> None:
        """Re-read the bot's books. Read-only, short-lived, never blocking."""
        try:
            snapshot = bot_readonly.read_snapshot()
        except bot_readonly.EngineUnavailable as exc:
            self.header.setText("Cannot read the bot's journal")
            self.header.setStyleSheet(
                f"font-size: 15px; font-weight: 600; padding: 6px;"
                f" border: 1px solid {RED}; background: {PANEL}; color: {RED};")
            self.facts.setText(f"{exc}\n\nThe engine may never have run on this "
                              f"machine, or it is mid-write. Nothing is wrong "
                              f"with this window.")
            return

        text, red = header_line(snapshot)
        self.header.setText(text)
        colour = RED if red else GREEN
        self.header.setStyleSheet(
            f"font-size: 15px; font-weight: 600; padding: 6px;"
            f" border: 1px solid {colour}; background: {PANEL}; color: {colour};")
        width = max(len(label) for label, _ in describe(snapshot))
        self.facts.setText("\n".join(
            f"{label.ljust(width)}   {value}" for label, value in describe(snapshot)))
        self._refresh_killswitch()

    def _refresh_killswitch(self) -> None:
        armed = bot_governance.killswitch_armed()
        self.killswitch.setText(
            "KILLSWITCH: ARMED — the bot will place no new orders" if armed
            else "killswitch: not armed — the bot may place orders")
        self.killswitch.setStyleSheet(
            f"padding: 2px 6px; color: {AMBER if armed else MUTED};")

    # ----------------------------------------------------------- governing ---

    def busy(self) -> str | None:
        """The action currently running, if any (the window asks before closing)."""
        return bot_governance.busy() if self._worker is not None else None

    def _press(self, action: str, question: str | None) -> None:
        if action == "killswitch":
            self._toggle_killswitch()
            return
        if self.busy() is not None:
            QMessageBox.information(
                self, "One at a time",
                f"“{self.busy()}” is still running. The window never "
                f"runs two engine commands at once.")
            return
        if question is not None and not self._confirmed("Run this?", question):
            return
        self._set_enabled(False)
        self._append(f"── {action} started ──")
        self._worker = _ActionWorker(action)
        self._worker.finished_with.connect(self._done)
        self._worker.start()

    def _toggle_killswitch(self) -> None:
        if bot_governance.killswitch_armed():
            if self._confirmed(
                    "Disarm killswitch",
                    "Let the bot place new orders again?"):
                self._append(bot_governance.disarm_killswitch())
        elif self._confirmed(
                "Arm killswitch",
                "Stop the bot placing any NEW orders?\n\nPending fills still "
                "settle and equity is still marked -- it stops new buying only."):
            self._append(bot_governance.arm_killswitch())
        self._refresh_killswitch()

    def _confirmed(self, title: str, question: str) -> bool:
        return QMessageBox.question(
            self, title, question,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def _done(self, action: str, code: int, output: str) -> None:
        self._append(output)
        self._append(f"── {action} finished (exit {code}) ──")
        self._worker = None
        self._set_enabled(True)
        self.refresh()

    def _set_enabled(self, enabled: bool) -> None:
        """Failure mode (c): a double-click must not fire a command twice."""
        for button in self._buttons.values():
            button.setEnabled(enabled)

    def _append(self, text: str) -> None:
        self.output.append(text)
