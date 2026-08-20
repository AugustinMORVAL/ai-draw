import { useCallback, useEffect, useState } from 'react'
import { api, type DeckSaved, type LibraryDeck } from '@/lib/api'

/**
 * The deck library, held for the whole app.
 *
 * One copy, in `App`, because three surfaces write to it: the editor saves the
 * deck on screen, the duel farm saves the deck a job produced, and the library
 * itself deletes and compares. Two hooks would mean two shelves disagreeing about
 * how many versions "Shaddoll" has.
 *
 * `testsFinished` is the other reload signal. A Gate result is joined to a saved
 * deck by its decklist rather than by a pointer, so a test job finishing changes
 * what the shelf says without anything on the shelf being touched -- and the only
 * way to know is to ask again.
 */
export function useLibrary(testsFinished = 0) {
  const [decks, setDecks] = useState<LibraryDeck[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  // Bumped by every write. The fetch lives in one effect rather than in each
  // mutation, so a save, a delete and a finished test job all refresh the shelf
  // the same way and cannot race each other into a stale list.
  const [asked, setAsked] = useState(0)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const next = await api.library()
        if (!cancelled) {
          setDecks(next)
          setError(null)
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e))
      }
    })()
    return () => {
      cancelled = true
    }
  }, [asked, testsFinished])

  const reload = useCallback(() => setAsked((n) => n + 1), [])

  const save = useCallback(
    async (body: {
      name: string
      main: number[]
      extra: number[]
      note?: string | null
    }): Promise<DeckSaved | null> => {
      try {
        const saved = await api.saveDeck(body)
        setError(null)
        reload()
        return saved
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e))
        return null
      }
    },
    [reload],
  )

  const remove = useCallback(
    async (deckId: string) => {
      try {
        await api.deleteDeck(deckId)
        setError(null)
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e))
      }
      reload()
    },
    [reload],
  )

  return {
    decks: decks ?? [],
    loading: decks === null && error === null,
    error,
    save,
    remove,
    reload,
  }
}

export type Library = ReturnType<typeof useLibrary>
