import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type Health, type Job } from '@/lib/api'

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
    async (body: { mutations: number; screening_duels: number }) => {
      setError(null)
      try {
        const job = await api.submitRefine(body)
        await refresh()
        return job
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e))
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
