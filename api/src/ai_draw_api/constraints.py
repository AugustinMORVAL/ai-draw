"""Constraints: what the user asked for, enforced by Masking.

A **Constraint** is a user-supplied restriction on deck composition -- "at least 20
Spellcaster cards", "at most 6 Traps", "40 cards, not 60". It is not Legality.
Legality is never negotiated and breaking it aborts `ygopro-core`; a Constraint is a
preference the user chose and may drop, and breaking it just means the deck is not
the deck they wanted (CONTEXT.md).

Until Conditioning lands in phase 3, a Constraint is honoured by **Masking alone**
(ADR-0005): picks that would break it are removed from the Builder's action space,
so the deck comes back respecting the Constraint without the policy ever having been
steered toward it. A user asking for a Spellcaster deck gets a legal Spellcaster
deck, not a deck the Builder *wanted* to build that way. This module is that mask.

The two bounds mask differently, and the asymmetry is the interesting part:

- An **at-most** clause leaves the action space the moment its cap is met. Easy.
- An **at-least** clause is masked by the *slots that are left*. When the empty
  slots run down to exactly the cards still owed, everything else is masked out.
  That is what makes a feasible minimum always satisfied by construction, rather
  than satisfied if the draw happens to cooperate.

One function, `action_space`, answers "what may be picked into this deck" for all
three callers -- the Masking preview the deck editor shows, deck construction, and
each swap a refine job proposes -- so the preview cannot promise a pick the Builder
would not make.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass

from .cards import CardIndex, card_index
from .models import (
    Bound,
    ClauseStatus,
    Card,
    CardSection,
    Constraint,
    ConstraintClause,
    ConstraintFacet,
    ConstraintFlag,
    ConstraintIssue,
    ConstraintReport,
    Deck,
    FacetValue,
    Facets,
)

#: The deck a build lands on when the user set no card-count cap. Legality's floor,
#: and the size a deck is built at unless there is a reason not to.
DEFAULT_MAIN_SIZE = 40

#: Facets whose values are mutually exclusive: a card has exactly one race, one
#: attribute, one kind. Their floors therefore add up, and a total above the deck
#: size is impossible. Subtypes overlap (a card is both `effect` and `tuner`), so
#: they are never summed.
EXCLUSIVE = (ConstraintFacet.RACE, ConstraintFacet.ATTRIBUTE, ConstraintFacet.KIND)

FACET_NOUN = {
    ConstraintFacet.RACE: "race",
    ConstraintFacet.ATTRIBUTE: "attribute",
    ConstraintFacet.KIND: "card type",
    ConstraintFacet.SUBTYPE: "subtype",
}


class Impossible(Exception):
    """No legal deck satisfies this Constraint. Carries the sentences to show."""

    def __init__(self, flags: list[ConstraintFlag]) -> None:
        super().__init__("; ".join(flag.reason for flag in flags))
        self.flags = flags


def deck_size(constraint: Constraint) -> int:
    """How big a deck built under this Constraint should be."""
    return constraint.main_size or DEFAULT_MAIN_SIZE


def describe(clause: ConstraintClause) -> str:
    """A clause as a user would say it, for reuse in every sentence about it."""
    bound = "at least" if clause.bound is Bound.AT_LEAST else "at most"
    return f"{bound} {clause.count} {clause.value} ({FACET_NOUN[clause.facet]})"


def matches(card: Card, clause: ConstraintClause) -> bool:
    """Does this card count toward this clause? Values compare case-insensitively.

    A `.ydk` and a form both come from humans: `DARK` and `dark` are the same
    attribute, and a Constraint is not the place to teach that lesson.
    """
    wanted = clause.value.casefold()
    if clause.facet is ConstraintFacet.RACE:
        return (card.race or "").casefold() == wanted
    if clause.facet is ConstraintFacet.ATTRIBUTE:
        return (card.attribute or "").casefold() == wanted
    if clause.facet is ConstraintFacet.KIND:
        return card.kind.casefold() == wanted
    return any(subtype.casefold() == wanted for subtype in card.subtypes)


@dataclass(frozen=True)
class Space:
    """The Builder's action space inside one deck: what it may add, and what it may not.

    `masked` is grouped by reason rather than listed card by card, because "712
    picks are gone" tells a user nothing about what the Builder is choosing between.
    """

    allowed: tuple[int, ...]
    masked: dict[str, int]

    def pays(self, index: CardIndex, clauses: list[ConstraintClause]) -> tuple[int, ...]:
        """Allowed picks that count toward at least one of these clauses."""
        return tuple(
            code
            for code in self.allowed
            if any(matches(index.pool[code], clause) for clause in clauses)
        )


def _legality_reason(card: Card, main: Counter[int]) -> str | None:
    """Why Legality removes this card from the action space, if it does."""
    if card.section is CardSection.TOKEN:
        return "Tokens, which are made and never deckable"
    if card.section is CardSection.EXTRA:
        return "Extra Deck: phase 1 builds main decks only"
    if card.limit == 0:
        return "Forbidden on the banlist"
    if main.get(card.code, 0) >= card.limit:
        return "Already at its copy limit in this deck"
    return None


def held_counts(
    index: CardIndex, main: Counter[int], constraint: Constraint
) -> list[int]:
    """How many cards this deck already holds for each clause, in clause order."""
    counts = [0] * len(constraint.clauses)
    for code, copies in main.items():
        card = index.get(code)
        if card is None:
            continue
        for i, clause in enumerate(constraint.clauses):
            if matches(card, clause):
                counts[i] += copies
    return counts


def action_space(
    index: CardIndex,
    main: Counter[int],
    constraint: Constraint | None = None,
    *,
    target_size: int | None = None,
) -> Space:
    """What may be added to this main deck, and the reasons for everything that may not.

    `target_size` is how big the deck is meant to end up: the Constraint's card
    count while building, the deck's own size while swapping. It is what makes an
    at-least clause maskable — without knowing how many slots are left, "you still
    owe 8 Spellcasters" cannot be turned into "only Spellcasters may be picked".
    """
    groups: Counter[str] = Counter()
    legal: list[int] = []
    for code, card in index.pool.items():
        reason = _legality_reason(card, main)
        if reason is None:
            legal.append(code)
        else:
            groups[reason] += 1

    if constraint is None or not constraint.clauses:
        return Space(tuple(legal), dict(groups))

    held = held_counts(index, main, constraint)
    size = sum(main.values())
    slots_left = max(0, (target_size or deck_size(constraint)) - size)
    owed = {
        i: clause.count - held[i]
        for i, clause in enumerate(constraint.clauses)
        if clause.bound is Bound.AT_LEAST and clause.count > held[i]
    }
    # Every remaining slot is spoken for, so nothing that pays down a floor may take
    # one. Overlapping floors (DARK Dragons pay two at once) make this trigger a
    # little early, which costs some variety and never costs correctness.
    forced = bool(owed) and sum(owed.values()) >= slots_left > 0

    allowed: list[int] = []
    for code in legal:
        card = index.pool[code]
        capped = next(
            (
                clause
                for i, clause in enumerate(constraint.clauses)
                if clause.bound is Bound.AT_MOST
                and held[i] >= clause.count
                and matches(card, clause)
            ),
            None,
        )
        if capped is not None:
            groups[f"Ruled out by your Constraint: {describe(capped)}"] += 1
            continue
        if forced and not any(matches(card, constraint.clauses[i]) for i in owed):
            groups["The slots left are owed to a minimum you set"] += 1
            continue
        allowed.append(code)

    return Space(tuple(allowed), dict(groups))


def ceiling(index: CardIndex, clause: ConstraintClause) -> int:
    """The most copies the supported pool could supply for this clause.

    Counted over main-deck cards only, with the banlist applied, because those are
    the only cards a deck can be built from. A floor above this number is a
    Constraint the pool cannot meet however good the Builder gets.
    """
    return sum(
        index.pool[code].limit
        for code in index.main_deck_codes()
        if matches(index.pool[code], clause)
    )


def _impossible_flags(index: CardIndex, constraint: Constraint) -> list[ConstraintFlag]:
    """Why no legal deck could satisfy this Constraint. Empty when one could."""
    flags: list[ConstraintFlag] = []
    caps = {
        (clause.facet, clause.value.casefold()): clause
        for clause in constraint.clauses
        if clause.bound is Bound.AT_MOST
    }

    for clause in constraint.clauses:
        if clause.bound is not Bound.AT_LEAST:
            continue

        room = ceiling(index, clause)
        if clause.count > room:
            outside = sum(
                1
                for card in index.pool.values()
                if matches(card, clause) and card.section is not CardSection.MAIN
            )
            aside = (
                f" The pool carries {outside} more, and every one is a Token or an "
                "Extra Deck monster, which no main deck may hold."
                if outside
                else ""
            )
            flags.append(
                ConstraintFlag(
                    issue=ConstraintIssue.IMPOSSIBLE,
                    clause=clause,
                    reason=(
                        f"You asked for {describe(clause)}, but the 864-card pool can "
                        f"supply at most {room} such {'copy' if room == 1 else 'copies'} "
                        f"to a main deck.{aside}"
                    ),
                )
            )
            continue

        if clause.count > deck_size(constraint):
            flags.append(
                ConstraintFlag(
                    issue=ConstraintIssue.IMPOSSIBLE,
                    clause=clause,
                    reason=(
                        f"You asked for {describe(clause)} in a deck of "
                        f"{deck_size(constraint)} cards."
                    ),
                )
            )
            continue

        cap = caps.get((clause.facet, clause.value.casefold()))
        if cap is not None and cap.count < clause.count:
            flags.append(
                ConstraintFlag(
                    issue=ConstraintIssue.IMPOSSIBLE,
                    clause=clause,
                    reason=(
                        f"You asked for {describe(clause)} and {describe(cap)} at the "
                        "same time."
                    ),
                )
            )

    for facet in EXCLUSIVE:
        floors = [
            clause
            for clause in constraint.clauses
            if clause.facet is facet and clause.bound is Bound.AT_LEAST
        ]
        total = sum(clause.count for clause in floors)
        if len(floors) > 1 and total > deck_size(constraint):
            named = ", ".join(f"{c.count} {c.value}" for c in floors)
            flags.append(
                ConstraintFlag(
                    issue=ConstraintIssue.IMPOSSIBLE,
                    reason=(
                        f"{named} is {total} cards, and a card has exactly one "
                        f"{FACET_NOUN[facet]}, so they cannot share a deck of "
                        f"{deck_size(constraint)}."
                    ),
                )
            )

    # Can the deck even be filled? An upper bound: cards under no cap contribute
    # every copy they have, each capped group contributes at most its cap. It
    # over-counts cards sitting in two capped groups, which is safe -- an upper
    # bound below the deck size is impossible for certain.
    if caps:
        uncapped = sum(
            index.pool[code].limit
            for code in index.main_deck_codes()
            if not any(matches(index.pool[code], cap) for cap in caps.values())
        )
        room = uncapped + sum(cap.count for cap in caps.values())
        if room < deck_size(constraint):
            flags.append(
                ConstraintFlag(
                    issue=ConstraintIssue.IMPOSSIBLE,
                    reason=(
                        f"Your caps leave room for at most {room} cards, and you asked "
                        f"for a deck of {deck_size(constraint)}."
                    ),
                )
            )

    return flags


def review(
    index: CardIndex, main: Counter[int], constraint: Constraint, *, main_count: int
) -> ConstraintReport:
    """Judge a deck against what was asked for. Never against Legality -- that is `legality`."""
    impossible = _impossible_flags(index, constraint)
    held = held_counts(index, main, constraint)

    clauses: list[ClauseStatus] = []
    flags: list[ConstraintFlag] = list(impossible)
    for i, clause in enumerate(constraint.clauses):
        ok = (
            held[i] >= clause.count
            if clause.bound is Bound.AT_LEAST
            else held[i] <= clause.count
        )
        clauses.append(
            ClauseStatus(
                clause=clause,
                held=held[i],
                satisfied=ok,
                ceiling=ceiling(index, clause),
            )
        )
        if ok:
            continue
        if clause.bound is Bound.AT_LEAST:
            flags.append(
                ConstraintFlag(
                    issue=ConstraintIssue.UNMET_MINIMUM,
                    clause=clause,
                    reason=(
                        f"{held[i]} of the {clause.count} {clause.value} cards you "
                        f"asked for. {clause.count - held[i]} to go."
                    ),
                )
            )
        else:
            flags.append(
                ConstraintFlag(
                    issue=ConstraintIssue.OVER_MAXIMUM,
                    clause=clause,
                    reason=(
                        f"{held[i]} {clause.value} cards, {held[i] - clause.count} "
                        f"over the {clause.count} you allowed."
                    ),
                )
            )

    # No cap means no size to fall short of: legality's 40-to-60 already holds and
    # is reported by `legality`, so repeating it here as a Constraint would invent
    # a preference the user never stated.
    if constraint.main_size is not None and main_count not in (
        0,
        constraint.main_size,
    ):
        flags.append(
            ConstraintFlag(
                issue=ConstraintIssue.WRONG_SIZE,
                reason=(
                    f"{main_count} cards in the main deck; you asked for "
                    f"{constraint.main_size}. Legality allows 40 to 60, so this is "
                    "your cap talking, not the rules."
                ),
            )
        )

    return ConstraintReport(
        constraint=constraint,
        feasible=not impossible,
        satisfied=not flags,
        clauses=clauses,
        flags=flags,
    )


def construct(
    index: CardIndex, constraint: Constraint, *, seed: int | None = None
) -> Deck:
    """Build a deck that satisfies a Constraint, by only ever picking inside the mask.

    Floors are paid first. Draw filler first and a cap can steal the slots a floor
    needed -- 25 non-Spellcaster monsters under "at most 25 monsters" leaves "at
    least 20 Spellcasters" unpayable in a Constraint that was perfectly satisfiable.

    This is not the Builder. It is a uniform draw inside the mask, which is exactly
    what ADR-0005 says "based on their interest" means before phase 3: a legal deck
    that respects the Constraint, not a deck a policy intended.
    """
    impossible = _impossible_flags(index, constraint)
    if impossible:
        raise Impossible(impossible)

    rng = random.Random(seed)
    main: Counter[int] = Counter()

    size = deck_size(constraint)
    while sum(main.values()) < size:
        space = action_space(index, main, constraint, target_size=size)
        if not space.allowed:
            raise Impossible(
                [
                    ConstraintFlag(
                        issue=ConstraintIssue.IMPOSSIBLE,
                        reason=(
                            f"After {sum(main.values())} cards, your Constraint leaves "
                            "no card that may be added. Two of its clauses are pulling "
                            "against each other."
                        ),
                    )
                ]
            )
        held = held_counts(index, main, constraint)
        owed = [
            clause
            for i, clause in enumerate(constraint.clauses)
            if clause.bound is Bound.AT_LEAST and held[i] < clause.count
        ]
        pool = space.pays(index, owed) if owed else ()
        main[rng.choice(pool or space.allowed)] += 1

    return Deck(main=sorted(main.elements()))


def random_deck(size: int = 40, *, seed: int | None = None) -> Deck:
    """A legal deck from the supported pool, under no Constraint. Legal, not good."""
    return construct(card_index(), Constraint(main_size=size), seed=seed)


def facets(index: CardIndex) -> Facets:
    """Every value a clause can name, with what the pool can supply for it.

    Values the pool knows but cannot put in a main deck are listed too, at a
    ceiling of zero. Omitting them would leave a user asking for a Cyberse deck
    with an empty dropdown and no idea why -- and Cyberse is a real case here: the
    pool carries 34 of them and every one is a Token or a Link monster.
    """
    tally: dict[tuple[ConstraintFacet, str], list[int]] = {}

    def add(facet: ConstraintFacet, value: str, card: Card) -> None:
        entry = tally.setdefault((facet, value), [0, 0, 0])
        if card.section is CardSection.MAIN and card.limit > 0:
            entry[0] += 1
            entry[1] += card.limit
        else:
            entry[2] += 1

    for card in index.pool.values():
        if card.race:
            add(ConstraintFacet.RACE, card.race, card)
        if card.attribute:
            add(ConstraintFacet.ATTRIBUTE, card.attribute, card)
        add(ConstraintFacet.KIND, card.kind, card)
        for subtype in card.subtypes:
            add(ConstraintFacet.SUBTYPE, subtype, card)

    values = [
        FacetValue(
            facet=facet, value=value, cards=cards, copies=copies, elsewhere=elsewhere
        )
        for (facet, value), (cards, copies, elsewhere) in tally.items()
    ]
    values.sort(key=lambda v: (v.facet.value, -v.copies, v.value))
    return Facets(main_deck_pool_size=len(index.main_deck_codes()), values=values)
