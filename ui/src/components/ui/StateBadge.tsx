import type { JobState } from '@/lib/api'
import { cn } from '@/lib/cn'

const STYLES: Record<JobState, string> = {
  queued: 'border-line text-muted',
  running: 'border-accent/50 text-accent-soft bg-accent/10',
  succeeded: 'border-good/40 text-good bg-good/10',
  failed: 'border-bad/40 text-bad bg-bad/10',
  cancelled: 'border-line text-faint',
}

export function StateBadge({ state, className }: { state: JobState; className?: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5',
        'font-mono text-[10px] uppercase tracking-[0.1em]',
        STYLES[state],
        className,
      )}
    >
      {state === 'running' && (
        <span className="size-1.5 animate-pulse rounded-full bg-accent-soft" />
      )}
      {state}
    </span>
  )
}
