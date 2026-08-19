import { useEffect, useState } from 'react'
import { api, type Card } from '@/lib/api'
import { cn } from '@/lib/cn'

const DEBOUNCE_MS = 200

const SECTION_LABEL: Record<Card['section'], string> = {
  main: 'main',
  extra: 'extra deck',
  token: 'token',
}

function limitLabel(limit: number) {
  return ['forbidden', 'limited', 'semi-limited'][limit] ?? null
}

/**
 * Search the card database, not the pool.
 *
 * A user who types a card the frozen Pilot cannot represent gets the card back,
 * greyed out and labelled — showing nothing would let them conclude the app is
 * broken rather than that the pool is small (ADR-0005).
 */
export function CardSearch({ onPick }: { onPick: (card: Card) => void }) {
  const [query, setQuery] = useState('')
  // Results carry the query they answer, so "still searching" is derived, not tracked.
  const [result, setResult] = useState<{ query: string; hits: Card[] }>({
    query: '',
    hits: [],
  })
  const ready = query.trim().length >= 2

  useEffect(() => {
    if (!ready) return
    let cancelled = false
    const timer = setTimeout(async () => {
      try {
        const hits = await api.searchCards(query, 12)
        if (!cancelled) setResult({ query, hits })
      } catch {
        if (!cancelled) setResult({ query, hits: [] })
      }
    }, DEBOUNCE_MS)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [query, ready])

  const pending = result.query !== query
  const hits = ready ? result.hits : []

  return (
    <div className="space-y-2 p-4">
      <input
        className={cn(
          'w-full rounded-md border border-line bg-panel-2 px-3 py-2 text-sm',
          'placeholder:text-faint focus:border-accent focus:outline-none',
        )}
        placeholder="Search cards by name…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        spellCheck={false}
      />

      {ready && (
        <ul className="max-h-72 space-y-1 overflow-y-auto">
          {hits.length === 0 && !pending && (
            <li className="px-1 py-2 text-xs text-faint">
              No card is named that. The database is the executor's own, frozen at the
              2024 build — 2026 cards are not in it yet.
            </li>
          )}
          {hits.map((card) => (
            <li key={card.code}>
              <button
                type="button"
                disabled={!card.in_pool || card.section !== 'main'}
                onClick={() => onPick(card)}
                className={cn(
                  'w-full rounded-md border px-2.5 py-1.5 text-left transition-colors',
                  'disabled:cursor-not-allowed',
                  card.in_pool && card.section === 'main'
                    ? 'border-line bg-panel-2 hover:border-accent/60'
                    : 'border-line-soft bg-transparent opacity-55',
                )}
              >
                <div className="flex items-baseline gap-2">
                  <span className="truncate text-sm">{card.name}</span>
                  <span className="ml-auto shrink-0 font-mono text-[10px] uppercase tracking-[0.1em] text-faint">
                    {card.in_pool ? SECTION_LABEL[card.section] : 'not in pool'}
                  </span>
                </div>
                <div className="mt-0.5 flex items-center gap-2 font-mono text-[10px] text-faint">
                  <span>{card.code}</span>
                  {card.race && <span>{card.race}</span>}
                  {card.kind !== 'monster' && card.kind !== 'unknown' && (
                    <span>{card.kind}</span>
                  )}
                  {card.in_pool && limitLabel(card.limit) && (
                    <span className="text-warn">{limitLabel(card.limit)}</span>
                  )}
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
