"""Constraints: the Masking that makes a build respect what the user asked for.

Includes the slice-2 manual test, and its honest other half -- the Constraint the
864-card pool cannot satisfy at all.
"""

from __future__ import annotations

from collections import Counter

import pytest

from ai_draw_api import constraints
from ai_draw_api.cards import card_index
from ai_draw_api.constraints import Impossible, action_space, construct, facets
from ai_draw_api.decklist import parse
from ai_draw_api.legality import review
from ai_draw_api.models import (
    Bound,
    Constraint,
    ConstraintClause,
    ConstraintFacet,
    ConstraintIssue,
)


def clause(facet: str, value: str, bound: str, count: int) -> ConstraintClause:
    return ConstraintClause(
        facet=ConstraintFacet(facet), value=value, bound=Bound(bound), count=count
    )


def held(deck_codes: list[int], facet: str, value: str) -> int:
    """How many cards in this deck carry a facet value, counted from the index."""
    index = card_index()
    single = clause(facet, value, "at_least", 0)
    return sum(
        1 for code in deck_codes if constraints.matches(index.pool[code], single)
    )


def test_a_deck_is_built_under_the_constraint_that_was_asked_for():
    """The slice-2 manual test: ask for a themed deck under a card-count cap."""
    index = card_index()
    asked = Constraint(
        main_size=40,
        clauses=[
            clause("race", "Spellcaster", "at_least", 20),
            clause("kind", "trap", "at_most", 4),
        ],
    )
    deck = construct(index, asked, seed=11)

    assert len(deck.main) == 40, "the card-count cap is the deck size, not a hope"
    assert held(deck.main, "race", "Spellcaster") >= 20
    assert held(deck.main, "kind", "trap") <= 4

    report = review(parse("\n".join(str(c) for c in deck.main), index), index, asked)
    assert report.legal is True, report.flags
    assert report.constraint is not None
    assert report.constraint.satisfied is True, report.constraint.flags


def test_a_cyberse_deck_is_impossible_and_the_pool_says_why():
    """The pool knows 34 Cyberse cards and can build no Cyberse deck.

    Every one of them is a Token or an Extra Deck monster: the pool is the Pilot's
    vocabulary, not a list of buildable cards (CONTEXT.md). Answering "no deck" is
    the only honest answer, and it has to come with that sentence.
    """
    index = card_index()
    asked = Constraint(clauses=[clause("race", "Cyberse", "at_least", 12)])

    with pytest.raises(Impossible) as raised:
        construct(index, asked, seed=1)

    reason = raised.value.flags[0].reason
    assert raised.value.flags[0].issue is ConstraintIssue.IMPOSSIBLE
    assert "at most 0" in reason
    assert "Extra Deck monster" in reason, "the user is told where the 34 cards went"

    report = constraints.review(index, Counter(), asked, main_count=0)
    assert report.feasible is False


def test_a_cap_leaves_the_action_space_once_the_deck_meets_it():
    index = card_index()
    asked = Constraint(clauses=[clause("kind", "trap", "at_most", 0)])
    space = action_space(index, Counter(), asked, target_size=40)

    assert space.allowed, "capping traps does not cap the deck"
    assert all(index.pool[code].kind != "trap" for code in space.allowed)
    assert any("at most 0 trap" in reason for reason in space.masked)


def test_a_floor_masks_everything_else_once_the_slots_run_out():
    """This is what makes a feasible minimum satisfied by construction, not by luck."""
    index = card_index()
    asked = Constraint(
        main_size=40, clauses=[clause("race", "Dragon", "at_least", 10)]
    )
    others = [
        code for code in index.main_deck_codes() if index.pool[code].race != "Dragon"
    ]

    # 30 cards down, 10 slots left, 10 Dragons owed: only Dragons may be picked.
    late = Counter({code: 1 for code in others[:30]})
    space = action_space(index, late, asked, target_size=40)
    assert space.allowed
    assert all(index.pool[code].race == "Dragon" for code in space.allowed)
    assert any("owed to a minimum" in reason for reason in space.masked)

    # 20 cards down, and the floor does not yet dictate the pick.
    early = Counter({code: 1 for code in others[:20]})
    assert any(
        index.pool[code].race != "Dragon"
        for code in action_space(index, early, asked, target_size=40).allowed
    )


def test_a_cap_cannot_starve_a_floor_of_its_slots():
    """Filler drawn first would spend the slots the floor needed, on a Constraint
    that is perfectly satisfiable. Floors are paid first for exactly this deck."""
    index = card_index()
    asked = Constraint(
        main_size=40,
        clauses=[
            clause("race", "Spellcaster", "at_least", 20),
            clause("kind", "monster", "at_most", 22),
        ],
    )
    deck = construct(index, asked, seed=3)
    assert held(deck.main, "race", "Spellcaster") >= 20
    assert held(deck.main, "kind", "monster") <= 22


def test_the_same_seed_builds_the_same_deck():
    """A build can be handed to someone else and re-derived, seed and all."""
    index = card_index()
    asked = Constraint(clauses=[clause("attribute", "DARK", "at_least", 15)])
    assert construct(index, asked, seed=5).main == construct(index, asked, seed=5).main
    assert construct(index, asked, seed=5).main != construct(index, asked, seed=6).main


def test_two_floors_on_one_facet_cannot_share_a_deck():
    """A card has exactly one race, so 25 and 25 do not fit in 40."""
    index = card_index()
    asked = Constraint(
        main_size=40,
        clauses=[
            clause("race", "Dragon", "at_least", 25),
            clause("race", "Spellcaster", "at_least", 25),
        ],
    )
    with pytest.raises(Impossible) as raised:
        construct(index, asked)
    assert "cannot share a deck of 40" in " ".join(
        flag.reason for flag in raised.value.flags
    )


def test_caps_that_cannot_fill_a_deck_are_refused_before_the_draw():
    index = card_index()
    asked = Constraint(
        main_size=40,
        clauses=[
            clause("kind", "monster", "at_most", 5),
            clause("kind", "spell", "at_most", 5),
            clause("kind", "trap", "at_most", 5),
        ],
    )
    with pytest.raises(Impossible) as raised:
        construct(index, asked)
    assert "at most 15 cards" in " ".join(flag.reason for flag in raised.value.flags)


def test_an_unmet_constraint_is_not_illegality():
    """The two verdicts are reported side by side and never merged.

    An illegal deck aborts `ygopro-core`; a deck that is not what the user asked
    for is a deck they may keep anyway. Only one of them stops a job.
    """
    index = card_index()
    deck = construct(index, Constraint(main_size=40), seed=9)
    asked = Constraint(main_size=60, clauses=[clause("race", "Dragon", "at_least", 30)])
    report = review(parse("\n".join(str(c) for c in deck.main), index), index, asked)

    assert report.legal is True, report.flags
    assert report.constraint is not None
    assert report.constraint.feasible is True, "30 Dragons in 60 cards is buildable"
    assert report.constraint.satisfied is False
    issues = {flag.issue for flag in report.constraint.flags}
    assert issues == {ConstraintIssue.UNMET_MINIMUM, ConstraintIssue.WRONG_SIZE}
    status = report.constraint.clauses[0]
    assert status.held < 30 and status.ceiling >= 30


def test_the_facets_report_carries_the_pools_ceilings():
    index = card_index()
    listed = facets(index)
    assert listed.main_deck_pool_size == 408

    by_value = {(v.facet.value, v.value): v for v in listed.values}
    spellcaster = by_value[("race", "Spellcaster")]
    assert spellcaster.cards == 28 and spellcaster.copies > 28

    cyberse = by_value[("race", "Cyberse")]
    assert cyberse.cards == 0, "no main-deck Cyberse card is in the pool"
    assert cyberse.copies == 0
    assert cyberse.elsewhere == 34, "all 34 are Tokens or Extra Deck monsters"


def test_the_masking_preview_counts_the_constraint_too():
    """The preview is the same function the Builder picks from, so it cannot lie."""
    index = card_index()
    asked = Constraint(clauses=[clause("kind", "monster", "at_most", 0)])
    bare = review(parse("", index), index).mask
    masked = review(parse("", index), index, asked).mask

    assert masked.legal_picks < bare.legal_picks
    assert masked.legal_picks == bare.legal_picks - 199, "every monster is out"
    assert masked.pool_size == 864


def test_no_card_count_cap_means_no_size_to_fall_short_of():
    """A user who never chose 40 is not told their 42-card deck is wrong.

    Legality already has an opinion about deck size (40 to 60) and reports it. A
    Constraint repeating it would be a preference nobody stated.
    """
    index = card_index()
    deck = construct(index, Constraint(main_size=42), seed=12)
    asked = Constraint(clauses=[clause("kind", "trap", "at_most", 20)])
    report = review(parse("\n".join(str(c) for c in deck.main), index), index, asked)

    assert report.constraint is not None
    assert report.constraint.constraint.main_size is None
    assert report.constraint.satisfied is True, report.constraint.flags
