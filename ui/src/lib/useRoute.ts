import { useCallback, useEffect, useState } from 'react'

export type View = 'deck' | 'farm' | 'replay'

export interface Route {
  view: View
  /** The job a farm or replay route is looking at. */
  jobId: string | null
  /** Which of that job's kept duels is open. */
  replay: number | null
}

const DEFAULT: Route = { view: 'deck', jobId: null, replay: null }

function parse(hash: string): Route {
  const parts = hash.replace(/^#\/?/, '').split('/').filter(Boolean)
  const [view, jobId, replay] = parts
  if (view !== 'deck' && view !== 'farm' && view !== 'replay') return DEFAULT
  return {
    view,
    jobId: jobId ?? null,
    replay: replay === undefined ? null : Number(replay),
  }
}

function serialise(route: Route): string {
  const parts: (string | number)[] = [route.view]
  if (route.jobId) parts.push(route.jobId)
  if (route.jobId && route.replay !== null) parts.push(route.replay)
  return `#/${parts.join('/')}`
}

/**
 * The whole location of the app, in the URL fragment.
 *
 * A refine job runs for minutes and a user will reload, close the tab, and come
 * back. Which job they were watching and which duel they were part-way through are
 * both worth surviving that, and the fragment is the cheapest place to keep them.
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
