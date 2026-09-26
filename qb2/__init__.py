"""qb2 — QuantBot v2: the two-part system (the bot and the advisor).

SKELETON ONLY. Every subpackage below is importable and deliberately empty of
logic: no signals, no model, no orders, nothing that could place a trade. The
plan that fills them is docs/plan/PLAN_V2.md (and the revision that follows it).

Why a new package instead of editing v1: v1 is producing a live forward paper
record, and its value is that nothing has been changed underneath it. v1 keeps
running untouched on its frozen environment and remains the baseline v2 has to
beat out-of-sample at 2x costs. qb2 has its own single environment
(requirements-qb2.txt -> .venv-qb2, see docs/plan/ENV_QB2.md), which is the real
fix for the pandas/yfinance pin conflict that forces v1 to run two.

qb2 never imports a v1 engine package, and v1 never imports qb2. tests/wall/
enforces both directions.
"""
