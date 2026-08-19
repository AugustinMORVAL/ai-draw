"""Legality and the Masking preview, including the slice's manual test."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_draw_api.cards import card_index
from ai_draw_api.decklist import parse
from ai_draw_api.legality import review
from ai_draw_api.models import CardIssue, DeckIssue

ASH_BLOSSOM = 14558127
SHADDOLL_BEAST = 3717252
DARK_MAGICIAN = 46986414  # a real card, outside the 864
POT_OF_DESIRES = 35261759  # Semi-Limited on 2024.7
MAXX_C = 32909498  # Forbidden on 2024.7
EL_SHADDOLL_WINDA = 94977269  # Extra Deck
TOKEN = 91512836  # "Insect Monster Token"

SEED_DECK = Path(__file__).parent / "fixtures" / "Shaddoll.ydk"


@pytest.fixture(scope="module")
def index():
    return card_index()


def judge(text: str, index):
    return review(parse(text, index), index)


def issues(report) -> set[CardIssue]:
    return {flag.issue for flag in report.flags}


def test_a_shipped_seed_deck_is_legal(index):
    """If the decks the executor ships with fail our rules, our rules are wrong."""
    report = judge(SEED_DECK.read_text(), index)
    assert report.legal is True, [flag.reason for flag in report.flags]
    assert report.main_count == 42
    assert report.extra_count == 14


def test_the_manual_test_four_copies_and_an_out_of_pool_card(index):
    """Slice 1's manual test: both are flagged, and each says why."""
    lines = SEED_DECK.read_text().splitlines()
    cut = lines.index("#extra")
    text = "\n".join(
        lines[:cut] + [str(SHADDOLL_BEAST), str(DARK_MAGICIAN)] + lines[cut:]
    )

    report = judge(text, index)
    assert report.legal is False
    assert issues(report) == {CardIssue.OVER_LIMIT, CardIssue.NOT_IN_POOL}

    over = next(f for f in report.flags if f.issue is CardIssue.OVER_LIMIT)
    assert over.count == 4
    assert "Shaddoll Beast" in over.reason and "3 times" in over.reason

    outside = next(f for f in report.flags if f.issue is CardIssue.NOT_IN_POOL)
    assert outside.name == "Dark Magician"
    assert "864" in outside.reason, "the reason names the boundary, not just the fact"


def test_the_banlist_is_stricter_than_three(index):
    report = judge(f"{POT_OF_DESIRES}\n" * 3, index)
    over = next(f for f in report.flags if f.issue is CardIssue.OVER_LIMIT)
    assert over.limit == 2
    assert index.banlist in over.reason


def test_a_forbidden_card_is_forbidden_at_one_copy(index):
    report = judge(str(MAXX_C) + "\n", index)
    assert CardIssue.FORBIDDEN in issues(report)


def test_a_token_is_never_part_of_a_deck(index):
    """It is in the pool because the Pilot must recognise it on the field."""
    report = judge(str(TOKEN) + "\n", index)
    assert CardIssue.TOKEN in issues(report)


def test_an_extra_deck_monster_in_the_main_deck_is_flagged(index):
    report = judge(f"#main\n{EL_SHADDOLL_WINDA}\n", index)
    assert CardIssue.WRONG_SECTION in issues(report)


def test_an_extra_deck_monster_in_the_extra_deck_is_not(index):
    report = judge(f"#main\n#extra\n{EL_SHADDOLL_WINDA}\n", index)
    assert issues(report) == set()


def test_a_code_no_database_carries_is_unknown_not_unsupported(index):
    report = judge("999999999\n", index)
    assert CardIssue.UNKNOWN_CARD in issues(report)


def test_deck_size_rules(index):
    small = judge(f"{ASH_BLOSSOM}\n", index)
    assert {f.issue for f in small.deck_flags} == {DeckIssue.MAIN_TOO_SMALL}

    empty = judge("# nothing here\n", index)
    assert {f.issue for f in empty.deck_flags} == {DeckIssue.NOTHING_PARSED}
    assert empty.deck is None


def test_too_many_extra_deck_cards(index):
    text = "#main\n" + f"{ASH_BLOSSOM}\n" * 40 + "#extra\n" + f"{EL_SHADDOLL_WINDA}\n" * 16
    report = judge(text, index)
    assert DeckIssue.EXTRA_TOO_LARGE in {f.issue for f in report.deck_flags}


def test_the_mask_accounts_for_every_card_in_the_pool(index):
    """A Masking preview that does not add up is a Masking preview nobody trusts."""
    report = judge(SEED_DECK.read_text(), index)
    mask = report.mask
    assert mask.pool_size == len(index)
    assert mask.legal_picks + sum(group.count for group in mask.masked) == len(index)
    assert mask.legal_picks < len(index.main_deck_codes()), (
        "cards already at their copy limit in this deck are masked out"
    )


def test_the_mask_closes_as_the_deck_fills_up(index):
    empty = judge(f"{ASH_BLOSSOM}\n", index).mask
    maxed = judge(f"{ASH_BLOSSOM}\n" * 3, index).mask
    assert maxed.legal_picks == empty.legal_picks - 1
