/**
 * Editing a deck by clicking, while the text stays the source of truth.
 *
 * The paste box is not decoration: legality lives on the server and only on the
 * server (`/api/decks/parse`), and the text is what gets parsed. So a click on a
 * card in the grid does not mutate a client-side deck object, it rewrites the text
 * and lets the server say what the deck now is. There is exactly one answer to
 * "what is in this deck", and it comes back over the wire.
 *
 * The cost is that the first visual edit rewrites whatever was pasted into a
 * canonical `.ydk`. That is deliberate and visible: the raw text stays on screen in
 * the deck editor's text drawer, so nothing changes behind the user's back.
 */

import type { Card, DeckReport } from '@/lib/api'

/** A `.ydk`, the format every other client in the ecosystem reads and writes. */
export function toYdk(main: number[], extra: number[]): string {
  const lines = ['#main', ...main.map(String)]
  if (extra.length > 0) lines.push('#extra', ...extra.map(String))
  return `${lines.join('\n')}\n`
}

function currentCodes(report: DeckReport | null): { main: number[]; extra: number[] } {
  return { main: report?.deck?.main ?? [], extra: report?.extra ?? [] }
}

/**
 * Add one copy. Returns the text unchanged when the copy limit is already met:
 * refusing the click is Masking, the same rule the Builder plays under, and it is
 * kinder than accepting the card and flagging it a keystroke later.
 */
export function addCopy(report: DeckReport | null, card: Card): string | null {
  const { main, extra } = currentCodes(report)
  const target = card.section === 'extra' ? extra : main
  const held = target.filter((code) => code === card.code).length
  if (held >= card.limit) return null
  if (card.section === 'extra' && extra.length >= 15) return null
  if (card.section === 'main' && main.length >= 60) return null
  if (card.section === 'token') return null

  return card.section === 'extra'
    ? toYdk(main, [...extra, card.code].sort((a, b) => a - b))
    : toYdk([...main, card.code].sort((a, b) => a - b), extra)
}

/** Remove one copy of a code, from whichever section holds it. */
export function removeCopy(report: DeckReport | null, code: number): string | null {
  const { main, extra } = currentCodes(report)
  const drop = (codes: number[]) => {
    const at = codes.indexOf(code)
    if (at === -1) return null
    return [...codes.slice(0, at), ...codes.slice(at + 1)]
  }
  const nextMain = drop(main)
  if (nextMain) return toYdk(nextMain, extra)
  const nextExtra = drop(extra)
  if (nextExtra) return toYdk(main, nextExtra)
  return null
}

/** How many copies of a code the deck holds right now, across both sections. */
export function copiesOf(report: DeckReport | null, code: number): number {
  const { main, extra } = currentCodes(report)
  return (
    main.filter((c) => c === code).length + extra.filter((c) => c === code).length
  )
}

/** Download the deck as a `.ydk`, named for the user, openable in any client. */
export function downloadYdk(report: DeckReport | null, name = 'ai-draw'): void {
  const { main, extra } = currentCodes(report)
  const blob = new Blob([toYdk(main, extra)], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${name}.ydk`
  link.click()
  URL.revokeObjectURL(url)
}
