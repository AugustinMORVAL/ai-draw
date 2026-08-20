import { useState } from 'react'
import { BookmarkPlus } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import type { DeckSaved, LibraryDeck } from '@/lib/api'
import { cn } from '@/lib/cn'

/**
 * Put the deck on screen on the shelf, under a name.
 *
 * The same control in both places a deck comes from: the editor, where a user
 * built it, and the duel farm, where a job produced one. The name is the deck's
 * identity, so typing one the library already holds adds a version to that deck --
 * which is why the existing names are offered as a datalist rather than hidden
 * behind a separate "new version of..." mode.
 *
 * The answer is shown verbatim, including when nothing was written: a save that
 * quietly did nothing because the list was unchanged is the one outcome a user
 * would otherwise misread as a lost deck.
 */
export function SaveToLibrary({
  main,
  extra,
  decks,
  onSave,
  note,
  hint,
  className,
}: {
  main: number[]
  extra: number[]
  decks: LibraryDeck[]
  onSave: (body: {
    name: string
    main: number[]
    extra: number[]
    note?: string | null
  }) => Promise<DeckSaved | null>
  note?: string
  hint?: string
  className?: string
}) {
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [said, setSaid] = useState<DeckSaved | null>(null)

  const trimmed = name.trim()
  const known = decks.find(
    (deck) => deck.name.toLowerCase() === trimmed.toLowerCase(),
  )

  const submit = async () => {
    if (!trimmed || main.length === 0) return
    setBusy(true)
    const saved = await onSave({ name: trimmed, main, extra, note: note ?? null })
    setBusy(false)
    setSaid(saved)
  }

  return (
    <div className={cn('space-y-2', className)}>
      <div className="flex gap-2">
        <input
          className="min-w-0 flex-1 border border-edge bg-slot px-2 py-1.5 font-mono text-xs text-fg placeholder:text-faint focus:border-gold focus:outline-none"
          placeholder="Deck name"
          value={name}
          list="ai-draw-library-names"
          maxLength={64}
          onChange={(e) => {
            setName(e.target.value)
            setSaid(null)
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              void submit()
            }
          }}
        />
        <datalist id="ai-draw-library-names">
          {decks.map((deck) => (
            <option key={deck.id} value={deck.name} />
          ))}
        </datalist>
        <Button
          variant="ghost"
          disabled={busy || !trimmed || main.length === 0}
          onClick={() => void submit()}
        >
          <BookmarkPlus size={12} />
          {known ? `Save v${known.versions.length + 1}` : 'Save'}
        </Button>
      </div>

      <p className="text-[10.5px] leading-relaxed text-faint">
        {said
          ? said.reason
          : known
            ? `${known.name} is already on the shelf with ${known.versions.length} version${known.versions.length === 1 ? '' : 's'}. Saving adds another; the older ones are never rewritten.`
            : (hint ??
              'The name is the deck. Saving under a name the library already holds adds a version to it rather than making a second deck.')}
      </p>
    </div>
  )
}
