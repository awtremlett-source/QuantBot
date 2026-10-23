"""Each pot's brake, measured from that pot's own peak (PLAN_V3 P12; QT-16 B2).

* **Down 10%** from the pot's own peak: no new buys, and its stops tighten
  (stops.unsettled). The brake clears when the pot is back within 5% of its peak
  -- the 5% is a STARTING FIGURE.
* **Down 15%:** the BOT pauses; only the operator's own words clear it, entered
  with ``python -m qb2.tools.clear_pause --words "..."``, recorded verbatim (empty
  words refused). His words restart the bot's measuring: the peak becomes that
  day's value -- otherwise the pause would clear into a 10% brake that a bot which
  cannot buy (it holds cash) could never climb out of. The ADVISOR says "hold off",
  and since QT-23 that too clears ONLY on his words (``--pot advisor``), restarting
  its peak that day. Operator, 2026-10-19 (verbatim): "GO on the advisor's brake:
  after an urgent exit, my own words clear the advisor's hold-off and restart its
  peak from that day, as for the bot's pause; no code clears it." 
* After an URGENT EXIT his words clear the advisor's 10% brake too (QT-24): its pot is
  then cash, which never climbs back within 5%, so the re-buy would wait for ever.
  Operator, 2026-10-23 (verbatim): "GO on the advisor's 10% brake: after an urgent
  exit, my own words also clear the advisor's 10% brake and restart its peak from that
  day." Before an exit, and for the bot, the 10% brake clears only as above.
* 10% and 15% are P12's own figures, tested against 2008, 2020 and 2022 in
  docs/research/brake_replay_2026-10.md; they are NOT changed here.

State is append-only JSON lines (data/qb2/brakes.jsonl), so it survives a restart.
No saved state for a pot = no buys from it: a brake that was never measured is not
a brake that is off.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from qb2.execution.safety import ADVISOR, BOT, Blocked

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE = REPO_ROOT / "data" / "qb2" / "brakes.jsonl"

BRAKE = 0.10                 # P12: no new buys, stops tighten
PAUSE = 0.15                 # P12: the bot pauses; the advisor says hold off
CLEAR_WITHIN = 0.05          # STARTING FIGURE: the brake clears back within 5% of peak
OK, BRAKED, PAUSED, HOLD_OFF = "OK", "BRAKE-10", "PAUSED-15", "HOLD-OFF-15"


@dataclass(frozen=True, slots=True)
class State:
    pot: str
    peak: float
    value: float
    level: str
    at: str

    @property
    def drawdown(self) -> float:
        return self.value / self.peak - 1.0


def step(prev: State | None, pot: str, value: float, at: str) -> State:
    """The next state from the last one and today's value. Pure."""
    if pot not in (BOT, ADVISOR):
        raise Blocked(f"no brake for pot {pot!r}: brakes are the bot's and the advisor's")
    if value is None or not math.isfinite(value) or value <= 0:
        raise Blocked(f"the {pot} pot's value {value!r} is not a value -- nothing measured")
    peak = value if prev is None else max(prev.peak, value)
    fall, was = value / peak - 1.0, OK if prev is None else prev.level
    if was == (PAUSED if pot == BOT else HOLD_OFF):
        level = was                                       # only his words clear it (GO 2)
    elif fall <= -PAUSE:
        level = PAUSED if pot == BOT else HOLD_OFF
    elif was == BRAKED and fall < -CLEAR_WITHIN:
        level = was                                       # not yet back within 5%
    elif fall <= -BRAKE:
        level = BRAKED
    else:
        level = OK
    return State(pot, peak, value, level, at)


def check_buy(state: State | None, pot: str) -> None:
    """Sender check 6 (bot) and the suggestion check (advisor)."""
    if state is None:
        raise Blocked(f"no brake state saved for the {pot} pot -- no buys until it is "
                      "measured (a missing brake is not an off brake)")
    if state.pot != pot:
        raise Blocked(f"brake state is the {state.pot} pot's, not the {pot} pot's")
    if state.level != OK:
        raise Blocked(f"the {pot} pot is {state.drawdown:.1%} from its peak ({state.level}): "
                      "no new buys")


def tighten(state: State | None) -> bool:
    """Stops tighten while the brake is on -- or when nobody knows (fail closed)."""
    return state is None or state.level != OK


def advisor_message(state: State | None) -> str:
    if state is None:
        return "no new buys: the advisor pot's brake has no saved state"
    return {OK: "", BRAKED: "no new buys: the pot is down 10% from its peak",
            HOLD_OFF: "hold off: the pot is down 15% from its peak"}.get(state.level, "")


class Brakes:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DEFAULT_STATE

    def _write(self, row: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    def state(self, pot: str) -> State | None:
        if not self.path.is_file():
            return None
        found = None
        for n, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise Blocked(f"brake state line {n} is unreadable -- no buys") from exc
            if row.get("pot") == pot and "level" in row:
                found = State(pot, row["peak"], row["value"], row["level"], row["at"])
        return found

    def update(self, pot: str, value: float, at: datetime | None = None) -> State:
        stamp = (at or datetime.now(timezone.utc)).isoformat(timespec="seconds")
        new = step(self.state(pot), pot, value, stamp)
        self._write({"event": "measured", "pot": pot, "peak": new.peak, "value": new.value,
                     "level": new.level, "at": new.at})
        return new

    def clear_pause(self, words: str, at: datetime | None = None, pot: str = BOT, *,
                    after_exit: bool = False) -> State:
        """The bot's 15% pause -- or the advisor's hold-off (GO 2), or after an urgent exit its
        10% brake (QT-24) -- cleared by the operator's own words, nothing else; the pot's peak
        restarts at that day's value."""
        if not words or not words.strip():
            raise Blocked("empty words refused: only the operator's own words clear the pause")
        held = (PAUSED,) if pot == BOT else (HOLD_OFF, BRAKED) if after_exit else (HOLD_OFF,)
        now = self.state(pot)
        if now is None or now.level not in held:
            why = (" -- the advisor's 10% brake is yours to clear only after an urgent exit"
                   if pot == ADVISOR and now is not None and now.level == BRAKED else "")
            raise Blocked(f"the {pot} pot is not {'paused' if pot == BOT else 'held off'} "
                          f"({now.level if now else 'no state'}); nothing to clear{why}")
        stamp = (at or datetime.now(timezone.utc)).isoformat(timespec="seconds")
        self._write({"event": "cleared", "pot": pot, "words": words, "at": stamp,
                     "was_peak": now.peak})
        fresh = State(pot, now.value, now.value, OK, stamp)
        self._write({"event": "restarted", "pot": pot, "peak": fresh.peak,
                     "value": fresh.value, "level": OK, "at": stamp})
        return fresh
