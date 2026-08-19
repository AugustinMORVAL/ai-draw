/** Typed client for the ai-draw API. Mirrors `api/src/ai_draw_api/models.py`. */

export type JobState =
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'cancelled'

export type Fidelity = 'screening' | 'gate'

export interface Deck {
  main: number[]
}

export type CardSection = 'main' | 'extra' | 'token'

export interface Card {
  code: number
  name: string
  kind: string
  subtypes: string[]
  section: CardSection
  race: string | null
  attribute: string | null
  level: number | null
  atk: number | null
  defense: number | null
  limit: number
  /** Stated by the server, never inferred here: can the frozen Pilot represent it? */
  in_pool: boolean
  /** The printed card text. Pool cards only, so the inspector can read it out. */
  desc: string | null
}

export type CardIssue =
  | 'unknown_card'
  | 'not_in_pool'
  | 'forbidden'
  | 'over_limit'
  | 'token'
  | 'wrong_section'

export type DeckIssue =
  | 'main_too_small'
  | 'main_too_large'
  | 'extra_too_large'
  | 'nothing_parsed'

export interface CardFlag {
  code: number
  name: string | null
  count: number
  section: CardSection
  issue: CardIssue
  reason: string
  limit: number | null
}

export interface DeckFlag {
  issue: DeckIssue
  reason: string
}

export interface UnresolvedLine {
  line: number
  text: string
  reason: string
}

export interface DeckEntry {
  card: Card
  count: number
  section: CardSection
}

export interface MaskPreview {
  pool_size: number
  legal_picks: number
  masked: { reason: string; count: number }[]
}

export interface DeckReport {
  deck: Deck | null
  extra: number[]
  legal: boolean
  banlist: string
  entries: DeckEntry[]
  flags: CardFlag[]
  deck_flags: DeckFlag[]
  unresolved: UnresolvedLine[]
  mask: MaskPreview
  main_count: number
  extra_count: number
}

export interface Swap {
  step: number
  card_out: number
  card_in: number
  win_rate: number
  delta: number
  accepted: boolean
}

export interface RefineResult {
  deck: Deck
  swaps: Swap[]
  accepted: number
  win_rate: number
  fidelity: Fidelity
  live: boolean
  /** A sample of the final deck's duels, not all of them. */
  replays: DuelReplaySummary[]
}

export type DuelSeat = 'candidate' | 'opponent'

export type DuelPhase = 'draw' | 'standby' | 'main1' | 'battle' | 'main2' | 'end'

export interface DuelEvent {
  index: number
  turn: number
  seat: DuelSeat
  phase: DuelPhase
  action: string
  card: number | null
  target: number | null
  text: string
  /** Life totals *after* this event, so scrubbing never has to replay from zero. */
  life_candidate: number
  life_opponent: number
}

export interface DuelReplaySummary {
  index: number
  opponent: string
  going_first: DuelSeat
  winner: DuelSeat
  turns: number
  events: number
  /** False means the fake executor wrote this log and no duel happened. */
  live: boolean
}

export interface DuelReplay extends DuelReplaySummary {
  log: DuelEvent[]
}

export interface Progress {
  step: number
  total: number
  message: string
}

export interface Job {
  id: string
  kind: 'refine' | 'test'
  state: JobState
  created_at: number
  started_at: number | null
  finished_at: number | null
  queue_position: number | null
  progress: Progress
  params: { deck?: Deck; mutations?: number; screening_duels?: number }
  result: RefineResult | null
  error: string | null
}

export interface Health {
  status: string
  live: boolean
  executor: string
  pool_size: number
  main_deck_pool_size: number
  banlist: string
  version: string
}

export const TERMINAL: JobState[] = ['succeeded', 'failed', 'cancelled']

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { 'content-type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(`${res.status} ${res.statusText}${detail ? `: ${detail}` : ''}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<Health>('/health'),
  /** All 864 at once. The pool never changes at runtime, so the editor holds it. */
  pool: () => request<Card[]>('/pool'),
  jobs: () => request<Job[]>('/jobs'),
  job: (id: string) => request<Job>(`/jobs/${id}`),
  submitRefine: (body: {
    deck?: Deck | null
    mutations: number
    screening_duels: number
  }) => request<Job>('/jobs/refine', { method: 'POST', body: JSON.stringify(body) }),
  searchCards: (q: string, limit = 12) =>
    request<Card[]>(`/cards?q=${encodeURIComponent(q)}&limit=${limit}`),
  parseDeck: (text: string) =>
    request<DeckReport>('/decks/parse', {
      method: 'POST',
      body: JSON.stringify({ text }),
    }),
  cancel: (id: string) => request<Job>(`/jobs/${id}/cancel`, { method: 'POST' }),
  replays: (jobId: string) => request<DuelReplaySummary[]>(`/jobs/${jobId}/replays`),
  replay: (jobId: string, index: number) =>
    request<DuelReplay>(`/jobs/${jobId}/replays/${index}`),
}
