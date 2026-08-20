import { useEffect, useMemo, useState } from 'react'
import { Shell } from '@/components/chrome/Shell'
import type { Constraint, Deck, DeckRef, DeckVersion } from '@/lib/api'
import { toYdk } from '@/lib/deckText'
import { useConstraint } from '@/lib/useConstraint'
import { useDeckReport } from '@/lib/useDeckReport'
import { useJobs } from '@/lib/useJobs'
import { useLibrary } from '@/lib/useLibrary'
import { formatRef, parseRef } from '@/lib/useComparison'
import { useRoute } from '@/lib/useRoute'
import { DeckEditor, SEED } from '@/views/DeckEditor'
import { DeckLibrary } from '@/views/DeckLibrary'
import { DuelFarm } from '@/views/DuelFarm'
import { ReplayTheatre } from '@/views/ReplayTheatre'

const DECK_KEY = 'ai-draw.deck'

/**
 * The deck in progress, kept across reloads.
 *
 * The library is where a deck is kept on purpose; this is the one being edited,
 * which is not a saved deck yet and has nowhere else to live. Losing forty card
 * picks to a refresh is the one failure this app can trivially avoid.
 */
function useDeckText() {
  const [text, setText] = useState(() => localStorage.getItem(DECK_KEY) ?? SEED)
  useEffect(() => {
    if (text) localStorage.setItem(DECK_KEY, text)
    else localStorage.removeItem(DECK_KEY)
  }, [text])
  return [text, setText] as const
}

export default function App() {
  const { jobs, health, offline, error, submitRefine, submitTest, cancel } = useJobs()
  const [route, go] = useRoute()
  const [busy, setBusy] = useState(false)
  const [deckText, setDeckText] = useDeckText()
  const interests = useConstraint()
  const deck = useDeckReport(deckText, interests.asked)
  // A finished test job changes what the shelf says without anything on the shelf
  // being touched: a Gate result is matched to a saved deck by its decklist. So the
  // count of finished tests is the library's reload signal.
  const testsFinished = useMemo(
    () => jobs.filter((job) => job.kind === 'test' && job.state === 'succeeded').length,
    [jobs],
  )
  const library = useLibrary(testsFinished)

  /** Queueing anything is the one action that changes what you should look at. */
  const watch = (job: { id: string } | null) => {
    if (job) go({ view: 'farm', jobId: job.id, replay: null })
  }

  const onSubmit = async (body: {
    deck?: Deck | null
    mutations: number
    screening_duels: number
    constraint?: Constraint | null
  }) => {
    setBusy(true)
    const job = await submitRefine(body)
    setBusy(false)
    watch(job)
  }

  const onTest = async (body: {
    deck?: Deck | null
    gate_duels: number
    constraint?: Constraint | null
  }) => {
    setBusy(true)
    const job = await submitTest(body)
    setBusy(false)
    watch(job)
  }

  /** Open a saved version in the editor. The text stays the deck's definition. */
  const loadVersion = (version: DeckVersion) => {
    setDeckText(toYdk(version.main, version.extra))
    go({ view: 'deck' })
  }

  const pick = (side: 'left' | 'right', ref: DeckRef | null) => {
    go({ [side]: ref === null ? null : formatRef(ref) })
  }

  return (
    <Shell
      health={health}
      offline={offline}
      view={route.view}
      onNavigate={(view) => go({ view })}
    >
      {route.view === 'deck' && (
        <DeckEditor
          text={deckText}
          setText={setDeckText}
          report={deck.report}
          pending={deck.pending}
          parseError={deck.error}
          health={health}
          interests={interests}
          library={library}
          onSubmit={onSubmit}
          onTest={onTest}
          busy={busy}
          submitError={error}
        />
      )}

      {route.view === 'farm' && (
        <DuelFarm
          jobs={jobs}
          selectedId={route.jobId}
          onSelect={(id) => go({ jobId: id, replay: null })}
          onCancel={cancel}
          onWatch={(jobId) => go({ view: 'replay', jobId, replay: 0 })}
          library={library}
          error={error}
        />
      )}

      {route.view === 'replay' && (
        <ReplayTheatre
          jobs={jobs}
          jobId={route.jobId}
          replayIndex={route.replay}
          onPick={(jobId, replay) => go({ view: 'replay', jobId, replay })}
        />
      )}

      {route.view === 'library' && (
        <DeckLibrary
          library={library}
          left={parseRef(route.left)}
          right={parseRef(route.right)}
          onPick={pick}
          onLoad={loadVersion}
        />
      )}
    </Shell>
  )
}
