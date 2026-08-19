import { CardSlot, EmptySlot } from '@/components/card/CardSlot'
import type { Card, CardFlag, DeckReport } from '@/lib/api'
import { cn } from '@/lib/cn'
import { frameOf } from '@/lib/frames'

const KIND_ORDER: Record<string, number> = { monster: 0, spell: 1, trap: 2 }

/**
 * Deck order, the way every client in the ecosystem sorts one: monsters first,
 * then spells, then traps, and copies of a card kept together.
 */
function deckOrder(codes: number[], byCode: Map<number, Card>): number[] {
  return [...codes].sort((a, b) => {
    const left = byCode.get(a)
    const right = byCode.get(b)
    if (!left || !right) return a - b
    const kind = (KIND_ORDER[left.kind] ?? 3) - (KIND_ORDER[right.kind] ?? 3)
    if (kind !== 0) return kind
    if (left.kind === 'monster') {
      const level = (right.level ?? 0) - (left.level ?? 0)
      if (level !== 0) return level
    }
    const frame = frameOf(left).localeCompare(frameOf(right))
    if (frame !== 0) return frame
    return left.name.localeCompare(right.name)
  })
}

function Counter({
  label,
  count,
  min,
  max,
}: {
  label: string
  count: number
  min?: number
  max: number
}) {
  const over = count > max
  const under = min !== undefined && count > 0 && count < min
  return (
    <div className="flex items-baseline gap-1.5">
      <span className="label text-faint">{label}</span>
      <span
        className={cn(
          'font-mono text-sm tabular',
          over || under ? 'text-bad' : 'text-fg',
        )}
      >
        {count}
      </span>
      <span className="font-mono text-[10px] tabular text-faint">/ {max}</span>
    </div>
  )
}

/**
 * The deck, laid out as cards rather than as a list.
 *
 * One slot per copy, not one row per card with a count beside it: three copies of a
 * hand trap take up three slots, because that is what they take up in a deck and
 * seeing the shape of it is the point of the grid.
 */
export function DeckGrid({
  report,
  byCode,
  selectedCode,
  onInspect,
  onRemove,
}: {
  report: DeckReport | null
  byCode: Map<number, Card>
  selectedCode: number | null
  onInspect: (card: Card) => void
  onRemove: (code: number) => void
}) {
  const main = deckOrder(report?.deck?.main ?? [], byCode)
  const extra = deckOrder(report?.extra ?? [], byCode)

  // Which codes legality has something to say about, so the grid can mark them.
  const trouble = new Map<number, 'bad' | 'warn'>()
  for (const flag of report?.flags ?? []) {
    trouble.set(flag.code, severity(flag))
  }

  const slots = (codes: number[], min: number) => {
    const cells = codes.map((code, i) => (
      <CardSlot
        key={`${code}-${i}`}
        code={code}
        card={byCode.get(code) ?? null}
        index={i}
        selected={selectedCode === code}
        problem={trouble.get(code) ?? null}
        onInspect={() => {
          const card = byCode.get(code)
          if (card) onInspect(card)
        }}
        onRemove={() => onRemove(code)}
      />
    ))
    for (let i = codes.length; i < min; i++) {
      cells.push(<EmptySlot key={`empty-${i}`} />)
    }
    return cells
  }

  return (
    <div className="flex flex-col gap-3">
      <section className="border border-edge bg-panel">
        <header className="flex items-center gap-4 border-b border-edge-soft bg-panel-2 px-3 py-2">
          <h2 className="font-display text-xs font-semibold tracking-[0.14em] text-gold">
            MAIN DECK
          </h2>
          <Counter label="cards" count={main.length} min={40} max={60} />
          {main.length > 0 && main.length < 40 && (
            <span className="text-[11px] text-bad">
              {40 - main.length} short of the minimum
            </span>
          )}
        </header>
        <div className="grid grid-cols-[repeat(auto-fill,minmax(4.5rem,1fr))] gap-1 p-2">
          {slots(main, main.length === 0 ? 40 : Math.max(40, main.length))}
        </div>
      </section>

      <section className="border border-edge bg-panel">
        <header className="flex items-center gap-4 border-b border-edge-soft bg-panel-2 px-3 py-2">
          <h2 className="font-display text-xs font-semibold tracking-[0.14em] text-gold">
            EXTRA DECK
          </h2>
          <Counter label="cards" count={extra.length} max={15} />
          <span className="ml-auto text-[10.5px] text-faint">
            Carried and checked, never built. Phase 1 builds main decks.
          </span>
        </header>
        <div className="grid grid-cols-[repeat(auto-fill,minmax(4.5rem,1fr))] gap-1 p-2">
          {slots(extra, 15)}
        </div>
      </section>
    </div>
  )
}

function severity(flag: CardFlag): 'bad' | 'warn' {
  return flag.issue === 'over_limit' ? 'warn' : 'bad'
}
