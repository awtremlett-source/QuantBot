"""The operator's hand tool: clear the bot's 15% pause -- or, since QT-23, the advisor's
hold-off (``--pot advisor``, his GO of 2026-10-19), and since QT-24 the advisor's 10% brake
after an urgent exit (his GO of 2026-10-23) -- with his own words (P12).

Only his words clear the pause -- no code path does. The words are recorded
verbatim in the brake state (data/qb2/brakes.jsonl); empty words are refused, and
so is a clear when the bot is not paused. Clearing restarts the bot's measuring
from that day's value (qb2/guard/brakes.py says why).

CLI: ``python -m qb2.tools.clear_pause --words "GO: ..." [--pot advisor]``
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from qb2.advisor import engine
from qb2.advisor import state as record
from qb2.execution.safety import Blocked
from qb2.guard import brakes


def main(argv: Sequence[str] | None = None, *, state: Path | None = None,
         advisor: record.Paths | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clear the bot's 15% pause, or the advisor's hold-off "
                                                 "(or, after an urgent exit, its 10% brake).")
    parser.add_argument("--words", required=True, help="your own words, verbatim")
    parser.add_argument("--pot", choices=("bot", "advisor"), default="bot")
    args = parser.parse_args(argv)
    try:
        exited = args.pot == "advisor" and engine.after_exit(advisor or record.Paths.default())
        fresh = brakes.Brakes(state).clear_pause(args.words, pot=args.pot, after_exit=exited)
    except Blocked as why:
        print(f"NOT cleared: {why}")
        return 1
    print(f"Cleared with your words, recorded verbatim. The {args.pot}'s peak restarts at "
          f"£{fresh.peak:,.2f}; its brake is {fresh.level}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
