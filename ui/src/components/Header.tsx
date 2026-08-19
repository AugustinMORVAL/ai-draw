import type { Health } from '@/lib/api'
import { cn } from '@/lib/cn'

/**
 * The `live` flag is load-bearing: it tells anyone reading a screenshot whether the
 * numbers below came from real duels or from the fake executor (ADR-0005).
 */
export function Header({ health, offline }: { health: Health | null; offline: boolean }) {
  const live = health?.live ?? false
  return (
    <header className="sticky top-0 z-10 border-b border-line bg-ink/85 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-4 px-6 py-3.5">
        <div className="flex items-baseline gap-2.5">
          <span className="font-mono text-sm font-semibold tracking-tight">ai-draw</span>
          <span className="text-xs text-faint">deck builder</span>
        </div>

        <div className="ml-auto flex items-center gap-2.5 font-mono text-[10px] uppercase tracking-[0.12em]">
          {health && (
            <span className="hidden text-faint sm:inline">
              pool {health.pool_size} cards
            </span>
          )}
          <span
            className={cn(
              'rounded-full border px-2.5 py-1',
              live
                ? 'border-good/40 bg-good/10 text-good'
                : 'border-warn/40 bg-warn/10 text-warn',
            )}
            title={
              live
                ? 'Real duels, run by the ygo-agent executor.'
                : 'Fake executor: every number below is fabricated.'
            }
          >
            {live ? 'live: true' : 'live: false — fake executor'}
          </span>
          <span
            className={cn(
              'rounded-full border px-2.5 py-1',
              offline ? 'border-bad/40 bg-bad/10 text-bad' : 'border-line text-faint',
            )}
          >
            {offline ? 'api unreachable' : 'api ok'}
          </span>
        </div>
      </div>
    </header>
  )
}
