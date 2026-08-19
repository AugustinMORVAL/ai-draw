import { Ban, Star } from 'lucide-react'
import { CardArt } from '@/components/card/CardArt'
import type { Card } from '@/lib/api'
import { CARD_ASPECT } from '@/lib/cardArt'
import { cn } from '@/lib/cn'
import { FRAME_BG, FRAME_TEXT, attributeTint, frameOf, typeLine } from '@/lib/frames'

const LIMIT_WORD = ['Forbidden', 'Limited', 'Semi-Limited']

function StatCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2 px-2.5 py-1.5">
      <span className="label text-faint">{label}</span>
      <span className="font-mono text-xs tabular text-fg">{value}</span>
    </div>
  )
}

/**
 * The card under the cursor, read out in full.
 *
 * This is the panel that makes the difference between a grid of pictures and a
 * deck editor: the printed text is what a player is actually checking when they
 * decide whether a card belongs. It also carries the one fact this app adds to the
 * card, and the reason half the pool is unbuildable: whether the frozen Pilot can
 * represent it at all.
 */
export function CardInspector({
  card,
  copies,
  className,
}: {
  card: Card | null
  copies?: number
  className?: string
}) {
  if (!card) {
    return (
      <div
        className={cn(
          'flex flex-col items-center justify-center gap-3 border border-edge bg-panel p-6',
          className,
        )}
      >
        <div
          style={{ aspectRatio: CARD_ASPECT }}
          className="w-32 border border-dashed border-edge-soft bg-slot/50"
        />
        <p className="max-w-52 text-center text-xs leading-relaxed text-faint">
          Point at a card in the deck or the search results and it opens here, with
          its printed text.
        </p>
      </div>
    )
  }

  const frame = frameOf(card)
  const level = card.level ?? 0
  const isLink = card.subtypes.includes('link')

  return (
    <div className={cn('flex flex-col border border-edge bg-panel', className)}>
      <div className="relative shrink-0 overflow-hidden border-b border-edge-soft">
        {/* The art, blown out behind itself, so the panel head takes the card's
            own colour instead of sitting on flat navy. */}
        <div aria-hidden className="absolute inset-0 opacity-25 blur-2xl">
          <CardArt card={card} code={card.code} size="art" className="h-full w-full" />
        </div>
        <div className="relative flex justify-center p-4">
          <CardArt
            card={card}
            code={card.code}
            size="full"
            eager
            className="w-40 shadow-[0_8px_28px_-6px_rgb(0_0_0/0.9)]"
          />
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="space-y-1 px-3 pt-3">
          <h3 className="font-display text-base leading-tight font-semibold text-fg">
            {card.name}
          </h3>
          <p className={cn('font-mono text-[11px]', FRAME_TEXT[frame])}>
            {typeLine(card)}
          </p>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-1.5 px-3">
          {card.attribute && (
            <span
              className={cn(
                'border border-edge bg-panel-2 px-1.5 py-0.5 font-display text-[10px] font-semibold tracking-wider',
                attributeTint(card.attribute),
              )}
            >
              {card.attribute}
            </span>
          )}
          {card.kind === 'monster' && level > 0 && (
            <span className="flex items-center gap-0.5 border border-edge bg-panel-2 px-1.5 py-0.5 font-mono text-[10px] tabular text-gold">
              {isLink ? 'LINK' : <Star size={9} fill="currentColor" strokeWidth={0} />}
              {level}
            </span>
          )}
          {card.limit < 3 && (
            <span
              className={cn(
                'flex items-center gap-1 border px-1.5 py-0.5 font-display text-[10px] font-semibold tracking-wider',
                card.limit === 0
                  ? 'border-bad/50 bg-bad/10 text-bad'
                  : 'border-warn/50 bg-warn/10 text-warn',
              )}
            >
              {card.limit === 0 && <Ban size={9} />}
              {LIMIT_WORD[card.limit]}
            </span>
          )}
          {copies !== undefined && copies > 0 && (
            <span className="ml-auto font-mono text-[10px] tabular text-gold">
              {copies} in deck
            </span>
          )}
        </div>

        {card.kind === 'monster' && (
          <div className="mt-3 grid grid-cols-2 border-y border-edge-soft divide-x divide-edge-soft">
            <StatCell label="ATK" value={card.atk === null ? '?' : String(card.atk)} />
            <StatCell
              label={isLink ? 'Link' : 'DEF'}
              value={
                isLink
                  ? String(card.level ?? '?')
                  : card.defense === null
                    ? '?'
                    : String(card.defense)
              }
            />
          </div>
        )}

        <p className="px-3 py-3 text-[11.5px] leading-[1.65] whitespace-pre-line text-muted">
          {card.desc ?? 'No card text is carried for this card.'}
        </p>
      </div>

      <div className="flex shrink-0 items-center gap-2 border-t border-edge-soft px-3 py-2">
        <span className="font-mono text-[10px] text-faint">{card.code}</span>
        <span
          className={cn(
            'ml-auto flex items-center gap-1.5 font-display text-[10px] font-semibold tracking-wider',
            card.in_pool ? 'text-good' : 'text-bad',
          )}
          title={
            card.in_pool
              ? 'The frozen Pilot has an embedding for this card, so it can play it.'
              : 'Outside the 864 the frozen Pilot can represent. Real card, unusable here.'
          }
        >
          <span className={cn('size-1.5', card.in_pool ? 'bg-good' : 'bg-bad')} />
          {card.in_pool ? 'IN POOL' : 'NOT IN POOL'}
        </span>
      </div>
    </div>
  )
}

/** The frame legend. Colour is doing real work in the grid, so it gets a key. */
export function FrameLegend({ className }: { className?: string }) {
  const shown: [string, string][] = [
    ['Monster', FRAME_BG.effect],
    ['Ritual', FRAME_BG.ritual],
    ['Fusion', FRAME_BG.fusion],
    ['Synchro', FRAME_BG.synchro],
    ['Xyz', FRAME_BG.xyz],
    ['Link', FRAME_BG.link],
    ['Spell', FRAME_BG.spell],
    ['Trap', FRAME_BG.trap],
  ]
  return (
    <div className={cn('flex flex-wrap items-center gap-x-3 gap-y-1', className)}>
      {shown.map(([label, bg]) => (
        <span key={label} className="flex items-center gap-1 text-[10px] text-faint">
          <span className={cn('size-2', bg)} />
          {label}
        </span>
      ))}
    </div>
  )
}
