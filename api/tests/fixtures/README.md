# Test fixtures

`Shaddoll.ydk` is a copy of `vendor/ygo-agent/assets/deck/Shaddoll.ydk`, one of the 33
decks the executor ships with. It is copied rather than read through the submodule so
the app's tests run on a checkout that has not initialised `vendor/` -- slices 0-6 are
frontend-and-fake work and do not need the executor (ADR-0005).

It is the strongest fixture available: a deck built by a human for this exact card
pool. If our legality rules reject it, our rules are wrong, not the deck.
