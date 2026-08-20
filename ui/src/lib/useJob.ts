import { useEffect, useState } from 'react'
import { TERMINAL, api, type Job } from '@/lib/api'
import { POLL_MS } from '@/lib/useJobs'

/**
 * The one job being watched, whole: its interests, its checkpoint, its result.
 *
 * Polled on its own rather than read out of the queue list, because this is the
 * only job whose payload anyone is looking at. Polling stops the moment the job
 * reaches a terminal state — a finished job's result does not change, and it is
 * the largest thing this API serves.
 *
 * The answer carries the job it answers, so "we are looking at a different job
 * now" is derived by comparing ids rather than tracked by clearing state: nothing
 * on screen is ever a previous request's answer wearing the current job's label.
 */
export function useJob(jobId: string | null) {
  const [answer, setAnswer] = useState<{
    id: string | null
    job: Job | null
    error: string | null
  }>({ id: null, job: null, error: null })

  useEffect(() => {
    if (jobId === null) return
    let cancelled = false
    let timer: number | undefined

    const tick = async () => {
      try {
        const next = await api.job(jobId)
        if (cancelled) return
        setAnswer({ id: jobId, job: next, error: null })
        if (TERMINAL.includes(next.state)) return
      } catch (e) {
        if (cancelled) return
        // A dropped poll is not a lost job. Keep the last answer on screen and
        // try again: the queue is durable and the next tick will find it.
        setAnswer((prev) =>
          prev.id === jobId
            ? { ...prev, error: e instanceof Error ? e.message : String(e) }
            : { id: jobId, job: null, error: String(e) },
        )
      }
      timer = window.setTimeout(() => void tick(), POLL_MS)
    }

    void tick()
    return () => {
      cancelled = true
      if (timer !== undefined) clearTimeout(timer)
    }
  }, [jobId])

  const fresh = answer.id === jobId
  return { job: fresh ? answer.job : null, error: fresh ? answer.error : null }
}
