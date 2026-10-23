"""QT-24 C: after an urgent exit, his words also clear the advisor's 10% brake. Offline.

Operator, 2026-10-23 (verbatim): "GO on the advisor's 10% brake: after an urgent exit, my own words
also clear the advisor's 10% brake and restart its peak from that day."
Why: after an exit the advisor pot is cash, 10-15% below its peak; the 10% brake clears only when
the pot is back within 5% of its peak, which cash never is -- so the re-buy waited for ever.
Each test was seen RED on the old code (docs/reports/QT-24_redfirst_brake.txt); mutants (i)-(iii)
in the report.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from qb2.advisor import page, state
from qb2.execution.safety import ADVISOR, BOT
from qb2.guard import brakes
from qb2.tools import clear_pause

WORDS = "GO: the exit is done -- clear the advisor's brake"
ARMED = datetime(2026, 10, 20, 20, 39, 40, tzinfo=timezone.utc)


def _exited(tmp: Path, *, exit_: bool = True) -> tuple[brakes.Brakes, state.Paths]:
    """The advisor pot 12% below its peak (10% brake on); with ``exit_`` its latest allowed
    suggestion is an URGENT-EXIT SELL, as the daily job writes it."""
    b, paths = brakes.Brakes(tmp / "brakes.jsonl"), state.Paths.under(tmp)
    for v in (7000.0, 6160.0, 6160.0):                                   # -12%, then cash: flat
        b.update(ADVISOR, v)
    state.append(paths.log("suggestions"), {"action": "BUY", "allowed": True, "kind": "weekly"})
    if exit_:
        state.append(paths.log("suggestions"), {"action": "SELL", "allowed": True, "kind": "urgent-exit"})
    return b, paths


def _clear(b: brakes.Brakes, paths: state.Paths, words: str, pot: str = "advisor") -> int:
    return clear_pause.main(["--words", words, "--pot", pot], state=b.path, advisor=paths)


def test_after_an_urgent_exit_his_words_clear_the_ten_percent_brake_and_restart_the_peak(tmp_path: Path) -> None:
    b, paths = _exited(tmp_path)
    assert b.state(ADVISOR).level == brakes.BRAKED                       # type: ignore[union-attr]
    assert _clear(b, paths, WORDS) == 0
    now = b.state(ADVISOR)
    assert now is not None and (now.level, now.peak, now.value) == (brakes.OK, 6160.0, 6160.0)
    rows = [json.loads(x) for x in b.path.read_text(encoding="utf-8").splitlines()]
    assert {"event": "cleared", "pot": ADVISOR, "words": WORDS, "was_peak": 7000.0}.items() <= rows[-2].items()
    assert b.update(ADVISOR, 6160.0).level == brakes.OK                  # the next day: measured afresh
    brakes.check_buy(b.state(ADVISOR), ADVISOR)                          # no raise: the re-buy may go ahead


def test_without_his_words_nothing_clears_it(tmp_path: Path) -> None:
    b, paths = _exited(tmp_path)
    for words in ("", "   "):
        assert _clear(b, paths, words) == 1
    for _ in range(30):                                                  # a month in cash: still braked
        assert b.update(ADVISOR, 6160.0).level == brakes.BRAKED


def test_before_any_exit_the_ten_percent_brake_is_not_his_words_to_clear(tmp_path: Path) -> None:
    b, paths = _exited(tmp_path, exit_=False)                            # held and falling: the GO is
    assert _clear(b, paths, WORDS) == 1                                  # for after an exit only
    assert b.state(ADVISOR).level == brakes.BRAKED                       # type: ignore[union-attr]


def test_the_bot_pot_is_untouched_by_the_advisors_clear(tmp_path: Path) -> None:
    b, paths = _exited(tmp_path)
    for v in (100.0, 89.0):
        b.update(BOT, v)                                                 # the bot's own 10% brake
    bot_before = b.state(BOT)
    assert _clear(b, paths, WORDS) == 0
    assert b.state(BOT) == bot_before                                    # untouched by the advisor's clear
    assert _clear(b, paths, WORDS, pot="bot") == 1                       # and his GO is not the bot's
    assert b.state(BOT) == bot_before


def test_the_page_says_what_the_brake_does_after_an_exit() -> None:
    text = page.build(ARMED, arm=ARMED.date(), days=[], suggestions=[], runs=[], shadows=[], status={})
    assert "## The brake" in text
    assert "only your own words clear it" in text and "restarts from that day" in text
