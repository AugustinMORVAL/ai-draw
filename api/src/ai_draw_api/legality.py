"""Legality, and the Masking preview that follows from it.

Legality is banlist, copy limits and deck-size rules. Per CONTEXT.md these are not
Constraints: a Constraint is something the user asked for and can drop, legality is
never negotiable and is always enforced. On top of those, this app enforces one rule
the paper game does not have -- **a card must be in the supported pool** -- because a
code outside the 864 is a card the Pilot literally cannot see.

Every rejection carries a sentence, not a code. A user who pastes their deck and gets
back "3 flags" has learned nothing; the point of the screen is to say which card, how
many, and against which rule.

`ygopro-core` aborts the process on a malformed deck rather than refusing it (#4), so
everything here is a guard, not a nicety: a Token or an Extra Deck monster that reaches
the executor in a main deck is a dead worker, not a bad result.
"""

from __future__ import annotations

from collections import Counter

from . import constraints
from .cards import DEFAULT_COPY_LIMIT, CardIndex
from .decklist import ParsedDeck
from .models import (
    Card,
    CardFlag,
    CardIssue,
    CardSection,
    Constraint,
    Deck,
    DeckEntry,
    DeckFlag,
    DeckIssue,
    DeckReport,
    MaskedGroup,
    MaskPreview,
)

MAIN_MIN = 40
MAIN_MAX = 60
EXTRA_MAX = 15


def _limit_word(limit: int) -> str:
    return {0: "Forbidden", 1: "Limited", 2: "Semi-Limited"}.get(limit, "Unlimited")


def _flag_card(
    index: CardIndex, code: int, count: int, section: CardSection, banlist: str
) -> CardFlag | None:
    """The first rule this card breaks, phrased for the person who pasted it."""
    card = index.get(code)

    if card is None:
        return CardFlag(
            code=code,
            name=None,
            count=count,
            section=section,
            issue=CardIssue.UNKNOWN_CARD,
            reason=(
                f"Code {code} is not a card the duel executor knows. It is in no "
                "version of the card database this build was made from."
            ),
        )

    if not card.in_pool:
        return CardFlag(
            code=code,
            name=card.name,
            count=count,
            section=section,
            issue=CardIssue.NOT_IN_POOL,
            reason=(
                f"{card.name} is a real card, but it is not one of the 864 the frozen "
                "Pilot can represent, so it cannot be played or built with. Widening "
                "the supported pool means training a new Pilot, not editing a file."
            ),
        )

    if card.section is CardSection.TOKEN:
        return CardFlag(
            code=code,
            name=card.name,
            count=count,
            section=section,
            issue=CardIssue.TOKEN,
            reason=(
                f"{card.name} is a Token. Tokens are created during a duel and are "
                "never part of a deck -- the pool lists them because the Pilot has to "
                "recognise them on the field."
            ),
        )

    if section is CardSection.MAIN and card.section is CardSection.EXTRA:
        return CardFlag(
            code=code,
            name=card.name,
            count=count,
            section=section,
            issue=CardIssue.WRONG_SECTION,
            reason=(
                f"{card.name} is an Extra Deck monster and was listed in the main "
                "deck. Phase 1 builds main decks only, so it has nowhere to go."
            ),
        )

    if card.limit == 0:
        return CardFlag(
            code=code,
            name=card.name,
            count=count,
            section=section,
            issue=CardIssue.FORBIDDEN,
            limit=0,
            reason=(
                f"{card.name} is Forbidden on the {banlist} banlist. Legality is "
                "always enforced -- it is not a Constraint you can drop."
            ),
        )

    if count > card.limit:
        return CardFlag(
            code=code,
            name=card.name,
            count=count,
            section=section,
            issue=CardIssue.OVER_LIMIT,
            limit=card.limit,
            reason=(
                f"{count} copies of {card.name}. No card may be played more than "
                f"{DEFAULT_COPY_LIMIT} times."
                if card.limit >= DEFAULT_COPY_LIMIT
                else (
                    f"{count} copies of {card.name}, but it is "
                    f"{_limit_word(card.limit)} on the {banlist} banlist "
                    f"-- at most {card.limit}."
                )
            ),
        )

    return None


def _mask(
    index: CardIndex, main: Counter[int], constraint: Constraint | None
) -> MaskPreview:
    """Count the Builder's action space for this deck: what it may still add.

    The count comes from `constraints.action_space`, the same function the deck
    builder and every proposed swap pick from, so this preview cannot promise a
    pick the Builder would not actually be allowed to make.
    """
    space = constraints.action_space(index, main, constraint)
    return MaskPreview(
        pool_size=len(index),
        legal_picks=len(space.allowed),
        masked=[
            MaskedGroup(reason=reason, count=count)
            for reason, count in sorted(space.masked.items(), key=lambda g: -g[1])
        ],
    )


def review(
    parsed: ParsedDeck, index: CardIndex, constraint: Constraint | None = None
) -> DeckReport:
    """Judge a parsed decklist and describe the Builder's room to move within it.

    A Constraint, when the caller has one, is judged *beside* legality and never
    folded into it: `legal` stays a statement about the rules, because that is the
    field that decides whether the queue may see this deck at all.
    """
    banlist = index.banlist
    main = Counter(parsed.main)
    extra = Counter(parsed.extra)

    flags: list[CardFlag] = []
    for code, count in main.items():
        flag = _flag_card(index, code, count, CardSection.MAIN, banlist)
        if flag is not None:
            flags.append(flag)
    for code, count in extra.items():
        flag = _flag_card(index, code, count, CardSection.EXTRA, banlist)
        if flag is not None:
            flags.append(flag)

    deck_flags: list[DeckFlag] = []
    main_count = len(parsed.main)
    extra_count = len(parsed.extra)

    if not parsed.main and not parsed.extra:
        deck_flags.append(
            DeckFlag(
                issue=DeckIssue.NOTHING_PARSED,
                reason=(
                    "No cards were read. Paste a .ydk export, or one card name per "
                    "line with an optional count, like `3 Ash Blossom & Joyous Spring`."
                ),
            )
        )
    elif main_count < MAIN_MIN:
        deck_flags.append(
            DeckFlag(
                issue=DeckIssue.MAIN_TOO_SMALL,
                reason=f"{main_count} cards in the main deck; the minimum is {MAIN_MIN}.",
            )
        )
    elif main_count > MAIN_MAX:
        deck_flags.append(
            DeckFlag(
                issue=DeckIssue.MAIN_TOO_LARGE,
                reason=f"{main_count} cards in the main deck; the maximum is {MAIN_MAX}.",
            )
        )

    if extra_count > EXTRA_MAX:
        deck_flags.append(
            DeckFlag(
                issue=DeckIssue.EXTRA_TOO_LARGE,
                reason=f"{extra_count} cards in the Extra Deck; the maximum is {EXTRA_MAX}.",
            )
        )

    entries = [
        DeckEntry(card=card, count=count, section=section)
        for section, counts in ((CardSection.MAIN, main), (CardSection.EXTRA, extra))
        for card, count in _resolved(index, counts)
    ]

    legal = not flags and not deck_flags
    return DeckReport(
        deck=Deck(main=sorted(parsed.main)) if parsed.main else None,
        extra=sorted(parsed.extra),
        legal=legal,
        banlist=banlist,
        entries=entries,
        flags=sorted(flags, key=lambda f: (f.issue.value, f.name or "")),
        deck_flags=deck_flags,
        unresolved=parsed.unresolved,
        mask=_mask(index, main, constraint),
        constraint=(
            constraints.review(index, main, constraint, main_count=main_count)
            if constraint is not None
            else None
        ),
        main_count=main_count,
        extra_count=extra_count,
    )


def _resolved(index: CardIndex, counts: Counter[int]) -> list[tuple[Card, int]]:
    """Entries the app can name. A code it cannot name lives only in the flags."""
    out: list[tuple[Card, int]] = []
    for code, count in counts.items():
        card = index.get(code)
        if card is not None:
            out.append((card, count))
    out.sort(key=lambda pair: (not pair[0].in_pool, pair[0].kind, pair[0].name))
    return out
