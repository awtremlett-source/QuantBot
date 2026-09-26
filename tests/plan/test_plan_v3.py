"""The V3 plan gate: the two-part design must say what was actually agreed.

PLAN_V3 is the plan every later box builds on, so the things that are easiest to
lose are pinned here rather than trusted to memory:

* the operator's own words, typos and all -- a tidied quote is no longer evidence;
* the sixteen decisions, each with a named ENFORCER, because a rule with nothing
  to enforce it is a wish;
* the figures he actually chose (70/30, the 25% primary cap, the 10%/15% brakes,
  the 12-month limit), because round numbers drift when nobody is watching;
* every stage carrying a way to tell when it is finished;
* and the trail from V2 to V3, so the superseded plan cannot be picked up by
  mistake.

Written RED before the plan existed (SCARS #2).

This file never touches tests/plan/test_plan_v2.py. The V2 gate is evidence
about V2 and stays exactly as it was.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.wall.test_forbidden_paths import FORBIDDEN

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN_V3 = REPO_ROOT / "docs" / "plan" / "PLAN_V3.md"
PLAN_V2 = REPO_ROOT / "docs" / "plan" / "PLAN_V2.md"
CLAUDE = REPO_ROOT / "CLAUDE.md"

REQUIRED_SECTIONS: tuple[str, ...] = (
    "Operator words",
    "The two parts",
    "Decisions",
    "Carried from V2",
    "Superseded in V2",
    "Stages",
    "Premortem",
    "DECISION REQUESTED",
    "Sources",
)

# The operator's own words, 2026-09-21 -> 2026-09-26. Typos are HIS and are kept.
OPERATOR_WORDS: tuple[str, ...] = (
    "forget the £10k, we are looking for percentages.",
    "I Want to create a short term bot that tries its hardest to immitate the "
    "jim simons strategy, and a manual large trader advisor that will "
    "automatically suggest long term strategies that advise staying, falling out "
    "of a stock and suggesting new stock. nothing should be held for more than a "
    "year.",
    "You can break rules if you want to in order to make this happen.",
    "both, all trades available on Trading 212.",
    "The Advisor should track as many holdings as i want, perhaps it can use the "
    "50%/25%/12.5% etc method of the 70% the advisor has in total of the holding "
    "investments. reguardless it shouldnt have a limit.",
    "the massive amount of money as a 30%+ investment was a bad idea, however i "
    "still believe a strong primary investment isa good idea.",
    "The escape would be a moving stop that follows the trends untill theres a "
    "massive fall that triggers that moving stop. theoretically the same should "
    "be the case with every trade, advisor and bot. even the opposite for the "
    "bot, a moving buy that triggers when a stock reaches a potential big climb "
    "with confidence.",
    "The goal for the bot at least, is to be able to leave it alone and profit by "
    "doing nothing while it works. the advior will generally be a guide that "
    "drives the manual investments course.",
    "the bot should be a ground for improvement and constantly iterating and "
    "improving itself, it should not get less for doing a worse job, it should be "
    "more precise and evolve.",
    "If the bot really does THAT badly we can talk about changing it after "
    "testing, eg: probably making the 30%/70% scalable by the user or even moving "
    "to an all advisor setup, but the dream is to have it all automated honestly.",
    "A phone alert should be the last thing to do, unless you can send a message "
    "directly from the Trading 212 app on mobile.",
    "im using an ISA account, but before that we are using a paper trader.",
)

DECISION_IDS: tuple[str, ...] = tuple(f"P{n}" for n in range(1, 17))
STAGE_IDS: tuple[str, ...] = tuple(f"S{n}" for n in range(14))
STAGE_LINES: tuple[str, ...] = ("Exit gate:", "Enforcer:", "Built/Wired/Armed:")

# Figures he chose. A round number nobody guards is a round number that drifts.
PINNED_FIGURES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("P2", ("70%", "30%", "not shrunk")),
    ("P8", ("25%",)),
    ("P12", ("10%", "15%")),
    ("P13", ("12 months",)),
)

BUDGETS: tuple[tuple[str, int], ...] = (
    ("CLAUDE.md", 3_600),        # tightened by QT-04, from 4,000
    ("GRAND_TODO.md", 10_000),
)

TOUCHED: tuple[str, ...] = (
    "docs/plan/PLAN_V3.md",
    "docs/plan/PLAN_V2.md",
    "tests/plan/test_plan_v3.py",
    "CLAUDE.md",
    "GRAND_TODO.md",
    "STATE.md",
    "docs/archive/GRAND_TODO_v2.md",
)


def plan_text() -> str:
    assert PLAN_V3.is_file(), f"the plan does not exist yet: {PLAN_V3}"
    return PLAN_V3.read_text(encoding="utf-8")


def flattened() -> str:
    """The plan with its layout collapsed, for comparing words not wrapping."""
    return " ".join(plan_text().split())


def _blocks(text: str, pattern: str) -> dict[str, str]:
    marker = re.compile(pattern, re.MULTILINE)
    matches = list(marker.finditer(text))
    out: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        out[match.group(1)] = text[match.start():end]
    return out


def decision_blocks() -> dict[str, str]:
    return _blocks(plan_text(), r"^\*\*(P\d+)\b")


def stage_blocks() -> dict[str, str]:
    return _blocks(plan_text(), r"^###\s+(S\d+)\b")


# ------------------------------------------------------------------- (a) ---

def test_the_plan_exists_and_carries_every_required_section() -> None:
    lowered = plan_text().lower()
    missing = [s for s in REQUIRED_SECTIONS if s.lower() not in lowered]
    assert missing == [], f"the plan is missing sections: {missing}"


# ------------------------------------------------------------------- (b) ---

@pytest.mark.parametrize("quote", OPERATOR_WORDS,
                         ids=[f"quote{n}" for n in range(len(OPERATOR_WORDS))])
def test_the_operator_words_are_quoted_exactly(quote: str) -> None:
    assert " ".join(quote.split()) in flattened(), (
        f"the plan does not quote the operator exactly: {quote[:60]!r}...")


def test_the_quotes_are_dated_and_marked_verbatim() -> None:
    text = plan_text()
    assert "verbatim" in text.lower()
    assert "2026-09-21" in text and "2026-09-26" in text


# ------------------------------------------------------------------- (c) ---

def test_every_decision_is_present() -> None:
    blocks = decision_blocks()
    missing = [p for p in DECISION_IDS if p not in blocks]
    assert missing == [], f"the plan is missing decisions: {missing}"
    assert len(blocks) == len(DECISION_IDS), (
        f"unexpected decisions: {sorted(set(blocks) - set(DECISION_IDS))}")


@pytest.mark.parametrize("decision", DECISION_IDS)
def test_every_decision_names_a_non_empty_enforcer(decision: str) -> None:
    """A rule with nothing to enforce it is a wish."""
    block = decision_blocks().get(decision, "")
    assert block, f"{decision} has no block"
    assert "Enforcer:" in block, f"{decision} names no Enforcer"
    tail = block.split("Enforcer:", 1)[1].strip()
    assert len(tail) >= 15, f"{decision}'s Enforcer says nothing useful: {tail!r}"


# ------------------------------------------------------------------- (d) ---

@pytest.mark.parametrize(("decision", "figures"), PINNED_FIGURES,
                         ids=[p for p, _ in PINNED_FIGURES])
def test_the_chosen_figures_are_written_down(
        decision: str, figures: tuple[str, ...]) -> None:
    block = " ".join(decision_blocks().get(decision, "").split())
    assert block, f"{decision} has no block"
    missing = [f for f in figures if f not in block]
    assert missing == [], f"{decision} is missing its figures: {missing}"


def test_untested_numbers_are_labelled_as_starting_figures() -> None:
    """An untested number believed is how a plan becomes a guess."""
    assert "starting figure" in flattened().lower()


# ------------------------------------------------------------------- (e) ---

def test_every_stage_is_present() -> None:
    missing = [s for s in STAGE_IDS if s not in stage_blocks()]
    assert missing == [], f"the plan is missing stages: {missing}"


@pytest.mark.parametrize("stage", STAGE_IDS)
def test_every_stage_states_its_gate_enforcer_and_checklist(stage: str) -> None:
    block = stage_blocks().get(stage, "")
    assert block, f"{stage} has no block in the plan"
    missing = [line for line in STAGE_LINES if line not in block]
    assert missing == [], f"{stage} is missing: {missing}"


def test_the_last_stage_is_the_phone_alerts() -> None:
    """He asked for it last, so it is last -- not quietly promoted."""
    blocks = stage_blocks()
    last = max(blocks, key=lambda name: int(name[1:]))
    assert last == "S13", f"the highest stage is {last}, expected S13"
    assert "phone alert" in blocks[last].lower()


def test_s1_is_recorded_as_already_done() -> None:
    assert "22c67f7" in stage_blocks().get("S1", "")


# ------------------------------------------------------------------- (f) ---

def test_plan_v2_opens_with_a_banner_pointing_here() -> None:
    opening = "\n".join(PLAN_V2.read_text(encoding="utf-8").splitlines()[:8])
    assert "PLAN_V3.md" in opening, (
        "PLAN_V2 must say, at the top, that it has been superseded")
    assert "supersede" in opening.lower()


def test_claude_md_points_at_the_current_plan() -> None:
    assert "docs/plan/PLAN_V3.md" in CLAUDE.read_text(encoding="utf-8")


def test_the_v2_plan_is_kept_not_deleted() -> None:
    assert PLAN_V2.is_file()
    assert "Operator words" in PLAN_V2.read_text(encoding="utf-8")


# ------------------------------------------------------------------- (g) ---

@pytest.mark.parametrize(("name", "budget"), BUDGETS)
def test_the_working_memory_stays_inside_its_budget(name: str, budget: int) -> None:
    size = len((REPO_ROOT / name).read_text(encoding="utf-8"))
    assert size <= budget, f"{name} is {size} chars, over its {budget} budget"


@pytest.mark.parametrize("relative", TOUCHED)
def test_nothing_this_box_touched_names_the_isolated_project(
        relative: str) -> None:
    path = REPO_ROOT / relative
    assert path.is_file(), f"expected this box to have written {relative}"
    lowered = path.read_text(encoding="utf-8", errors="replace").lower()
    assert [t for t in FORBIDDEN if t in lowered] == []
    assert [t for t in FORBIDDEN if t in relative.lower()] == []


# ------------------------------------------- the plan's own honesty, again ---

def test_broker_facts_are_cited_or_marked_unverified() -> None:
    assert "UNVERIFIED" in plan_text()


def test_the_search_loop_still_may_not_stop_on_profit() -> None:
    upper = flattened().upper()
    assert "NEVER ON PROFIT" in upper or "NEVER PROFIT" in upper


def test_the_advisor_only_ever_suggests() -> None:
    """The one thing that must not be misread: it does not trade for him."""
    lowered = flattened().lower()
    assert "only suggests" in lowered or "only ever suggests" in lowered
