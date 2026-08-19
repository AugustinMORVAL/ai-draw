import type { ReactNode } from 'react'
import { Layers, Radio, Swords } from 'lucide-react'
import type { Health } from '@/lib/api'
import { cn } from '@/lib/cn'
import type { View } from '@/lib/useRoute'

const TABS: { view: View; label: string; icon: typeof Layers }[] = [
  { view: 'deck', label: 'Deck', icon: Layers },
  { view: 'farm', label: 'Duel farm', icon: Swords },
  { view: 'replay', label: 'Replays', icon: Radio },
]

function LiveBadge({ live }: { live: boolean }) {
  return (
    <span
      title={
        live
          ? 'Real duels, run by the ygo-agent executor.'
          : 'Fake executor: every number and every duel log in this app is fabricated.'
      }
      className={cn(
        'bevel-sm flex items-center gap-1.5 border px-2 py-1 font-display text-[10px] font-semibold tracking-[0.14em]',
        live
          ? 'border-good/50 bg-good/10 text-good'
          : 'border-warn/50 bg-warn/10 text-warn',
      )}
    >
      <span className={cn('size-1.5', live ? 'bg-good' : 'bg-warn')} />
      {live ? 'LIVE DUELS' : 'FAKE EXECUTOR'}
    </span>
  )
}

/**
 * The app frame.
 *
 * The `live` flag is the load-bearing piece of chrome: it tells anyone reading a
 * screenshot whether the win rates and the duel logs below came from real duels or
 * from the fake executor (ADR-0005). It sits in the header on every view, not on
 * the one view that happens to show a number.
 */
export function Shell({
  health,
  offline,
  view,
  onNavigate,
  children,
}: {
  health: Health | null
  offline: boolean
  view: View
  onNavigate: (view: View) => void
  children: ReactNode
}) {
  return (
    <div className="flex min-h-svh flex-col">
      {/* Fixed, so it never repaints while a 60-card grid scrolls under it. */}
      <div
        aria-hidden
        className="scanlines pointer-events-none fixed inset-0 z-50 opacity-60"
      />

      <header className="sticky top-0 z-40 border-b border-edge bg-field/92 backdrop-blur-md">
        <div className="flex h-14 items-center gap-5 px-4">
          <div className="flex items-baseline gap-2">
            <span className="font-display text-base font-bold tracking-[0.18em] text-gold">
              AI-DRAW
            </span>
            <span className="hidden font-display text-[10px] tracking-[0.2em] text-faint sm:inline">
              DECK LAB
            </span>
          </div>

          <nav className="flex items-stretch self-stretch">
            {TABS.map(({ view: tab, label, icon: Icon }) => (
              <button
                key={tab}
                type="button"
                onClick={() => onNavigate(tab)}
                aria-current={view === tab ? 'page' : undefined}
                className={cn(
                  'flex items-center gap-1.5 border-b-2 px-3 font-display text-[11px] font-semibold tracking-[0.12em] transition-colors',
                  view === tab
                    ? 'border-b-gold text-gold'
                    : 'border-b-transparent text-faint hover:text-fg',
                )}
              >
                <Icon size={13} />
                <span className="hidden sm:inline">{label.toUpperCase()}</span>
              </button>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-2">
            {health && (
              <span
                className="hidden font-mono text-[10px] text-faint lg:inline"
                title={
                  `${health.pool_size} cards the frozen Pilot can represent; ` +
                  `${health.main_deck_pool_size} of them can go in a main deck. ` +
                  'The rest are Tokens and Extra Deck monsters it only has to recognise.'
                }
              >
                pool {health.main_deck_pool_size}/{health.pool_size} · banlist{' '}
                {health.banlist}
              </span>
            )}
            <LiveBadge live={health?.live ?? false} />
            {offline && (
              <span className="bevel-sm border border-bad/50 bg-bad/10 px-2 py-1 font-display text-[10px] font-semibold tracking-[0.14em] text-bad">
                API UNREACHABLE
              </span>
            )}
          </div>
        </div>
      </header>

      <main className="min-h-0 flex-1">{children}</main>
    </div>
  )
}
