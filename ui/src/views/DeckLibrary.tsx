import { BookMarked, Download, GitCompareArrows, Trash2, Upload } from 'lucide-react'
import { CardChanges } from '@/components/deck/CardChanges'
import { Button } from '@/components/ui/Button'
import type {
  Card,
  DeckComparison,
  DeckRef,
  DeckVersion,
  GateSnapshot,
  LibraryDeck,
} from '@/lib/api'
import { cn } from '@/lib/cn'
import { countOf } from '@/lib/diff'
import { toYdk } from '@/lib/deckText'
import type { Library } from '@/lib/useLibrary'
import { formatRef, useComparison } from '@/lib/useComparison'
import { usePool } from '@/lib/usePool'

const pct = (n: number, digits = 1) => `${(n * 100).toFixed(digits)}%`
const band = (n: number) => `±${(n * 100).toFixed(1)}`
const signed = (n: number) => `${n >= 0 ? '+' : '−'}${Math.abs(n * 100).toFixed(1)}`

function when(seconds: number) {
  return new Date(seconds * 1000).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** A version's Gate result, or the sentence explaining why there is none. */
function GateLine({ gate }: { gate: GateSnapshot | null }) {
  if (!gate) {
    return <span className="font-mono text-[10px] text-faint">never tested</span>
  }
  return (
    <span className="flex items-baseline gap-1">
      <span
        className={cn(
          'font-mono text-[11px] tabular',
          gate.win_rate >= 0.5 ? 'text-good' : 'text-bad',
        )}
      >
        {pct(gate.win_rate)}
      </span>
      <span className="font-mono text-[9.5px] tabular text-faint">
        {band(gate.margin)}
      </span>
      {!gate.live && (
        <span className="font-mono text-[9px] tracking-[0.1em] text-warn">FAKE</span>
      )}
    </span>
  )
}

function VersionRow({
  version,
  side,
  onPick,
  onLoad,
}: {
  version: DeckVersion
  side: 'left' | 'right' | null
  onPick: (side: 'left' | 'right') => void
  onLoad: () => void
}) {
  return (
    <li
      className={cn(
        'flex items-center gap-2 border-l-2 px-2 py-1.5',
        side ? 'border-l-gold bg-gold/5' : 'border-l-transparent',
      )}
    >
      <span className="w-6 shrink-0 font-mono text-[10.5px] tabular text-faint">
        v{version.version}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block font-mono text-[10.5px] tabular text-muted">
          {version.main_count}
          {version.extra_count > 0 && ` + ${version.extra_count}`} cards
        </span>
        <span className="block">
          <GateLine gate={version.gate} />
        </span>
      </span>
      <span className="flex shrink-0 items-center gap-1">
        {(['left', 'right'] as const).map((which) => (
          <button
            key={which}
            type="button"
            title={`Compare as the ${which}-hand deck`}
            onClick={() => onPick(which)}
            className={cn(
              'size-5 border font-display text-[10px] font-semibold transition-colors',
              side === which
                ? 'border-gold bg-gold text-void'
                : 'border-edge text-faint hover:border-gold/60 hover:text-gold',
            )}
          >
            {which === 'left' ? 'A' : 'B'}
          </button>
        ))}
        <button
          type="button"
          title="Open this version in the deck editor"
          onClick={onLoad}
          className="flex size-5 items-center justify-center border border-edge text-faint transition-colors hover:border-gold/60 hover:text-gold"
        >
          <Upload size={10} />
        </button>
      </span>
    </li>
  )
}

function Shelf({
  decks,
  left,
  right,
  onPick,
  onLoad,
  onDelete,
}: {
  decks: LibraryDeck[]
  left: DeckRef | null
  right: DeckRef | null
  onPick: (side: 'left' | 'right', ref: DeckRef) => void
  onLoad: (version: DeckVersion) => void
  onDelete: (deck: LibraryDeck) => void
}) {
  const sideOf = (deck: LibraryDeck, version: DeckVersion) => {
    if (left?.deck_id === deck.id && left.version === version.version) return 'left'
    if (right?.deck_id === deck.id && right.version === version.version) return 'right'
    return null
  }

  return (
    <div className="flex min-h-0 flex-col border border-edge bg-panel">
      <header className="flex shrink-0 items-center gap-2 border-b border-edge-soft bg-panel-2 px-3 py-2">
        <h2 className="font-display text-xs font-semibold tracking-[0.14em] text-gold">
          SHELF
        </h2>
        <span className="ml-auto font-mono text-[10px] tabular text-faint">
          {decks.length}
        </span>
      </header>

      {decks.length === 0 ? (
        <p className="p-6 text-center text-xs leading-relaxed text-faint">
          Nothing saved. Build a deck and save it from the deck editor, or save the
          deck a finished job came back with.
        </p>
      ) : (
        <ul className="min-h-0 flex-1 divide-y divide-edge overflow-y-auto">
          {decks.map((deck) => (
            <li key={deck.id}>
              <div className="flex items-center gap-2 bg-panel-2/60 px-3 py-1.5">
                <BookMarked size={12} className="shrink-0 text-gold-dim" />
                <span className="min-w-0 flex-1 truncate font-display text-[11.5px] tracking-[0.06em] text-fg">
                  {deck.name}
                </span>
                <span className="shrink-0 font-mono text-[9.5px] tabular text-faint">
                  {deck.versions.length}v
                </span>
                <button
                  type="button"
                  title="Forget this deck and every version of it"
                  onClick={() => onDelete(deck)}
                  className="shrink-0 text-faint transition-colors hover:text-bad"
                >
                  <Trash2 size={11} />
                </button>
              </div>
              <ul className="divide-y divide-edge-soft">
                {deck.versions.map((version) => (
                  <VersionRow
                    key={version.version}
                    version={version}
                    side={sideOf(deck, version)}
                    onPick={(side) =>
                      onPick(side, { deck_id: deck.id, version: version.version })
                    }
                    onLoad={() => onLoad(version)}
                  />
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/**
 * Two Gate win rates on one scale, each standing on the band its duels earn.
 *
 * The bands are the point of the picture. Two 500-duel Gate results carry ±4.4
 * points each, so two bars whose bands overlap have not been told apart by these
 * measurements however far apart their numbers read — and that is the common case
 * once the real executor lands.
 */
function BandScale({ left, right }: { left: GateSnapshot; right: GateSnapshot }) {
  const lo = Math.min(left.win_rate - left.margin, right.win_rate - right.margin) - 0.04
  const hi = Math.max(left.win_rate + left.margin, right.win_rate + right.margin) + 0.04
  const at = (value: number) => ((value - lo) / (hi - lo)) * 100

  return (
    <div className="space-y-1.5 px-3 py-2.5">
      {([
        ['A', left],
        ['B', right],
      ] as const).map(([label, snapshot]) => (
        <div key={label} className="flex items-center gap-2">
          <span className="w-3 shrink-0 font-display text-[10px] text-faint">
            {label}
          </span>
          <span className="relative h-4 flex-1">
            {lo < 0.5 && hi > 0.5 && (
              <span
                className="absolute inset-y-0 w-px bg-edge"
                style={{ left: `${at(0.5)}%` }}
              />
            )}
            <span
              className="absolute inset-y-0.5 border-x border-edge bg-fg/6"
              style={{
                left: `${at(snapshot.win_rate - snapshot.margin)}%`,
                width: `${((snapshot.margin * 2) / (hi - lo)) * 100}%`,
              }}
            />
            <span
              className={cn(
                'absolute inset-y-0 w-0.5',
                snapshot.win_rate >= 0.5 ? 'bg-good' : 'bg-bad',
              )}
              style={{ left: `${at(snapshot.win_rate)}%` }}
            />
          </span>
          <span className="w-24 shrink-0 text-right font-mono text-[10.5px] tabular text-muted">
            {pct(snapshot.win_rate)} {band(snapshot.margin)}
          </span>
        </div>
      ))}
      <p className="pl-5 font-mono text-[9.5px] text-faint">
        {pct(lo, 0)} — {pct(hi, 0)}, with the 50% line where it falls
      </p>
    </div>
  )
}

/** The Gate half of a comparison: two numbers, and what their bands allow. */
function GateVerdict({ comparison }: { comparison: DeckComparison }) {
  const { gate, left, right } = comparison
  const tone = gate === null ? 'warn' : gate.separated ? 'good' : 'warn'

  return (
    <div className="border border-edge-soft bg-panel-2">
      <header className="flex items-baseline gap-2 border-b border-edge-soft px-3 py-1.5">
        <h3 className="label text-faint">Gate results</h3>
        {gate && (
          <span
            className={cn(
              'ml-auto font-mono text-[10.5px] tabular',
              gate.separated ? 'text-fg' : 'text-faint',
            )}
          >
            {signed(gate.difference)} points {band(gate.margin)}
          </span>
        )}
      </header>

      {gate && left.version.gate && right.version.gate && (
        <BandScale left={left.version.gate} right={right.version.gate} />
      )}

      <p
        className={cn(
          'border-l-2 px-3 py-2 text-[11px] leading-relaxed',
          tone === 'good'
            ? 'border-l-good bg-good/8 text-good'
            : 'border-l-warn bg-warn/8 text-warn',
        )}
      >
        {comparison.gate_note}
      </p>
    </div>
  )
}

function SideHeader({
  label,
  side,
}: {
  label: 'A' | 'B'
  side: DeckComparison['left']
}) {
  return (
    <div className="min-w-0 px-3 py-2">
      <div className="flex items-baseline gap-1.5">
        <span className="font-display text-[10px] text-faint">{label}</span>
        <span className="min-w-0 truncate font-display text-[12.5px] tracking-[0.06em] text-fg">
          {side.name}
        </span>
        <span className="font-mono text-[10px] tabular text-faint">
          v{side.version.version}
        </span>
      </div>
      <div className="mt-0.5 font-mono text-[10px] tabular text-faint">
        {side.version.main_count}
        {side.version.extra_count > 0 && ` + ${side.version.extra_count}`} cards ·
        saved {when(side.version.created_at)}
      </div>
      {side.version.note && (
        <div className="mt-0.5 truncate font-mono text-[10px] text-faint">
          {side.version.note}
        </div>
      )}
    </div>
  )
}

function Comparison({
  comparison,
  byCode,
}: {
  comparison: DeckComparison
  byCode: Map<number, Card>
}) {
  const changed = countOf(comparison.diff.added)
  const extraChanged =
    countOf(comparison.extra_diff.added) + countOf(comparison.extra_diff.removed)

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 divide-x divide-edge-soft border border-edge-soft bg-panel-2">
        <SideHeader label="A" side={comparison.left} />
        <SideHeader label="B" side={comparison.right} />
      </div>

      <GateVerdict comparison={comparison} />

      <div className="border border-edge-soft bg-panel-2">
        <header className="flex items-baseline gap-2 border-b border-edge-soft px-3 py-1.5">
          <h3 className="label text-faint">Main deck, A to B</h3>
          <span className="ml-auto font-mono text-[10.5px] tabular text-faint">
            {changed} of {changed + comparison.diff.unchanged} cards differ
          </span>
        </header>
        {changed === 0 && comparison.diff.removed.length === 0 ? (
          <p className="px-3 py-2.5 text-[11px] leading-relaxed text-faint">
            The same forty cards. Two versions can differ by their Extra Deck alone,
            and a job never sees that half of a deck.
          </p>
        ) : (
          <CardChanges
            diff={comparison.diff}
            byCode={byCode}
            outLabel="Only in A"
            inLabel="Only in B"
          />
        )}
      </div>

      {extraChanged > 0 && (
        <div className="border border-edge-soft bg-panel-2">
          <header className="flex items-baseline gap-2 border-b border-edge-soft px-3 py-1.5">
            <h3 className="label text-faint">Extra deck</h3>
            <span className="ml-auto text-[10px] text-faint">
              never sent to the duel farm, so no win rate is about these
            </span>
          </header>
          <CardChanges
            diff={comparison.extra_diff}
            byCode={byCode}
            outLabel="Only in A"
            inLabel="Only in B"
          />
        </div>
      )}
    </div>
  )
}

/**
 * The deck library: saved decks, their versions, and two of them side by side.
 *
 * The shelf is where a deck stops being the contents of a text box. Everything on
 * screen that is a number came from a test job, matched to the version by its
 * decklist rather than by a pointer someone remembered to attach — which is why a
 * deck saved long after its own Gate evaluation still shows it.
 */
export function DeckLibrary({
  library,
  left,
  right,
  onPick,
  onLoad,
}: {
  library: Library
  left: DeckRef | null
  right: DeckRef | null
  onPick: (side: 'left' | 'right', ref: DeckRef | null) => void
  onLoad: (version: DeckVersion) => void
}) {
  const { byCode } = usePool()
  const { comparison, error, pending } = useComparison(left, right)

  const remove = async (deck: LibraryDeck) => {
    if (left?.deck_id === deck.id) onPick('left', null)
    if (right?.deck_id === deck.id) onPick('right', null)
    await library.remove(deck.id)
  }

  const download = (version: DeckVersion, name: string) => {
    const blob = new Blob([toYdk(version.main, version.extra)], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${name} v${version.version}.ydk`
    link.click()
    URL.revokeObjectURL(url)
  }

  const picked = [left, right].filter(Boolean).length

  return (
    <div className="grid min-h-0 gap-3 p-3 lg:h-[calc(100svh-3.5rem)] lg:grid-cols-[21rem_minmax(0,1fr)]">
      <Shelf
        decks={library.decks}
        left={left}
        right={right}
        onPick={onPick}
        onLoad={onLoad}
        onDelete={(deck) => void remove(deck)}
      />

      <div className="min-h-0 lg:overflow-y-auto lg:pr-1">
        {(library.error ?? error) && (
          <p className="mb-3 border-l-2 border-l-bad bg-bad/8 px-3 py-2 font-mono text-[11px] text-bad">
            {library.error ?? error}
          </p>
        )}

        {comparison === null ? (
          <div className="flex h-full items-center justify-center border border-edge bg-panel p-10">
            <div className="max-w-sm space-y-3 text-center">
              <GitCompareArrows size={20} className="mx-auto text-gold-dim" />
              <p className="text-xs leading-relaxed text-faint">
                {pending
                  ? 'Comparing…'
                  : picked === 1
                    ? 'One deck picked. Pick a B to compare it against — any version of any deck, including another version of this one.'
                    : 'Pick two versions with the A and B buttons. You get the cards that differ, and each deck’s last Gate result with the band its duels earn.'}
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="ghost"
                onClick={() => download(comparison.left.version, comparison.left.name)}
              >
                <Download size={12} />
                Export A
              </Button>
              <Button
                variant="ghost"
                onClick={() =>
                  download(comparison.right.version, comparison.right.name)
                }
              >
                <Download size={12} />
                Export B
              </Button>
              <span className="ml-auto font-mono text-[10px] text-faint">
                {formatRef({
                  deck_id: comparison.left.deck_id,
                  version: comparison.left.version.version,
                })}{' '}
                ·{' '}
                {formatRef({
                  deck_id: comparison.right.deck_id,
                  version: comparison.right.version.version,
                })}
              </span>
            </div>
            <Comparison comparison={comparison} byCode={byCode} />
          </div>
        )}
      </div>
    </div>
  )
}
