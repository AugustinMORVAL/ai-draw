"""Reading a paste box: `.ydk` codes, typed names, and the mess in between."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_draw_api.cards import card_index
from ai_draw_api.decklist import parse

ASH_BLOSSOM = 14558127
ASH_BLOSSOM_ALT = 14558128
DARK_MAGICIAN = 46986414
SHADDOLL_BEAST = 3717252
EL_SHADDOLL_WINDA = 94977269  # Extra Deck

SEED_DECK = Path(__file__).parent / "fixtures" / "Shaddoll.ydk"


@pytest.fixture(scope="module")
def index():
    return card_index()


def test_a_ydk_keeps_its_sections(index):
    parsed = parse(
        "#main\n3717252\n3717252\n#extra\n94977269\n!side\n14558127\n", index
    )
    assert parsed.main == [SHADDOLL_BEAST, SHADDOLL_BEAST]
    assert parsed.extra == [EL_SHADDOLL_WINDA]
    assert parsed.side == [ASH_BLOSSOM]
    assert parsed.sectioned is True


def test_a_ydk_is_filed_as_written_so_legality_can_object(index):
    """An Extra Deck monster under `#main` is a claim, not a typo to fix silently."""
    parsed = parse("#main\n94977269\n", index)
    assert parsed.main == [EL_SHADDOLL_WINDA]
    assert parsed.extra == []


def test_typed_names_go_where_the_card_belongs(index):
    """Nobody types `#extra`."""
    parsed = parse("Ash Blossom & Joyous Spring\nEl Shaddoll Winda\n", index)
    assert parsed.main == [ASH_BLOSSOM]
    assert parsed.extra == [EL_SHADDOLL_WINDA]


@pytest.mark.parametrize(
    "line",
    [
        "3 Ash Blossom & Joyous Spring",
        "3x Ash Blossom & Joyous Spring",
        "Ash Blossom & Joyous Spring x3",
        "Ash Blossom & Joyous Spring (3)",
    ],
)
def test_counts_are_read_however_they_were_written(index, line):
    assert parse(line, index).main == [ASH_BLOSSOM] * 3


def test_an_alt_art_code_resolves_to_the_supported_printing(index):
    assert parse(f"{ASH_BLOSSOM_ALT}\n", index).main == [ASH_BLOSSOM]


def test_an_out_of_pool_card_is_read_not_dropped(index):
    """It has to reach legality to be flagged with a reason (CONTEXT.md)."""
    assert parse("Dark Magician\n", index).main == [DARK_MAGICIAN]


def test_a_line_naming_no_card_is_reported_with_its_number(index):
    parsed = parse("Ash Blossom & Joyous Spring\nNot A Real Card\n", index)
    assert parsed.main == [ASH_BLOSSOM]
    assert len(parsed.unresolved) == 1
    assert parsed.unresolved[0].line == 2
    assert "Not A Real Card" in parsed.unresolved[0].reason


def test_comments_and_blank_lines_are_not_cards(index):
    parsed = parse("#created by ...\n\n#main\n\n3717252\n\n", index)
    assert parsed.main == [SHADDOLL_BEAST]
    assert parsed.unresolved == []


def test_a_paste_that_is_too_long_is_truncated_out_loud(index):
    parsed = parse("3717252\n" * 500, index)
    assert len(parsed.main) == 400
    assert "more lines" in parsed.unresolved[0].text


def test_a_shipped_seed_deck_round_trips(index):
    """The decks the executor ships with are the strongest fixture available."""
    parsed = parse(SEED_DECK.read_text(), index)
    assert len(parsed.main) == 42
    assert len(parsed.extra) == 14
    assert parsed.unresolved == []


def test_a_four_digit_code_is_a_card_not_a_typo(index):
    """"Labrynth Cooclock" is code 2511, the shortest passcode in the pool.

    A five-digit floor on the code pattern sent it to the name matcher, where a
    number matches nothing, so a `.ydk` carrying it came back one card short with
    "no card is named '2511'" against it.
    """
    parsed = parse("#main\n2511\n", index)
    assert parsed.main == [2511]
    assert parsed.unresolved == []


def test_a_number_no_card_uses_is_still_read_as_a_code(index):
    parsed = parse("999999999\n", index)
    assert parsed.main == [999999999], "legality says it is unknown; parsing does not"
    assert parsed.unresolved == []
