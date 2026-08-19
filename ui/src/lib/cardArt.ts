/**
 * Where card art comes from.
 *
 * The codes this app deals in are real passcodes, so the community image hosts
 * answer to them directly. Nothing is bundled and nothing is proxied: the browser
 * fetches art, the API stays network-free, and a box with no egress still runs the
 * whole app with placeholder tiles in place of pictures.
 *
 * Two hosts, tried in order, because one of them is occasionally slow and a deck
 * editor showing forty grey rectangles is a broken deck editor.
 */

export type ArtSize = 'thumb' | 'full' | 'art'

const YGOPRODECK: Record<ArtSize, string> = {
  thumb: 'https://images.ygoprodeck.com/images/cards_small',
  full: 'https://images.ygoprodeck.com/images/cards',
  // Frameless art, cropped to the illustration. What the duel field paints with.
  art: 'https://images.ygoprodeck.com/images/cards_cropped',
}

/** The mycard/EDOPro picture host. Full cards only, so it stands in for any size. */
const MOECUBE = 'https://cdn.233.momobako.com/ygopro/pics'

/** Every URL to try for one card, best first. */
export function artSources(code: number, size: ArtSize): string[] {
  return [`${YGOPRODECK[size]}/${code}.jpg`, `${MOECUBE}/${code}.jpg`]
}

/** The card back, for anything set face-down on the field. */
export const CARD_BACK = 'https://images.ygoprodeck.com/images/cards/back.jpg'

/** Yu-Gi-Oh card art is 813x1185 on the modern frame. Reserve it, never guess it. */
export const CARD_ASPECT = 813 / 1185
