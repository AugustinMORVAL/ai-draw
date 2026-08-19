import { useEffect, useRef, useState } from 'react'
import type { DuelSeat } from '@/lib/api'
import { cn } from '@/lib/cn'

const START = 8000

function Bar({
  seat,
  name,
  life,
  first,
  won,
}: {
  seat: DuelSeat
  name: string
  life: number
  first: boolean
  won: boolean
}) {
  const [hit, setHit] = useState(false)
  const previous = useRef(life)

  // Flash on damage only. Scrubbing backwards restores life and must not flash.
  useEffect(() => {
    if (life < previous.current) {
      setHit(true)
      const timer = setTimeout(() => setHit(false), 500)
      previous.current = life
      return () => clearTimeout(timer)
    }
    previous.current = life
  }, [life])

  const self = seat === 'candidate'
  const share = Math.max(0, Math.min(1, life / START))

  return (
    <div className={cn('flex items-center gap-2.5', !self && 'flex-row-reverse')}>
      <div className={cn('shrink-0', !self && 'text-right')}>
        <div className="flex items-center gap-1.5">
          <span
            className={cn(
              'font-display text-[11px] font-semibold tracking-[0.14em]',
              self ? 'text-seat-self' : 'text-seat-foe',
            )}
          >
            {name}
          </span>
          {first && (
            <span className="border border-edge px-1 font-mono text-[8.5px] text-faint">
              1ST
            </span>
          )}
          {won && (
            <span className="border border-good/50 bg-good/10 px-1 font-display text-[8.5px] font-semibold tracking-wider text-good">
              WIN
            </span>
          )}
        </div>
        <div
          className={cn(
            'font-display text-2xl leading-none font-bold tabular',
            life === 0 ? 'text-bad' : 'text-fg',
          )}
        >
          {life}
        </div>
      </div>

      <div
        className={cn(
          'relative h-3 min-w-0 flex-1 overflow-hidden border border-edge bg-slot',
          hit && 'life-flash',
        )}
      >
        <div
          className={cn(
            'h-full transition-[width] duration-300 ease-out',
            self
              ? 'bg-gradient-to-r from-[#8a6a22] to-seat-self'
              : 'bg-gradient-to-l from-[#2f5aa8] to-seat-foe',
          )}
          style={{ width: `${share * 100}%`, marginLeft: self ? 0 : 'auto' }}
        />
      </div>
    </div>
  )
}

/**
 * Life points, the way a duel is actually scored.
 *
 * The candidate deck is always the gold side and the Gauntlet is always the blue
 * side, here and on the field and in the log, so the seat never has to be worked
 * out from a name.
 */
export function LifeBars({
  candidateLife,
  opponentLife,
  opponentName,
  goingFirst,
  winner,
  finished,
}: {
  candidateLife: number
  opponentLife: number
  opponentName: string
  goingFirst: DuelSeat
  winner: DuelSeat
  /** True only once the log has been walked to its end: the badge is a result,
      not a prediction, and scrubbing back has to take it away again. */
  finished: boolean
}) {
  return (
    <div className="space-y-2 border border-edge bg-panel p-3">
      <Bar
        seat="opponent"
        name={opponentName}
        life={opponentLife}
        first={goingFirst === 'opponent'}
        won={finished && winner === 'opponent'}
      />
      <Bar
        seat="candidate"
        name="CANDIDATE DECK"
        life={candidateLife}
        first={goingFirst === 'candidate'}
        won={finished && winner === 'candidate'}
      />
    </div>
  )
}
