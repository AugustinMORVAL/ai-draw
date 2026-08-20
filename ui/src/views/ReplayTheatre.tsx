import { useEffect, useMemo, useState } from 'react'
import { Swords } from 'lucide-react'
import { CardInspector } from '@/components/card/CardInspector'
import { ActionLog } from '@/components/duel/ActionLog'
import { DuelField } from '@/components/duel/DuelField'
import { LifeBars } from '@/components/duel/LifeBars'
import { ReplayControls } from '@/components/duel/ReplayControls'
import { boardAt } from '@/components/duel/board'
import {
  api,
  type Card,
  type DuelReplay,
  type DuelReplaySummary,
  type JobSummary,
} from '@/lib/api'
import { cn } from '@/lib/cn'
import { usePool } from '@/lib/usePool'

const STEP_MS = 900

/**
 * One duel's log.
 *
 * The result carries the duel it answers, so "we are looking at a different duel
 * now" is derived by comparing keys rather than tracked by clearing state. Same
 * shape as `useDeckReport`, and for the same reason: nothing on screen is ever a
 * previous request's answer wearing the current request's label.
 */
function useReplay(jobId: string | null, index: number | null) {
  const key = jobId === null || index === null ? null : `${jobId}:${index}`
  const [answer, setAnswer] = useState<{
    key: string | null
    replay: DuelReplay | null
    error: string | null
  }>({ key: null, replay: null, error: null })

  useEffect(() => {
    if (jobId === null || index === null) return
    let cancelled = false
    void (async () => {
      try {
        const found = await api.replay(jobId, index)
        if (!cancelled) {
          setAnswer({ key: `${jobId}:${index}`, replay: found, error: null })
        }
      } catch (e) {
        if (!cancelled) {
          setAnswer({
            key: `${jobId}:${index}`,
            replay: null,
            error: e instanceof Error ? e.message : String(e),
          })
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [jobId, index])

  const fresh = answer.key === key
  return { replay: fresh ? answer.replay : null, error: fresh ? answer.error : null }
}

function useReplayList(jobId: string | null) {
  const [answer, setAnswer] = useState<{
    jobId: string | null
    list: DuelReplaySummary[]
  }>({ jobId: null, list: [] })

  useEffect(() => {
    if (!jobId) return
    let cancelled = false
    void (async () => {
      try {
        const found = await api.replays(jobId)
        if (!cancelled) setAnswer({ jobId, list: found })
      } catch {
        if (!cancelled) setAnswer({ jobId, list: [] })
      }
    })()
    return () => {
      cancelled = true
    }
  }, [jobId])

  return answer.jobId === jobId ? answer.list : []
}

/**
 * Watching one duel the deck played.
 *
 * The whole surface reads from one number: which event of the log we are standing
 * on. The field, the life bars and the log are all derived from it, so there is no
 * way for them to disagree with each other.
 */
export function ReplayTheatre({
  jobs,
  jobId,
  replayIndex,
  onPick,
}: {
  jobs: JobSummary[]
  jobId: string | null
  replayIndex: number | null
  onPick: (jobId: string, replay: number | null) => void
}) {
  const { byCode } = usePool()
  // Counted by the server on the queue list, so picking a job to watch costs no
  // duel logs: the log of the duel actually opened is the only one fetched.
  const watchable = jobs.filter((job) => job.replays > 0)
  const list = useReplayList(jobId)
  const { replay, error } = useReplay(jobId, replayIndex)

  const [index, setIndex] = useState(0)
  const [requested, setRequested] = useState(false)
  const [speed, setSpeed] = useState(1)
  const [inspected, setInspected] = useState<Card | null>(null)

  // A different duel starts at its own first event, stopped.
  const key = `${jobId}:${replayIndex}`
  const [watching, setWatching] = useState(key)
  if (watching !== key) {
    setWatching(key)
    setIndex(0)
    setRequested(false)
  }

  // A fresh array every render would re-run every memo below it.
  const log = useMemo(() => replay?.log ?? [], [replay])
  const last = Math.max(0, log.length - 1)

  // Playing is derived, not stored: a duel that has reached its last event is not
  // playing, and there is nothing to switch off when it gets there.
  const playing = requested && log.length > 0 && index < last

  useEffect(() => {
    if (!playing) return
    const timer = setTimeout(
      () => setIndex((i) => Math.min(last, i + 1)),
      STEP_MS / speed,
    )
    return () => clearTimeout(timer)
  }, [playing, index, last, speed])

  const board = useMemo(() => boardAt(log, index, byCode), [log, index, byCode])

  if (watchable.length === 0) {
    return (
      <div className="flex min-h-[60svh] items-center justify-center p-6">
        <div className="max-w-md space-y-3 border border-edge bg-panel p-6 text-center">
          <Swords size={20} className="mx-auto text-faint" />
          <h2 className="font-display text-sm font-semibold tracking-[0.14em] text-fg">
            NO DUELS TO WATCH YET
          </h2>
          <p className="text-[11.5px] leading-relaxed text-muted">
            A refine job keeps a sample of the duels its final deck played. Send a deck
            to the duel farm and the kept duels turn up here when it finishes.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="grid min-h-0 gap-3 p-3 lg:h-[calc(100svh-3.5rem)] lg:grid-cols-[15rem_minmax(0,1fr)_19rem]">
      <div className="flex min-h-0 flex-col gap-3">
        <div className="flex max-h-[40%] min-h-0 shrink-0 flex-col border border-edge bg-panel">
          <header className="shrink-0 border-b border-edge-soft bg-panel-2 px-3 py-2">
            <h2 className="font-display text-xs font-semibold tracking-[0.14em] text-gold">
              KEPT DUELS
            </h2>
          </header>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {watchable.map((job) => (
              <div key={job.id}>
                <button
                  type="button"
                  onClick={() => onPick(job.id, 0)}
                  className={cn(
                    'w-full px-3 py-1.5 text-left font-mono text-[10.5px] transition-colors hover:bg-panel-2',
                    jobId === job.id ? 'text-gold' : 'text-faint',
                  )}
                >
                  {job.id}
                </button>
                {jobId === job.id && (
                  <ul className="pb-1">
                    {list.map((summary) => {
                      const won = summary.winner === 'candidate'
                      return (
                        <li key={summary.index}>
                          <button
                            type="button"
                            onClick={() => onPick(job.id, summary.index)}
                            className={cn(
                              'flex w-full items-center gap-2 border-l-2 py-1.5 pr-2 pl-3 text-left transition-colors hover:bg-panel-2',
                              replayIndex === summary.index
                                ? 'border-l-gold bg-panel-2'
                                : 'border-l-transparent',
                            )}
                          >
                            <span
                              className={cn(
                                'size-1.5 shrink-0',
                                won ? 'bg-good' : 'bg-bad',
                              )}
                            />
                            <span className="min-w-0 flex-1 truncate text-[11px] text-muted">
                              {summary.opponent}
                            </span>
                            <span className="shrink-0 font-mono text-[9.5px] tabular text-faint">
                              {summary.turns}T
                            </span>
                          </button>
                        </li>
                      )
                    })}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </div>

        <CardInspector
          card={inspected}
          className={inspected ? "min-h-0 flex-1" : "shrink-0"}
        />
      </div>

      <div className="flex min-h-0 flex-col gap-3 overflow-y-auto">
        {error && (
          <p className="border-l-2 border-l-bad bg-bad/8 px-3 py-2 font-mono text-[11px] text-bad">
            {error}
          </p>
        )}

        {!replay ? (
          <div className="flex flex-1 items-center justify-center border border-edge bg-panel p-10">
            <p className="text-center text-xs text-faint">
              {jobId ? 'Pick a duel on the left.' : 'Pick a job on the left.'}
            </p>
          </div>
        ) : (
          <>
            <LifeBars
              candidateLife={board.candidate.life}
              opponentLife={board.opponent.life}
              opponentName={replay.opponent.toUpperCase()}
              goingFirst={replay.going_first}
              winner={replay.winner}
              finished={index >= last}
            />

            <DuelField
              board={board}
              byCode={byCode}
              onInspect={setInspected}
              lastEvent={index}
            />

            <ReplayControls
              index={index}
              total={log.length}
              playing={playing}
              speed={speed}
              onSeek={(next) => {
                setRequested(false)
                setIndex(next)
              }}
              onTogglePlay={() => {
                // Pressing play on a finished duel watches it again.
                if (index >= last) setIndex(0)
                setRequested((on) => (index >= last ? true : !on))
              }}
              onSpeed={setSpeed}
            />

            {!replay.live && (
              <p className="border-l-2 border-l-warn bg-warn/8 px-3 py-2 text-[11px] leading-relaxed text-warn">
                This duel did not happen. The fake executor wrote the log from the
                deck's own cards so the viewer has something real to render, and the
                board below is that log drawn out. Real logs arrive with the ygoenv
                executor.
              </p>
            )}
          </>
        )}
      </div>

      <div className="min-h-0">
        {replay && (
          <ActionLog
            log={log}
            index={index}
            byCode={byCode}
            onSeek={(next) => {
              setRequested(false)
              setIndex(next)
            }}
          />
        )}
      </div>
    </div>
  )
}
