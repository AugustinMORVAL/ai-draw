"""Slice 6: a finished job keeps a sample of duels, and they can be watched.

The logs are fabricated -- `FakeExecutor` has no duels behind it (ADR-0005) -- so
every assertion here is about the *shape* the replay viewer relies on, never about
Yu-Gi-Oh. The one thing that must hold either way: a replay that names a winner has
to show that winner winning.
"""

from __future__ import annotations

import asyncio

import pytest

from ai_draw_api.constraints import random_deck
from ai_draw_api.executor import GAUNTLET, REPLAY_SAMPLE, FakeExecutor
from ai_draw_api.models import DuelSeat
from ai_draw_api.gauntlet import gauntlet_decks, gauntlet_names

pytestmark = pytest.mark.asyncio


async def _finished_job(client) -> dict:
    r = await client.post(
        "/api/jobs/refine", json={"mutations": 2, "screening_duels": 10}
    )
    job_id = r.json()["id"]
    deadline = asyncio.get_running_loop().time() + 10.0
    while asyncio.get_running_loop().time() < deadline:
        job = (await client.get(f"/api/jobs/{job_id}")).json()
        if job["state"] in {"succeeded", "failed"}:
            assert job["state"] == "succeeded", job["error"]
            return job
        await asyncio.sleep(0.02)
    raise AssertionError("job never finished")


async def test_a_finished_job_keeps_one_duel_per_gauntlet_deck(client):
    """The sample is stratified, in the Gauntlet's fixed order.

    Picking the opponents by hash left half the Gauntlet unrepresented and two duels
    against the same deck, which on a test job means matchup rows a user can read and
    cannot open.
    """
    job = await _finished_job(client)
    replays = (await client.get(f"/api/jobs/{job['id']}/replays")).json()
    assert len(replays) == REPLAY_SAMPLE == len(GAUNTLET)
    assert [r["opponent"] for r in replays] == list(GAUNTLET)
    assert all(r["live"] is False for r in replays), "a fake duel must say so"
    assert "log" not in replays[0], "the list is summaries; logs come one at a time"


async def test_half_the_kept_duels_are_on_the_play(client):
    """ADR-0004 forces the seat 50/50 over a batch, and this sample is the batch."""
    job = await _finished_job(client)
    replays = (await client.get(f"/api/jobs/{job['id']}/replays")).json()
    first = [r for r in replays if r["going_first"] == "candidate"]
    assert len(first) == len(replays) - len(first)


async def test_the_kept_duels_a_deck_wins_are_its_best_matchups():
    """A duel lost in an 80% matchup would teach a user to distrust the breakdown."""
    fake = FakeExecutor(duel_seconds=0.0)
    deck = random_deck(seed=11)
    replays = await fake.replays(deck, count=REPLAY_SAMPLE)
    rates = fake._matchup_rates(deck, fake._true_win_rate(deck))

    won = {r.opponent for r in replays if r.winner is DuelSeat.CANDIDATE}
    lost = {r.opponent for r in replays if r.winner is DuelSeat.OPPONENT}
    assert won and lost, "a sample of ten all one way says nothing"
    assert min(rates[o] for o in won) > max(rates[o] for o in lost)

    # And the count is the deck's own win rate, so the list agrees with the number
    # printed above it rather than being a second opinion about the same deck.
    assert len(won) == round(len(replays) * fake._true_win_rate(deck))


async def test_the_job_says_which_duels_it_kept_and_carries_no_logs(client):
    """The button to watch is drawn from the job; the log comes from one endpoint.

    `GET /api/jobs/{id}` is what the browser polls, so ten logs on it would be ten
    logs every 700 ms for a job whose result nobody has opened.
    """
    job = await _finished_job(client)
    kept = job["result"]["replays"]
    assert len(kept) == REPLAY_SAMPLE
    assert all("log" not in replay for replay in kept)


async def test_one_replay_comes_back_with_its_log(client):
    job = await _finished_job(client)
    replay = (await client.get(f"/api/jobs/{job['id']}/replays/0")).json()
    log = replay["log"]
    assert len(log) == replay["events"]
    assert [event["index"] for event in log] == list(range(len(log)))
    assert {event["seat"] for event in log} == {"candidate", "opponent"}


async def test_the_winner_is_the_one_still_standing(client):
    """A declared winner with the loser above 0 life points is a broken log."""
    job = await _finished_job(client)
    for summary in (await client.get(f"/api/jobs/{job['id']}/replays")).json():
        replay = (
            await client.get(f"/api/jobs/{job['id']}/replays/{summary['index']}")
        ).json()
        last = replay["log"][-1]
        loser_life = (
            last["life_opponent"]
            if replay["winner"] == "candidate"
            else last["life_candidate"]
        )
        assert loser_life == 0, f"replay {summary['index']} ends with a living loser"


async def test_life_points_only_ever_fall(client):
    job = await _finished_job(client)
    log = (await client.get(f"/api/jobs/{job['id']}/replays/0")).json()["log"]
    for before, after in zip(log, log[1:]):
        assert after["life_candidate"] <= before["life_candidate"]
        assert after["life_opponent"] <= before["life_opponent"]


async def test_an_unfinished_job_has_nothing_to_replay(client):
    r = await client.post(
        "/api/jobs/refine", json={"mutations": 200, "screening_duels": 1000}
    )
    job_id = r.json()["id"]
    r = await client.get(f"/api/jobs/{job_id}/replays")
    assert r.status_code == 409
    assert "no duels to replay yet" in r.json()["detail"]


async def test_unknown_job_and_unknown_replay_are_404(client):
    assert (await client.get("/api/jobs/nope/replays")).status_code == 404
    job = await _finished_job(client)
    assert (await client.get(f"/api/jobs/{job['id']}/replays/99")).status_code == 404


async def test_each_seat_plays_its_own_deck():
    """A "Sky Striker Ace" summoning Shaddoll Dragon is a lie the mat draws.

    The board is the one screen a user reads card by card, so the fabrication has to
    hold per seat: the candidate plays what was submitted, the opponent plays the
    Gauntlet deck it is named after.
    """
    deck = random_deck(seed=7)
    replays = await FakeExecutor(duel_seconds=0.0).replays(deck, count=REPLAY_SAMPLE)
    decks = gauntlet_decks()
    for replay in replays:
        played: dict[str, set[int]] = {"candidate": set(), "opponent": set()}
        for event in replay.log:
            if event.card is not None:
                played[event.seat.value].add(event.card)
        assert played["candidate"], "a duel with no cards in it is not a duel"
        assert played["candidate"] <= set(deck.main)
        assert played["opponent"] <= set(decks[replay.opponent].main), (
            f"{replay.opponent} played cards from another deck"
        )


async def test_the_verb_agrees_with_the_card():
    """A Spell is activated or set; nothing Special Summons a Super Polymerization.

    The board already places a card by its own type, so without this the sentence
    and the zone it lands in describe two different plays.
    """
    from ai_draw_api.cards import card_index

    index = card_index()
    replays = await FakeExecutor(duel_seconds=0.0).replays(
        random_deck(seed=3), count=REPLAY_SAMPLE
    )
    allowed = {
        "monster": {"Normal Summons", "Special Summons", "sets"},
        "spell": {"activates", "sets"},
        "trap": {"sets"},
    }
    for replay in replays:
        for event in replay.log:
            if event.action != "summon" or event.card is None:
                continue
            card = index.get(event.card)
            assert card is not None, "a fake log still plays cards the app can draw"
            assert event.text in allowed[card.kind], (
                f"{card.name} ({card.kind}) cannot be {event.text!r}"
            )


async def test_an_attack_is_made_by_a_monster_on_the_board():
    """The mat highlights the attacker, so a Spell swinging for 1300 is visible."""
    from ai_draw_api.cards import card_index

    index = card_index()
    for replay in await FakeExecutor(duel_seconds=0.0).replays(
        random_deck(seed=5), count=REPLAY_SAMPLE
    ):
        summoned: dict[str, set[int]] = {"candidate": set(), "opponent": set()}
        for event in replay.log:
            seat = event.seat.value
            if event.action == "summon" and event.card is not None:
                card = index.get(event.card)
                if card and card.kind == "monster" and not event.text.startswith("sets"):
                    summoned[seat].add(event.card)
            elif event.action == "attack":
                assert event.card in summoned[seat], (
                    f"{seat} attacked with a card it never summoned face-up"
                )


async def test_the_gauntlet_decks_are_the_ten_the_breakdown_names():
    """One Gauntlet, in one order: the breakdown and the replays index the same list."""
    decks = gauntlet_decks()
    assert tuple(decks) == GAUNTLET == gauntlet_names()
    assert len(GAUNTLET) == 10
    for name, deck in decks.items():
        assert 40 <= len(deck.main) <= 60, f"{name} is not a legal main deck"
        assert deck.extra, f"{name} plays no Extra Deck"
