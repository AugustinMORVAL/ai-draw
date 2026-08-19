import { ArrowRight, Play } from 'lucide-react'
import { CardArt } from '@/components/card/CardArt'
import { Button } from '@/components/ui/Button'
import { StateBadge } from '@/components/ui/StateBadge'
import type { Card, Job, RefineResult, Swap } from '@/lib/api'
import { cn } from '@/lib/cn'
import { usePool } from '@/lib/usePool'

const pct = (n: number) => `${(n * 100).toFixed(1)}%`
const signed = (n: number) => `${n >= 0 ? '+' : ''}${(n * 100).toFixed(1)}`

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

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="min-w-0 px-3 py-2">
      <div className="label text-faint">{label}</div>
      <div className="mt-1 font-display text-xl tabular text-fg">{value}</div>
      {hint && <div className="mt-0.5 text-[10.5px] text-faint">{hint}</div>}
    </div>
  )
}

/** One mutation, as the two cards it traded. */
function SwapRow({ swap, byCode }: { swap: Swap; byCode: Map<number, Card> }) {
  const out = byCode.get(swap.card_out) ?? null
  const into = byCode.get(swap.card_in) ?? null
  return (
    <li
      className={cn(
        'flex items-center gap-2.5 border-l-2 px-2.5 py-1.5',
        swap.accepted ? 'border-l-good bg-good/5' : 'border-l-transparent',
      )}
    >
      <span className="w-6 shrink-0 font-mono text-[10px] tabular text-faint">
        {swap.step}
      </span>

      <span className="flex items-center gap-1.5">
        <CardArt
          card={out}
          code={swap.card_out}
          size="thumb"
          className={cn('h-9 w-6.5 border border-edge-soft', swap.accepted && 'opacity-45')}
        />
        <ArrowRight size={11} className="shrink-0 text-faint" />
        <CardArt
          card={into}
          code={swap.card_in}
          size="thumb"
          className="h-9 w-6.5 border border-edge-soft"
        />
      </span>

      <span className="min-w-0 flex-1 truncate text-[11px] text-muted">
        {into?.name ?? swap.card_in}
      </span>

      <span className="shrink-0 font-mono text-[10.5px] tabular text-muted">
        {pct(swap.win_rate)}
      </span>
      <span
        className={cn(
          'w-12 shrink-0 text-right font-mono text-[10.5px] tabular',
          swap.delta > 0 ? 'text-good' : 'text-faint',
        )}
      >
        {signed(swap.delta)}
      </span>
    </li>
  )
}

function JobDetail({
  job,
  byCode,
  onCancel,
  onWatch,
}: {
  job: Job | null
  byCode: Map<number, Card>
  onCancel: (id: string) => void
  onWatch: (jobId: string) => void
}) {
  if (!job) {
    return (
      <div className="flex h-full items-center justify-center border border-edge bg-panel p-10">
        <p className="max-w-xs text-center text-xs leading-relaxed text-faint">
          Pick a job to watch it run. Jobs are durable: they outlive this tab and an
          API restart, so a reload comes back to the same one.
        </p>
      </div>
    )
  }

  const running = job.state === 'running'
  const cancellable = running || job.state === 'queued'
  const result = job.result as RefineResult | null
  const swaps = [...(result?.swaps ?? [])].reverse()
  const ratio =
    job.progress.total > 0 ? Math.min(job.progress.step / job.progress.total, 1) : 0

  return (
    <div className="flex h-full min-h-0 flex-col border border-edge bg-panel">
      <header className="flex shrink-0 items-center gap-2 border-b border-edge-soft bg-panel-2 px-3 py-2">
        <h2 className="font-display text-xs font-semibold tracking-[0.14em] text-gold">
          JOB
        </h2>
        <span className="font-mono text-[11px] text-muted">{job.id}</span>
        <StateBadge state={job.state} className="ml-auto" />
        {cancellable && (
          <Button
            variant="danger"
            className="px-2 py-1"
            onClick={() => onCancel(job.id)}
          >
            Cancel
          </Button>
        )}
      </header>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
        {job.state === 'queued' && (
          <p className="text-xs text-muted">
            Position{' '}
            <span className="font-mono tabular text-fg">#{job.queue_position}</span> in
            the queue. One job runs at a time.
          </p>
        )}

        {(running || job.progress.total > 0) && (
          <div className="space-y-1.5">
            <div
              className={cn(
                'relative h-1.5 overflow-hidden bg-edge-soft',
                running && 'sweep',
              )}
            >
              <div
                className="h-full bg-gold transition-[width] duration-300"
                style={{ width: `${ratio * 100}%` }}
              />
            </div>
            <div className="flex items-baseline justify-between gap-3">
              <p className="truncate font-mono text-[10.5px] text-muted">
                {job.progress.message || 'Waiting for the duel farm'}
              </p>
              <p className="shrink-0 font-mono text-[10.5px] tabular text-faint">
                {job.progress.step}/{job.progress.total}
              </p>
            </div>
          </div>
        )}

        {job.error && (
          <p className="border-l-2 border-l-bad bg-bad/8 px-3 py-2 font-mono text-[11px] text-bad">
            {job.error}
          </p>
        )}

        {result && (
          <>
            <div className="grid grid-cols-3 divide-x divide-edge-soft border border-edge-soft bg-panel-2">
              <Stat
                label="Win rate"
                value={pct(result.win_rate)}
                hint={`${result.fidelity} fidelity`}
              />
              <Stat
                label="Swaps kept"
                value={`${result.accepted}/${result.swaps.length}`}
              />
              <Stat label="Deck size" value={String(result.deck.main.length)} />
            </div>

            <p className="border-l-2 border-l-warn bg-warn/8 px-3 py-2 text-[11px] leading-relaxed text-warn">
              Screening win rates are noisy by design (4 to 6 points either way). They
              are refinement progress, not a claim about this deck's strength. Only
              Gate evaluation produces that number.
            </p>

            {result.replays.length > 0 && (
              <Button className="w-full" onClick={() => onWatch(job.id)}>
                <Play size={12} />
                Watch {result.replays.length} kept duels
              </Button>
            )}

            <div>
              <h3 className="label mb-1.5 text-faint">Mutations, newest first</h3>
              <ul className="max-h-96 divide-y divide-edge-soft overflow-y-auto border border-edge-soft">
                {swaps.map((swap) => (
                  <SwapRow key={swap.step} swap={swap} byCode={byCode} />
                ))}
              </ul>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export function DuelFarm({
  jobs,
  selectedId,
  onSelect,
  onCancel,
  onWatch,
  error,
}: {
  jobs: Job[]
  selectedId: string | null
  onSelect: (id: string) => void
  onCancel: (id: string) => void
  onWatch: (jobId: string) => void
  error: string | null
}) {
  const { byCode } = usePool()
  const selected = jobs.find((job) => job.id === selectedId) ?? null

  return (
    <div className="grid min-h-0 gap-3 p-3 lg:h-[calc(100svh-3.5rem)] lg:grid-cols-[20rem_minmax(0,1fr)]">
      <div className="flex min-h-0 flex-col border border-edge bg-panel">
        <header className="flex shrink-0 items-center gap-2 border-b border-edge-soft bg-panel-2 px-3 py-2">
          <h2 className="font-display text-xs font-semibold tracking-[0.14em] text-gold">
            QUEUE
          </h2>
          <span className="ml-auto font-mono text-[10px] tabular text-faint">
            {jobs.length}
          </span>
        </header>

        {jobs.length === 0 ? (
          <p className="p-6 text-center text-xs leading-relaxed text-faint">
            Nothing queued. Build a deck and send it to the farm.
          </p>
        ) : (
          <ul className="min-h-0 flex-1 divide-y divide-edge-soft overflow-y-auto">
            {jobs.map((job) => (
              <li key={job.id}>
                <button
                  type="button"
                  onClick={() => onSelect(job.id)}
                  className={cn(
                    'flex w-full items-center gap-2.5 px-3 py-2 text-left transition-colors hover:bg-panel-2',
                    selectedId === job.id && 'bg-panel-2',
                  )}
                >
                  <span
                    className={cn(
                      'h-7 w-0.5 shrink-0',
                      selectedId === job.id ? 'bg-gold' : 'bg-transparent',
                    )}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-mono text-[11px] text-muted">
                      {job.id}
                    </span>
                    <span className="block font-mono text-[10px] tabular text-faint">
                      {positionLabel(job)}
                    </span>
                  </span>
                  <StateBadge state={job.state} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="min-h-0">
        {error && (
          <p className="mb-3 border-l-2 border-l-bad bg-bad/8 px-3 py-2 font-mono text-[11px] text-bad">
            {error}
          </p>
        )}
        <JobDetail
          job={selected}
          byCode={byCode}
          onCancel={onCancel}
          onWatch={onWatch}
        />
      </div>
    </div>
  )
}
