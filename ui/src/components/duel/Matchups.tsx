import type { GateResult, Matchup } from '@/lib/api'
import { cn } from '@/lib/cn'

const pct = (n: number, digits = 1) => `${(n * 100).toFixed(digits)}%`
const band = (n: number) => `±${(n * 100).toFixed(1)}`

/**
 * One matchup, drawn against the 50% line.
 *
 * The bar grows from the middle, not from the left: what a reader wants from a
 * matchup row is which side of even it fell on and by how far, and a bar anchored
 * at zero makes 48% and 52% look like the same number.
 */
function MatchupRow({ row }: { row: Matchup }) {
  const edge = row.win_rate - 0.5
  const width = Math.min(Math.abs(edge) * 2, 1) * 50
  const second = row.duels - row.first_duels
  return (
    <li className="grid grid-cols-[8.5rem_minmax(0,1fr)_4.5rem] items-center gap-2 px-2.5 py-1.5">
      <span className="truncate text-[11px] text-muted" title={row.opponent}>
        {row.opponent}
      </span>

      <span className="relative flex h-4 items-center">
        <span className="absolute inset-y-0 left-1/2 w-px bg-edge" />
        <span
          className={cn(
            'absolute h-2',
            edge >= 0 ? 'left-1/2 bg-good/70' : 'right-1/2 bg-bad/70',
          )}
          style={{ width: `${width}%` }}
        />
        {/* The band the row's fifty duels earn, drawn as the ground the bar
            stands on: it is wider than most of these bars. */}
        <span
          className="absolute h-4 border-x border-edge-soft bg-fg/4"
          style={{
            left: `${Math.max(0, 50 + (edge - row.margin) * 100)}%`,
            width: `${Math.min(100, row.margin * 200)}%`,
          }}
        />
      </span>

      <span className="text-right">
        <span
          className={cn(
            'block font-mono text-[11px] tabular',
            edge >= 0 ? 'text-good' : 'text-bad',
          )}
        >
          {pct(row.win_rate, 0)}
        </span>
        <span className="block font-mono text-[9.5px] tabular text-faint">
          {row.first_wins}/{row.first_duels} · {row.wins - row.first_wins}/{second}
        </span>
      </span>
    </li>
  )
}

/**
 * The Gate result: one quotable win rate, and the ten numbers it is the mean of.
 *
 * The Gauntlet is shown in its fixed order rather than sorted best-to-worst. It is
 * fixed within a phase precisely so two decks' rows line up (CONTEXT.md), and
 * re-sorting per deck would throw that away for a nicer-looking column.
 */
export function Matchups({ result }: { result: GateResult }) {
  const worst = result.matchups.reduce(
    (low, row) => (row.win_rate < low.win_rate ? row : low),
    result.matchups[0],
  )
  const best = result.matchups.reduce(
    (high, row) => (row.win_rate > high.win_rate ? row : high),
    result.matchups[0],
  )
  const perOpponent = result.matchups[0]?.duels ?? 0

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 divide-x divide-edge-soft border border-edge-soft bg-panel-2">
        <div className="min-w-0 px-3 py-2">
          <div className="label text-faint">Win rate</div>
          <div className="mt-1 flex items-baseline gap-1.5">
            <span className="font-display text-xl tabular text-gold">
              {pct(result.win_rate)}
            </span>
            <span className="font-mono text-[10.5px] tabular text-faint">
              {band(result.margin)}
            </span>
          </div>
          <div className="mt-0.5 text-[10.5px] text-faint">
            gate fidelity, {result.duels} duels
          </div>
        </div>
        <div className="min-w-0 px-3 py-2">
          <div className="label text-faint">Best matchup</div>
          <div className="mt-1 truncate font-display text-sm text-good">
            {best?.opponent ?? '—'}
          </div>
          <div className="mt-0.5 font-mono text-[10.5px] tabular text-faint">
            {best ? pct(best.win_rate, 0) : ''}
          </div>
        </div>
        <div className="min-w-0 px-3 py-2">
          <div className="label text-faint">Worst matchup</div>
          <div className="mt-1 truncate font-display text-sm text-bad">
            {worst?.opponent ?? '—'}
          </div>
          <div className="mt-0.5 font-mono text-[10.5px] tabular text-faint">
            {worst ? pct(worst.win_rate, 0) : ''}
          </div>
        </div>
      </div>

      <div className="border border-edge-soft bg-panel-2">
        <header className="flex items-baseline gap-2 border-b border-edge-soft px-3 py-1.5">
          <h3 className="label text-faint">The Gauntlet</h3>
          <span className="ml-auto font-mono text-[10px] tabular text-faint">
            {perOpponent} duels each · on the play / on the draw
          </span>
        </header>
        <ul className="divide-y divide-edge-soft">
          {result.matchups.map((row) => (
            <MatchupRow key={row.opponent} row={row} />
          ))}
        </ul>
      </div>

      <p className="border-l-2 border-l-good bg-good/8 px-3 py-2 text-[11px] leading-relaxed text-good">
        Gate evaluation, so this is the one number in the app that may be quoted
        (ADR-0003) — {pct(result.win_rate)} {band(result.margin)} over {result.duels}{' '}
        paired duels. A single row is only {perOpponent} of them and carries a{' '}
        {band(result.matchups[0]?.margin ?? 0)} band of its own, so read the
        ordering rather than the digits.
      </p>
    </div>
  )
}
