import { useMemo, useState } from 'react'
import { ChevronDown, Download, Trash2 } from 'lucide-react'
import { CardBrowser } from '@/components/card/CardBrowser'
import { CardInspector, FrameLegend } from '@/components/card/CardInspector'
import { ConstraintPanel } from '@/components/deck/ConstraintPanel'
import { DeckGrid } from '@/components/deck/DeckGrid'
import { DeckStatus } from '@/components/deck/DeckStatus'
import { Button } from '@/components/ui/Button'
import type { Card, Constraint, Deck, DeckReport, Health } from '@/lib/api'
import { cn } from '@/lib/cn'
import { addCopy, copiesOf, downloadYdk, removeCopy, toYdk } from '@/lib/deckText'
import type { useConstraint } from '@/lib/useConstraint'
import { usePool } from '@/lib/usePool'

/** A shipped seed deck, so the editor can be tried without owning a `.ydk`. */
export const SEED = `#main
3717252
3717252
3717252
77723643
77723643
30328508
30328508
59546797
97518132
34710660
51023024
51023024
4939890
4939890
4939890
59438930
59438930
69764158
24635329
37445295
37445295
23434538
23434538
1475311
11827244
44394295
44394295
44394295
53129443
81439173
6417578
6417578
48130397
23912837
23912837
77505534
77505534
77505534
4904633
40605147
40605147
84749824
#extra
84433295
74822425
74822425
19261966
20366274
48424886
50907446
50907446
94977269
52687916
73580471
56832966
84013237
82633039`

const FIELD =
  'w-full border border-edge bg-slot px-2 py-1.5 font-mono text-xs tabular text-fg ' +
  'focus:border-gold focus:outline-none'

export function DeckEditor({
  text,
  setText,
  report,
  pending,
  parseError,
  health,
  interests,
  onSubmit,
  busy,
  submitError,
}: {
  text: string
  setText: (next: string) => void
  report: DeckReport | null
  pending: boolean
  parseError: string | null
  health: Health | null
  interests: ReturnType<typeof useConstraint>
  onSubmit: (body: {
    deck?: Deck | null
    mutations: number
    screening_duels: number
    constraint?: Constraint | null
  }) => Promise<void>
  busy: boolean
  submitError: string | null
}) {
  const { cards, byCode, error: poolError } = usePool()
  const [inspected, setInspected] = useState<Card | null>(null)
  const [showText, setShowText] = useState(false)
  const [mutations, setMutations] = useState(25)
  const [duels, setDuels] = useState(100)

  const held = useMemo(
    () => (code: number) => copiesOf(report, code),
    [report],
  )

  const add = (card: Card) => {
    const next = addCopy(report, card)
    if (next !== null) setText(next)
    setInspected(card)
  }

  const remove = (code: number) => {
    const next = removeCopy(report, code)
    if (next !== null) setText(next)
  }

  const hasDeck = report !== null && (report.deck?.main.length ?? 0) > 0
  const blocked = hasDeck && !report.legal

  return (
    <div className="grid min-h-0 gap-3 p-3 lg:h-[calc(100svh-3.5rem)] lg:grid-cols-[17rem_minmax(0,1fr)_19rem]">
      <div className="min-h-0 lg:overflow-hidden">
        <CardInspector
          card={inspected}
          copies={inspected ? held(inspected.code) : undefined}
          className={cn(inspected ? 'h-full' : 'shrink-0')}
        />
      </div>

      <div className="flex min-h-0 flex-col gap-3 lg:overflow-y-auto lg:pr-1">
        <div className="bevel flex flex-wrap items-center gap-3 border border-edge bg-panel px-3 py-2">
          <FrameLegend className="hidden xl:flex" />
          <div className="ml-auto flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowText((on) => !on)}
              className="flex items-center gap-1 font-display text-[10px] font-semibold tracking-[0.14em] text-faint hover:text-gold"
            >
              <ChevronDown
                size={12}
                className={cn('transition-transform', showText && 'rotate-180')}
              />
              YDK TEXT
            </button>
            <button
              type="button"
              onClick={() => downloadYdk(report)}
              disabled={!hasDeck}
              className="flex items-center gap-1 font-display text-[10px] font-semibold tracking-[0.14em] text-faint hover:text-gold disabled:opacity-40 disabled:hover:text-faint"
            >
              <Download size={12} />
              EXPORT
            </button>
            <button
              type="button"
              onClick={() => setText('')}
              disabled={!text}
              className="flex items-center gap-1 font-display text-[10px] font-semibold tracking-[0.14em] text-faint hover:text-bad disabled:opacity-40 disabled:hover:text-faint"
            >
              <Trash2 size={12} />
              CLEAR
            </button>
          </div>
        </div>

        {showText && (
          <div className="space-y-2 border border-edge bg-panel p-2">
            <textarea
              className="h-40 w-full resize-y border border-edge bg-slot px-2 py-1.5 font-mono text-[11px] leading-relaxed text-fg placeholder:text-faint focus:border-gold focus:outline-none"
              placeholder={'#main\n23434538\n...\n\nor\n\n3 Ash Blossom & Joyous Spring'}
              value={text}
              onChange={(e) => setText(e.target.value)}
              spellCheck={false}
            />
            <p className="text-[10.5px] leading-relaxed text-faint">
              The text is what the server parses, so it stays the deck's one
              definition. Adding or removing a card in the grid rewrites it as a
              canonical .ydk.
            </p>
          </div>
        )}

        {parseError && (
          <p className="border-l-2 border-l-bad bg-bad/8 px-3 py-2 font-mono text-[11px] text-bad">
            {parseError}
          </p>
        )}

        <ConstraintPanel
          constraint={interests.constraint}
          stated={interests.stated}
          report={report}
          pending={pending}
          onSize={interests.setSize}
          onAdd={interests.addClause}
          onEdit={interests.editClause}
          onDrop={interests.dropClause}
          onClear={interests.clear}
          onBuilt={(main) => {
            setText(toYdk(main, []))
            setInspected(null)
          }}
        />

        {!text && (
          <div className="flex flex-wrap items-center gap-3 border border-dashed border-edge bg-panel/60 px-3 py-4">
            <p className="text-[11.5px] text-muted">
              Empty deck. Add cards from the browser, paste a .ydk, or start from a
              deck the executor ships with.
            </p>
            <Button className="ml-auto" onClick={() => setText(SEED)}>
              Load Shaddoll seed deck
            </Button>
          </div>
        )}

        <DeckGrid
          report={report}
          byCode={byCode}
          selectedCode={inspected?.code ?? null}
          onInspect={setInspected}
          onRemove={remove}
        />

        <div className="grid gap-3 xl:grid-cols-2">
          <DeckStatus
            report={report}
            pending={pending}
            banlist={health?.banlist ?? '2024.7'}
          />

          <form
            className="flex flex-col gap-3 border border-edge bg-panel p-3"
            onSubmit={(e) => {
              e.preventDefault()
              void onSubmit({
                deck: report?.deck ?? null,
                mutations,
                screening_duels: duels,
                constraint: interests.asked,
              })
            }}
          >
            <h2 className="font-display text-xs font-semibold tracking-[0.14em] text-gold">
              SEND TO THE DUEL FARM
            </h2>
            <p className="text-[11.5px] leading-relaxed text-muted">
              {hasDeck
                ? 'The Builder mutates this deck swap by swap, keeping any swap with a positive Delta score. Every swap comes from inside the Masked action space, so the deck stays legal at every step.'
                : interests.stated
                  ? 'With no deck built, this builds one under your interests first, then refines it.'
                  : 'With no deck built, this refines a random legal deck drawn from the 408 main-deck cards the Pilot can play.'}
            </p>
            {interests.stated && (
              <p className="text-[10.5px] leading-relaxed text-faint">
                Your interests mask every swap, so the job cannot spend a mutation on
                a card you ruled out.
                {hasDeck && report?.constraint?.satisfied === false
                  ? ' This deck does not meet them yet: each masked swap pays that down, but only swaps with a positive Delta are kept, so the job pulls toward your interests without promising to arrive. Build the deck to be sure of it.'
                  : ''}
              </p>
            )}

            <div className="grid grid-cols-2 gap-2">
              <label className="space-y-1">
                <span className="label block text-faint">Mutations</span>
                <input
                  className={FIELD}
                  type="number"
                  min={1}
                  max={200}
                  value={mutations}
                  onChange={(e) => setMutations(Number(e.target.value))}
                />
              </label>
              <label className="space-y-1">
                <span className="label block text-faint">Screening duels</span>
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
              {busy ? 'Queueing' : hasDeck ? 'Queue refine job' : 'Queue on a random deck'}
            </Button>

            {submitError && (
              <p className="border-l-2 border-l-bad bg-bad/8 px-2 py-1.5 text-[11px] text-bad">
                {submitError}
              </p>
            )}

            <p
              className={cn(
                'text-[10.5px] leading-relaxed',
                blocked ? 'text-bad' : 'text-faint',
              )}
            >
              {blocked
                ? 'This deck is not legal, so it will not be queued. ygopro-core kills the process on a malformed deck rather than refusing it, so illegality is caught here and never at duel time.'
                : 'The queue is single-slot: one job runs at a time because the duel farm already saturates every core. You get a queue position, not a spinner.'}
            </p>
          </form>
        </div>
      </div>

      <div className="min-h-0 lg:overflow-hidden">
        {poolError ? (
          <div className="border border-bad/40 bg-bad/8 p-3 text-[11.5px] text-bad">
            The card pool did not load, so the browser is empty. {poolError}
          </div>
        ) : (
          <CardBrowser
            pool={cards}
            onInspect={setInspected}
            onAdd={add}
            selectedCode={inspected?.code ?? null}
            copiesOf={held}
          />
        )}
      </div>
    </div>
  )
}
