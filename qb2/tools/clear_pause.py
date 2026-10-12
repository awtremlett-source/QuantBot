"""The operator's hand tool: clear the bot's 15% pause with his own words (P12).

Only his words clear the pause -- no code path does. The words are recorded
verbatim in the brake state (data/qb2/brakes.jsonl); empty words are refused, and
so is a clear when the bot is not paused. Clearing restarts the bot's measuring
from that day's value (qb2/guard/brakes.py says why).

CLI: ``python -m qb2.tools.clear_pause --words "GO: ..."``
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from qb2.execution.safety import Blocked
from qb2.guard import brakes


def main(argv: Sequence[str] | None = None, *, state: Path | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clear the bot's 15% pause.")
    parser.add_argument("--words", required=True, help="your own words, verbatim")
    args = parser.parse_args(argv)
    try:
        fresh = brakes.Brakes(state).clear_pause(args.words)
    except Blocked as why:
        print(f"NOT cleared: {why}")
        return 1
    print(f"Cleared with your words, recorded verbatim. The bot's peak restarts at "
          f"£{fresh.peak:,.2f}; its brake is {fresh.level}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
