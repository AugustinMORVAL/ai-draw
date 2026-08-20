import { Minus, Plus } from 'lucide-react'
import { CardArt } from '@/components/card/CardArt'
import type { Card, DeckChange, DeckDiff } from '@/lib/api'
import { cn } from '@/lib/cn'
import { countOf } from '@/lib/diff'

/**
 * Which cards changed between two decks, as cards.
 *
 * Drawn here once and used by both readers of a diff: the duel farm, comparing a
 * refine job's final deck against the one it was given, and the library, comparing
 * two saved decks. Both diffs are counted by the same function on the server
 * (`refine.diff_codes`), so drawing them twice was the only way left for the two
 * screens to disagree.
 */
function DiffColumn({
  title,
  tone,
  changes,
  byCode,
}: {
  title: string
  tone: 'out' | 'in'
  changes: DeckChange[]
  byCode: Map<number, Card>
}) {
  const Icon = tone === 'out' ? Minus : Plus
  return (
    <div className="min-w-0 px-3 py-2">
      <div className="flex items-center gap-1.5">
        <Icon size={11} className={tone === 'out' ? 'text-bad' : 'text-good'} />
        <span className="label text-faint">{title}</span>
        <span className="ml-auto font-mono text-[10px] tabular text-faint">
          {countOf(changes)}
        </span>
      </div>
      <ul className="mt-2 space-y-1.5">
        {changes.map((change) => {
          const card = byCode.get(change.card) ?? null
          return (
            <li key={change.card} className="flex items-center gap-2">
              <CardArt
                card={card}
                code={change.card}
                size="thumb"
                className={cn(
                  'h-10 w-7 shrink-0 border',
                  tone === 'out' ? 'border-bad/40 opacity-55' : 'border-good/40',
                )}
              />
              <span className="min-w-0 flex-1 truncate text-[11px] text-muted">
                {card?.name ?? change.card}
              </span>
              {change.count > 1 && (
                <span className="shrink-0 font-mono text-[10px] tabular text-faint">
                  x{change.count}
                </span>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

/** The two columns: what the left-hand deck had, and what the right-hand one has. */
export function CardChanges({
  diff,
  byCode,
  outLabel = 'Cut',
  inLabel = 'Added',
}: {
  diff: DeckDiff
  byCode: Map<number, Card>
  outLabel?: string
  inLabel?: string
}) {
  return (
    <div className="grid grid-cols-2 divide-x divide-edge-soft">
      <DiffColumn title={outLabel} tone="out" changes={diff.removed} byCode={byCode} />
      <DiffColumn title={inLabel} tone="in" changes={diff.added} byCode={byCode} />
    </div>
  )
}
