import { useEffect, useState } from 'react'
import { api, type DeckComparison, type DeckRef } from '@/lib/api'

/** `deckId.version`, the form a comparison ref takes in the URL fragment. */
export function parseRef(raw: string | null): DeckRef | null {
  if (!raw) return null
  const [deckId, version] = raw.split('.')
  if (!deckId || !version || !Number.isFinite(Number(version))) return null
  return { deck_id: deckId, version: Number(version) }
}

export function formatRef(ref: DeckRef): string {
  return `${ref.deck_id}.${ref.version}`
}

/**
 * One comparison of two saved versions, fetched.
 *
 * Not computed here. The diff is the refine job's diff function and the verdict on
 * two win rates is a statement about ADR-0003's bands; a second implementation in
 * the browser would be a second answer to both, and the two would drift.
 *
 * The answer carries the pair it answers, so a stale response can never be drawn
 * under a newly picked deck's name.
 */
export function useComparison(left: DeckRef | null, right: DeckRef | null) {
  const [answer, setAnswer] = useState<{
    key: string
    body: DeckComparison | null
    error: string | null
  }>({ key: '', body: null, error: null })

  const key = left && right ? `${formatRef(left)}:${formatRef(right)}` : ''

  useEffect(() => {
    if (!left || !right) return
    let cancelled = false
    void (async () => {
      try {
        const body = await api.compareDecks(left, right)
        if (!cancelled) setAnswer({ key, body, error: null })
      } catch (e) {
        if (!cancelled) {
          setAnswer({
            key,
            body: null,
            error: e instanceof Error ? e.message : String(e),
          })
        }
      }
    })()
    return () => {
      cancelled = true
    }
    // `key` is the whole of both refs, so the effect keys on their value rather
    // than on the objects the router hands over fresh on every render.
  }, [key]) // eslint-disable-line react-hooks/exhaustive-deps

  const fresh = answer.key === key && key !== ''
  return {
    comparison: fresh ? answer.body : null,
    error: fresh ? answer.error : null,
    pending: key !== '' && !fresh,
  }
}
