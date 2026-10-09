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

import hashlib
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
    "the project will LATER be ported to a always on home PC, that comes at the "
    "very end of development.",
    "well the stop needs to come from either Trading 212 or the algorithm.",
    "the bot trades very short (same day), holds nothing when the PC is off or "
    "overnight, sells before shutdown including pre-market; add power-off "
    "detection, UPS, auto-restart and an outside watchdog to the home-PC stage "
    "(S13); test BOTH markets to the limit after costs — US shares (live "
    "yfinance prices, currency fee), London (cheap, prices 20 min late) and a "
    "mix — every attempt counted.",
)

# P18/P19 agreed 2026-10-03, P20 agreed 2026-10-04 -- all added verbatim.
DECISION_IDS: tuple[str, ...] = tuple(f"P{n}" for n in range(1, 21))
STAGE_IDS: tuple[str, ...] = (
    "S0", "S1", "S2a", "S2b", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "S10",
    "S11", "S12", "S13", "S14", "S15",
)
STAGE_LINES: tuple[str, ...] = ("Exit gate:", "Enforcer:", "Built/Wired/Armed:")

# Figures he chose. A round number nobody guards is a round number that drifts.
PINNED_FIGURES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("P2", ("70%", "30%", "not shrunk")),
    ("P8", ("25%",)),
    ("P12", ("10%", "15%")),
    ("P13", ("12 months",)),
)

BUDGETS: tuple[tuple[str, int], ...] = (
    ("CLAUDE.md", 4_000),        # "must stay ≤4k chars" (LEAN-CODE GO 2026-10-05); QT-04 had 3,600
    ("GRAND_TODO.md", 10_000),
    ("STATE.md", 6_000),          # read every resume; history → docs/archive (GO 2026-10-05)
    ("docs/MANIFEST.md", 8_000),
)

# Read at every resume, so a reversed rule here is acted on, not just misfiled.
ALWAYS_READ: tuple[str, ...] = ("CLAUDE.md", "STATE.md")

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
    return _blocks(plan_text(), r"^###\s+(S\d+[a-z]?)\b")


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


def _stage_order(name: str) -> tuple[int, str]:
    digits = "".join(c for c in name[1:] if c.isdigit())
    letter = name[1 + len(digits):]
    return int(digits), letter


def test_the_last_stage_is_the_phone_alerts() -> None:
    """He asked for it last, so it is last -- not quietly promoted."""
    blocks = stage_blocks()
    last = max(blocks, key=_stage_order)
    assert last == "S15", f"the highest stage is {last}, expected S15"
    assert "phone alert" in blocks[last].lower()


def test_the_home_pc_move_comes_before_any_real_money() -> None:
    """He put the home-PC port at "the very end"; real money waits for it.

    The stop is run by our own code (P10), so it only watches prices while the
    machine is awake. Real money before the always-on machine would mean a stop
    that sleeps when the laptop does.
    """
    text = plan_text()
    home = text.index("### S13")
    isa = text.index("### S14")
    assert home < isa, "S13 (the home PC) must come before S14 (the ISA)"
    assert "home" in stage_blocks()["S13"].lower()
    assert "isa" in stage_blocks()["S14"].lower()


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


# ------------------------------------------------- QT-06: the broker facts ---

FACTS = REPO_ROOT / "docs" / "t212" / "FACTS.md"


def test_the_broker_facts_file_exists_and_dates_every_row() -> None:
    assert FACTS.is_file(), "docs/t212/FACTS.md is missing"
    body = FACTS.read_text(encoding="utf-8")
    assert "2026-09-27" in body
    for status in ("VERIFIED", "UNVERIFIED", "CONTRADICTED"):
        assert status in body, f"no row is marked {status}"
    assert "docs.trading212.com" in body, "no row cites a source URL"


def test_the_plan_points_broker_claims_at_the_facts_file() -> None:
    """A fact in the plan must be traceable to the row that was checked."""
    assert "docs/t212/FACTS.md" in plan_text() or "t212/FACTS.md" in plan_text()


def test_the_stop_is_run_by_our_own_code() -> None:
    """The decisive finding: the broker has no trailing stop and no amend.

    So P10's stop cannot live at Trading 212. It is ours to run -- which is the
    half of his sentence that survives contact with the documentation.
    """
    block = " ".join(decision_blocks()["P10"].split()).lower()
    assert "algorithm" in block, "P10 must say the algorithm holds the stop"
    assert "facts.md" in block, "P10 must cite the checked facts"
    for kept in ("raised", "never lowered"):
        assert kept in block, f"P10 lost its {kept!r} rule"


def test_the_premortem_guards_the_two_new_dangers() -> None:
    lowered = flattened().lower()
    assert "duplicate" in lowered, "no guard for duplicate orders (FACTS row e)"
    assert "pending orders" in lowered, "the duplicate guard must check pending orders"
    assert "asleep" in lowered or "laptop off" in lowered or "while the laptop" in lowered


def test_stage_s2_is_split_into_a_and_b() -> None:
    blocks = stage_blocks()
    assert "read-only" in blocks["S2a"].lower()
    assert "cost model" in blocks["S2b"].lower()
    assert "S2" not in blocks, "the old undivided S2 is still present"


# --------------------------------------------------- QT-07: the same-day bot ---

def test_the_bot_is_same_day_and_holds_nothing_overnight() -> None:
    """P4 reversed: "holds days" is gone, and the reason is written down."""
    block = " ".join(decision_blocks()["P4"].split()).lower()
    assert "same day" in block, "P4 must say the bot trades same day"
    for promise in ("overnight", "shutdown", "flat"):
        assert promise in block, f"P4 does not mention {promise!r}"
    assert "15 min" in block or "15 minutes" in block, (
        "P4 must state the last-sell margin before close")
    assert "starting figure" in block, (
        "the 15-minute margin is untested and must say so")


def test_the_bot_never_buys_into_a_closed_market() -> None:
    block = " ".join(decision_blocks()["P4"].split()).lower()
    assert "closed" in block
    assert "queued" in block, (
        "P4 must explain WHY: a queued buy would fill unwatched (FACTS j2)")


def test_the_old_multi_day_wording_survives_only_where_it_is_superseded() -> None:
    """A reversed rule left lying around elsewhere is how a plan lies."""
    text = plan_text()
    superseded_at = text.lower().index("superseded in v2")
    stages_at = text.index("## Stages")
    # Naming the old rule in order to say it was replaced is fine -- that is
    # how a record stays readable. What must not survive is the old rule stated
    # as though it were still true.
    # These four cannot match inside another word. "old " could -- it hides in
    # "hold and", which is how an earlier version of this test let a planted
    # live rule through.
    replacement_markers = ("replac", "supersede", "reversed", "no longer")
    for stale in ("holds days", "days not weeks", "daily horizon"):
        for position in _positions(text.lower(), stale):
            if superseded_at <= position < stages_at:
                continue
            context = text.lower()[max(0, position - 120):position]
            assert any(marker in context for marker in replacement_markers), (
                f"{stale!r} appears at character {position} as a LIVE rule -- "
                f"it was reversed on 2026-09-27; context: "
                f"...{text[max(0, position - 80):position + 40]}...")


@pytest.mark.parametrize("name", ALWAYS_READ)
def test_the_always_read_files_never_state_the_old_horizon(name: str) -> None:
    """No 'superseded' escape here: these files carry live rules only."""
    flat = " ".join((REPO_ROOT / name).read_text(encoding="utf-8").lower().split())
    assert [s for s in ("holds days", "days not weeks", "daily horizon")
            if s in flat] == []


def _positions(haystack: str, needle: str) -> list[int]:
    found: list[int] = []
    start = 0
    while True:
        at = haystack.find(needle, start)
        if at == -1:
            return found
        found.append(at)
        start = at + 1


def test_the_two_parts_table_says_same_day() -> None:
    table = plan_text()[plan_text().index("## The two parts"):
                        plan_text().index("**Shared by both")]
    assert "same day" in table.lower()


# ------------------------------------------------ QT-07: the markets test P17 ---

def test_p17_pre_registers_a_three_arm_both_markets_test() -> None:
    block = " ".join(decision_blocks()["P17"].split())
    lowered = block.lower()
    assert "pre-regist" in lowered, "P17 must be pre-registered BEFORE any result"
    for arm in ("us", "london", "mix"):
        assert arm in lowered, f"P17 is missing the {arm!r} arm"
    assert "1x" in lowered or "1×" in block, "P17 must test at 1x costs"
    assert "2x" in lowered or "2×" in block, "P17 must test at 2x costs"
    assert "delay" in lowered, "P17 must build each market's data delay in"
    assert "trials.jsonl" in lowered, "every attempt must be counted"
    assert "known-null" in lowered or "known null" in lowered


def test_p17_says_what_happens_when_nothing_passes() -> None:
    """The honest branch: no arm passes -> the bot stays off."""
    block = " ".join(decision_blocks()["P17"].split()).lower()
    assert "stays off" in block or "bot stays off" in block
    assert "never" in block and "loosen" in block


# ------------------------------------------- QT-07: pricing without a quote ----

def test_p14_is_redesigned_around_having_no_broker_quote() -> None:
    block = " ".join(decision_blocks()["P14"].split()).lower()
    assert "facts.md" in block or "row h" in block
    for check in ("age", "band", "cap"):
        assert check in block, f"P14 is missing the {check!r} check"
    assert "stop_new_trades" in block or "stop new trades" in block


# ------------------------------------------ QT-07: power safety on the home PC -

def test_s13_adds_the_four_power_safety_pieces() -> None:
    block = " ".join(stage_blocks()["S13"].split()).lower()
    for piece in ("power-off", "ups", "auto-restart", "watchdog"):
        assert piece in block, f"S13 is missing {piece!r}"
    assert "heartbeat" in block
    for drill in ("unplug", "kill", "network"):
        assert drill in block, f"S13's exit gate is missing the {drill!r} drill"


def test_the_laptop_gets_the_same_rules_from_the_first_demo_trade() -> None:
    lowered = " ".join(plan_text().split()).lower()
    assert "lid" in lowered, "the laptop phase must cover closing the lid"
    assert "battery" in lowered, "the laptop's battery is its UPS -- say so"


def test_s3_records_intraday_data_before_it_is_lost() -> None:
    block = " ".join(stage_blocks()["S3"].split()).lower()
    assert "intraday" in block
    assert "recorder" in block
    assert "fx" in block or "currency" in block


# --------------------------------------------- QT-07: FACTS row c stays honest -

def test_facts_row_c_cites_both_sources_and_stays_unresolved() -> None:
    """It must never quietly become VERIFIED on one source again."""
    body = FACTS.read_text(encoding="utf-8")
    row = next(line for line in body.splitlines() if line.startswith("| c |"))
    assert "docs.trading212.com" in row, "row c lost the API-reference source"
    assert "helpcentre.trading212.com" in row, "row c lost the help-centre source"
    assert "CONFLICT" in row and "UNRESOLVED" in row
    assert "**VERIFIED**" not in row, (
        "row c must not be marked VERIFIED: one source asserts it, the other is "
        "silent, and that is not corroboration")
    assert "S14" in row, "row c must name where it gets resolved"


def test_s14_will_not_go_live_until_row_c_is_settled() -> None:
    block = " ".join(stage_blocks()["S14"].split())
    assert "row c" in block.lower() or "FACTS" in block
    assert "stop" in block.lower()


# ------------------------------- QT-08: the two S2b gaps, carried to later gates ---

def test_s4_carries_the_cost_model_into_the_backtest() -> None:
    """S2b built the cost model but had no backtest to put it inside.

    That half of S2b's exit gate could not be met then, so it is carried here
    rather than quietly dropped -- which is how a gap becomes a hole.
    """
    block = " ".join(stage_blocks()["S4"].split()).lower()
    assert "cost model" in block, "S4 must require the S2b cost model be applied"
    assert "every simulated fill" in block
    assert "gross" in block and "net" in block
    assert "2x" in block or "2×" in stage_blocks()["S4"]


def test_s10_carries_the_killswitch_dry_run() -> None:
    """The other S2b half: no dry-run loop existed to halt."""
    block = " ".join(stage_blocks()["S10"].split()).lower()
    assert "dry run" in block
    assert "stop_new_trades" in block
    assert "flatten" in block


# ============================================================ S3b's two gates ==
# Both were written fail-first: each assertion was watched to fail on the plan as
# it stood before S3b, so neither can be deleted without the gate going red.

def test_s4_cannot_open_on_a_universe_nobody_agreed_to() -> None:
    """S3b proposed the bot's 50 names. Proposing is not agreeing.

    The failure this prevents is subtle and total: a firewall run against a list
    the operator never chose produces numbers that have to be thrown away, and
    nobody notices until the list is questioned much later.
    """
    gate = stage_blocks()["S4"]
    assert "AGREED" in gate
    assert "operator's own words" in gate
    assert "date" in gate.lower()


def _s3_exit_check() -> dict[str, str]:
    """QT-13: the S3 block carries one line, '- Exit check (...): item GREEN ·
    item RED · ...', each item judged against the gate on evidence."""
    lines = [line for line in stage_blocks()["S3"].splitlines()
             if line.startswith("- Exit check (")]
    assert len(lines) == 1, "S3 must carry exactly one exit-check line"
    items = re.findall(r"([^·:]+?) (GREEN|RED)\b", lines[0].split("):", 1)[1])
    return {name.strip(" *"): verdict for name, verdict in items}


def test_s3_is_done_only_when_every_exit_item_is_green() -> None:
    """Marking a stage DONE with an item red is the failure this guards.

    The check line names every gate item (and the stage's own promise, the
    quote delay, and its Wired line); DONE in the heading needs all GREEN, and
    any RED must leave the block saying NOT complete.
    """
    check = _s3_exit_check()
    assert len(check) >= 8, f"the exit check lost items: {sorted(check)}"
    heading = stage_blocks()["S3"].splitlines()[0]
    red = sorted(name for name, verdict in check.items() if verdict == "RED")
    if "DONE" in heading:
        assert not red, f"S3 is marked DONE with items red: {red}"
    if red:
        assert "NOT complete" in stage_blocks()["S3"], (
            f"items red ({red}) but the block does not say NOT complete")


# ------------------------------------------- QT-11a: the minute rule, P18 ---

def test_p18_is_recorded_in_the_operators_own_words() -> None:
    """A rule that lives only in code is a rule the plan cannot check.

    P18 was proposed in STATE and agreed on 2026-10-03. The words and the date are
    pinned here for the same reason every other operator decision is: so that a
    later edit has to be deliberate and visible in a diff.
    """
    block = decision_blocks()["P18"]
    assert "Minute bars are only used where minute bars exist" in block
    assert "2026-10-03" in block
    assert "GO on P18" in block, "the operator's own words must be quoted"


def test_p18_says_plainly_that_it_changes_no_gate() -> None:
    """THE thing this rule must never become: a back door around the 95% bar.

    If labelling could remove names from the census, a gate could be made to pass
    by relabelling rather than by fixing the data. The plan has to say so, because
    the plan is what a future box checks itself against.
    """
    block = " ".join(decision_blocks()["P18"].split())
    assert "changes no gate" in block
    assert "every name in the active universe" in block
    assert "beside that figure, never inside it" in block


def test_p18_carries_both_halves_of_the_rule_and_an_enforcer() -> None:
    """Cautious by default, demotion immediate, promotion needing two passes."""
    block = " ".join(decision_blocks()["P18"].split()).lower()
    assert "five_min_only" in block and "minute_ok" in block
    assert "refused at the data layer" in block
    assert "cautious label is the default" in block
    assert "demotion is immediate" in block
    assert "two consecutive passing censuses" in block
    assert "enforcer:" in block


# ------------------------------- QT-11c: the EMAs and Keltner Channels, P19 ---

def test_p19_is_recorded_in_the_operators_own_words() -> None:
    """The requirement and the GO are both quoted, with the date.

    Same discipline as P18: a later edit has to be deliberate and visible in a
    diff, and nobody has to remember what was actually asked for.
    """
    block = decision_blocks()["P19"]
    assert ("The program follows the EMA 9, EMA 21 and EMA 50, as well as using "
            "Keltner Channels.") in " ".join(block.split())
    assert "2026-10-03" in block
    assert "GO on P19" in block


def test_p19_keeps_the_indicators_as_candidates_not_instructions() -> None:
    """The failure this prevents: a popular indicator kept because it is popular.

    Being asked for by name is not evidence that it works. The firewall decides,
    and only survivors reach the confidence score.
    """
    block = " ".join(decision_blocks()["P19"].split())
    assert "candidates, not instructions" in block
    assert "only the ones that survive feed the confidence score" in block
    assert "Built in **S4**" in block
    # The advisor may show them before they are tested, but not recommend them.
    assert "drawn on the charts" in block
    assert "once they have been tested" in block


def test_p19_pins_the_settings_that_were_agreed() -> None:
    """Settings fixed before any result is the whole point of pre-registration."""
    block = " ".join(decision_blocks()["P19"].split())
    assert "middle line is **EMA 21**" in block
    assert "2.0 × Wilder ATR(14)" in block
    assert "5-minute for the bot" in block and "daily for the advisor" in block


def test_p19_fixes_the_trial_count_before_any_result() -> None:
    """A trial count decided after the results is not a trial count.

    The arithmetic is re-derived from the plan's own table rather than trusting
    the sentence: if a row is added without updating the total, this fails.
    """
    block = decision_blocks()["P19"]
    flat = " ".join(block.split())

    # Count the numbered rows of the pre-registered table.
    rules = re.findall(r"^\| (\d+) \| ", block, flags=re.MULTILINE)
    assert [int(r) for r in rules] == list(range(1, 10)), (
        f"the pre-registered rule table should run 1..9, found {rules}")

    assert "Nine rules × two bar sizes = 18 trials" in flat
    assert len(rules) * 2 == 18, "the table and the stated total disagree"
    assert "before any result is seen" in flat


def test_p19_does_not_count_the_same_test_twice() -> None:
    """Keltner's middle line IS the EMA 21, so crossing it is already rule 2.

    Counting it again would be one test wearing two names, and would make the
    deflated score look better than the work done deserves.
    """
    flat = " ".join(decision_blocks()["P19"].split())
    assert "deliberately absent — it is rule 2" in flat
    assert "wearing a second name" in flat


def test_p19_says_a_later_variant_is_a_new_trial() -> None:
    """The loophole this closes: trying 2.5 after 2.0 fails, and not logging it.

    That is how an honest count becomes a dishonest one without anybody lying.
    """
    flat = " ".join(decision_blocks()["P19"].split())
    assert "NEW trial and must be logged" in flat
    assert "trials.jsonl" in flat
    assert "1.5 or 2.5" in flat, "the obvious next variant is named in advance"
    assert "never on profit" in flat or "SCARS #21" in flat


# -------------------------------- QT-12a: the broker cross-check, P20 ---

def test_p20_is_recorded_in_the_operators_own_words() -> None:
    """The requirement and the GO, with the date, as every decision gets."""
    block = decision_blocks()["P20"]
    flat = " ".join(block.split())
    assert ("Compare yfinance with Trading 212 prices: hold one share of each bot "
            "name in the practice account so Trading 212 prices all 50, and "
            "cross-check before every trade.") in flat
    assert "2026-10-04" in block
    assert "GO on P20" in block


def test_p20_fences_the_anchor_shares() -> None:
    """An anchor is measuring equipment, not a position.

    Two ways this goes wrong: the bot's record silently includes 50 holdings it
    never chose, or flatten sells the anchors and blinds the check they feed.
    """
    flat = " ".join(decision_blocks()["P20"].split())
    assert "never sells an anchor" in flat
    assert "excluded from the bot's results and from its pot" in flat
    assert "flatten (P4) leaves them alone" in flat


def test_p20_converts_units_before_comparing() -> None:
    """The 100x trap again: pence against pounds would halt the market daily."""
    flat = " ".join(decision_blocks()["P20"].split())
    assert "converted to the instrument's own quote currency before anything is "\
           "compared" in flat
    assert "100x" in flat


def test_p20_states_what_each_threshold_blocks_and_why() -> None:
    """A threshold without a reason is a number nobody can argue with."""
    flat = " ".join(decision_blocks()["P20"].split())
    for number in ("0.25%", "0.5%", "5%"):
        assert number in flat, f"the {number} threshold is missing"
    assert "that name's trade is blocked" in flat
    assert "STOP_NEW_TRADES for that market" in flat
    assert "ATR" in flat, "the volatility term must be stated"
    assert "3 or more names" in flat


def test_p20_treats_a_missing_check_as_a_failed_one() -> None:
    """THE quiet failure: the check cannot run, and that reads as a pass."""
    flat = " ".join(decision_blocks()["P20"].split())
    assert "no comparison possible" in flat
    assert "must never read the same as the check passing" in flat


def test_p20_records_the_measured_obstacle_rather_than_discovering_it_later() -> None:
    """One whole share of each costs more than the whole demo account.

    Writing the number into the plan is what stops S4 starting on a plan that
    cannot be carried out, and the unknown minimum is marked as unknown.
    """
    flat = " ".join(decision_blocks()["P20"].split())
    assert "£14,032" in flat
    assert "fractional" in flat
    assert "NOT on record" in flat, "the unknown minimum must be flagged as unknown"
    assert "S14" in flat, "real money is decided later, not here"


# ------------------------------ QT-12: the anchors are bought by the program ---

# P20 as agreed and committed in ea4d008, from "**P20 —" to the end of its
# Enforcer paragraph. The addendum is APPENDED; the decision itself never moves.
P20_ORIGINAL_SHA256 = (
    "d39f1bc7477dd834750250705603e5197ac3b82e6475dc3e395a6c7833e35d2b")
QT12_WORDS = (
    "write the anchor-buyer box (QT-12) — P20 anchors bought by the program, "
    "practice only, fenced; S3 close becomes QT-13")
QT12_EARLIER_WORDS = (
    "Can't the algorithm do this? this is what we a building for")
STATE = REPO_ROOT / "STATE.md"


def p20_addendum() -> str:
    block = decision_blocks()["P20"]
    marker = "*Addendum, 2026-10-04"
    assert marker in block, "P20 has no dated addendum for the anchor buyer"
    return " ".join(block[block.index(marker):].split())


def test_p20_original_text_is_byte_identical_after_the_addendum() -> None:
    """An addendum that quietly edits what was agreed is not an addendum."""
    text = plan_text()
    start = text.index("**P20 —")
    end = text.index("than passes.", start) + len("than passes.")
    digest = hashlib.sha256(text[start:end].encode("utf-8")).hexdigest()
    assert digest == P20_ORIGINAL_SHA256, (
        "P20's agreed text changed -- add to it in the addendum, never edit it")


def test_p20_addendum_records_the_operators_words_verbatim_and_dated() -> None:
    """Typos are his and are kept: 'we a building' is evidence, not a mistake."""
    addendum = p20_addendum()
    assert QT12_WORDS in addendum
    assert QT12_EARLIER_WORDS in addendum


def test_p20_addendum_makes_the_anchor_about_a_pound_not_a_whole_share() -> None:
    """The measured obstacle is the reason, so the figures travel with it."""
    addendum = p20_addendum()
    assert "not a whole share" in addendum
    assert "£1" in addendum
    assert "£14,032" in addendum and "£10,000" in addendum


def test_p20_addendum_keeps_anchors_practice_only_and_outside_both_pots() -> None:
    """Outside BOTH pots: an anchor shrinks neither the bot's 30% nor the 70%."""
    addendum = p20_addendum()
    assert "bought and topped up by the program" in addendum
    assert "practice server only" in addendum
    assert "outside BOTH pots" in addendum
    assert "30%" in addendum and "70%" in addendum


def test_p20_addendum_refuses_the_live_server_until_s14() -> None:
    addendum = p20_addendum()
    assert "decided at S14" in addendum
    assert "refuses the live server outright" in addendum


def test_p20_addendum_pins_the_caps_so_raising_one_needs_a_go() -> None:
    """A cap that lives only in code can be raised by an edit nobody reads."""
    addendum = p20_addendum()
    for figure in ("£1 target", "£3 per order", "£100 lifetime",
                   "50 orders a day"):
        assert figure in addendum, f"cap missing from the plan: {figure}"
    assert "never raised without the operator's GO" in addendum


def test_p20_addendum_is_not_the_bots_sender_and_changes_no_stage() -> None:
    """The one order path before S10 must say it is not the bot's, in the plan."""
    addendum = p20_addendum()
    assert "qb2/execution/anchors.py" in addendum
    assert "the bot cannot import it" in addendum
    assert "still built in S4" in addendum
    assert "arms nothing" in addendum


def test_state_carries_the_s4_flag_and_the_renumbered_s3_close() -> None:
    """Carried until S4 consumes it: two pairs that are one bet each."""
    flat = " ".join(STATE.read_text(encoding="utf-8").split())
    assert "S3 close = QT-13" in flat
    assert ("GOOG/GOOGL and VUAG/VUSA each count as ONE bet when the bot "
            "trades") in flat
