"""The Gauntlet: the ten fixed opponents, and the decks they play.

The names were a tuple in `executor.py` while a Gauntlet opponent was only ever a
label on a win rate. A duel replay asks for more than the label: the mat draws the
opponent's cards one by one, and a "Sky Striker Ace" summoning Shaddoll Dragon is a
fabrication in the one screen a user reads card by card. So the decklists ship as
data (`data/pilot-864/gauntlet.json`, written by `tools/gen_gauntlet.py`) and each
seat of a replay plays out of its own deck.

The order is fixed and comes from the file. It is fixed *within a phase* so two
decks' matchup rows line up (CONTEXT.md); nothing here may sort per deck.

Committed data, not the submodule: the API container carries `data/pilot-864/` and
neither `vendor/ygo-agent` nor any network access.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

_REPO_GAUNTLET = (
    Path(__file__).resolve().parents[3] / "data" / "pilot-864" / "gauntlet.json"
)


def gauntlet_file() -> Path:
    """Where to read the Gauntlet from. `AI_DRAW_GAUNTLET` overrides the repo copy."""
    override = os.environ.get("AI_DRAW_GAUNTLET")
    return Path(override) if override else _REPO_GAUNTLET


class GauntletDeck(BaseModel):
    """One opponent's full decklist.

    Not a `Deck`: that model is a candidate's *main* deck and nothing else, because
    a candidate is what the executor is handed and a win rate can only ever be
    attributed to those forty cards. A Gauntlet deck is a shipped `.ydk` the Pilot
    is sat opposite, Extra Deck included -- the mat has an Extra Monster Zone and
    real logs will summon into it.
    """

    name: str
    main: list[int]
    extra: list[int] = []


@lru_cache(maxsize=1)
def gauntlet_decks() -> dict[str, GauntletDeck]:
    """Each opponent's deck, keyed by name, in the Gauntlet's fixed order.

    Insertion order *is* the Gauntlet order -- a dict preserves it, so callers that
    want the order iterate this and callers that want one deck index it, and there
    is no second list to fall out of step with the first.
    """
    payload = json.loads(gauntlet_file().read_text(encoding="utf-8"))
    decks = {
        entry["name"]: GauntletDeck.model_validate(entry)
        for entry in payload["gauntlet"]
    }
    if not decks:
        raise RuntimeError(f"the Gauntlet is empty: {gauntlet_file()}")
    return decks


@lru_cache(maxsize=1)
def gauntlet_names() -> tuple[str, ...]:
    """The ten opponents, in the fixed order. What a matchup breakdown is keyed on."""
    return tuple(gauntlet_decks())
