"""The slice-5 manual test, automated: save two decks, diff them, read their Gates."""

from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio

from ai_draw_api.library import fingerprint
from ai_draw_api.refine import deck_diff
from ai_draw_api.models import Deck

pytestmark = pytest.mark.asyncio

# Three lists over pool cards, differing by known amounts. The library never judges
# legality, so these are as short as the assertions need them to be.
ASH = 14558127
MAXX_C = 101210009
SHADDOLL_DRAGON = 8240199
SHADDOLL_BEAST = 62834229


async def _await_state(client, job_id: str, states: set[str], timeout: float = 20.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        job = (await client.get(f"/api/jobs/{job_id}")).json()
        if job["state"] in states:
            return job
        await asyncio.sleep(0.02)
    raise AssertionError(f"job {job_id} never reached {states}; last was {job}")


async def _save(client, name: str, main: list[int], extra: list[int] | None = None):
    r = await client.post(
        "/api/library/decks",
        json={"name": name, "main": main, "extra": extra or []},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _gate(client, main: list[int]):
    """Run a Gate evaluation of exactly this main deck, and wait for it."""
    r = await client.post(
        "/api/jobs/test", json={"deck": {"main": main}, "gate_duels": 500}
    )
    assert r.status_code == 201, r.text
    return await _await_state(client, r.json()["id"], {"succeeded", "failed"})


def _legal_deck(pool: list[int], size: int = 40) -> list[int]:
    """A 40-card main deck of distinct pool cards, so a test job will accept it."""
    return sorted(pool[:size])


@pytest_asyncio.fixture
async def main_pool(client) -> list[int]:
    cards = (await client.get("/api/pool")).json()
    return [c["code"] for c in cards if c["section"] == "main" and c["limit"] > 0]


# --- naming and versioning -------------------------------------------------------


async def test_the_name_is_the_deck_s_identity(client):
    first = await _save(client, "Shaddoll", [ASH, ASH])
    second = await _save(client, "shaddoll", [ASH, MAXX_C])
    assert second["deck"]["id"] == first["deck"]["id"], (
        "saving under a name the library holds is a new version of that deck, "
        "however it was capitalised"
    )
    assert second["version"] == 2
    library = (await client.get("/api/library")).json()
    assert len(library) == 1


async def test_saving_an_unchanged_deck_writes_no_version(client):
    await _save(client, "Shaddoll", [ASH, MAXX_C])
    again = await _save(client, "Shaddoll", [MAXX_C, ASH])
    assert again["created"] is False, "a version number records a change, not a click"
    assert again["version"] == 1
    assert len(again["deck"]["versions"]) == 1
    assert "card for card" in again["reason"]


async def test_editing_the_extra_deck_alone_is_a_new_version(client):
    await _save(client, "Shaddoll", [ASH], extra=[])
    second = await _save(client, "Shaddoll", [ASH], extra=[SHADDOLL_DRAGON])
    assert second["created"] is True
    assert second["version"] == 2
    versions = second["deck"]["versions"]
    assert versions[0]["extra"] == [SHADDOLL_DRAGON]
    assert versions[1]["extra"] == [], "an older version is never rewritten"


async def test_versions_come_back_newest_first_with_their_counts(client):
    await _save(client, "Shaddoll", [ASH])
    saved = await _save(client, "Shaddoll", [ASH, MAXX_C], extra=[SHADDOLL_DRAGON])
    versions = saved["deck"]["versions"]
    assert [v["version"] for v in versions] == [2, 1]
    assert versions[0]["main_count"] == 2 and versions[0]["extra_count"] == 1


async def test_two_names_are_two_decks(client):
    await _save(client, "Shaddoll", [ASH])
    await _save(client, "Labrynth", [MAXX_C])
    library = (await client.get("/api/library")).json()
    assert [deck["name"] for deck in library] == ["Labrynth", "Shaddoll"], (
        "the library is listed by name, so it reads the same on every reload"
    )


async def test_deleting_a_deck_forgets_every_version_of_it(client):
    saved = await _save(client, "Shaddoll", [ASH])
    await _save(client, "Shaddoll", [ASH, MAXX_C])
    r = await client.delete(f"/api/library/decks/{saved['deck']['id']}")
    assert r.status_code == 204
    assert (await client.get("/api/library")).json() == []
    assert (await client.delete(f"/api/library/decks/{saved['deck']['id']}")).status_code == 404


# --- the two content addresses ---------------------------------------------------


async def test_a_fingerprint_ignores_order_and_counts_copies():
    assert fingerprint([1, 2, 3]) == fingerprint([3, 2, 1])
    assert fingerprint([1, 1, 2]) != fingerprint([1, 2])


async def test_the_extra_deck_is_in_the_fingerprint_and_not_in_the_main_key():
    assert fingerprint([1, 2], [9]) != fingerprint([1, 2], [])
    assert fingerprint([1, 2]) == fingerprint([2, 1])


async def test_the_gate_key_is_the_main_deck_alone(client):
    """A job carries a main deck, so a win rate cannot be about an Extra Deck."""
    a = await _save(client, "A", [ASH, MAXX_C], extra=[SHADDOLL_DRAGON])
    b = await _save(client, "B", [MAXX_C, ASH], extra=[])
    assert a["deck"]["versions"][0]["fingerprint"] != b["deck"]["versions"][0]["fingerprint"]
    assert a["deck"]["versions"][0]["main_key"] == b["deck"]["versions"][0]["main_key"]


# --- the link to a Gate result ---------------------------------------------------


async def test_a_gate_result_finds_the_deck_saved_after_it_ran(client, main_pool):
    """The link is the decklist, not a pointer written at submit time."""
    main = _legal_deck(main_pool)
    done = await _gate(client, main)
    assert done["state"] == "succeeded", done["error"]

    saved = await _save(client, "Tested", main)
    gate = saved["deck"]["versions"][0]["gate"]
    assert gate is not None, "saved after the job, and still attached to it"
    assert gate["job_id"] == done["id"]
    assert gate["duels"] == 500
    assert gate["fidelity"] == "gate"
    assert gate["win_rate"] == pytest.approx(done["result"]["win_rate"])
    assert gate["margin"] == pytest.approx(done["result"]["margin"])


async def test_the_latest_gate_result_wins(client, main_pool):
    main = _legal_deck(main_pool)
    await _gate(client, main)
    second = await _gate(client, main)
    saved = await _save(client, "Tested", main)
    assert saved["deck"]["versions"][0]["gate"]["job_id"] == second["id"], (
        "a deck's win rate is the last one it measured"
    )


async def test_a_version_nobody_tested_carries_no_gate_result(client, main_pool):
    main = _legal_deck(main_pool)
    await _gate(client, main)
    saved = await _save(client, "Tested", main)
    edited = await _save(client, "Tested", main[:-1] + [main_pool[41]])
    assert saved["deck"]["versions"][0]["gate"] is not None
    assert edited["deck"]["versions"][0]["gate"] is None, (
        "one card different is a different deck, and it has never been measured"
    )


async def test_a_refine_job_s_screening_number_is_never_a_library_result(
    client, main_pool
):
    main = _legal_deck(main_pool)
    r = await client.post(
        "/api/jobs/refine",
        json={"deck": {"main": main}, "mutations": 1, "screening_duels": 10},
    )
    done = await _await_state(client, r.json()["id"], {"succeeded", "failed"})
    assert done["state"] == "succeeded", done["error"]
    saved = await _save(client, "Refined", done["result"]["starting_deck"]["main"])
    assert saved["deck"]["versions"][0]["gate"] is None, (
        "a Screening win rate is refinement progress, and ADR-0003 forbids quoting "
        "it; the library must not present one as a deck's strength"
    )


async def test_a_cancelled_test_leaves_no_result_on_the_shelf(client, main_pool):
    main = _legal_deck(main_pool)
    r = await client.post(
        "/api/jobs/test", json={"deck": {"main": main}, "gate_duels": 500}
    )
    job_id = r.json()["id"]
    await client.post(f"/api/jobs/{job_id}/cancel")
    await _await_state(client, job_id, {"cancelled", "succeeded", "failed"})
    saved = await _save(client, "Half tested", main)
    if (await client.get(f"/api/jobs/{job_id}")).json()["state"] == "cancelled":
        assert saved["deck"]["versions"][0]["gate"] is None


# --- comparing two saved decks ---------------------------------------------------


async def _compare(client, left, right):
    r = await client.post("/api/library/compare", json={"left": left, "right": right})
    assert r.status_code == 200, r.text
    return r.json()


def _ref(saved, version: int | None = None) -> dict:
    return {
        "deck_id": saved["deck"]["id"],
        "version": saved["version"] if version is None else version,
    }


async def test_the_diff_is_the_refine_job_s_diff(client):
    left = await _save(client, "Left", [ASH, ASH, MAXX_C])
    right = await _save(client, "Right", [ASH, SHADDOLL_BEAST, SHADDOLL_DRAGON])
    body = await _compare(client, _ref(left), _ref(right))
    expected = deck_diff(
        Deck(main=[ASH, ASH, MAXX_C]),
        Deck(main=[ASH, SHADDOLL_BEAST, SHADDOLL_DRAGON]),
    ).model_dump(mode="json")
    assert body["diff"] == expected, "one counting function, one answer"
    assert body["diff"]["unchanged"] == 1


async def test_extra_decks_are_diffed_too_and_kept_apart_from_the_main_deck(client):
    left = await _save(client, "Left", [ASH], extra=[SHADDOLL_DRAGON])
    right = await _save(client, "Right", [ASH], extra=[SHADDOLL_BEAST])
    body = await _compare(client, _ref(left), _ref(right))
    assert body["diff"]["added"] == [] and body["diff"]["removed"] == []
    assert [c["card"] for c in body["extra_diff"]["added"]] == [SHADDOLL_BEAST]
    assert [c["card"] for c in body["extra_diff"]["removed"]] == [SHADDOLL_DRAGON]


async def test_comparing_two_versions_of_one_deck(client):
    saved = await _save(client, "Shaddoll", [ASH, MAXX_C])
    second = await _save(client, "Shaddoll", [ASH, SHADDOLL_DRAGON])
    body = await _compare(client, _ref(saved, 1), _ref(second, 2))
    assert body["left"]["name"] == body["right"]["name"] == "Shaddoll"
    assert [c["card"] for c in body["diff"]["added"]] == [SHADDOLL_DRAGON]


async def test_a_version_the_library_does_not_have_is_a_404(client):
    saved = await _save(client, "Shaddoll", [ASH])
    r = await client.post(
        "/api/library/compare",
        json={"left": _ref(saved), "right": _ref(saved, 7)},
    )
    assert r.status_code == 404
    assert "version" in r.json()["detail"]


async def test_a_comparison_with_no_gate_result_says_which_side_is_missing(client):
    left = await _save(client, "Untested", [ASH])
    right = await _save(client, "Also untested", [MAXX_C])
    body = await _compare(client, _ref(left), _ref(right))
    assert body["gate"] is None
    assert "Untested v1" in body["gate_note"]
    assert "Also untested v1" in body["gate_note"]


async def test_a_difference_smaller_than_the_two_bands_separates_nothing():
    """The verdict a real executor will hand out constantly, asserted directly.

    The fake executor's win rate is a hash of the decklist, so two decks one card
    apart land 18 points apart today and every comparison in the app says
    "separated". Real duels will not do that: three points between two 500-duel
    Gate results is the ordinary case, and it is inside the band.
    """
    from ai_draw_api.library import _gate_verdict
    from ai_draw_api.models import GateSnapshot

    verdict = _gate_verdict(
        GateSnapshot(job_id="a", win_rate=0.52, duels=500, live=True, finished_at=1.0),
        GateSnapshot(job_id="b", win_rate=0.55, duels=500, live=True, finished_at=2.0),
    )
    assert verdict.difference == pytest.approx(0.03)
    assert verdict.margin == pytest.approx(0.062, abs=0.002)
    assert verdict.separated is False
    assert "do not tell these decks apart" in verdict.reason
    assert "Paired" in verdict.reason, (
        "the sentence has to say what would separate them, not only that this "
        "does not"
    )


async def test_a_comparison_carries_the_band_its_two_measurements_earn(
    client, main_pool
):
    """Two 500-duel Gate results carry a combined band of about six points."""
    a, b = _legal_deck(main_pool), _legal_deck(main_pool[1:])
    for main in (a, b):
        assert (await _gate(client, main))["state"] == "succeeded"
    left, right = await _save(client, "A", a), await _save(client, "B", b)
    body = await _compare(client, _ref(left), _ref(right))
    gate = body["gate"]
    assert gate is not None
    assert gate["difference"] == pytest.approx(
        body["right"]["version"]["gate"]["win_rate"]
        - body["left"]["version"]["gate"]["win_rate"]
    )
    assert gate["margin"] == pytest.approx(
        (
            body["left"]["version"]["gate"]["margin"] ** 2
            + body["right"]["version"]["gate"]["margin"] ** 2
        )
        ** 0.5
    )
    assert gate["separated"] is (abs(gate["difference"]) > gate["margin"])
    assert ("does not tell" in gate["reason"]) is not gate["separated"]
    assert "Delta score" in gate["reason"], (
        "a difference of two absolute win rates is not a Delta score, and the "
        "sentence has to say so"
    )


async def test_the_same_deck_compared_with_itself_is_a_zero_no_one_can_read(
    client, main_pool
):
    main = _legal_deck(main_pool)
    await _gate(client, main)
    saved = await _save(client, "Twice", main)
    body = await _compare(client, _ref(saved), _ref(saved))
    assert body["diff"]["added"] == []
    assert body["gate"]["difference"] == 0.0
    assert body["gate"]["separated"] is False


async def test_a_fake_win_rate_is_never_compared_with_a_real_one(client, main_pool):
    """Slice 7 swaps the executor, so one library will hold both kinds."""
    from ai_draw_api.library import _gate_verdict
    from ai_draw_api.models import GateSnapshot

    real = GateSnapshot(
        job_id="a", win_rate=0.6, duels=500, live=True, finished_at=1.0
    )
    fake = GateSnapshot(
        job_id="b", win_rate=0.4, duels=500, live=False, finished_at=2.0
    )
    # The verdict itself is pure arithmetic; the refusal is in `compare`, which is
    # what the endpoint calls, so the two are asserted where each of them lives.
    assert _gate_verdict(fake, real).difference == pytest.approx(0.2)

    main = _legal_deck(main_pool)
    done = await _gate(client, main)
    assert done["result"]["live"] is False, "the test suite runs on the fake executor"
    saved = await _save(client, "Fake", main)
    assert saved["deck"]["versions"][0]["gate"]["live"] is False


# --- the manual test -------------------------------------------------------------


async def test_the_slice_5_manual_test(client, main_pool):
    """Save two decks, diff them, and see each one's last Gate result."""
    first = _legal_deck(main_pool)
    # Four cards swapped out for four the first deck does not hold.
    second = sorted(first[:36] + main_pool[40:44])
    assert len(second) == 40 and len(set(second) & set(first)) == 36

    for main in (first, second):
        done = await _gate(client, main)
        assert done["state"] == "succeeded", done["error"]

    left = await _save(client, "Shaddoll", first)
    right = await _save(client, "Shaddoll, four cards later", second)

    library = (await client.get("/api/library")).json()
    assert len(library) == 2
    for deck in library:
        assert deck["versions"][0]["gate"]["fidelity"] == "gate"
        assert deck["versions"][0]["gate"]["duels"] == 500

    body = await _compare(client, _ref(left), _ref(right))
    assert sum(c["count"] for c in body["diff"]["added"]) == 4
    assert sum(c["count"] for c in body["diff"]["removed"]) == 4
    assert body["diff"]["unchanged"] == 36
    assert body["left"]["version"]["gate"]["job_id"] != body["right"]["version"]["gate"]["job_id"]
    assert body["gate"]["margin"] == pytest.approx(0.062, abs=0.01), (
        "two 500-duel Gate results are +/-6 points apart before they say anything"
    )


async def test_the_shelf_refuses_nothing_the_queue_would(client):
    """An illegal deck is saved. Legality gates the queue, not the library."""
    over = await _save(client, "Sixty-one cards", [ASH] * 61)
    assert over["created"] is True
    assert over["deck"]["versions"][0]["main_count"] == 61
    short = await _save(client, "Work in progress", [ASH, MAXX_C])
    assert short["created"] is True
    # And the queue still refuses what it always refused.
    r = await client.post("/api/jobs/test", json={"deck": {"main": [ASH] * 61}})
    assert r.status_code == 422


async def test_reverting_to_an_earlier_list_is_a_new_version(client):
    """Unchanged is judged against the newest version, and only that one.

    A, then B, then A again is v1, v2, v3. Folding the third save back onto v1
    would be claiming the deck never went to B and came back, which is the one
    thing the history is for.
    """
    await _save(client, "Shaddoll", [ASH])
    await _save(client, "Shaddoll", [MAXX_C])
    back = await _save(client, "Shaddoll", [ASH])
    assert back["created"] is True
    assert back["version"] == 3
    assert [v["main"] for v in back["deck"]["versions"]] == [[ASH], [MAXX_C], [ASH]]
