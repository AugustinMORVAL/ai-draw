import { CardArt } from '@/components/card/CardArt'
import type { Board, Placed, SeatBoard } from '@/components/duel/board'
import { MONSTER_ZONES, PHASE_LABEL, SPELL_ZONES } from '@/components/duel/board'
import type { Card, DuelSeat } from '@/lib/api'
import { CARD_ASPECT, CARD_BACK } from '@/lib/cardArt'
import { cn } from '@/lib/cn'

const SEAT_TINT: Record<DuelSeat, string> = {
  candidate: 'border-seat-self/50',
  opponent: 'border-seat-foe/50',
}

function Zone({
  placed,
  byCode,
  seat,
  onInspect,
  spell,
  lastEvent,
}: {
  placed: Placed | null
  byCode: Map<number, Card>
  seat: DuelSeat
  onInspect: (card: Card) => void
  spell?: boolean
  lastEvent: number
}) {
  if (!placed) {
    return (
      <div
        style={{ aspectRatio: CARD_ASPECT }}
        className={cn(
          'border bg-slot/70 shadow-[inset_0_0_12px_rgb(0_0_0/0.5)]',
          spell ? 'border-edge-soft' : 'border-edge',
          seat === 'candidate' ? 'border-b-gold/25' : 'border-t-seat-foe/25',
        )}
      />
    )
  }

  const card = byCode.get(placed.code) ?? null
  const fresh = placed.since === lastEvent

  return (
    <button
      type="button"
      onClick={() => card && onInspect(card)}
      style={{ aspectRatio: CARD_ASPECT }}
      title={card?.name ?? String(placed.code)}
      className={cn(
        'card-slot relative block border bg-slot',
        SEAT_TINT[seat],
        fresh && 'ring-2 ring-gold',
      )}
    >
      {placed.facedown ? (
        <span className="absolute inset-0 bg-gradient-to-br from-[#3a2d17] to-[#1a1409]">
          <img
            src={CARD_BACK}
            alt="Face-down card"
            loading="lazy"
            decoding="async"
            draggable={false}
            className="h-full w-full object-cover"
            // The gradient underneath is the fallback, so a blocked host leaves a
            // card-shaped brown tile rather than a broken-image icon.
            onError={(e) => {
              e.currentTarget.style.display = 'none'
            }}
          />
        </span>
      ) : (
        <CardArt card={card} code={placed.code} size="thumb" className="h-full w-full" />
      )}
    </button>
  )
}

function Pile({ label, count }: { label: string; count: number }) {
  return (
    <div
      style={{ aspectRatio: CARD_ASPECT }}
      className={cn(
        'flex flex-col items-center justify-center gap-0.5 border bg-slot/60',
        count > 0 ? 'border-edge' : 'border-edge-soft/60',
      )}
    >
      <span className="font-mono text-xs tabular text-muted">{count}</span>
      <span className="font-display text-[8px] tracking-[0.16em] text-faint">
        {label}
      </span>
    </div>
  )
}

function SeatRows({
  board,
  seat,
  byCode,
  onInspect,
  lastEvent,
  flipped,
}: {
  board: SeatBoard
  seat: DuelSeat
  byCode: Map<number, Card>
  onInspect: (card: Card) => void
  lastEvent: number
  /** The opponent sits across the table, so their rows read outward-in. */
  flipped: boolean
}) {
  const monsters = (
    <div className="grid grid-cols-5 gap-1">
      {Array.from({ length: MONSTER_ZONES }, (_, i) => (
        <Zone
          key={`m${i}`}
          placed={board.monsters[i]}
          byCode={byCode}
          seat={seat}
          onInspect={onInspect}
          lastEvent={lastEvent}
        />
      ))}
    </div>
  )
  const spells = (
    <div className="grid grid-cols-5 gap-1">
      {Array.from({ length: SPELL_ZONES }, (_, i) => (
        <Zone
          key={`s${i}`}
          placed={board.spells[i]}
          byCode={byCode}
          seat={seat}
          onInspect={onInspect}
          spell
          lastEvent={lastEvent}
        />
      ))}
    </div>
  )

  return (
    <div className="flex items-center gap-1.5">
      <div className="w-[9%] shrink-0">
        <Pile label="GY" count={board.graveyard.length} />
      </div>
      <div className="min-w-0 flex-1 space-y-1">
        {flipped ? spells : monsters}
        {flipped ? monsters : spells}
      </div>
      <div className="w-[9%] shrink-0">
        <Pile label="HAND" count={board.hand} />
      </div>
    </div>
  )
}

/**
 * The duel mat.
 *
 * Tilted into perspective, because a Yu-Gi-Oh field is a table you sit at and a
 * flat grid of rectangles is a spreadsheet. The tilt is one transform on the
 * wrapper: the zones themselves stay ordinary boxes, so hit targets, focus rings
 * and text all behave.
 */
export function DuelField({
  board,
  byCode,
  onInspect,
  lastEvent,
}: {
  board: Board
  byCode: Map<number, Card>
  onInspect: (card: Card) => void
  lastEvent: number
}) {
  return (
    <div className="relative overflow-hidden border border-edge bg-field">
      {/* The mat glow. Cold under the opponent, gold under the candidate, so the
          seats are legible before a single card is read. */}
      <div
        aria-hidden
        className="absolute inset-0 opacity-70"
        style={{
          background:
            'radial-gradient(70% 45% at 50% 0%, rgb(91 143 245 / 0.16), transparent 70%),' +
            'radial-gradient(70% 45% at 50% 100%, rgb(224 183 85 / 0.16), transparent 70%)',
        }}
      />

      <div className="relative px-4 py-4" style={{ perspective: '2400px' }}>
        <div
          className="mx-auto max-w-[34rem] space-y-1.5"
          style={{ transform: 'rotateX(7deg)', transformStyle: 'preserve-3d' }}
        >
          <SeatRows
            board={board.opponent}
            seat="opponent"
            byCode={byCode}
            onInspect={onInspect}
            lastEvent={lastEvent}
            flipped
          />

          <div className="flex items-center gap-3 py-1">
            <span className="h-px flex-1 bg-gradient-to-r from-transparent via-edge to-transparent" />
            <span className="font-display text-[10px] tracking-[0.24em] text-faint">
              TURN {board.turn} · {PHASE_LABEL[board.phase] ?? board.phase}
            </span>
            <span className="h-px flex-1 bg-gradient-to-r from-transparent via-edge to-transparent" />
          </div>

          <SeatRows
            board={board.candidate}
            seat="candidate"
            byCode={byCode}
            onInspect={onInspect}
            lastEvent={lastEvent}
            flipped={false}
          />
        </div>
      </div>
    </div>
  )
}
