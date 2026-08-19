import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Panel } from '@/components/ui/Panel'
import type { Deck, DeckReport } from '@/lib/api'

const FIELD =
  'w-full rounded-md border border-line bg-panel-2 px-3 py-2 font-mono text-sm tabular ' +
  'focus:border-accent focus:outline-none'

export function SubmitPanel({
  onSubmit,
  busy,
  report,
}: {
  onSubmit: (body: {
    deck?: Deck | null
    mutations: number
    screening_duels: number
  }) => Promise<void>
  busy: boolean
  report: DeckReport | null
}) {
  const [mutations, setMutations] = useState(25)
  const [duels, setDuels] = useState(100)

  const hasDeck = report !== null
  const blocked = hasDeck && !report.legal

  return (
    <Panel title="Refine">
      <form
        className="space-y-4 p-4"
        onSubmit={(e) => {
          e.preventDefault()
          void onSubmit({
            deck: report?.deck ?? null,
            mutations,
            screening_duels: duels,
          })
        }}
      >
        <p className="text-sm leading-relaxed text-muted">
          {hasDeck
            ? 'Mutates the deck above swap by swap, keeping any swap with a positive Delta score. Every swap is drawn from inside the Masked action space, so the deck stays legal at every step.'
            : 'With no deck pasted, this refines a random legal deck drawn from the 408 main-deck cards the Pilot can play.'}
        </p>

        <div className="grid grid-cols-2 gap-3">
          <label className="space-y-1.5">
            <span className="block text-[11px] uppercase tracking-[0.12em] text-faint">
              Mutations
            </span>
            <input
              className={FIELD}
              type="number"
              min={1}
              max={200}
              value={mutations}
              onChange={(e) => setMutations(Number(e.target.value))}
            />
          </label>
          <label className="space-y-1.5">
            <span className="block text-[11px] uppercase tracking-[0.12em] text-faint">
              Screening duels
            </span>
            <input
              className={FIELD}
              type="number"
              min={10}
              max={1000}
              step={10}
              value={duels}
              onChange={(e) => setDuels(Number(e.target.value))}
            />
          </label>
        </div>

        <Button type="submit" disabled={busy || blocked} className="w-full">
          {busy ? 'Submitting…' : hasDeck ? 'Queue refine job' : 'Queue on a random deck'}
        </Button>

        {blocked ? (
          <p className="text-xs leading-relaxed text-bad">
            The deck above is not legal, so it will not be queued.{' '}
            <code className="font-mono">ygopro-core</code> kills the process on a
            malformed deck rather than refusing it, so illegality is caught here, never
            at duel time.
          </p>
        ) : (
          <p className="text-xs leading-relaxed text-faint">
            The queue is single-slot: one job runs at a time because the duel farm
            already saturates every core. You get a queue position, not a spinner.
          </p>
        )}
      </form>
    </Panel>
  )
}
