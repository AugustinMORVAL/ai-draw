import { X } from 'lucide-react'
import { CardArt } from '@/components/card/CardArt'
import type { Card } from '@/lib/api'
import { CARD_ASPECT } from '@/lib/cardArt'
import { cn } from '@/lib/cn'
import { FRAME_BORDER, frameOf } from '@/lib/frames'

const LIMIT_MARK: Record<number, { label: string; tone: string; title: string }> = {
  0: { label: '0', tone: 'bg-bad text-void', title: 'Forbidden on the 2024.7 list' },
  1: { label: '1', tone: 'bg-warn text-void', title: 'Limited to 1 copy' },
  2: { label: '2', tone: 'bg-warn/70 text-void', title: 'Semi-Limited to 2 copies' },
}

/**
 * One card in the deck grid.
 *
 * Sized by the grid around it, never by itself, so a row of ten and a row of five
 * both stay on the card's own 813x1185 proportions instead of squashing.
 */
export function CardSlot({
  card,
  code,
  count,
  index = 0,
  selected,
  onInspect,
  onRemove,
  problem,
}: {
  card?: Card | null
  code: number
  count?: number
  index?: number
  selected?: boolean
  onInspect?: () => void
  onRemove?: () => void
  /** Set when legality has something to say about this card. */
  problem?: 'bad' | 'warn' | null
}) {
  const frame = card ? frameOf(card) : 'unknown'
  const mark = card && card.limit < 3 ? LIMIT_MARK[card.limit] : null

  return (
    <div
      className="deal-in group relative"
      style={{ '--i': index, aspectRatio: CARD_ASPECT } as React.CSSProperties}
    >
      <button
        type="button"
        onClick={onInspect}
        onContextMenu={(e) => {
          if (!onRemove) return
          e.preventDefault()
          onRemove()
        }}
        onKeyDown={(e) => {
          if (onRemove && (e.key === 'Delete' || e.key === 'Backspace')) {
            e.preventDefault()
            onRemove()
          }
        }}
        title={card ? `${card.name}\n${card.code}` : String(code)}
        className={cn(
          'card-slot absolute inset-0 block border bg-slot',
          FRAME_BORDER[frame],
          selected && 'ring-2 ring-gold ring-offset-1 ring-offset-void',
          problem === 'bad' && 'border-bad',
          problem === 'warn' && 'border-warn',
        )}
      >
        <CardArt card={card} code={code} size="thumb" className="h-full w-full" />

        {problem === 'bad' && (
          <span
            aria-hidden
            className="absolute inset-0 bg-bad/25 mix-blend-hard-light"
          />
        )}

        {mark && (
          <span
            title={mark.title}
            className={cn(
              'absolute top-0.5 left-0.5 flex size-3.5 items-center justify-center',
              'rounded-full font-mono text-[8px] font-semibold tabular',
              mark.tone,
            )}
          >
            {mark.label}
          </span>
        )}

        {count !== undefined && count > 1 && (
          <span className="absolute right-0 bottom-0 bg-void/85 px-1 font-mono text-[10px] leading-tight font-500 tabular text-gold">
            x{count}
          </span>
        )}
      </button>

      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          aria-label={`Remove ${card?.name ?? code}`}
          className={cn(
            'absolute -top-1 -right-1 z-10 flex size-4 items-center justify-center',
            'border border-edge bg-void text-faint opacity-0 transition-opacity',
            'group-hover:opacity-100 hover:border-bad hover:text-bad focus-visible:opacity-100',
          )}
        >
          <X size={10} strokeWidth={2.5} />
        </button>
      )}
    </div>
  )
}

/** An empty slot. The grid keeps its shape whether the deck is 40 cards or 4. */
export function EmptySlot() {
  return (
    <div
      style={{ aspectRatio: CARD_ASPECT }}
      className="border border-dashed border-edge-soft bg-slot/40"
    />
  )
}
