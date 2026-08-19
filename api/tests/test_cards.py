"""The card index: two tiers, and the alt-art codes that fold onto them."""

from __future__ import annotations

import pytest

from ai_draw_api.cards import card_index, normalise
from ai_draw_api.models import CardSection
from ai_draw_api.pool import supported_pool

ASH_BLOSSOM = 14558127
ASH_BLOSSOM_ALT = 14558128
DARK_MAGICIAN = 46986414  # a real card, not one the Pilot can represent


@pytest.fixture(scope="module")
def index():
    return card_index()


def test_the_index_covers_the_pool_exactly(index):
    assert len(index) == len(supported_pool())
    assert set(index.pool) == set(supported_pool())


def test_most_of_the_pool_cannot_go_in_a_deck(index):
    """The pool is the Pilot's vocabulary, not a list of buildable cards."""
    sections = {}
    for card in index.pool.values():
        sections[card.section] = sections.get(card.section, 0) + 1
    assert sections[CardSection.TOKEN] == 232
    assert sections[CardSection.EXTRA] == 221
    assert sections[CardSection.MAIN] == 411
    assert len(index.main_deck_codes()) == 408, "three main-deck cards are Forbidden"


def test_a_pool_card_knows_what_it_is(index):
    ash = index.get(ASH_BLOSSOM)
    assert ash is not None
    assert ash.name == "Ash Blossom & Joyous Spring"
    assert ash.in_pool is True
    assert ash.kind == "monster"
    assert ash.race == "Zombie"
    assert ash.section is CardSection.MAIN


def test_a_known_card_outside_the_pool_is_named_not_denied(index):
    """"Unknown card" and "not in the pool" are different sentences (CONTEXT.md)."""
    card = index.get(DARK_MAGICIAN)
    assert card is not None
    assert card.name == "Dark Magician"
    assert card.in_pool is False


def test_a_code_no_database_carries_is_none(index):
    assert index.get(999_999_999) is None


def test_an_alt_art_folds_onto_the_printing_the_pilot_knows(index):
    """`.ydk` exports carry whichever printing the owner opened."""
    assert index.resolve(ASH_BLOSSOM_ALT) == ASH_BLOSSOM
    card = index.get(ASH_BLOSSOM_ALT)
    assert card is not None and card.in_pool is True


def test_a_pool_code_that_is_itself_an_alias_resolves_to_itself(index):
    """Membership wins: the Pilot has an embedding row for that exact code."""
    for code in index.pool:
        assert index.resolve(code) == code


def test_search_ranks_the_pool_first_and_says_which_is_which(index):
    hits = index.search("cyberse", limit=5)
    assert hits[0].in_pool is True
    assert any(hit.in_pool is False for hit in hits)


def test_search_does_not_repeat_a_card_once_per_printing(index):
    names = [card.name for card in index.search("dark magician", limit=10)]
    assert len(names) == len(set(names))


def test_search_can_be_told_to_stay_inside_the_pool(index):
    hits = index.search("dark magician", limit=10, unsupported=False)
    assert all(hit.in_pool for hit in hits)


def test_names_survive_the_way_people_type_them(index):
    assert normalise("Ash Blossom & Joyous Spring") == normalise(
        "  ash   blossom & joyous spring "
    )
    assert index.by_name("ASH BLOSSOM & JOYOUS SPRING")[0].code == ASH_BLOSSOM
