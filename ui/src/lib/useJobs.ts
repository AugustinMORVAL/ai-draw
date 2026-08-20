import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ApiError,
  api,
  type Constraint,
  type Deck,
  type Health,
  type JobSummary,
} from '@/lib/api'

export const POLL_MS = 700

/**
 * Polls the server for the queue. Nothing about a job lives in this hook — the
 * database is the truth, so a reload picks the same jobs back up mid-flight.
 *
 * Summaries only: what a job carries is fetched for the one job being watched,
 * by `useJob`. The whole list is on this timer and a refine result holds six full
 * duel logs, so polling those to draw a list of ids would cost the most and show
 * the least.
 */
export function useJobs() {
  const [jobs, setJobs] = useState<JobSummary[]>([])
  const [health, setHealth] = useState<Health | null>(null)
  const [offline, setOffline] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const alive = useRef(true)

  const refresh = useCallback(async () => {
    try {
      const next = await api.jobs()
      if (!alive.current) return
      setJobs(next)
      setOffline(false)
    } catch {
      if (alive.current) setOffline(true)
    }
  }, [])

  useEffect(() => {
    alive.current = true
    const loadHealth = async () => {
      try {
        const next = await api.health()
        if (alive.current) setHealth(next)
      } catch {
        if (alive.current) setOffline(true)
      }
    }
    void loadHealth()
    // Both of these only setState after an awaited fetch resolves, never in this tick.
    // oxlint-disable-next-line react/set-state-in-effect
    void refresh()
    const timer = setInterval(refresh, POLL_MS)
    return () => {
      alive.current = false
      clearInterval(timer)
    }
  }, [refresh])

  const submitRefine = useCallback(
    async (body: {
      deck?: Deck | null
      mutations: number
      screening_duels: number
      constraint?: Constraint | null
    }) => {
      setError(null)
      try {
        const job = await api.submitRefine(body)
        await refresh()
        return job
      } catch (e) {
        setError(submitMessage(e))
        return null
      }
    },
    [refresh],
  )

  const submitTest = useCallback(
    async (body: {
      deck?: Deck | null
      gate_duels: number
      constraint?: Constraint | null
    }) => {
      setError(null)
      try {
        const job = await api.submitTest(body)
        await refresh()
        return job
      } catch (e) {
        setError(submitMessage(e))
        return null
      }
    },
    [refresh],
  )

  const cancel = useCallback(
    async (id: string) => {
      try {
        await api.cancel(id)
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e))
      }
      await refresh()
    },
    [refresh],
  )

  return { jobs, health, offline, error, submitRefine, submitTest, cancel, refresh }
}

/**
 * A 422 from the queue carries the report the screen already shows -- a deck report
 * for an illegal deck, a Constraint report for an interest no deck can satisfy --
 * so surface the first reason rather than a wall of JSON.
 */
function submitMessage(e: unknown): string {
  const raw = e instanceof Error ? e.message : String(e)
  const detail = e instanceof ApiError ? e.detail : null
  if (detail !== null && typeof detail === 'object') {
    const body = detail as {
      flags?: { reason: string }[]
      deck_flags?: { reason: string }[]
    }
    const reason = body.flags?.[0]?.reason ?? body.deck_flags?.[0]?.reason
    if (reason) return `Refused: ${reason}`
  }
  return raw
}
