import type { JobState } from '@/lib/api'
import { cn } from '@/lib/cn'

const STYLES: Record<JobState, string> = {
  queued: 'border-edge text-muted',
  running: 'border-gold/50 bg-gold/10 text-gold',
  succeeded: 'border-good/40 bg-good/10 text-good',
  failed: 'border-bad/40 bg-bad/10 text-bad',
  cancelled: 'border-edge text-faint',
}

export function StateBadge({
  state,
  className,
}: {
  state: JobState
  className?: string
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 border px-1.5 py-0.5',
        'font-display text-[9.5px] font-semibold tracking-[0.14em] uppercase',
        STYLES[state],
        className,
      )}
    >
      {state === 'running' && (
        <span className="size-1.5 animate-pulse bg-gold" />
      )}
      {state}
    </span>
  )
}
