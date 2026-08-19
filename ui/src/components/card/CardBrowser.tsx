import { useEffect, useMemo, useState } from 'react'
import { Plus, Search } from 'lucide-react'
import { CardArt } from '@/components/card/CardArt'
import { api, type Card } from '@/lib/api'
import { cn } from '@/lib/cn'
import { FRAME_TEXT, frameOf, typeLine } from '@/lib/frames'

const SELECT =
  'min-w-0 border border-edge bg-slot px-1.5 py-1 font-mono text-[10px] text-fg ' +
  'focus:border-gold focus:outline-none'

const KINDS = ['monster', 'spell', 'trap'] as const
const ATTRIBUTES = ['DARK', 'LIGHT', 'EARTH', 'WATER', 'FIRE', 'WIND', 'DIVINE']
const FRAMES = ['normal', 'effect', 'ritual', 'fusion', 'synchro', 'xyz', 'link']

interface Filters {
  query: string
  kind: string
  attribute: string
  race: string
  frame: string
  level: string
  section: string
}

const BLANK: Filters = {
  query: '',
  kind: '',
  attribute: '',
  race: '',
  frame: '',
  level: '',
  section: 'main',
}

function matches(card: Card, f: Filters): boolean {
  if (f.section && card.section !== f.section) return false
  if (f.kind && card.kind !== f.kind) return false
  if (f.attribute && card.attribute !== f.attribute) return false
  if (f.race && card.race !== f.race) return false
  if (f.frame && frameOf(card) !== f.frame) return false
  if (f.level && String(card.level ?? '') !== f.level) return false
  if (f.query) {
    const needle = f.query.toLowerCase()
    const hay = `${card.name} ${card.desc ?? ''}`.toLowerCase()
    if (!hay.includes(needle)) return false
  }
  return true
}

/**
 * The card list, filtered in the browser.
 *
 * Filtering happens locally because the pool is 864 cards and cannot change while
 * the tab is open, so a keystroke should not cost a round trip. The exception is
 * the one question the client genuinely cannot answer: whether a card the pool does
 * *not* contain exists at all. When a search finds nothing here, the server is
 * asked, and a real card comes back marked rather than missing (ADR-0005) -- the
 * alternative is a user concluding the app is broken when the pool is just small.
 */
export function CardBrowser({
  pool,
  onInspect,
  onAdd,
  selectedCode,
  copiesOf,
}: {
  pool: Card[] | null
  onInspect: (card: Card) => void
  onAdd: (card: Card) => void
  selectedCode: number | null
  copiesOf: (code: number) => number
}) {
  const [f, setF] = useState<Filters>(BLANK)
  // Carries the query it answers, so a stale list never sits under a new search.
  const [outside, setOutside] = useState<{ query: string; cards: Card[] }>({
    query: '',
    cards: [],
  })

  const races = useMemo(() => {
    const set = new Set<string>()
    for (const card of pool ?? []) if (card.race) set.add(card.race)
    return [...set].sort()
  }, [pool])

  const hits = useMemo(() => {
    if (!pool) return []
    return pool
      .filter((card) => matches(card, f))
      .sort((a, b) => a.name.localeCompare(b.name))
  }, [pool, f])

  // Only when the pool answered nothing, and only for a real query: this is the
  // "that card exists, it is just not in the pool" path, not a search-as-you-type.
  const empty = hits.length === 0 && f.query.trim().length >= 3
  useEffect(() => {
    if (!empty) return
    let cancelled = false
    const query = f.query
    const timer = setTimeout(async () => {
      try {
        const found = await api.searchCards(query, 8)
        if (!cancelled) {
          setOutside({ query, cards: found.filter((card) => !card.in_pool) })
        }
      } catch {
        if (!cancelled) setOutside({ query, cards: [] })
      }
    }, 250)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [empty, f.query])

  const beyondPool = empty && outside.query === f.query ? outside.cards : []

  const set = (patch: Partial<Filters>) => setF((current) => ({ ...current, ...patch }))
  const active = Object.entries(f).filter(
    ([key, value]) => value !== '' && !(key === 'section' && value === 'main'),
  ).length

  return (
    <div className="flex h-full min-h-0 flex-col border border-edge bg-panel">
      <div className="shrink-0 space-y-1.5 border-b border-edge-soft p-2">
        <div className="relative">
          <Search
            size={12}
            className="pointer-events-none absolute top-1/2 left-2 -translate-y-1/2 text-faint"
          />
          <input
            value={f.query}
            onChange={(e) => set({ query: e.target.value })}
            placeholder="Name or card text"
            spellCheck={false}
            className="w-full border border-edge bg-slot py-1.5 pr-2 pl-6.5 text-xs text-fg placeholder:text-faint focus:border-gold focus:outline-none"
          />
        </div>

        <div className="grid grid-cols-3 gap-1">
          <select
            className={SELECT}
            value={f.section}
            onChange={(e) => set({ section: e.target.value })}
          >
            <option value="main">Main deck</option>
            <option value="extra">Extra deck</option>
            <option value="">Any section</option>
          </select>
          <select
            className={SELECT}
            value={f.kind}
            onChange={(e) => set({ kind: e.target.value, frame: '', attribute: '' })}
          >
            <option value="">Any type</option>
            {KINDS.map((k) => (
              <option key={k} value={k}>
                {k[0].toUpperCase() + k.slice(1)}
              </option>
            ))}
          </select>
          <select
            className={SELECT}
            value={f.frame}
            onChange={(e) => set({ frame: e.target.value })}
          >
            <option value="">Any frame</option>
            {FRAMES.map((frame) => (
              <option key={frame} value={frame}>
                {frame[0].toUpperCase() + frame.slice(1)}
              </option>
            ))}
          </select>
          <select
            className={SELECT}
            value={f.attribute}
            onChange={(e) => set({ attribute: e.target.value })}
          >
            <option value="">Any attribute</option>
            {ATTRIBUTES.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
          <select
            className={SELECT}
            value={f.race}
            onChange={(e) => set({ race: e.target.value })}
          >
            <option value="">Any race</option>
            {races.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
          <select
            className={SELECT}
            value={f.level}
            onChange={(e) => set({ level: e.target.value })}
          >
            <option value="">Any level</option>
            {Array.from({ length: 12 }, (_, i) => String(i + 1)).map((l) => (
              <option key={l} value={l}>
                Level {l}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] tabular text-faint">
            {pool === null ? 'loading pool' : `${hits.length} of ${pool.length}`}
          </span>
          {active > 0 && (
            <button
              type="button"
              onClick={() => setF(BLANK)}
              className="ml-auto font-display text-[10px] font-semibold tracking-wider text-faint hover:text-gold"
            >
              RESET
            </button>
          )}
        </div>
      </div>

      <ul className="min-h-0 flex-1 divide-y divide-edge-soft overflow-y-auto">
        {hits.map((card) => {
          const held = copiesOf(card.code)
          const full = held >= card.limit
          return (
            <li key={card.code}>
              <div
                className={cn(
                  'group flex items-stretch gap-2 pr-1 transition-colors hover:bg-panel-2',
                  selectedCode === card.code && 'bg-panel-2',
                )}
              >
                <button
                  type="button"
                  onClick={() => onInspect(card)}
                  className="flex min-w-0 flex-1 items-center gap-2 py-1.5 pl-1.5 text-left"
                >
                  <CardArt
                    card={card}
                    code={card.code}
                    size="thumb"
                    className="h-11 w-8 shrink-0 border border-edge-soft"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-baseline gap-1.5">
                      <span
                        className={cn(
                          'truncate text-xs',
                          card.limit === 0 ? 'text-faint line-through' : 'text-fg',
                        )}
                      >
                        {card.name}
                      </span>
                      {held > 0 && (
                        <span className="ml-auto shrink-0 font-mono text-[10px] tabular text-gold">
                          {held}
                        </span>
                      )}
                    </span>
                    <span
                      className={cn(
                        'block truncate font-mono text-[9.5px]',
                        FRAME_TEXT[frameOf(card)],
                      )}
                    >
                      {typeLine(card)}
                    </span>
                  </span>
                </button>

                <button
                  type="button"
                  onClick={() => onAdd(card)}
                  disabled={full}
                  title={
                    full
                      ? `The deck already holds every copy the banlist allows (${card.limit}).`
                      : `Add ${card.name}`
                  }
                  aria-label={`Add ${card.name}`}
                  className={cn(
                    'my-1.5 flex w-7 shrink-0 items-center justify-center border transition-colors',
                    full
                      ? 'cursor-not-allowed border-edge-soft text-faint/40'
                      : 'border-edge text-faint hover:border-gold hover:bg-gold/10 hover:text-gold',
                  )}
                >
                  <Plus size={13} />
                </button>
              </div>
            </li>
          )
        })}

        {hits.length === 0 && pool !== null && (
          <li className="space-y-3 p-3">
            <p className="text-[11px] leading-relaxed text-faint">
              Nothing in the supported pool matches. The pool is 864 cards frozen with
              the Pilot in 2024, so most of the game is outside it.
            </p>
            {beyondPool.length > 0 && (
              <div className="space-y-1.5">
                <p className="label text-warn">Real cards, outside the pool</p>
                <ul className="space-y-1">
                  {beyondPool.map((card) => (
                    <li
                      key={card.code}
                      className="flex items-baseline gap-2 border border-edge-soft bg-slot px-2 py-1.5"
                    >
                      <span className="truncate text-[11px] text-muted">
                        {card.name}
                      </span>
                      <span className="ml-auto shrink-0 font-mono text-[9px] text-faint">
                        {card.code}
                      </span>
                    </li>
                  ))}
                </ul>
                <p className="text-[10.5px] leading-relaxed text-faint">
                  These exist in the executor's card database. The Pilot has no
                  embedding for them, so no deck here can play them.
                </p>
              </div>
            )}
          </li>
        )}
      </ul>
    </div>
  )
}
