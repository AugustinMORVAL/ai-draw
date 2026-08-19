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

function Flag({ tone, label, children }: {
  tone: 'bad' | 'warn'
  label: string
  children: string
}) {
  return (
    <li
      className={cn(
        'rounded-md border px-3 py-2',
        tone === 'bad' ? 'border-bad/40 bg-bad/5' : 'border-warn/40 bg-warn/5',
      )}
    >
      <span
        className={cn(
          'mb-1 block font-mono text-[10px] uppercase tracking-[0.12em]',
          tone === 'bad' ? 'text-bad' : 'text-warn',
        )}
      >
        {label}
      </span>
      <span className="block text-xs leading-relaxed text-fg">{children}</span>
    </li>
  )
}

/**
 * The Masking preview: how many of the 864 the Builder may still pick, and why the
 * rest are out. Masking is hard enforcement — an illegal pick is removed from the
 * action space rather than rejected afterwards (CONTEXT.md) — so this is the
 * Builder's real room to move inside this deck, not a warning.
 */
function Mask({ mask }: { mask: DeckReport['mask'] }) {
  return (
    <div className="space-y-2 border-t border-line-soft px-4 py-3">
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-lg tabular text-accent-soft">
          {mask.legal_picks}
        </span>
        <span className="text-xs text-muted">
          of {mask.pool_size} pool cards are legal picks for the Builder here
        </span>
      </div>
      <div className="flex h-1.5 overflow-hidden rounded-full bg-line">
        <div
          className="bg-accent"
          style={{ width: `${(mask.legal_picks / mask.pool_size) * 100}%` }}
        />
      </div>
      <ul className="space-y-0.5">
        {mask.masked.map((group) => (
          <li
            key={group.reason}
            className="flex items-baseline gap-2 text-[11px] text-faint"
          >
            <span className="w-9 shrink-0 text-right font-mono tabular">
              −{group.count}
            </span>
            <span>{group.reason}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function DeckReportView({
  report,
  pending,
}: {
  report: DeckReport | null
  pending: boolean
}) {
  if (!report) {
    return (
      <p className="px-4 py-6 text-xs leading-relaxed text-faint">
        Paste a <span className="font-mono">.ydk</span> export, or type one card name
        per line with a count — <span className="font-mono">3 Ash Blossom</span>. Every
        card is checked against the 864 the frozen Pilot can represent, the copy limit,
        and the banlist.
      </p>
    )
  }

  const problems = report.flags.length + report.deck_flags.length
  return (
    <div className={cn(pending && 'opacity-60 transition-opacity')}>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-xs">
        <span
          className={cn(
            'rounded-full border px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.1em]',
            report.legal
              ? 'border-good/40 bg-good/10 text-good'
              : 'border-bad/40 bg-bad/10 text-bad',
          )}
        >
          {report.legal ? 'legal' : `${problems} problem${problems === 1 ? '' : 's'}`}
        </span>
        <span className="text-muted">
          main <span className="font-mono tabular text-fg">{report.main_count}</span>
          {report.extra_count > 0 && (
            <>
              {' · '}extra{' '}
              <span className="font-mono tabular text-fg">{report.extra_count}</span>
            </>
          )}
        </span>
        <span className="ml-auto font-mono text-[10px] uppercase tracking-[0.1em] text-faint">
          banlist {report.banlist}
        </span>
      </div>

      {problems > 0 && (
        <ul className="space-y-1.5 px-4 pb-3">
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
        <ul className="space-y-1.5 px-4 pb-3">
          {report.unresolved.map((line) => (
            <Flag key={line.line} tone="warn" label={`line ${line.line}`}>
              {line.reason}
            </Flag>
          ))}
        </ul>
      )}

      {report.entries.length > 0 && (
        <ul className="max-h-64 overflow-y-auto border-t border-line-soft">
          {report.entries.map((entry) => (
            <li
              key={`${entry.section}-${entry.card.code}`}
              className="flex items-baseline gap-2.5 border-b border-line-soft px-4 py-1.5 last:border-b-0"
            >
              <span className="w-5 shrink-0 font-mono text-xs tabular text-faint">
                {entry.count}×
              </span>
              <span
                className={cn(
                  'truncate text-sm',
                  entry.card.in_pool ? 'text-fg' : 'text-faint line-through',
                )}
              >
                {entry.card.name}
              </span>
              {entry.section === 'extra' && (
                <span className="ml-auto shrink-0 font-mono text-[10px] uppercase tracking-[0.1em] text-faint">
                  extra
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      <Mask mask={report.mask} />
    </div>
  )
}
