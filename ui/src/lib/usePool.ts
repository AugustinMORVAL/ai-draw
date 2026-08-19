import { useEffect, useMemo, useState } from 'react'
import { api, type Card } from '@/lib/api'

/**
 * The supported pool, held in the browser.
 *
 * 864 cards, fetched once, never invalidated: widening the pool means training a
 * new Pilot, not editing a file (CONTEXT.md), so it cannot change while the tab is
 * open. Everything the deck editor filters and every card name the replay viewer
 * needs comes from here rather than from a request per keystroke.
 */
export function usePool() {
  const [cards, setCards] = useState<Card[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const pool = await api.pool()
        if (!cancelled) setCards(pool)
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e))
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const byCode = useMemo(() => {
    const map = new Map<number, Card>()
    for (const card of cards ?? []) map.set(card.code, card)
    return map
  }, [cards])

  return { cards, byCode, loading: cards === null && error === null, error }
}
