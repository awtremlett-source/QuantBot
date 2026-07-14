"""Command-line entry point for the paper-trading loop.

Usage::

    python -m execution.paper_loop --db data/quantbot.db [--dry-run]

(``python -m execution`` is an alias for the same CLI.) Safe to run at any time,
any day, repeatedly: catch-up, idempotency, and the killswitch are handled inside
:mod:`execution.paper_loop`.
"""

from __future__ import annotations

from execution.paper_loop import main

if __name__ == "__main__":
    raise SystemExit(main())
