"""The plan gate: the revised plan must exist, and must say what it promised.

A plan is a promise about what will be built and in what order. This test is
what stops it quietly becoming something else: the operator's own words are
pinned here as constants, so if the plan is ever edited away from what he
actually asked for, this goes red rather than the drift going unnoticed.

It also holds the two shapes that make a stage a stage rather than a wish --
an EXIT GATE (how you know it is finished), an ENFORCER (the test or monitor
that keeps it finished) and a BUILT/WIRED/ARMED checklist (so "written" is
never mistaken for "running") -- plus the two token budgets that keep the
working memory readable, and the standing ban on the isolated project's name.

Written RED before the plan existed (SCARS #2: a test that fails on the old
state ships with every change).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.wall.test_forbidden_paths import FORBIDDEN

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN = REPO_ROOT / "docs" / "plan" / "PLAN_V2.md"

# The headings the plan must carry, in plain words.
REQUIRED_SECTIONS: tuple[str, ...] = (
    "Operator words",
    "What stays",
    "What changes",
    "Stages",
    "Premortem",
    "DECISION REQUESTED",
    "Sources",
)

# The operator's own words, 2026-09-20/21. Typos included ON PURPOSE: these are
# quotes, not prose, and a quote that has been tidied up is no longer evidence.
OPERATOR_WORDS: tuple[str, ...] = (
    "re-writing the quant bot to find mathmatical strategys to edge out small "
    "margins of money from patterns found in stock markets, even small amounts. "
    "Taking Strategies from Jim Simons as well as a strategy to split the "
    "holdings of stocks by 50% everytime a new trade is made. eg: 50% 25% 12.5% "
    "etc. most of Quant bot should already be built and the UI of TradeScout "
    "still needs work in revamping. Using Trading 212's API to make those "
    "trades, and using yfinance to make the quickest trades it can. building "
    "small increments to a large sum overtime, a fast trader but automatically "
    "and mathatically precise.",
    "the 50% 25% is based on confidence of the trade, we could even do a slower "
    "decline making everything more even, like 25% 20% 15%, and then exponetally "
    "carried on. if that worries you too much we can use that. there is also a "
    "limit to how many trades can happen with trading 212 per day or something, "
    "we need to find the balance in how fast and what yfinance says and what "
    "trading 212 allows.",
    "I want to combine them, not just add more features",
    "lets move more towards Simon's",
    "we are still finding a strategy",
)

# Every stage the plan commits to, S0 through S11.
STAGE_IDS: tuple[str, ...] = tuple(f"S{n}" for n in range(12))

# The three lines that turn a stage into something checkable.
STAGE_LINES: tuple[str, ...] = ("Exit gate:", "Enforcer:", "Built/Wired/Armed:")

# Budgets from CLAUDE.md's own token rules.
BUDGETS: tuple[tuple[str, int], ...] = (
    ("CLAUDE.md", 4_000),
    ("GRAND_TODO.md", 10_000),
)

# Everything this box writes or edits. All of it must stay free of the banned
# name, and the paths themselves must too.
TOUCHED: tuple[str, ...] = (
    "docs/plan/PLAN_V2.md",
    "tests/plan/test_plan_v2.py",
    "tests/plan/__init__.py",
    "CLAUDE.md",
    "GRAND_TODO.md",
    "STATE.md",
    "docs/merge/MERGE_PLAN.md",
    "docs/archive/GRAND_TODO_v1.md",
)


def plan_text() -> str:
    assert PLAN.is_file(), f"the plan does not exist yet: {PLAN}"
    return PLAN.read_text(encoding="utf-8")


def stage_blocks(text: str) -> dict[str, str]:
    """Split the Stages section into one block per stage heading."""
    blocks: dict[str, str] = {}
    pattern = re.compile(r"^###\s+(S\d+)\b(.*)$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        blocks[match.group(1)] = text[match.start():end]
    return blocks


# ------------------------------------------------------------------- (a) ---

def test_the_plan_exists_and_carries_every_required_section() -> None:
    text = plan_text()
    missing = [s for s in REQUIRED_SECTIONS if s.lower() not in text.lower()]
    assert missing == [], f"the plan is missing sections: {missing}"


# ------------------------------------------------------------------- (b) ---

@pytest.mark.parametrize("quote", OPERATOR_WORDS,
                         ids=[f"quote{n}" for n in range(len(OPERATOR_WORDS))])
def test_the_operator_words_are_quoted_exactly(quote: str) -> None:
    """Verbatim, typos and all -- a tidied quote is no longer evidence."""
    # Markdown block quotes and wrapping may add "> " and newlines; compare the
    # words themselves, not the layout.
    flattened = " ".join(plan_text().split())
    assert " ".join(quote.split()) in flattened, (
        f"the plan does not quote the operator exactly: {quote[:60]!r}...")


def test_the_quotes_are_dated_and_marked_verbatim() -> None:
    text = plan_text()
    assert "verbatim" in text.lower()
    assert "2026-09-20" in text and "2026-09-21" in text


# ------------------------------------------------------------------- (c) ---

def test_every_stage_is_present() -> None:
    blocks = stage_blocks(plan_text())
    missing = [s for s in STAGE_IDS if s not in blocks]
    assert missing == [], f"the plan is missing stages: {missing}"


@pytest.mark.parametrize("stage", STAGE_IDS)
def test_every_stage_states_its_gate_enforcer_and_checklist(stage: str) -> None:
    """A stage without these three is a wish, not a stage."""
    block = stage_blocks(plan_text()).get(stage, "")
    assert block, f"{stage} has no block in the plan"
    missing = [line for line in STAGE_LINES if line not in block]
    assert missing == [], f"{stage} is missing: {missing}"


# ------------------------------------------------------------------- (d) ---

@pytest.mark.parametrize(("name", "budget"), BUDGETS)
def test_the_working_memory_stays_inside_its_budget(name: str, budget: int) -> None:
    size = len((REPO_ROOT / name).read_text(encoding="utf-8"))
    assert size <= budget, f"{name} is {size} chars, over its {budget} budget"


# ------------------------------------------------------------------- (e) ---

@pytest.mark.parametrize("relative", TOUCHED)
def test_nothing_this_box_touched_names_the_isolated_project(
        relative: str) -> None:
    path = REPO_ROOT / relative
    assert path.is_file(), f"expected this box to have written {relative}"
    lowered = path.read_text(encoding="utf-8", errors="replace").lower()
    assert [t for t in FORBIDDEN if t in lowered] == []
    assert [t for t in FORBIDDEN if t in relative.lower()] == []


# ------------------------------------------------- the plan's own honesty ---

def test_unverified_numbers_are_labelled_unverified() -> None:
    """Broker fees and limits are claims about the world, not design choices.

    The plan may not state one as fact without a cited page and the date it was
    checked; until then it must say UNVERIFIED out loud.
    """
    text = plan_text()
    assert "UNVERIFIED" in text, (
        "the plan quotes no broker figures as unverified -- either cite them "
        "with a URL and a date, or mark them UNVERIFIED")


def test_the_search_loop_may_not_stop_on_profit() -> None:
    """SCARS #21, written into the plan rather than remembered."""
    flattened = " ".join(plan_text().split()).upper()
    assert "NEVER ON PROFIT" in flattened or "NEVER PROFIT" in flattened
