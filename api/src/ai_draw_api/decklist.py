"""Turning a paste box into card codes.

Two formats, because users have two things on their clipboard. `.ydk` is the
ecosystem's export format and is already codes; a typed list is names, and names
are where the pool boundary actually bites -- a user types a card the Pilot has
never seen and needs to be told which of those two facts is true.

Nothing here judges a deck. Parsing answers "which card is this line?"; legality
answers "may it be played?", and keeping them apart is what lets an out-of-pool
card be resolved by name and *then* flagged, instead of vanishing as a typo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .cards import CardIndex
from .models import CardSection, UnresolvedLine

# "3x Ash Blossom", "3 Ash Blossom", "Ash Blossom x3", "Ash Blossom (3)"
_PREFIX_COUNT = re.compile(r"^\s*(\d{1,2})\s*[x*]?\s+(.+?)\s*$", re.IGNORECASE)
_SUFFIX_COUNT = re.compile(r"^\s*(.+?)\s*(?:[x*]\s*(\d{1,2})|\((\d{1,2})\))\s*$", re.IGNORECASE)
# A bare number on its own line is always a code attempt. The lower bound matters:
# "Labrynth Cooclock" is code 2511, and a 5-digit floor made it the one pool card
# a .ydk could not paste -- it fell through to the name matcher and came back as a
# typo. The upper bound stays past the longest real code (8 digits) so an
# out-of-range number is reported as a card nobody has, not as a misspelling.
_CODE = re.compile(r"^\s*(\d{1,9})\s*$")

MAX_LINES = 400


@dataclass
class ParsedDeck:
    """Codes with the section the paste put them in, plus what could not be read."""

    main: list[int] = field(default_factory=list)
    extra: list[int] = field(default_factory=list)
    side: list[int] = field(default_factory=list)
    unresolved: list[UnresolvedLine] = field(default_factory=list)
    #: True when the paste declared its sections, so a card in the wrong one is
    #: the user's statement and worth flagging rather than silently corrected.
    sectioned: bool = False


def _split_count(text: str) -> tuple[int, str]:
    match = _PREFIX_COUNT.match(text)
    if match and not _CODE.match(text):
        return int(match.group(1)), match.group(2).strip()
    match = _SUFFIX_COUNT.match(text)
    if match:
        count = match.group(2) or match.group(3)
        return int(count), match.group(1).strip()
    return 1, text.strip()


def parse(text: str, index: CardIndex) -> ParsedDeck:
    """Read a pasted decklist. Never raises: unreadable lines are reported, not fatal."""
    result = ParsedDeck()
    section = CardSection.MAIN
    side = False

    lines = text.splitlines()
    if len(lines) > MAX_LINES:
        result.unresolved.append(
            UnresolvedLine(
                line=MAX_LINES + 1,
                text=f"... {len(lines) - MAX_LINES} more lines",
                reason=f"Only the first {MAX_LINES} lines were read.",
            )
        )
        lines = lines[:MAX_LINES]

    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            continue

        marker = line.lower().lstrip("#!").strip()
        if line.startswith(("#", "!")):
            if marker in {"main", "extra", "side"}:
                result.sectioned = True
                side = marker == "side"
                section = CardSection.EXTRA if marker == "extra" else CardSection.MAIN
            continue

        code_match = _CODE.match(line)
        if code_match:
            code = int(code_match.group(1))
            _place(result, index, code, section, side, declared=result.sectioned)
            continue

        count, name = _split_count(line)
        matches = index.by_name(name)
        if not matches:
            result.unresolved.append(
                UnresolvedLine(
                    line=number,
                    text=line,
                    reason=(
                        f"No card is named {name!r}. Check the spelling, or paste a "
                        ".ydk instead -- codes never depend on a spelling."
                    ),
                )
            )
            continue
        card = matches[0]
        for _ in range(min(count, 60)):
            _place(result, index, card.code, section, side, declared=False)

    return result


def _place(
    result: ParsedDeck,
    index: CardIndex,
    code: int,
    section: CardSection,
    side: bool,
    *,
    declared: bool,
) -> None:
    """File a code under a section.

    A typed name goes where the card itself belongs -- nobody types "#extra". A
    `.ydk` said where it wanted the card, so it is filed as written and legality
    gets to object.
    """
    if side:
        result.side.append(code)
        return
    code = index.resolve(code)
    if not declared:
        card = index.get(code)
        if card is not None and card.section is CardSection.EXTRA:
            result.extra.append(code)
            return
        result.main.append(code)
        return
    (result.extra if section is CardSection.EXTRA else result.main).append(code)
