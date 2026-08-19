import { useEffect, useState } from 'react'
import { Header } from '@/components/Header'
import { JobDetail } from '@/components/JobDetail'
import { JobList } from '@/components/JobList'
import { SubmitPanel } from '@/components/SubmitPanel'
import { useJobs } from '@/lib/useJobs'

/** The selected job lives in the URL, so a reload mid-job comes back to it. */
function useHashSelection() {
  const [id, setId] = useState(() => window.location.hash.slice(1) || null)
  useEffect(() => {
    const onHash = () => setId(window.location.hash.slice(1) || null)
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  const select = (next: string) => {
    window.location.hash = next
    setId(next)
  }
  return [id, select] as const
}

export default function App() {
  const { jobs, health, offline, error, submitRefine, cancel } = useJobs()
  const [selectedId, select] = useHashSelection()
  const [busy, setBusy] = useState(false)

  const selected = jobs.find((job) => job.id === selectedId) ?? null

  const onSubmit = async (body: { mutations: number; screening_duels: number }) => {
    setBusy(true)
    const job = await submitRefine(body)
    setBusy(false)
    if (job) select(job.id)
  }

  return (
    <div className="min-h-svh">
      <Header health={health} offline={offline} />

      <main className="mx-auto grid max-w-6xl gap-5 px-6 py-6 lg:grid-cols-[22rem_1fr]">
        <div className="space-y-5">
          <SubmitPanel onSubmit={onSubmit} busy={busy} />
          <JobList jobs={jobs} selectedId={selectedId} onSelect={select} />
        </div>

        <div className="space-y-5">
          {error && (
            <p className="rounded-md border border-bad/40 bg-bad/10 px-3 py-2 font-mono text-xs text-bad">
              {error}
            </p>
          )}
          <JobDetail job={selected} onCancel={cancel} />
        </div>
      </main>

      <footer className="mx-auto max-w-6xl px-6 pb-10 text-[11px] leading-relaxed text-faint">
        Slice 0 — shell, executor seam, fake executor, durable job queue. Jobs survive a
        reload and an API restart; the queue is single-slot by design (ADR-0005).
      </footer>
    </div>
  )
}
