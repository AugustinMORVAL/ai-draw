import { useState } from 'react'
import { CARD_ASPECT, artSources, type ArtSize } from '@/lib/cardArt'
import { cn } from '@/lib/cn'
import { FRAME_BG, frameOf } from '@/lib/frames'
import type { Card } from '@/lib/api'

/**
 * Card art, with somewhere to stand when there is none.
 *
 * Art is fetched from a community image host by passcode, which means it is the one
 * thing in this app that needs the network. When it does not arrive -- offline box,
 * blocked host, a code the host has no picture for -- the card does not vanish and
 * does not become a grey hole: it falls back to a frame-colored plate carrying the
 * name, which is enough to build a deck with.
 */
export function CardArt({
  card,
  code,
  size = 'thumb',
  className,
  eager = false,
}: {
  card?: Card | null
  code: number
  size?: ArtSize
  className?: string
  eager?: boolean
}) {
  const sources = artSources(code, size)
  // The state carries the card it belongs to. A different card in the same slot
  // starts over, or the new art inherits the old one's "already failed" state and
  // never renders. Adjusting during render rather than in an effect is what React
  // documents for exactly this: no wasted paint of the previous card's result.
  const [state, setState] = useState({ code, size, attempt: 0, loaded: false })
  if (state.code !== code || state.size !== size) {
    setState({ code, size, attempt: 0, loaded: false })
  }
  const { attempt, loaded } = state

  const exhausted = attempt >= sources.length
  const frame = card ? frameOf(card) : 'unknown'

  return (
    <span
      // The image is absolutely positioned, so without a ratio the box collapses to
      // nothing whenever a caller sets only a width. Callers that set both
      // dimensions override this, as CSS ignores a ratio when width and height
      // are both given.
      style={{ aspectRatio: CARD_ASPECT }}
      className={cn(
        'relative block overflow-hidden bg-slot',
        !loaded && 'animate-pulse',
        className,
      )}
    >
      {/* The frame-colored plate. Always painted: it is the loading state, the
          error state, and the backdrop a transparent-cornered card sits on. */}
      <span
        aria-hidden
        className={cn('absolute inset-0 opacity-25', FRAME_BG[frame])}
      />

      {exhausted ? (
        <span className="absolute inset-0 flex flex-col justify-end gap-0.5 p-1.5">
          <span className="line-clamp-3 font-display text-[10px] leading-tight font-semibold text-fg/90">
            {card?.name ?? code}
          </span>
          {card && (
            <span className="font-mono text-[8px] text-fg/50">{card.code}</span>
          )}
        </span>
      ) : (
        <img
          src={sources[attempt]}
          alt={card?.name ?? `Card ${code}`}
          loading={eager ? 'eager' : 'lazy'}
          decoding="async"
          draggable={false}
          onLoad={() => setState((s) => ({ ...s, loaded: true }))}
          onError={() => setState((s) => ({ ...s, attempt: s.attempt + 1 }))}
          className={cn(
            'absolute inset-0 h-full w-full object-cover transition-opacity duration-200',
            loaded ? 'opacity-100' : 'opacity-0',
          )}
        />
      )}
    </span>
  )
}
