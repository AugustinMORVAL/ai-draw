import { useEffect, useRef } from 'react'
import { PHASE_LABEL } from '@/components/duel/board'
import type { Card, DuelEvent } from '@/lib/api'
import { cn } from '@/lib/cn'

/**
 * The duel, as sentences.
 *
 * Follows the playhead: scrubbing the timeline scrolls the log, clicking a line
 * scrubs the timeline. They are two views of one index, so neither is the master.
 */
export function ActionLog({
  log,
  index,
  byCode,
  onSeek,
}: {
  log: DuelEvent[]
  index: number
  byCode: Map<number, Card>
  onSeek: (index: number) => void
}) {
  const activeRef = useRef<HTMLLIElement>(null)

  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: 'nearest' })
  }, [index])

  return (
    <div className="flex h-full min-h-0 flex-col border border-edge bg-panel">
      <header className="shrink-0 border-b border-edge-soft bg-panel-2 px-3 py-2">
        <h2 className="font-display text-xs font-semibold tracking-[0.14em] text-gold">
          ACTION LOG
        </h2>
      </header>

      <ol className="min-h-0 flex-1 overflow-y-auto">
        {log.map((event) => {
          const card = event.card === null ? null : byCode.get(event.card)
          const current = event.index === index
          const future = event.index > index
          const self = event.seat === 'candidate'
          return (
            <li
              key={event.index}
              ref={current ? activeRef : undefined}
              className={cn(
                'border-l-2 transition-colors',
                current
                  ? 'border-l-gold bg-gold/8'
                  : self
                    ? 'border-l-seat-self/40'
                    : 'border-l-seat-foe/40',
                future && 'opacity-40',
              )}
            >
              <button
                type="button"
                onClick={() => onSeek(event.index)}
                className="flex w-full items-baseline gap-2 px-2.5 py-1.5 text-left hover:bg-panel-2"
              >
                <span className="w-9 shrink-0 font-mono text-[9.5px] tabular text-faint">
                  T{event.turn}
                </span>
                <span className="min-w-0 flex-1">
                  <span
                    className={cn(
                      'text-[11px]',
                      self ? 'text-seat-self' : 'text-seat-foe',
                    )}
                  >
                    {self ? 'Candidate' : 'Gauntlet'}
                  </span>{' '}
                  <span className="text-[11px] text-muted">{event.text}</span>
                  {card && (
                    <span className="text-[11px] text-fg"> {card.name}</span>
                  )}
                </span>
                <span className="shrink-0 font-mono text-[9px] text-faint">
                  {(PHASE_LABEL[event.phase] ?? event.phase).replace(' Phase', '')}
                </span>
              </button>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
