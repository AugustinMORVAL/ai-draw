"""The deck library: named decks, versioned, and the Gate results that measured them.

A job is durable, but it is not a shelf. Slices 0 to 4 left a user with a list of
job ids and one deck in `localStorage`: the deck they were editing survived a
reload, and every deck before it did not. This is where a deck stops being the
contents of a text box and becomes something with a name, a history, and a measured
strength.

Three decisions carry the module:

- **The name is the identity.** Saving under a name the library already holds adds
  a version to that deck. There is no second "Shaddoll" and no rename-to-fork.
- **A version is immutable, and content-addressed.** Saving a list identical to the
  one already on the shelf writes nothing: a version number records a change, not a
  click.
- **A saved deck is joined to its Gate result by the decklist itself**, not by a
  stored pointer. A pointer would have to be written when the job was submitted,
  which would leave a deck saved after its own test with no result, and the same
  list saved twice with two disconnected histories.

The tables live in the job database, on the job store's connection, because that
last decision makes the library's central query a join against `jobs`.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections.abc import Iterable, Sequence

import aiosqlite

from .models import (
    ComparisonSide,
    DeckComparison,
    DeckRef,
    DeckSaved,
    DeckVersion,
    GateComparison,
    GateSnapshot,
    JobKind,
    JobState,
    LibraryDeck,
)
from .refine import diff_codes
from .store import JobStore

SCHEMA = """
CREATE TABLE IF NOT EXISTS decks (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS decks_name ON decks (name COLLATE NOCASE);
CREATE TABLE IF NOT EXISTS deck_versions (
    seq         INTEGER PRIMARY KEY AUTOINCREMENT,
    deck_id     TEXT    NOT NULL REFERENCES decks (id) ON DELETE CASCADE,
    version     INTEGER NOT NULL,
    fingerprint TEXT    NOT NULL,
    main_key    TEXT    NOT NULL,
    main        TEXT    NOT NULL,
    extra       TEXT    NOT NULL,
    note        TEXT,
    created_at  REAL    NOT NULL,
    UNIQUE (deck_id, version)
);
CREATE INDEX IF NOT EXISTS deck_versions_main_key ON deck_versions (main_key);
"""

#: Long enough that two different decklists will not collide inside one beta's
#: library, short enough to read in a URL.
KEY_LENGTH = 16


def fingerprint(main: Iterable[int], extra: Iterable[int] = ()) -> str:
    """A decklist's content address: order-independent, copy-sensitive.

    Called two ways on purpose. Over both sections it answers "is this the deck
    already on the shelf?". Over the main deck alone -- `fingerprint(main)` -- it
    answers "which Gate results measured this?", because a job carries a main deck
    and nothing else (`Deck.main`), so an Extra Deck the executor was never handed
    cannot be part of what a win rate is about.
    """
    payload = "{}|{}".format(
        ",".join(str(code) for code in sorted(main)),
        ",".join(str(code) for code in sorted(extra)),
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:KEY_LENGTH]


class DeckLibrary:
    """Named decks and their versions, over the job store's connection.

    One connection, and the job store's, because the library's central question --
    "what was this exact list last measured at?" -- is a join against the jobs
    table. Two connections to one SQLite file could answer it out of two snapshots
    and disagree about which result is the latest.

    Nothing here needs the migration `JobStore` carries: these tables did not exist
    in any earlier build, so `CREATE TABLE IF NOT EXISTS` is the whole story on a
    job volume `make down` kept.
    """

    def __init__(self, store: JobStore) -> None:
        self.store = store

    @property
    def db(self) -> aiosqlite.Connection:
        return self.store.db

    async def open(self) -> None:
        await self.db.executescript(SCHEMA)
        await self.db.commit()

    async def save(
        self,
        name: str,
        main: Sequence[int],
        extra: Sequence[int],
        note: str | None = None,
    ) -> DeckSaved:
        """Put a decklist on the shelf under `name`, as a new version if it is one.

        The name is matched case-insensitively: someone who typed "shaddoll" today
        and "Shaddoll" last week meant one deck both times.
        """
        clean = name.strip()
        now = time.time()
        async with self.db.execute(
            "SELECT id FROM decks WHERE name = ? COLLATE NOCASE", (clean,)
        ) as cur:
            row = await cur.fetchone()

        if row is None:
            deck_id = uuid.uuid4().hex[:12]
            await self.db.execute(
                "INSERT INTO decks (id, name, created_at) VALUES (?, ?, ?)",
                (deck_id, clean, now),
            )
        else:
            deck_id = row["id"]

        digest = fingerprint(main, extra)
        async with self.db.execute(
            "SELECT version, fingerprint FROM deck_versions"
            " WHERE deck_id = ? ORDER BY version DESC LIMIT 1",
            (deck_id,),
        ) as cur:
            latest = await cur.fetchone()

        if latest is not None and latest["fingerprint"] == digest:
            await self.db.commit()
            deck = await self.get(deck_id)
            assert deck is not None
            return DeckSaved(
                deck=deck,
                version=latest["version"],
                created=False,
                reason=(
                    f"This is exactly version {latest['version']} of {clean}, card "
                    "for card, so nothing was written. A version number records a "
                    "change, not a save."
                ),
            )

        version = 1 if latest is None else latest["version"] + 1
        await self.db.execute(
            "INSERT INTO deck_versions"
            " (deck_id, version, fingerprint, main_key, main, extra, note, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                deck_id,
                version,
                digest,
                fingerprint(main),
                json.dumps(sorted(main)),
                json.dumps(sorted(extra)),
                note,
                now,
            ),
        )
        await self.db.commit()
        deck = await self.get(deck_id)
        assert deck is not None
        return DeckSaved(
            deck=deck,
            version=version,
            created=True,
            reason=(
                f"Saved as {clean} v1."
                if version == 1
                else f"Saved as {clean} v{version}; v{version - 1} is untouched."
            ),
        )

    async def list(self) -> list[LibraryDeck]:
        """The whole library, versions and all, in one answer.

        Not paged and not summarised. A beta library is tens of decks of sixty
        integers; the comparison picker needs every version anyway, and a list that
        omitted the Gate results would send a user back for them one at a time.
        """
        gates = await self.gate_snapshots()
        async with self.db.execute(
            "SELECT d.id, d.name, d.created_at AS deck_created_at,"
            " v.version, v.fingerprint, v.main_key, v.main, v.extra, v.note,"
            " v.created_at"
            " FROM decks d JOIN deck_versions v ON v.deck_id = d.id"
            " ORDER BY d.name COLLATE NOCASE, v.version DESC"
        ) as cur:
            rows = await cur.fetchall()

        decks: dict[str, LibraryDeck] = {}
        for row in rows:
            deck = decks.get(row["id"])
            if deck is None:
                deck = LibraryDeck(
                    id=row["id"], name=row["name"], created_at=row["deck_created_at"]
                )
                decks[row["id"]] = deck
            deck.versions.append(_version(row, gates))
        return list(decks.values())

    async def get(self, deck_id: str) -> LibraryDeck | None:
        gates = await self.gate_snapshots()
        async with self.db.execute(
            "SELECT id, name, created_at FROM decks WHERE id = ?", (deck_id,)
        ) as cur:
            head = await cur.fetchone()
        if head is None:
            return None
        async with self.db.execute(
            "SELECT version, fingerprint, main_key, main, extra, note, created_at"
            " FROM deck_versions WHERE deck_id = ? ORDER BY version DESC",
            (deck_id,),
        ) as cur:
            rows = await cur.fetchall()
        return LibraryDeck(
            id=head["id"],
            name=head["name"],
            created_at=head["created_at"],
            versions=[_version(row, gates) for row in rows],
        )

    async def version(self, ref: DeckRef) -> tuple[LibraryDeck, DeckVersion] | None:
        deck = await self.get(ref.deck_id)
        if deck is None:
            return None
        match = next((v for v in deck.versions if v.version == ref.version), None)
        return None if match is None else (deck, match)

    async def delete(self, deck_id: str) -> bool:
        """Forget a deck and every version of it. Its jobs are untouched.

        A job is the record of work that was actually run, and deleting a shelf
        entry does not un-run it. What is lost is the name: the Gate result stays
        on its job, and re-saving the same list finds it again.
        """
        await self.db.execute("DELETE FROM deck_versions WHERE deck_id = ?", (deck_id,))
        cur = await self.db.execute("DELETE FROM decks WHERE id = ?", (deck_id,))
        await self.db.commit()
        return bool(cur.rowcount)

    async def gate_snapshots(self) -> dict[str, GateSnapshot]:
        """The latest Gate result for every main deck that has one.

        Test jobs only. A refine job also finishes with a win rate, but it is a
        Screening number ADR-0003 forbids quoting, so attaching one to a saved deck
        would be publishing the number the two fidelities exist to keep apart.

        The result's columns are pulled with `json_extract` rather than by loading
        the row: a Gate result carries six full duel logs, and none of them is
        needed to say what the deck scored.
        """
        async with self.db.execute(
            "SELECT id, finished_at,"
            " json_extract(result, '$.deck.main') AS main,"
            " json_extract(result, '$.win_rate')  AS win_rate,"
            " json_extract(result, '$.duels')     AS duels,"
            " json_extract(result, '$.live')      AS live"
            " FROM jobs"
            " WHERE kind = ? AND state = ? AND result IS NOT NULL"
            " ORDER BY seq",
            (JobKind.TEST.value, JobState.SUCCEEDED.value),
        ) as cur:
            rows = await cur.fetchall()

        # Ascending, so a later test of the same list overwrites an earlier one:
        # "the last Gate result" is what a user means by a deck's win rate.
        snapshots: dict[str, GateSnapshot] = {}
        for row in rows:
            if row["main"] is None or row["win_rate"] is None:
                continue
            key = fingerprint(json.loads(row["main"]))
            snapshots[key] = GateSnapshot(
                job_id=row["id"],
                win_rate=row["win_rate"],
                duels=row["duels"] or 0,
                live=bool(row["live"]),
                finished_at=row["finished_at"] or 0.0,
            )
        return snapshots


def _version(row: aiosqlite.Row, gates: dict[str, GateSnapshot]) -> DeckVersion:
    return DeckVersion(
        version=row["version"],
        fingerprint=row["fingerprint"],
        main_key=row["main_key"],
        main=json.loads(row["main"]),
        extra=json.loads(row["extra"]),
        note=row["note"],
        created_at=row["created_at"],
        gate=gates.get(row["main_key"]),
    )


def _gate_verdict(left: GateSnapshot, right: GateSnapshot) -> GateComparison:
    """Two Gate win rates, and whether they tell the two decks apart.

    This is not a Delta score. A Delta score is a win rate difference under one
    Environment set between a deck and its own mutation (CONTEXT.md), and it is
    sharp precisely because parent and child share 39 of 40 cards. Two library
    decks were measured by two separate jobs, so what is on offer is the difference
    of two absolute win rates, and the band on a difference is the two bands added
    in quadrature -- at 500 duels each, +/-6.2 points. Most deck changes are
    smaller than that, which the sentence has to say rather than imply.
    """
    difference = right.win_rate - left.win_rate
    margin = (left.margin**2 + right.margin**2) ** 0.5
    separated = abs(difference) > margin
    points = abs(difference) * 100
    band = margin * 100
    if separated:
        winner = "right" if difference > 0 else "left"
        reason = (
            f"{points:.1f} points apart, wider than the +/-{band:.1f} band the two "
            f"measurements earn between them, so the {winner}-hand deck really is "
            "the stronger of the two against this Gauntlet. Two separate Gate jobs, "
            "not a Paired A-vs-B run, so this is a difference of absolute win rates "
            "and not a Delta score."
        )
    else:
        reason = (
            f"{points:.1f} points apart, inside the +/-{band:.1f} band the two "
            "measurements earn between them: these numbers do not tell these decks "
            "apart. Gate evaluation measures one deck against the Gauntlet, so "
            "comparing two of them adds both bands; only a Paired run of the two "
            "decks under one Environment set would separate them more sharply, and "
            "no job in this app does that."
        )
    return GateComparison(
        difference=difference, margin=margin, separated=separated, reason=reason
    )


async def compare(library: DeckLibrary, left: DeckRef, right: DeckRef) -> DeckComparison:
    """Diff two saved versions, and compare the Gate results they carry.

    `KeyError` when a ref names nothing: the caller turns that into a 404, because
    a comparison of one deck is not a smaller comparison.
    """
    a = await library.version(left)
    b = await library.version(right)
    if a is None:
        raise KeyError(f"{left.deck_id} v{left.version}")
    if b is None:
        raise KeyError(f"{right.deck_id} v{right.version}")
    (left_deck, left_version), (right_deck, right_version) = a, b

    gate: GateComparison | None = None
    if left_version.gate is None or right_version.gate is None:
        missing = [
            f"{deck.name} v{version.version}"
            for deck, version in ((left_deck, left_version), (right_deck, right_version))
            if version.gate is None
        ]
        note = (
            f"No Gate result for {' or '.join(missing)}, so there is nothing to "
            "compare. Send it to the duel farm as a test: a Gate evaluation is the "
            "only number in this app that may be quoted (ADR-0003), and the library "
            "finds it by decklist, so it will attach itself to this version once the "
            "job finishes."
        )
    elif left_version.gate.live != right_version.gate.live:
        fake = left_deck.name if not left_version.gate.live else right_deck.name
        note = (
            f"These two Gate results are not comparable: {fake}'s was produced by "
            "the fake executor and the other by real duels. A fabricated win rate "
            "and a measured one differ by however much the fake felt like."
        )
    else:
        gate = _gate_verdict(left_version.gate, right_version.gate)
        note = gate.reason

    return DeckComparison(
        left=ComparisonSide(
            deck_id=left_deck.id, name=left_deck.name, version=left_version
        ),
        right=ComparisonSide(
            deck_id=right_deck.id, name=right_deck.name, version=right_version
        ),
        # The refine job's diff function, so the library and the duel farm cannot
        # disagree about which cards moved between two decks.
        diff=diff_codes(left_version.main, right_version.main),
        extra_diff=diff_codes(left_version.extra, right_version.extra),
        gate=gate,
        gate_note=note,
    )
