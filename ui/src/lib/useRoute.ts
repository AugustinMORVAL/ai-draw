import { useCallback, useEffect, useState } from 'react'

export type View = 'deck' | 'farm' | 'replay' | 'library'

export interface Route {
  view: View
  /** The job a farm or replay route is looking at. */
  jobId: string | null
  /** Which of that job's kept duels is open. */
  replay: number | null
  /** Library only: the two saved versions being compared, as `deckId.version`. */
  left: string | null
  right: string | null
}

const DEFAULT: Route = {
  view: 'deck',
  jobId: null,
  replay: null,
  left: null,
  right: null,
}

const VIEWS: View[] = ['deck', 'farm', 'replay', 'library']

/**
 * Two segments after the view, read differently by the views that use them.
 *
 * A farm route points at a job and one of its duels; a library route points at two
 * saved versions. Both are "which two things am I looking at", so they share the
 * same two slots rather than growing the fragment a key at a time.
 */
function parse(hash: string): Route {
  const parts = hash.replace(/^#\/?/, '').split('/').filter(Boolean)
  const [view, first, second] = parts
  if (!VIEWS.includes(view as View)) return DEFAULT
  if (view === 'library') {
    // `-` holds the left slot open, so picking a B before an A survives a reload.
    return {
      ...DEFAULT,
      view: 'library',
      left: first === '-' ? null : (first ?? null),
      right: second ?? null,
    }
  }
  return {
    ...DEFAULT,
    view: view as View,
    jobId: first ?? null,
    replay: second === undefined ? null : Number(second),
  }
}

function serialise(route: Route): string {
  const parts: (string | number)[] = [route.view]
  if (route.view === 'library') {
    if (route.left || route.right) parts.push(route.left ?? '-')
    if (route.right) parts.push(route.right)
  } else {
    if (route.jobId) parts.push(route.jobId)
    if (route.jobId && route.replay !== null) parts.push(route.replay)
  }
  return `#/${parts.join('/')}`
}

/**
 * The whole location of the app, in the URL fragment.
 *
 * A refine job runs for minutes and a user will reload, close the tab, and come
 * back. Which job they were watching, which duel they were part-way through, and
 * which two decks they had side by side are all worth surviving that, and the
 * fragment is the cheapest place to keep them.
 */
export function useRoute() {
  const [route, setRoute] = useState<Route>(() => parse(window.location.hash))

  useEffect(() => {
    const onHash = () => setRoute(parse(window.location.hash))
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const go = useCallback((next: Partial<Route>) => {
    setRoute((current) => {
      const merged = { ...current, ...next }
      window.location.hash = serialise(merged)
      return merged
    })
  }, [])

  return [route, go] as const
}
