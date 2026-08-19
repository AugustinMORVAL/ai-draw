import type { Job, Swap } from '@/lib/api'
import { Button } from '@/components/ui/Button'
import { Panel } from '@/components/ui/Panel'
import { StateBadge } from '@/components/ui/StateBadge'
import { cn } from '@/lib/cn'

const pct = (n: number) => `${(n * 100).toFixed(1)}%`
const signed = (n: number) => `${n >= 0 ? '+' : ''}${(n * 100).toFixed(1)}`

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="min-w-0">
      <div className="text-[11px] uppercase tracking-[0.12em] text-faint">{label}</div>
      <div className="mt-1 font-mono text-lg tabular text-fg">{value}</div>
      {hint && <div className="mt-0.5 text-[11px] text-faint">{hint}</div>}
    </div>
  )
}

function ProgressBar({ step, total }: { step: number; total: number }) {
  const ratio = total > 0 ? Math.min(step / total, 1) : 0
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-line-soft">
      <div
        className="h-full rounded-full bg-accent transition-[width] duration-300"
        style={{ width: `${ratio * 100}%` }}
      />
    </div>
  )
}

function SwapRow({ swap }: { swap: Swap }) {
  return (
    <tr className="border-t border-line-soft">
      <td className="py-1.5 pr-3 font-mono text-[11px] tabular text-faint">{swap.step}</td>
      <td className="py-1.5 pr-3 font-mono text-[11px] tabular text-muted">
        {swap.card_out} <span className="text-faint">→</span> {swap.card_in}
      </td>
      <td className="py-1.5 pr-3 text-right font-mono text-[11px] tabular text-muted">
        {pct(swap.win_rate)}
      </td>
      <td
        className={cn(
          'py-1.5 pr-3 text-right font-mono text-[11px] tabular',
          swap.delta > 0 ? 'text-good' : 'text-faint',
        )}
      >
        {signed(swap.delta)}
      </td>
      <td className="py-1.5 text-right font-mono text-[10px] uppercase tracking-[0.1em]">
        <span className={swap.accepted ? 'text-good' : 'text-faint'}>
          {swap.accepted ? 'kept' : 'rejected'}
        </span>
      </td>
    </tr>
  )
}

export function JobDetail({
  job,
  onCancel,
}: {
  job: Job | null
  onCancel: (id: string) => void
}) {
  if (!job) {
    return (
      <Panel title="Job">
        <p className="px-4 py-16 text-center text-sm text-faint">
          Select a job to watch it run.
        </p>
      </Panel>
    )
  }

  const running = job.state === 'running'
  const cancellable = running || job.state === 'queued'
  const result = job.result
  const swaps = [...(result?.swaps ?? [])].reverse()

  return (
    <Panel
      title={`Job ${job.id}`}
      aside={
        <div className="flex items-center gap-2">
          <StateBadge state={job.state} />
          {cancellable && (
            <Button variant="danger" className="px-2 py-1 text-xs" onClick={() => onCancel(job.id)}>
              Cancel
            </Button>
          )}
        </div>
      }
    >
      <div className="space-y-4 p-4">
        {job.state === 'queued' && (
          <p className="text-sm text-muted">
            Position <span className="font-mono tabular text-fg">#{job.queue_position}</span>{' '}
            in the queue. One job runs at a time.
          </p>
        )}

        {(running || job.progress.total > 0) && (
          <div className="space-y-2">
            <ProgressBar step={job.progress.step} total={job.progress.total} />
            <div className="flex items-baseline justify-between gap-3">
              <p className="truncate font-mono text-[11px] text-muted">
                {job.progress.message || 'Waiting for the duel farm…'}
              </p>
              <p className="shrink-0 font-mono text-[11px] tabular text-faint">
                {job.progress.step}/{job.progress.total}
              </p>
            </div>
          </div>
        )}

        {job.error && (
          <p className="rounded-md border border-bad/40 bg-bad/10 px-3 py-2 font-mono text-xs text-bad">
            {job.error}
          </p>
        )}

        {result && (
          <>
            <div className="grid grid-cols-3 gap-4 rounded-md border border-line-soft bg-panel-2 px-4 py-3">
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
            <p className="text-[11px] leading-relaxed text-warn">
              Screening win rates are noisy by design (±4–6 points) and are refinement
              progress, not a claim about this deck's strength. Only Gate evaluation
              produces that number.
            </p>

            <div className="max-h-72 overflow-y-auto rounded-md border border-line-soft">
              <table className="w-full px-3">
                <tbody>
                  {swaps.map((swap) => (
                    <SwapRow key={swap.step} swap={swap} />
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </Panel>
  )
}
