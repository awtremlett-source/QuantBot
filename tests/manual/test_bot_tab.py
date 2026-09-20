"""The Bot tab: it reads, it reports its own age, and it starts nothing by itself.

The birth certificate for staleness is here (SCARS #9): a fixture whose last run
is old MUST turn the header red, and a fresh one MUST leave it green. A warning
nobody has watched fire is not a warning.
"""
import sqlite3
from datetime import datetime, timezone

import pytest

from manual import bot_governance, bot_readonly
from manual.bot_readonly import BotSnapshot
from manual.ui import bot_tab
from manual.ui.theme import GREEN, RED

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402  (after importorskip)


@pytest.fixture(scope="module")
def app():
    """One QApplication for the module -- offscreen, per tests/manual/conftest."""
    return QApplication.instance() or QApplication([])


def make_engine_db(path, bar_date, *, equity=10_500.0, close=210.0,
                   shares=50.0, first_bar=None):
    """A minimal stand-in for the engine's journal -- the two tables we read."""
    connection = sqlite3.connect(path)
    connection.executescript(
        "CREATE TABLE paper_equity (ticker TEXT, event_time TEXT,"
        " equity REAL, close REAL);"
        "CREATE TABLE paper_fills (order_id INTEGER, fill_event_time TEXT,"
        " fill_price REAL, shares_delta REAL, cash_delta REAL,"
        " knowable_time TEXT);")
    marks = [(first_bar or bar_date, equity - 100.0), (bar_date, equity)]
    for when, value in marks:
        connection.execute(
            "INSERT INTO paper_equity VALUES ('NVDA', ?, ?, ?)",
            (f"{when}T00:00:00Z", value, close))
    if shares:
        connection.execute(
            "INSERT INTO paper_fills VALUES (1, ?, ?, ?, ?, ?)",
            (f"{bar_date}T00:00:00Z", close, shares, -shares * close,
             f"{bar_date}T01:00:00Z"))
    connection.commit()
    connection.close()
    return path


def snapshot_for(tmp_path, bar_date, today, **kwargs):
    database = make_engine_db(tmp_path / "quantbot.db", bar_date, **kwargs)
    return bot_readonly.read_snapshot(
        db_path=database,
        trial_log=tmp_path / "absent-trials.jsonl",
        loop_log=tmp_path / "absent-loop.log",
        now=datetime(*today, tzinfo=timezone.utc))


# ------------------------------------------- staleness, read from a real DB ---

def test_a_bar_from_the_previous_session_is_fresh(tmp_path):
    """Friday's bar, read on Monday: nothing has been missed."""
    snap = snapshot_for(tmp_path, "2026-09-18", (2026, 9, 21))   # Fri -> Mon
    assert snap.trading_days_behind == 0
    assert snap.stale is False


def test_a_skipped_trading_day_is_stale(tmp_path):
    """Friday's bar, read on Tuesday: Monday went unprocessed."""
    snap = snapshot_for(tmp_path, "2026-09-18", (2026, 9, 22))   # Fri -> Tue
    assert snap.trading_days_behind == 1
    assert snap.stale is True


def test_a_long_dark_gap_counts_only_weekdays(tmp_path):
    snap = snapshot_for(tmp_path, "2026-09-01", (2026, 9, 21))
    assert snap.trading_days_behind == 13      # 20 days, 13 of them weekdays
    assert snap.stale is True


def test_the_figures_come_from_the_journal_not_from_a_constant(tmp_path):
    snap = snapshot_for(tmp_path, "2026-09-18", (2026, 9, 21),
                        equity=10_500.0, close=210.0, shares=50.0,
                        first_bar="2026-08-19")
    assert snap.equity == 10_500.0
    assert snap.shares == 50.0
    # cash is DERIVED: equity - shares * close, never a copied config value
    assert snap.cash == pytest.approx(10_500.0 - 50.0 * 210.0)
    assert snap.marks == 2
    assert snap.track_record_days == 30
    assert snap.bar_age_days == 3


# ------------------------------------- the header: red on old, green on new ---

def _fixture_snapshot(*, behind, latest="2026-09-18T00:00:00Z"):
    return BotSnapshot(
        latest_bar=latest, equity=10_500.0, close=210.0, ticker="NVDA",
        shares=50.0, cash=0.0, marks=2, first_bar="2026-08-19T00:00:00Z",
        trials=64, last_digest="PAPER NVDA @ 2026-09-18 | bars=1",
        last_log_time="2026-09-21 07:30:02", log_has_errors=False,
        trading_days_behind=behind,
        read_at=datetime(2026, 9, 21, tzinfo=timezone.utc))


def test_header_is_green_and_calm_when_up_to_date():
    text, red = bot_tab.header_line(_fixture_snapshot(behind=0))
    assert red is False
    assert "up to date" in text


def test_header_is_red_and_says_stale_when_a_day_was_missed():
    text, red = bot_tab.header_line(_fixture_snapshot(behind=1))
    assert red is True
    assert text.startswith("Bot data is stale")
    assert "1 completed trading day" in text


def test_header_is_red_when_there_is_no_journal_at_all():
    text, red = bot_tab.header_line(
        _fixture_snapshot(behind=0, latest=None))
    assert red is True
    assert "stale" in text


def test_the_tab_paints_the_header_red_on_a_stale_fixture(app, monkeypatch):
    """Birth certificate, through the real widget: old fixture -> RED."""
    monkeypatch.setattr(bot_readonly, "read_snapshot",
                        lambda *a, **k: _fixture_snapshot(behind=4))
    tab = bot_tab.BotTab()
    assert "Bot data is stale" in tab.header.text()
    assert RED in tab.header.styleSheet()
    assert GREEN not in tab.header.styleSheet()


def test_the_tab_paints_the_header_green_on_a_fresh_fixture(app, monkeypatch):
    monkeypatch.setattr(bot_readonly, "read_snapshot",
                        lambda *a, **k: _fixture_snapshot(behind=0))
    tab = bot_tab.BotTab()
    assert "up to date" in tab.header.text()
    assert GREEN in tab.header.styleSheet()
    assert RED not in tab.header.styleSheet()


def test_an_unreadable_journal_is_reported_not_crashed(app, monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise bot_readonly.EngineUnavailable("engine database not found: nowhere")

    monkeypatch.setattr(bot_readonly, "read_snapshot", unavailable)
    tab = bot_tab.BotTab()
    assert "Cannot read" in tab.header.text()
    assert "not found" in tab.facts.text()


# ----------------------------------------------- what the tab shows and is ---

def test_every_figure_is_shown_with_its_age(app):
    rows = dict(bot_tab.describe(_fixture_snapshot(behind=0)))
    assert "day" in rows["Last bar it processed"]          # carries an age
    assert rows["Up to date?"] == "yes"
    assert "10,500" in rows["Money (equity)"] or "10500" in rows["Money (equity)"]
    assert "50.000000 NVDA shares" in rows["Open position"]
    assert rows["Trials logged (honesty tally)"] == "64"
    assert "of 30 days" in rows["Forward record so far"]
    assert "2026-09-21 07:30:02" in rows["Last entry in its run log"]


def test_the_tab_has_exactly_the_panels_seven_buttons(app, monkeypatch):
    monkeypatch.setattr(bot_readonly, "read_snapshot",
                        lambda *a, **k: _fixture_snapshot(behind=0))
    tab = bot_tab.BotTab()
    labels = [label for label, _action, _confirm in bot_tab.BUTTONS]
    assert labels == ["Refresh Status", "Run Loop Now", "Health Report Now",
                      "Backup Now", "Test the Lights (drill)",
                      "Arm/Disarm Killswitch", "Send Test Telegram"]
    assert len(tab._buttons) == 7
    # every action is either on the governance allow-list or the killswitch file
    for _label, action, _confirm in bot_tab.BUTTONS:
        assert (action in bot_governance.ALLOWED_ACTIONS
                or action == "killswitch")


def test_the_loop_button_asks_before_it_runs():
    """The panel guards only the killswitch; here the loop is guarded too."""
    confirms = {action: question for _label, action, question in bot_tab.BUTTONS}
    assert confirms["loop"] is not None
    assert "live journal" in confirms["loop"]


def test_the_tab_offers_no_way_to_edit_anything(app, monkeypatch):
    """B5: no strategy settings, no parameters, no editing a position."""
    from PySide6.QtWidgets import (QAbstractSpinBox, QComboBox, QLineEdit,
                                   QSlider)

    monkeypatch.setattr(bot_readonly, "read_snapshot",
                        lambda *a, **k: _fixture_snapshot(behind=0))
    tab = bot_tab.BotTab()
    for widget_type in (QLineEdit, QAbstractSpinBox, QComboBox, QSlider):
        assert tab.findChildren(widget_type) == [], (
            f"the Bot tab must not contain a {widget_type.__name__}")
    assert tab.output.isReadOnly()
    # nothing on the tab mentions copying the bot's trades
    assert "copy" not in " ".join(
        label for label, _a, _c in bot_tab.BUTTONS).lower()


def test_building_the_tab_runs_no_engine_command(app, monkeypatch):
    """Opening the window must never start a subprocess by itself."""
    def refuse(*_args, **_kwargs):
        raise AssertionError("the Bot tab launched a command on construction")

    monkeypatch.setattr(bot_governance, "run", refuse)
    monkeypatch.setattr(bot_readonly, "read_snapshot",
                        lambda *a, **k: _fixture_snapshot(behind=0))
    tab = bot_tab.BotTab()
    assert tab.busy() is None
    assert "not run automatically" in tab.meters_hint.text()
