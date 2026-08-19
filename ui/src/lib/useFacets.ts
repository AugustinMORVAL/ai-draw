import { useEffect, useMemo, useState } from 'react'
import { api, type ConstraintFacet, type FacetValue } from '@/lib/api'

/**
 * Every value a Constraint may be written against, fetched once.
 *
 * The form offers only what the server says exists, and shows the ceiling beside
 * each one, so an interest the pool cannot serve is visible before it is asked for
 * rather than as a refusal afterwards. Values at a ceiling of zero are kept, not
 * hidden: "Cyberse, none in a main deck" is the answer to a real question.
 */
export function useFacets() {
  const [values, setValues] = useState<FacetValue[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const listed = await api.facets()
        if (!cancelled) setValues(listed.values)
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e))
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const byFacet = useMemo(() => {
    const map = new Map<ConstraintFacet, FacetValue[]>()
    for (const value of values ?? []) {
      const list = map.get(value.facet) ?? []
      list.push(value)
      map.set(value.facet, list)
    }
    return map
  }, [values])

  return { values, byFacet, error }
}
