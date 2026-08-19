import type { CSSProperties, ReactNode } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { CardArt } from '@/components/card/CardArt'
import type { Board, Placed, SeatBoard } from '@/components/duel/board'
import { MONSTER_ZONES, PHASE_LABEL, SPELL_ZONES } from '@/components/duel/board'
import type { Card, DuelSeat } from '@/lib/api'
import { CARD_ASPECT, CARD_BACK } from '@/lib/cardArt'
import { cn } from '@/lib/cn'

/** How many cards of a hand are drawn before the rest becomes a number. */
const HAND_FANNED = 7

/** The zones the mat prints. */
type ZoneKind = 'monster' | 'spell' | 'field' | 'extra'

/**
 * How loudly each zone is printed, per seat.
 *
 * The hue is the seat's -- the candidate deck is the gold side and the Gauntlet is
 * the blue side, here as in the life bars and the log -- except for the Extra
 * Monster Zones, which belong to neither and are pink on every mat ever printed.
 *
 * These are `color`, not `border-color`, because a zone's frame, its rhombus and
 * its printed name all read off `currentColor`: one class tints the whole zone.
 * The alpha lives in the color rather than in `opacity`, so a faint frame does not
 * also mean a see-through plate.
 */
const ZONE_TONE: Record<ZoneKind, Record<DuelSeat, string>> = {
  monster: { candidate: 'text-seat-self/55', opponent: 'text-seat-foe/55' },
  spell: { candidate: 'text-seat-self/38', opponent: 'text-seat-foe/38' },
  field: { candidate: 'text-seat-self/38', opponent: 'text-seat-foe/38' },
  extra: { candidate: 'text-frame-trap/60', opponent: 'text-frame-trap/60' },
}

/** An occupied zone is drawn brighter: something is in it. */
const FILLED_TONE: Record<DuelSeat, string> = {
  candidate: 'text-seat-self/75',
  opponent: 'text-seat-foe/75',
}

const PILE_TONE: Record<DuelSeat, string> = {
  candidate: 'text-seat-self/45',
  opponent: 'text-seat-foe/45',
}

/** The card back, for anything face-down. The gradient underneath is the fallback,
    so a blocked image host leaves a card-shaped brown tile and not a broken icon. */
function FaceDown({ alt, className }: { alt: string; className?: string }) {
  return (
    <span
      className={cn(
        'absolute inset-0 block overflow-hidden bg-gradient-to-br from-[#3a2d17] to-[#1a1409]',
        className,
      )}
    >
      <img
        src={CARD_BACK}
        alt={alt}
        loading="lazy"
        decoding="async"
        draggable={false}
        className="h-full w-full object-cover brightness-75 saturate-75"
        onError={(e) => {
          e.currentTarget.style.display = 'none'
        }}
      />
    </span>
  )
}

/** A zone's printed name, in the corner, the way the mat prints it. */
function ZoneLabel({ children }: { children: ReactNode }) {
  return (
    <span className="pointer-events-none absolute top-0.5 left-1 font-display text-[7px] font-600 tracking-[0.14em] text-faint/80">
      {children}
    </span>
  )
}

/**
 * One zone, empty or holding a card.
 *
 * A monster that was set lies on its side, because that is what a face-down
 * defence position is; a set Spell or Trap stays upright, because that is what
 * those do. Both are `rotate`/`scale` on the card inside the zone -- never on the
 * zone, so the hit target, the focus ring and the hover lift stay the right way
 * up, and never on `transform`, which the landing animation owns.
 */
function Zone({
  placed,
  byCode,
  seat,
  kind,
  label,
  onInspect,
  lastEvent,
  upsideDown,
}: {
  placed: Placed | null
  byCode: Map<number, Card>
  seat: DuelSeat
  kind: ZoneKind
  label?: string
  onInspect: (card: Card) => void
  lastEvent: number
  /** The opponent sits across the table, so their cards face away from us. */
  upsideDown: boolean
}) {
  if (!placed) {
    return (
      <div
        style={{ aspectRatio: CARD_ASPECT }}
        className={cn('duel-frame zone-glyph', ZONE_TONE[kind][seat])}
      >
        {label && <ZoneLabel>{label}</ZoneLabel>}
      </div>
    )
  }

  const card = byCode.get(placed.code) ?? null
  const fresh = placed.since === lastEvent
  const lying = placed.facedown && (kind === 'monster' || kind === 'extra')

  // Rotated a quarter turn, a card's long edge is the zone's short one, so it
  // shrinks by the card ratio to sit inside the zone it is lying in.
  const pose: CSSProperties = lying
    ? { rotate: upsideDown ? '-90deg' : '90deg', scale: String(CARD_ASPECT) }
    : { rotate: upsideDown ? '180deg' : undefined }

  return (
    <button
      type="button"
      onClick={() => card && onInspect(card)}
      style={{ aspectRatio: CARD_ASPECT }}
      title={card?.name ?? String(placed.code)}
      className={cn('card-slot duel-frame block w-full', FILLED_TONE[seat], fresh && 'z-10')}
    >
      {/* Two spans, because the landing animation and the card's position are two
          different transforms and one element can only hold one. */}
      <span className={cn('absolute inset-0 block', fresh && 'land')}>
        <span className="absolute inset-0 block" style={pose}>
          {placed.facedown ? (
            <FaceDown alt="Face-down card" />
          ) : (
            <CardArt
              card={card}
              code={placed.code}
              size="thumb"
              className="h-full w-full"
            />
          )}
        </span>
      </span>
      {fresh && (
        <span aria-hidden className="pointer-events-none absolute inset-0 ring-2 ring-gold" />
      )}
    </button>
  )
}

/** The Deck and the Extra Deck: face-down stacks, which is all either one ever
    shows. The log does not know how many cards are left in them, so neither does
    this -- a stack is a shape, not a claim about a count. */
function Stack({ label, seat }: { label: string; seat: DuelSeat }) {
  return (
    <div
      style={{ aspectRatio: CARD_ASPECT }}
      className={cn('duel-frame', PILE_TONE[seat])}
    >
      <span
        aria-hidden
        className="absolute inset-[7%] translate-x-[5px] -translate-y-[5px] bg-[#101a2e] shadow-[0_0_0_1px_rgb(255_255_255/0.07)]"
      />
      <span
        aria-hidden
        className="absolute inset-[7%] translate-x-[2.5px] -translate-y-[2.5px] bg-[#0b1220] shadow-[0_0_0_1px_rgb(255_255_255/0.06)]"
      />
      <FaceDown alt={`${label} pile`} className="inset-[7%]" />
      <ZoneLabel>{label}</ZoneLabel>
    </div>
  )
}

/** The graveyard, face-up, the way it sits on a table: the last card sent there is
    the one you can see, with the depth of the pile under it. */
function Graveyard({
  codes,
  byCode,
  seat,
  onInspect,
}: {
  codes: number[]
  byCode: Map<number, Card>
  seat: DuelSeat
  onInspect: (card: Card) => void
}) {
  const top = codes.at(-1)

  if (top === undefined) {
    return (
      <div
        style={{ aspectRatio: CARD_ASPECT }}
        className={cn('duel-frame zone-glyph', PILE_TONE[seat])}
      >
        <ZoneLabel>GY</ZoneLabel>
      </div>
    )
  }

  const card = byCode.get(top) ?? null

  return (
    <button
      type="button"
      onClick={() => card && onInspect(card)}
      style={{ aspectRatio: CARD_ASPECT }}
      title={
        card
          ? `${card.name}\nTop of ${codes.length} in the graveyard`
          : `Top of ${codes.length} in the graveyard`
      }
      className={cn('card-slot duel-frame block w-full', PILE_TONE[seat])}
    >
      <span
        aria-hidden
        className="absolute inset-[7%] translate-x-[2px] -translate-y-[2px] bg-[#0a1020]"
      />
      <CardArt
        card={card}
        code={top}
        size="thumb"
        className="absolute inset-[7%] h-auto w-auto saturate-50"
      />
      <span className="absolute right-0 bottom-0 border-l border-t border-current bg-void/90 px-1 font-mono text-[9px] leading-[1.5] tabular text-muted">
        {codes.length}
      </span>
      <ZoneLabel>GY</ZoneLabel>
    </button>
  )
}

/**
 * A seat's half of the mat.
 *
 * Seven zones across, exactly as the mat is printed: the Field Zone and the
 * graveyard bracket the monster row, the Extra Deck and the Deck bracket the Spell
 * & Trap row, and the monster row is the one that faces the middle. The opponent's
 * half is this half turned through half a circle -- rows outward-in, columns right
 * to left -- because that is what sitting across the table means.
 */
function SeatHalf({
  board,
  seat,
  byCode,
  onInspect,
  lastEvent,
  foe,
}: {
  board: SeatBoard
  seat: DuelSeat
  byCode: Map<number, Card>
  onInspect: (card: Card) => void
  lastEvent: number
  foe: boolean
}) {
  const zone = (key: string, placed: Placed | null, kind: ZoneKind, label?: string) => (
    <Zone
      key={key}
      placed={placed}
      byCode={byCode}
      seat={seat}
      kind={kind}
      label={label}
      onInspect={onInspect}
      lastEvent={lastEvent}
      upsideDown={foe}
    />
  )

  const monsterRow = [
    zone('field', board.field, 'field', 'FIELD'),
    ...Array.from({ length: MONSTER_ZONES }, (_, i) =>
      zone(`m${i}`, board.monsters[i], 'monster'),
    ),
    <Graveyard
      key="gy"
      codes={board.graveyard}
      byCode={byCode}
      seat={seat}
      onInspect={onInspect}
    />,
  ]

  const spellRow = [
    <Stack key="extra" label="EXTRA" seat={seat} />,
    ...Array.from({ length: SPELL_ZONES }, (_, i) =>
      zone(`s${i}`, board.spells[i], 'spell'),
    ),
    <Stack key="deck" label="DECK" seat={seat} />,
  ]

  const rows = foe
    ? [[...spellRow].reverse(), [...monsterRow].reverse()]
    : [monsterRow, spellRow]

  return (
    <div className="space-y-1">
      {rows.map((row, i) => (
        <div key={i} className="grid grid-cols-7 gap-1">
          {row}
        </div>
      ))}
    </div>
  )
}

/**
 * The two Extra Monster Zones, down the middle, shared.
 *
 * They stand in the columns over each player's second and fourth Monster Zone,
 * which is where the mat prints them. A player may only ever hold one, so the
 * candidate takes the left and the Gauntlet the right.
 */
function ExtraMonsterRow({
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
  const attacking = board.attacking
  const Chevron = attacking === 'candidate' ? ChevronUp : ChevronDown
  const rule = attacking
    ? attacking === 'candidate'
      ? 'bg-seat-self/70'
      : 'bg-seat-foe/70'
    : 'bg-edge/70'

  return (
    <div className="grid grid-cols-7 items-center gap-1 py-1.5">
      <span aria-hidden className={cn('col-span-2 h-px', rule)} />

      <div className="col-start-3">
        <Zone
          placed={board.candidate.extraMonster}
          byCode={byCode}
          seat="candidate"
          kind="extra"
          label="EMZ"
          onInspect={onInspect}
          lastEvent={lastEvent}
          upsideDown={false}
        />
      </div>

      {/* The battle, when there is one: which way the attack is going. */}
      <div className="col-start-4 flex items-center justify-center">
        {attacking ? (
          <>
            <Chevron
              size={34}
              strokeWidth={2.5}
              aria-hidden
              className={cn(
                'motion-safe:animate-pulse',
                attacking === 'candidate'
                  ? 'text-seat-self drop-shadow-[0_0_8px_rgb(224_183_85/0.7)]'
                  : 'text-seat-foe drop-shadow-[0_0_8px_rgb(91_143_245/0.7)]',
              )}
            />
            <span className="sr-only">
              {attacking === 'candidate'
                ? 'The candidate deck attacks'
                : 'The opponent attacks'}
            </span>
          </>
        ) : (
          <span aria-hidden className={cn('h-px w-full', rule)} />
        )}
      </div>

      <div className="col-start-5">
        <Zone
          placed={board.opponent.extraMonster}
          byCode={byCode}
          seat="opponent"
          kind="extra"
          label="EMZ"
          onInspect={onInspect}
          lastEvent={lastEvent}
          upsideDown
        />
      </div>

      <span aria-hidden className={cn('col-start-6 col-span-2 h-px', rule)} />
    </div>
  )
}

/**
 * A hand, held in front of the mat.
 *
 * The log tracks how many cards a hand holds, never which ones, so these are
 * backs -- for both seats, and honestly so. They fan and overlap because a hand is
 * held, not filed, and they sit outside the tilt because a hand is nearer to you
 * than the table is.
 */
function Hand({ count, seat, foe }: { count: number; seat: DuelSeat; foe: boolean }) {
  const shown = Math.min(count, HAND_FANNED)
  const middle = (shown - 1) / 2
  const away = foe ? -1 : 1

  return (
    <div
      className={cn(
        'relative z-10 flex items-center justify-center',
        // Just enough overlap to sit in front of the mat, never enough to cover
        // what a card in the row behind it says.
        foe ? '-mb-1.5' : '-mt-1.5',
      )}
    >
      {Array.from({ length: shown }, (_, i) => {
        const offset = i - middle
        return (
          <span
            key={i}
            style={{
              width: '10%',
              aspectRatio: CARD_ASPECT,
              marginInline: '-1.3%',
              rotate: `${offset * 3.4 * away}deg`,
              translate: `0 ${Math.abs(offset) * 2.5 * away}px`,
              zIndex: shown - Math.abs(Math.round(offset)),
            }}
            className="relative block shadow-[0_6px_14px_-6px_#000]"
          >
            <FaceDown alt="" />
          </span>
        )
      })}

      <span
        className={cn(
          'ml-2 border bg-void/70 px-1.5 py-0.5 font-mono text-[10px] leading-none tabular',
          seat === 'candidate'
            ? 'border-seat-self/40 text-seat-self/90'
            : 'border-seat-foe/40 text-seat-foe/90',
        )}
      >
        {count}
      </span>
      <span className="sr-only">
        {`${seat === 'candidate' ? 'The candidate deck' : 'The opponent'} holds ${count} cards`}
      </span>
    </div>
  )
}

/**
 * The duel mat.
 *
 * A field in this game is a printed table, and the zones printed on it are the
 * rules: a Field Spell has one place it can go, an Extra Deck monster has one
 * place it can go, and a monster that was set lies on its side. So the mat is
 * drawn as the mat -- seven zones across, two rows a side, the two Extra Monster
 * Zones shared down the middle, hands held in front of it -- and the board, folded
 * out of the log, fills it in.
 *
 * The tilt is one transform on the plate. The zones stay ordinary boxes, so hit
 * targets, focus rings and text all behave.
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
    <section
      aria-label="Duel field"
      // `shrink-0`: the mat sizes itself to the height it expects to be given, and
      // a flex column would otherwise squeeze it shorter than that and clip the
      // rows nearest the viewer instead of scrolling.
      className="relative shrink-0 overflow-hidden border border-edge bg-field"
    >
      {/* The mat glow. Cold over the opponent, gold over the candidate, so the
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
      <div
        aria-hidden
        className="scanlines pointer-events-none absolute inset-0 opacity-60"
      />

      <p className="absolute top-2 left-3 z-20 font-display text-[10px] font-600 tracking-[0.2em] text-faint">
        TURN {board.turn} · {PHASE_LABEL[board.phase] ?? board.phase}
      </p>

      <div className="relative flex justify-center px-3 pt-7 pb-3">
        {/* The perspective belongs to the plate's own parent: on a grandparent it
            is flattened away by the element in between, and the tilt comes out as
            a squash rather than a table. */}
        <div className="duel-mat">
          <Hand count={board.opponent.hand} seat="opponent" foe />

          <div
            className="duel-plate p-1.5"
            style={{ transform: 'rotateX(16deg)' }}
          >
            <SeatHalf
              board={board.opponent}
              seat="opponent"
              byCode={byCode}
              onInspect={onInspect}
              lastEvent={lastEvent}
              foe
            />

            <ExtraMonsterRow
              board={board}
              byCode={byCode}
              onInspect={onInspect}
              lastEvent={lastEvent}
            />

            <SeatHalf
              board={board.candidate}
              seat="candidate"
              byCode={byCode}
              onInspect={onInspect}
              lastEvent={lastEvent}
              foe={false}
            />
          </div>

          <Hand count={board.candidate.hand} seat="candidate" foe={false} />
        </div>
      </div>
    </section>
  )
}
