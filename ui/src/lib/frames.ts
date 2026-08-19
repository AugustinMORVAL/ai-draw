/**
 * Card frames, as the game prints them.
 *
 * This is domain data, not styling preference. A Fusion monster is purple on the
 * card, in every client anyone has used, and in a deck editor the frame color is
 * how a player counts their monster line at a glance. Reproducing it is the
 * difference between a deck grid and a list of rectangles.
 *
 * Derived from the `subtypes` and `kind` the API sends, both straight out of the
 * executor's own `cards.cdb` type bits.
 */

import type { Card } from '@/lib/api'

export type Frame =
  | 'normal'
  | 'effect'
  | 'ritual'
  | 'fusion'
  | 'synchro'
  | 'xyz'
  | 'link'
  | 'pendulum'
  | 'spell'
  | 'trap'
  | 'token'
  | 'unknown'

/** Most specific first: a Pendulum Fusion is drawn as a Fusion with a scale. */
const MONSTER_FRAMES: [string, Frame][] = [
  ['link', 'link'],
  ['xyz', 'xyz'],
  ['synchro', 'synchro'],
  ['fusion', 'fusion'],
  ['ritual', 'ritual'],
]

export function frameOf(card: Pick<Card, 'kind' | 'subtypes'>): Frame {
  if (card.subtypes.includes('token')) return 'token'
  if (card.kind === 'spell') return 'spell'
  if (card.kind === 'trap') return 'trap'
  if (card.kind !== 'monster') return 'unknown'
  for (const [subtype, frame] of MONSTER_FRAMES) {
    if (card.subtypes.includes(subtype)) return frame
  }
  if (card.subtypes.includes('pendulum')) return 'pendulum'
  return card.subtypes.includes('effect') ? 'effect' : 'normal'
}

/** Tailwind class fragments, so a frame can tint a border, a bar, or a dot. */
export const FRAME_BORDER: Record<Frame, string> = {
  normal: 'border-frame-normal/60',
  effect: 'border-frame-effect/60',
  ritual: 'border-frame-ritual/60',
  fusion: 'border-frame-fusion/60',
  synchro: 'border-frame-synchro/60',
  xyz: 'border-frame-xyz/60',
  link: 'border-frame-link/60',
  pendulum: 'border-frame-pendulum/60',
  spell: 'border-frame-spell/60',
  trap: 'border-frame-trap/60',
  token: 'border-frame-token/60',
  unknown: 'border-frame-unknown/60',
}

export const FRAME_BG: Record<Frame, string> = {
  normal: 'bg-frame-normal',
  effect: 'bg-frame-effect',
  ritual: 'bg-frame-ritual',
  fusion: 'bg-frame-fusion',
  synchro: 'bg-frame-synchro',
  xyz: 'bg-frame-xyz',
  link: 'bg-frame-link',
  pendulum: 'bg-frame-pendulum',
  spell: 'bg-frame-spell',
  trap: 'bg-frame-trap',
  token: 'bg-frame-token',
  unknown: 'bg-frame-unknown',
}

export const FRAME_TEXT: Record<Frame, string> = {
  normal: 'text-frame-normal',
  effect: 'text-frame-effect',
  ritual: 'text-frame-ritual',
  fusion: 'text-frame-fusion',
  synchro: 'text-frame-synchro',
  xyz: 'text-frame-xyz',
  link: 'text-frame-link',
  pendulum: 'text-frame-pendulum',
  spell: 'text-frame-spell',
  trap: 'text-frame-trap',
  token: 'text-frame-token',
  unknown: 'text-frame-unknown',
}

export const FRAME_LABEL: Record<Frame, string> = {
  normal: 'Normal',
  effect: 'Effect',
  ritual: 'Ritual',
  fusion: 'Fusion',
  synchro: 'Synchro',
  xyz: 'Xyz',
  link: 'Link',
  pendulum: 'Pendulum',
  spell: 'Spell',
  trap: 'Trap',
  token: 'Token',
  unknown: 'Unknown',
}

/** The one-line type row a card shows under its name, the way the card prints it. */
export function typeLine(card: Card): string {
  if (card.kind === 'monster') {
    const frame = frameOf(card)
    // Deduped: the frame and the subtype list both know a Pendulum Fusion is a
    // Fusion, and printing "[ Dragon / Effect / Effect ]" is how you can tell a
    // type line was assembled rather than read off the card.
    const parts = new Set<string>()
    if (card.race) parts.add(card.race)
    if (frame !== 'normal' && frame !== 'effect') parts.add(FRAME_LABEL[frame])
    for (const subtype of card.subtypes) {
      if (['tuner', 'flip', 'spirit', 'union', 'gemini', 'toon', 'pendulum'].includes(subtype)) {
        parts.add(subtype[0].toUpperCase() + subtype.slice(1))
      }
    }
    // The card always ends on how it behaves, never on how it is summoned.
    parts.add(card.subtypes.includes('effect') ? 'Effect' : 'Normal')
    return `[ ${[...parts].join(' / ')} ]`
  }
  const property = card.subtypes.find((s) =>
    ['quick-play', 'continuous', 'equip', 'field', 'counter', 'ritual'].includes(s),
  )
  const kind = card.kind === 'spell' ? 'Spell' : 'Trap'
  const label = property
    ? property
        .split('-')
        .map((w) => w[0].toUpperCase() + w.slice(1))
        .join('-')
    : 'Normal'
  return `[ ${label} ${kind} ]`
}

const ATTRIBUTE_TINT: Record<string, string> = {
  LIGHT: 'text-[#e8d9a0]',
  DARK: 'text-[#b48bd8]',
  EARTH: 'text-[#c0a888]',
  WATER: 'text-[#7fb8e8]',
  FIRE: 'text-[#e08464]',
  WIND: 'text-[#8fd0a8]',
  DIVINE: 'text-gold',
}

export function attributeTint(attribute: string | null): string {
  return (attribute && ATTRIBUTE_TINT[attribute]) || 'text-muted'
}
