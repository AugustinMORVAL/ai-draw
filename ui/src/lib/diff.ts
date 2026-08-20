import type { DeckChange } from '@/lib/api'

/** Copies, not distinct cards: three of one card is a change of three. */
export function countOf(changes: DeckChange[]): number {
  return changes.reduce((n, change) => n + change.count, 0)
}
