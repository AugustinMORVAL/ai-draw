/**
 * The board, derived from the action log.
 *
 * A duel log is a list of things that happened; a field is what the table looks
 * like after they have. This walks the log to a given event and returns the
 * second from the first, so scrubbing anywhere is a fold over a prefix rather than
 * state that has to be kept in sync.
 *
 * Where a card lands is decided by the card itself, not by the verb in the log: a
 * Spell goes to the spell row because the index says it is a Spell. The log's verb
 * is a sentence for a human, the card's type is data.
 */

import type { Card, DuelEvent, DuelSeat } from '@/lib/api'

export const MONSTER_ZONES = 5
export const SPELL_ZONES = 5

export interface Placed {
  code: number
  /** The event that put it there, so the field can flash what just moved. */
  since: number
  /** Set face-down when the log says it was set rather than summoned. */
  facedown: boolean
}

export interface SeatBoard {
  monsters: (Placed | null)[]
  spells: (Placed | null)[]
  graveyard: number[]
  life: number
  hand: number
}

export interface Board {
  candidate: SeatBoard
  opponent: SeatBoard
  turn: number
  phase: string
  /** The seat whose turn it is at this point in the log. */
  active: DuelSeat | null
  /** The zone that just changed, so it can be highlighted for one step. */
  attacking: DuelSeat | null
}

function emptySeat(): SeatBoard {
  return {
    monsters: Array(MONSTER_ZONES).fill(null),
    spells: Array(SPELL_ZONES).fill(null),
    graveyard: [],
    life: 8000,
    // Both players open on five and draw for turn. A fabricated log does not
    // track a hand, so this is a count, never a set of named cards.
    hand: 5,
  }
}

/** Fold the log up to and including `upTo` into a board. */
export function boardAt(
  log: DuelEvent[],
  upTo: number,
  byCode: Map<number, Card>,
): Board {
  const board: Board = {
    candidate: emptySeat(),
    opponent: emptySeat(),
    turn: 0,
    phase: '',
    active: null,
    attacking: null,
  }

  for (let i = 0; i <= Math.min(upTo, log.length - 1); i++) {
    const event = log[i]
    const seat = event.seat === 'candidate' ? board.candidate : board.opponent
    board.turn = event.turn
    board.phase = event.phase
    board.active = event.seat
    board.attacking = null

    if (event.action === 'draw') {
      seat.hand += 1
    } else if (event.action === 'summon' && event.card !== null) {
      const card = byCode.get(event.card)
      const row = card?.kind === 'monster' || !card ? seat.monsters : seat.spells
      const free = row.indexOf(null)
      const placed: Placed = {
        code: event.card,
        since: event.index,
        facedown: event.text.startsWith('sets'),
      }
      if (free === -1) {
        // The zones are full, so something goes to the graveyard to make room.
        const displaced = row[0]
        if (displaced) seat.graveyard.push(displaced.code)
        row[0] = placed
      } else {
        row[free] = placed
      }
      seat.hand = Math.max(0, seat.hand - 1)
    } else if (event.action === 'attack') {
      board.attacking = event.seat
    }

    board.candidate.life = event.life_candidate
    board.opponent.life = event.life_opponent
  }

  return board
}

export const PHASE_LABEL: Record<string, string> = {
  draw: 'Draw Phase',
  standby: 'Standby Phase',
  main1: 'Main Phase 1',
  battle: 'Battle Phase',
  main2: 'Main Phase 2',
  end: 'End Phase',
}
