import type { Job } from '@/lib/api'
import { Panel } from '@/components/ui/Panel'
import { StateBadge } from '@/components/ui/StateBadge'
import { cn } from '@/lib/cn'

function when(job: Job) {
  return new Date(job.created_at * 1000).toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function positionLabel(job: Job) {
  if (job.state === 'queued') return `#${job.queue_position} in queue`
  if (job.state === 'running') return `${job.progress.step}/${job.progress.total}`
  return when(job)
}

export function JobList({
  jobs,
  selectedId,
  onSelect,
}: {
  jobs: Job[]
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  return (
    <Panel
      title="Jobs"
      aside={<span className="font-mono text-[10px] text-faint">{jobs.length}</span>}
    >
      {jobs.length === 0 ? (
        <p className="px-4 py-8 text-center text-sm text-faint">
          Nothing queued yet.
        </p>
      ) : (
        <ul className="max-h-[26rem] divide-y divide-line-soft overflow-y-auto">
          {jobs.map((job) => (
            <li key={job.id}>
              <button
                type="button"
                onClick={() => onSelect(job.id)}
                className={cn(
                  'flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors',
                  'hover:bg-panel-2',
                  selectedId === job.id && 'bg-panel-2',
                )}
              >
                <span
                  className={cn(
                    'h-8 w-0.5 shrink-0 rounded-full',
                    selectedId === job.id ? 'bg-accent' : 'bg-transparent',
                  )}
                />
                <span className="font-mono text-xs text-muted">{job.id}</span>
                <StateBadge state={job.state} className="ml-auto" />
                <span className="w-24 shrink-0 text-right font-mono text-[11px] tabular text-faint">
                  {positionLabel(job)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}
