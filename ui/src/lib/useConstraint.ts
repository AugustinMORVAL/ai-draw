import { useCallback, useEffect, useMemo, useState } from 'react'
import type { Bound, Constraint, ConstraintClause, ConstraintFacet } from '@/lib/api'

const KEY = 'ai-draw.constraint'

export const NO_CONSTRAINT: Constraint = { main_size: null, clauses: [] }

/** Nothing asked for: no clause, no card-count cap. Nothing to send, nothing to mask. */
export function isStated(constraint: Constraint): boolean {
  return constraint.clauses.length > 0 || constraint.main_size !== null
}

function load(): Constraint {
  const raw = localStorage.getItem(KEY)
  if (!raw) return NO_CONSTRAINT
  try {
    const parsed = JSON.parse(raw) as Constraint
    return {
      main_size: parsed.main_size ?? null,
      clauses: Array.isArray(parsed.clauses) ? parsed.clauses.slice(0, 8) : [],
    }
  } catch {
    return NO_CONSTRAINT
  }
}

/**
 * The Constraint the user is writing, kept across reloads beside their deck.
 *
 * A Constraint is not a job parameter the user retypes each time; it is what they
 * are trying to build, and it outlives a refresh for the same reason the deck text
 * does. It is sent to the server only once stated: an empty form would otherwise
 * flag every pasted deck for a 40-card cap nobody chose.
 */
export function useConstraint() {
  const [constraint, setConstraint] = useState<Constraint>(load)

  useEffect(() => {
    if (isStated(constraint)) localStorage.setItem(KEY, JSON.stringify(constraint))
    else localStorage.removeItem(KEY)
  }, [constraint])

  const setSize = useCallback((main_size: number | null) => {
    setConstraint((current) => ({ ...current, main_size }))
  }, [])

  const addClause = useCallback((clause: ConstraintClause) => {
    setConstraint((current) =>
      current.clauses.length >= 8
        ? current
        : { ...current, clauses: [...current.clauses, clause] },
    )
  }, [])

  const editClause = useCallback((at: number, patch: Partial<ConstraintClause>) => {
    setConstraint((current) => ({
      ...current,
      clauses: current.clauses.map((clause, i) =>
        i === at ? { ...clause, ...patch } : clause,
      ),
    }))
  }, [])

  const dropClause = useCallback((at: number) => {
    setConstraint((current) => ({
      ...current,
      clauses: current.clauses.filter((_, i) => i !== at),
    }))
  }, [])

  const clear = useCallback(() => setConstraint(NO_CONSTRAINT), [])

  const stated = useMemo(() => isStated(constraint), [constraint])

  return {
    constraint,
    /** Null until the user has actually asked for something. */
    asked: stated ? constraint : null,
    stated,
    setSize,
    addClause,
    editClause,
    dropClause,
    clear,
  }
}

export const FACETS: { facet: ConstraintFacet; label: string }[] = [
  { facet: 'race', label: 'race' },
  { facet: 'attribute', label: 'attribute' },
  { facet: 'kind', label: 'card type' },
  { facet: 'subtype', label: 'subtype' },
]

export const BOUNDS: { bound: Bound; label: string }[] = [
  { bound: 'at_least', label: 'at least' },
  { bound: 'at_most', label: 'at most' },
]
