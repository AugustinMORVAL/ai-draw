import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Panel } from '@/components/ui/Panel'

const FIELD =
  'w-full rounded-md border border-line bg-panel-2 px-3 py-2 font-mono text-sm tabular ' +
  'focus:border-accent focus:outline-none'

export function SubmitPanel({
  onSubmit,
  busy,
}: {
  onSubmit: (body: { mutations: number; screening_duels: number }) => Promise<void>
  busy: boolean
}) {
  const [mutations, setMutations] = useState(25)
  const [duels, setDuels] = useState(100)

  return (
    <Panel title="Refine a deck">
      <form
        className="space-y-4 p-4"
        onSubmit={(e) => {
          e.preventDefault()
          void onSubmit({ mutations, screening_duels: duels })
        }}
      >
        <p className="text-sm leading-relaxed text-muted">
          Submits a random legal deck from the supported pool and mutates it swap by
          swap, keeping any swap with a positive Delta score. Deck input lands in the
          next slice.
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

        <Button type="submit" disabled={busy} className="w-full">
          {busy ? 'Submitting…' : 'Queue refine job'}
        </Button>
        <p className="text-xs leading-relaxed text-faint">
          The queue is single-slot: one job runs at a time because the duel farm already
          saturates every core. You get a queue position, not a spinner.
        </p>
      </form>
    </Panel>
  )
}
