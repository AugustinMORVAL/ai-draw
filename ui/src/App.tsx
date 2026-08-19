import { useEffect, useState } from 'react'
import { Shell } from '@/components/chrome/Shell'
import type { Deck } from '@/lib/api'
import { useDeckReport } from '@/lib/useDeckReport'
import { useJobs } from '@/lib/useJobs'
import { useRoute } from '@/lib/useRoute'
import { DeckEditor, SEED } from '@/views/DeckEditor'
import { DuelFarm } from '@/views/DuelFarm'
import { ReplayTheatre } from '@/views/ReplayTheatre'

const DECK_KEY = 'ai-draw.deck'

/**
 * The deck in progress, kept across reloads.
 *
 * Jobs are durable because the database holds them; a deck someone is part-way
 * through building is not a job yet and has nowhere else to live. Losing forty
 * card picks to a refresh is the one failure this app can trivially avoid.
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
  const { jobs, health, offline, error, submitRefine, cancel } = useJobs()
  const [route, go] = useRoute()
  const [busy, setBusy] = useState(false)
  const [deckText, setDeckText] = useDeckText()
  const deck = useDeckReport(deckText)

  const onSubmit = async (body: {
    deck?: Deck | null
    mutations: number
    screening_duels: number
  }) => {
    setBusy(true)
    const job = await submitRefine(body)
    setBusy(false)
    // Submitting is the one action that changes what you should be looking at.
    if (job) go({ view: 'farm', jobId: job.id, replay: null })
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
          onSubmit={onSubmit}
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
    </Shell>
  )
}
