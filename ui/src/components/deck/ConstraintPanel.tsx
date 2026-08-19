import { useState } from 'react'
import { AlertTriangle, Check, Dices, Plus, X } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import {
  ApiError,
  api,
  type ClauseStatus,
  type Constraint,
  type ConstraintFacet,
  type ConstraintReport,
  type DeckReport,
  type FacetValue,
} from '@/lib/api'
import { cn } from '@/lib/cn'
import { BOUNDS, FACETS } from '@/lib/useConstraint'
import { useFacets } from '@/lib/useFacets'

const SELECT =
  'min-w-0 border border-edge bg-slot px-1.5 py-1 font-mono text-[10.5px] text-fg ' +
  'focus:border-gold focus:outline-none'

const NUMBER = `${SELECT} w-12 text-right tabular`

const SIZES = Array.from({ length: 21 }, (_, i) => 40 + i)

/** What the pool can supply for one value, said in the form rather than after it. */
function ceilingLabel(value: FacetValue): string {
  if (value.copies === 0) {
    return value.elsewhere > 0
      ? `${value.value} — none in a main deck (${value.elsewhere} in the Extra Deck or as Tokens)`
      : `${value.value} — none`
  }
  return `${value.value} — up to ${value.copies}`
}

/** Held against asked, for one clause. The number the user is actually watching. */
function Held({ status }: { status: ClauseStatus | undefined }) {
  if (!status) {
    return <span className="w-16 shrink-0 font-mono text-[10px] text-faint">—</span>
  }
  return (
    <span
      className={cn(
        'flex w-16 shrink-0 items-center justify-end gap-1 font-mono text-[10.5px] tabular',
        status.satisfied ? 'text-good' : 'text-warn',
      )}
    >
      {status.held}/{status.clause.count}
      {status.satisfied ? <Check size={11} /> : <AlertTriangle size={11} />}
    </span>
  )
}

/**
 * The Interests form: the Constraint that drives a build.
 *
 * A Constraint is what the user asked for and may drop; Legality is what nobody
 * may drop (CONTEXT.md). They are two panels for that reason, and this one never
 * says "illegal" -- an unmet interest is a deck that is not what you wanted, not a
 * deck the duel farm refuses.
 *
 * Until Conditioning lands in phase 3, an interest is honoured by Masking alone
 * (ADR-0005): picks that would break it leave the Builder's action space. The panel
 * says so, because "filtered to Spellcasters" and "built as a Spellcaster deck" are
 * different products and a screenshot should not blur them.
 */
export function ConstraintPanel({
  constraint,
  stated,
  report,
  pending,
  onSize,
  onAdd,
  onEdit,
  onDrop,
  onClear,
  onBuilt,
}: {
  constraint: Constraint
  stated: boolean
  report: DeckReport | null
  /** A report is in flight: the counts on screen answer the previous question. */
  pending: boolean
  onSize: (size: number | null) => void
  onAdd: (clause: Constraint['clauses'][number]) => void
  onEdit: (at: number, patch: Partial<Constraint['clauses'][number]>) => void
  onDrop: (at: number) => void
  onClear: () => void
  onBuilt: (main: number[]) => void
}) {
  const { byFacet, error: facetError } = useFacets()
  const [building, setBuilding] = useState(false)
  const [refusal, setRefusal] = useState<ConstraintReport | string | null>(null)

  const judged = report?.constraint ?? null
  // A refused build is about the Constraint, so it replaces the conformance read-out
  // rather than piling a second panel of reasons under it.
  const shown = typeof refusal === 'object' && refusal !== null ? refusal : judged
  const flags = shown?.flags ?? []

  const valuesFor = (facet: ConstraintFacet) => byFacet.get(facet) ?? []

  const addDefault = () => {
    const first = valuesFor('race').find((value) => value.copies > 0)
    onAdd({
      facet: 'race',
      value: first?.value ?? 'Dragon',
      bound: 'at_least',
      count: 12,
    })
  }

  const build = async () => {
    setBuilding(true)
    setRefusal(null)
    try {
      const built = await api.buildDeck(constraint)
      onBuilt(built.deck?.main ?? [])
    } catch (e) {
      const detail = e instanceof ApiError ? (e.detail as ConstraintReport | null) : null
      setRefusal(
        detail && Array.isArray(detail.flags)
          ? detail
          : e instanceof Error
            ? e.message
            : String(e),
      )
    } finally {
      setBuilding(false)
    }
  }

  return (
    <section
      className={cn(
        'border border-edge bg-panel transition-opacity',
        pending && 'opacity-60',
      )}
    >
      <header className="flex items-center gap-2 border-b border-edge-soft bg-panel-2 px-3 py-2">
        <h2 className="font-display text-xs font-semibold tracking-[0.14em] text-gold">
          INTERESTS
        </h2>
        <span className="hidden text-[10.5px] text-faint sm:inline">
          what you asked for, beside the rules you cannot drop
        </span>
        {stated && (
          <button
            type="button"
            onClick={() => {
              setRefusal(null)
              onClear()
            }}
            className="ml-auto font-display text-[10px] font-semibold tracking-[0.14em] text-faint hover:text-bad"
          >
            CLEAR
          </button>
        )}
      </header>

      <div className="space-y-2.5 p-3">
        <label className="flex flex-wrap items-center gap-2">
          <span className="label text-faint">Deck size</span>
          <select
            className={SELECT}
            value={constraint.main_size ?? ''}
            onChange={(e) =>
              onSize(e.target.value === '' ? null : Number(e.target.value))
            }
          >
            <option value="">Any (40 to 60)</option>
            {SIZES.map((size) => (
              <option key={size} value={size}>
                {size} cards
              </option>
            ))}
          </select>
          <span className="text-[10.5px] leading-snug text-faint">
            Legality allows 40 to 60 and says nothing about which. Pick one and a
            build lands on it; leave it open and no size is held against your deck.
          </span>
        </label>

        <ul className="space-y-1">
          {constraint.clauses.map((clause, at) => {
            const values = valuesFor(clause.facet)
            const known = values.find((value) => value.value === clause.value)
            const impossible =
              clause.bound === 'at_least' && known !== undefined && known.copies === 0
            return (
              <li
                key={`${clause.facet}-${clause.value}-${at}`}
                className={cn(
                  'flex flex-wrap items-center gap-1.5 border-l-2 bg-slot/60 py-1.5 pr-1.5 pl-2',
                  impossible ? 'border-l-bad' : 'border-l-edge',
                )}
              >
                <select
                  className={SELECT}
                  value={clause.bound}
                  onChange={(e) =>
                    onEdit(at, { bound: e.target.value as typeof clause.bound })
                  }
                >
                  {BOUNDS.map((bound) => (
                    <option key={bound.bound} value={bound.bound}>
                      {bound.label}
                    </option>
                  ))}
                </select>

                <input
                  className={NUMBER}
                  type="number"
                  min={0}
                  max={60}
                  value={clause.count}
                  onChange={(e) => onEdit(at, { count: Number(e.target.value) })}
                />

                <select
                  className={SELECT}
                  value={clause.facet}
                  onChange={(e) => {
                    const facet = e.target.value as ConstraintFacet
                    const first = (byFacet.get(facet) ?? []).find((v) => v.copies > 0)
                    onEdit(at, { facet, value: first?.value ?? '' })
                  }}
                >
                  {FACETS.map((facet) => (
                    <option key={facet.facet} value={facet.facet}>
                      {facet.label}
                    </option>
                  ))}
                </select>

                <select
                  className={cn(SELECT, 'flex-1')}
                  value={clause.value}
                  onChange={(e) => onEdit(at, { value: e.target.value })}
                >
                  {known === undefined && (
                    <option value={clause.value}>{clause.value}</option>
                  )}
                  {values.map((value) => (
                    <option key={value.value} value={value.value}>
                      {ceilingLabel(value)}
                    </option>
                  ))}
                </select>

                <Held status={judged?.clauses[at]} />

                <button
                  type="button"
                  onClick={() => onDrop(at)}
                  aria-label="Drop this interest"
                  className="shrink-0 border border-edge px-1 py-1 text-faint hover:border-bad hover:text-bad"
                >
                  <X size={11} />
                </button>
              </li>
            )
          })}
        </ul>

        {constraint.clauses.length === 0 && (
          <p className="text-[11.5px] leading-relaxed text-muted">
            No interests stated, so the Builder may pick any of the legal cards the
            Masking preview counts. Add one and the picks that would break it leave
            the action space.
          </p>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={addDefault}
            disabled={constraint.clauses.length >= 8}
            className="flex items-center gap-1 border border-edge px-2 py-1 font-display text-[10px] font-semibold tracking-[0.14em] text-faint hover:border-gold/60 hover:text-gold disabled:opacity-40"
          >
            <Plus size={11} />
            ADD AN INTEREST
          </button>
          <Button
            variant="ghost"
            className="ml-auto"
            onClick={() => void build()}
            disabled={building}
          >
            <Dices size={12} />
            {building ? 'Building' : 'Build a deck'}
          </Button>
        </div>

        {typeof refusal === 'string' && (
          <p className="border-l-2 border-l-bad bg-bad/8 px-2 py-1.5 font-mono text-[11px] text-bad">
            {refusal}
          </p>
        )}

        {flags.length > 0 && (
          <ul className="space-y-1">
            {flags.map((flag, at) => (
              <li
                key={`${flag.issue}-${at}`}
                className={cn(
                  'border-l-2 bg-panel-2 px-2.5 py-1.5',
                  flag.issue === 'impossible' ? 'border-l-bad' : 'border-l-warn',
                )}
              >
                <span
                  className={cn(
                    'mb-0.5 block label',
                    flag.issue === 'impossible' ? 'text-bad' : 'text-warn',
                  )}
                >
                  {flag.issue === 'impossible'
                    ? 'no deck can do this'
                    : flag.issue === 'wrong_size'
                      ? 'deck size'
                      : 'not there yet'}
                </span>
                <span className="block text-[11.5px] leading-relaxed text-muted">
                  {flag.reason}
                </span>
              </li>
            ))}
          </ul>
        )}

        {shown?.satisfied && (
          <p className="border-l-2 border-l-good bg-good/8 px-2.5 py-1.5 text-[11.5px] leading-relaxed text-good">
            This deck is what you asked for, and it is legal.
          </p>
        )}

        <p className="text-[10.5px] leading-relaxed text-faint">
          Interests are enforced by Masking: a pick that would break one is removed
          from the Builder's action space, so the deck respects it at every step. The
          Builder was not <em>steered</em> toward it — that is Conditioning, and it is
          phase 3. A build is a uniform draw inside the mask.
          {facetError && ' The facet list did not load, so the dropdowns are empty.'}
        </p>
      </div>
    </section>
  )
}
