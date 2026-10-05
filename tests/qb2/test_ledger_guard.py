"""F13: the anchor ledger is the memory of every order, so --live refuses without it.

A missing or empty ledger used to read as "nothing ever happened": the GBP 100
lifetime tally, the refusals and the daily count all silently back to zero. An
unreadable one raised from deep inside the run. Now each refuses before the broker
is touched, says why, and leaves the file exactly as found -- rebuilding it is the
operator's GO, from the broker's order history. The dry run still works.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from qb2.execution import anchors
from qb2.execution.anchor_ledger import AnchorLedger
from tests.qb2.test_qt12_anchors import (IDENTITIES, MON_OVERLAP, FakeReader,
                                         OrderWire, calendar, fx_on, live,
                                         quotes_on)

BROKEN = {
    "missing": None,
    "empty": "",
    "blank lines only": "\n\n",
    "corrupt": '{"kind": "INTENT", "intent_id": "a1"\n',
    "not a ledger record": '{"kind": "BOGUS", "intent_id": "a1"}\n',
}
WHY = {"missing": "missing", "empty": "empty", "blank lines only": "empty",
       "corrupt": "unreadable", "not a ledger record": "unreadable"}


def ledger_at(tmp_path: Path, content: str | None) -> AnchorLedger:
    path = tmp_path / "anchors" / "ledger.jsonl"
    if content is not None:
        path.parent.mkdir(parents=True)
        path.write_text(content, encoding="utf-8")
    return AnchorLedger(path)


@pytest.mark.parametrize("case", list(BROKEN))
def test_live_sends_nothing_and_says_why(tmp_path: Path, case: str) -> None:
    book = ledger_at(tmp_path, BROKEN[case])
    before = book.path.read_bytes() if book.path.exists() else None
    wire = OrderWire()

    report, reader, wire, _ = live(tmp_path, ledger=book, wire=wire)

    assert wire.posts == 0 and wire.calls == []      # no order, not even a GET
    assert reader.calls == []                        # refused before the broker
    assert f"anchor ledger {WHY[case]}" in report.halted
    assert "operator's GO, from broker order history" in report.halted
    assert report.accepted == []
    after = book.path.read_bytes() if book.path.exists() else None
    assert after == before                           # never recreated or reset


@pytest.mark.parametrize("case", ["missing", "empty"])
def test_the_dry_run_still_plans_without_a_ledger(tmp_path: Path, case: str) -> None:
    book = ledger_at(tmp_path, BROKEN[case])
    day = MON_OVERLAP.date() - timedelta(days=1)
    result = anchors.run_dry(
        inputs=anchors.Inputs(list(IDENTITIES), quotes_on(day), fx_on(day)),
        reader=FakeReader(exchanges=calendar(MON_OVERLAP.date())),
        ledger=book, now=MON_OVERLAP, root=tmp_path)
    assert result.rows                                # it planned
    assert book.path.exists() == (case != "missing")  # and wrote nothing


def test_unusable_is_empty_for_a_real_ledger(tmp_path: Path) -> None:
    book = ledger_at(tmp_path, '{"kind": "PRE_EXISTING", "intent_id": "p1", '
                               '"ticker": "X_US_EQ", "quantity": 1}\n')
    assert book.unusable() == ""
