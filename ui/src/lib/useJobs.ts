import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type Deck, type Health, type Job } from '@/lib/api'

const POLL_MS = 700

/**
 * Polls the server for job state. Nothing about a job lives in this hook — the
 * database is the truth, so a reload picks the same jobs back up mid-flight.
 */
export function useJobs() {
  const [jobs, setJobs] = useState<Job[]>([])
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

  return { jobs, health, offline, error, submitRefine, cancel, refresh }
}

/**
 * A 422 from the queue carries the same deck report the paste box already shows,
 * so surface the first reason rather than a wall of JSON.
 */
function submitMessage(e: unknown): string {
  const raw = e instanceof Error ? e.message : String(e)
  const start = raw.indexOf('{')
  if (start === -1) return raw
  try {
    const body = JSON.parse(raw.slice(start)) as {
      detail?: { flags?: { reason: string }[]; deck_flags?: { reason: string }[] }
    }
    const reason = body.detail?.flags?.[0]?.reason ?? body.detail?.deck_flags?.[0]?.reason
    return reason ? `Deck refused: ${reason}` : raw
  } catch {
    return raw
  }
}
