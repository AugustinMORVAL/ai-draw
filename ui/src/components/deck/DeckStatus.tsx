import { AlertTriangle, CheckCircle2, ShieldAlert } from 'lucide-react'
import type { CardFlag, DeckReport } from '@/lib/api'
import { cn } from '@/lib/cn'

const SEVERITY: Record<CardFlag['issue'], 'bad' | 'warn'> = {
  unknown_card: 'bad',
  not_in_pool: 'bad',
  token: 'bad',
  wrong_section: 'bad',
  forbidden: 'bad',
  over_limit: 'warn',
}

const ISSUE_LABEL: Record<CardFlag['issue'], string> = {
  unknown_card: 'unknown card',
  not_in_pool: 'not in the supported pool',
  token: 'token',
  wrong_section: 'extra deck card in the main deck',
  forbidden: 'forbidden',
  over_limit: 'over the copy limit',
}

function Flag({
  tone,
  label,
  children,
}: {
  tone: 'bad' | 'warn'
  label: string
  children: string
}) {
  return (
    <li
      className={cn(
        'border-l-2 bg-panel-2 px-3 py-2',
        tone === 'bad' ? 'border-l-bad' : 'border-l-warn',
      )}
    >
      <span
        className={cn('mb-0.5 block label', tone === 'bad' ? 'text-bad' : 'text-warn')}
      >
        {label}
      </span>
      <span className="block text-[11.5px] leading-relaxed text-muted">{children}</span>
    </li>
  )
}

/**
 * The Masking preview: how much of the pool the Builder may still pick from here.
 *
 * Masking is hard enforcement -- an illegal pick is removed from the action space
 * rather than rejected afterwards (CONTEXT.md) -- so this is the Builder's real room
 * to move inside this deck, not a warning about what might go wrong later.
 */
function Mask({ mask }: { mask: DeckReport['mask'] }) {
  const share = mask.pool_size > 0 ? mask.legal_picks / mask.pool_size : 0
  return (
    <div className="space-y-2 p-3">
      <div className="flex items-baseline gap-2">
        <span className="font-display text-xl tabular text-gold">
          {mask.legal_picks}
        </span>
        <span className="text-[11.5px] leading-snug text-muted">
          of {mask.pool_size} pool cards are legal picks for the Builder here
        </span>
      </div>
      <div className="h-1 overflow-hidden bg-edge-soft">
        <div className="h-full bg-gold" style={{ width: `${share * 100}%` }} />
      </div>
      <ul className="space-y-0.5 pt-0.5">
        {mask.masked.map((group) => (
          <li
            key={group.reason}
            className="flex items-baseline gap-2 text-[10.5px] text-faint"
          >
            <span className="w-9 shrink-0 text-right font-mono tabular text-muted">
              -{group.count}
            </span>
            <span className="leading-snug">{group.reason}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function DeckStatus({
  report,
  pending,
  banlist,
}: {
  report: DeckReport | null
  pending: boolean
  banlist: string
}) {
  if (!report) {
    return (
      <div className="border border-edge bg-panel p-3">
        <p className="text-[11.5px] leading-relaxed text-faint">
          Add cards from the browser, or paste a{' '}
          <span className="font-mono text-muted">.ydk</span> in the text drawer below.
          Every card is checked against the 864 the frozen Pilot can represent, the
          copy limit, and the {banlist} banlist.
        </p>
      </div>
    )
  }

  const problems = report.flags.length + report.deck_flags.length
  const Icon = report.legal ? CheckCircle2 : problems > 0 ? ShieldAlert : AlertTriangle

  return (
    <div
      className={cn(
        'border border-edge bg-panel transition-opacity',
        pending && 'opacity-60',
      )}
    >
      <header
        className={cn(
          'flex items-center gap-2 border-b px-3 py-2',
          report.legal
            ? 'border-good/30 bg-good/8 text-good'
            : 'border-bad/30 bg-bad/8 text-bad',
        )}
      >
        <Icon size={14} />
        <span className="font-display text-xs font-semibold tracking-[0.14em]">
          {report.legal ? 'LEGAL' : `${problems} PROBLEM${problems === 1 ? '' : 'S'}`}
        </span>
        <span className="ml-auto font-mono text-[10px] text-faint">
          banlist {report.banlist}
        </span>
      </header>

      {problems > 0 && (
        <ul className="space-y-1 p-2">
          {report.deck_flags.map((flag) => (
            <Flag key={flag.issue} tone="bad" label="deck">
              {flag.reason}
            </Flag>
          ))}
          {report.flags.map((flag) => (
            <Flag
              key={`${flag.issue}-${flag.code}`}
              tone={SEVERITY[flag.issue]}
              label={ISSUE_LABEL[flag.issue]}
            >
              {flag.reason}
            </Flag>
          ))}
        </ul>
      )}

      {report.unresolved.length > 0 && (
        <ul className="space-y-1 px-2 pb-2">
          {report.unresolved.map((line) => (
            <Flag key={line.line} tone="warn" label={`line ${line.line}`}>
              {line.reason}
            </Flag>
          ))}
        </ul>
      )}

      <div className="border-t border-edge-soft">
        <Mask mask={report.mask} />
      </div>
    </div>
  )
}
