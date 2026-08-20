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
  /** Only when a Constraint was sent. Judged beside legality, never inside it. */
  constraint: ConstraintReport | null
  main_count: number
  extra_count: number
}

export type ConstraintFacet = 'race' | 'attribute' | 'kind' | 'subtype'

export type Bound = 'at_least' | 'at_most'

export interface ConstraintClause {
  facet: ConstraintFacet
  value: string
  bound: Bound
  count: number
}

/**
 * What the user asked for, and may drop. Legality is neither.
 *
 * `main_size` is null when the user set no card-count cap: legality's 40-to-60
 * still holds, and a 42-card deck is not flagged for being 42.
 */
export interface Constraint {
  main_size: number | null
  clauses: ConstraintClause[]
}

export type ConstraintIssue =
  | 'impossible'
  | 'unmet_minimum'
  | 'over_maximum'
  | 'wrong_size'

export interface ConstraintFlag {
  issue: ConstraintIssue
  reason: string
  clause: ConstraintClause | null
}

export interface ClauseStatus {
  clause: ConstraintClause
  held: number
  satisfied: boolean
  /** The most copies the pool could ever supply. A floor above it is impossible. */
  ceiling: number
}

export interface ConstraintReport {
  constraint: Constraint
  /** False when no legal deck satisfies it — the pool's limit, not the deck's. */
  feasible: boolean
  satisfied: boolean
  clauses: ClauseStatus[]
  flags: ConstraintFlag[]
}

export interface FacetValue {
  facet: ConstraintFacet
  value: string
  cards: number
  copies: number
  /** Pool cards with this value that no main deck may hold: Tokens, Extra Deck. */
  elsewhere: number
}

export interface Facets {
  main_deck_pool_size: number
  values: FacetValue[]
}

export interface Swap {
  step: number
  card_out: number
  card_in: number
  win_rate: number
  delta: number
  accepted: boolean
}

export interface DeckChange {
  card: number
  count: number
}

/**
 * What a job changed, counted as cards rather than as mutations.
 *
 * The swap log says what was *tried*; this says what *landed*. A card cut at step
 * 3 and picked back up at step 17 is two swaps and no change.
 */
export interface DeckDiff {
  added: DeckChange[]
  removed: DeckChange[]
  /** Copies both decks hold. With `added` it accounts for the whole final deck. */
  unchanged: number
}

export interface RefineResult {
  deck: Deck
  /** The deck that was submitted, so "changed from what?" has an answer here. */
  starting_deck: Deck
  diff: DeckDiff
  swaps: Swap[]
  accepted: number
  win_rate: number
  fidelity: Fidelity
  live: boolean
  /** One duel against each Gauntlet deck, kept from the final deck's. Summaries:
      the job endpoint strips the logs, and `api.replay` fetches one. */
  replays: DuelReplaySummary[]
}

/**
 * One Gauntlet opponent's share of a Gate evaluation.
 *
 * `duels` rides on every row because it is what says how much the row is worth:
 * ten fixed opponents means a 500-duel evaluation is fifty duels each, and fifty
 * duels carries a ±14 point band. Read the ordering, not the digits.
 */
export interface Matchup {
  opponent: string
  duels: number
  wins: number
  win_rate: number
  /** The same duels, split by seat: ADR-0004 forces the 50/50. */
  first_duels: number
  first_wins: number
  /** This row's 95% band, computed server-side so one formula exists. */
  margin: number
}

/**
 * What a test job answers with: the one win rate in this app that may be quoted.
 *
 * `win_rate` is summed out of `matchups`, not carried beside them, so the headline
 * can never disagree with the breakdown underneath it.
 */
export interface GateResult {
  deck: Deck
  win_rate: number
  duels: number
  fidelity: Fidelity
  matchups: Matchup[]
  /** The 95% band on the headline. Quoting the number means quoting this. */
  margin: number
  live: boolean
  /** One duel per matchup row, so every row in the breakdown can be opened. */
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

/**
 * A Gate result the library found by matching decklists, not by a pointer.
 *
 * A pointer would have to be written when the job was submitted, so a deck saved
 * after its own test would have no result. The link is the decklist itself.
 */
export interface GateSnapshot {
  job_id: string
  win_rate: number
  duels: number
  fidelity: Fidelity
  /** Whether real duels produced it. A fake number and a real one never compare. */
  live: boolean
  finished_at: number
  margin: number
}

/**
 * One saved decklist, immutable once written.
 *
 * Two content addresses, two questions. `fingerprint` covers the whole list and
 * decides whether a save is a new version at all; `main_key` covers the main deck
 * alone and is what a Gate result is matched on, because a job carries a main deck
 * and nothing else.
 */
export interface DeckVersion {
  version: number
  fingerprint: string
  main_key: string
  main: number[]
  extra: number[]
  note: string | null
  created_at: number
  /** The last Gate evaluation of this main deck, if any deck ever was. */
  gate: GateSnapshot | null
  main_count: number
  extra_count: number
}

export interface LibraryDeck {
  id: string
  name: string
  created_at: number
  /** Newest first. */
  versions: DeckVersion[]
}

export interface DeckSaved {
  deck: LibraryDeck
  version: number
  /** False when the list was identical to the version already on the shelf. */
  created: boolean
  reason: string
}

export interface DeckRef {
  deck_id: string
  version: number
}

export interface ComparisonSide {
  deck_id: string
  name: string
  version: DeckVersion
}

/**
 * Two Gate win rates, and whether they tell the two decks apart.
 *
 * Not a Delta score: that is a win rate difference between a deck and its own
 * mutation under one Environment set. These are two separate jobs, so the bands
 * add, and `separated` is the honest verdict on the difference.
 */
export interface GateComparison {
  difference: number
  margin: number
  separated: boolean
  reason: string
}

export interface DeckComparison {
  left: ComparisonSide
  right: ComparisonSide
  /** Main deck, left to right. Drawn by the same code as a refine job's diff. */
  diff: DeckDiff
  extra_diff: DeckDiff
  gate: GateComparison | null
  /** Always said, including when there is no comparison — especially then. */
  gate_note: string
}

export interface Progress {
  step: number
  total: number
  message: string
}

/**
 * How far a running job has got, as the worker last wrote it.
 *
 * Written after every mutation, so the swap log on screen is the log the worker
 * has actually made — it builds up as the job runs instead of arriving whole at
 * the end. It is also what the worker resumes from after a restart, which is why
 * there is only one of these and not a progress shape and a recovery shape.
 */
export interface RefineCheckpoint {
  step: number
  total: number
  deck: Deck
  win_rate: number
  swaps: Swap[]
  diff: DeckDiff
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
  params: {
    deck?: Deck
    mutations?: number
    screening_duels?: number
    /** Test jobs only. Never below 500: that is ADR-0003's floor for a Gate. */
    gate_duels?: number
    constraint?: Constraint | null
  }
  /** Shaped by `kind`: a refine job returns swaps, a test job returns matchups. */
  result: RefineResult | GateResult | null
  /** Null once a result replaces it, and on a job that never started one. */
  checkpoint: RefineCheckpoint | null
  error: string | null
}

/**
 * A job as the queue list shows it: where it stands, and nothing it carries.
 *
 * The list is polled while a job runs, so it says how far each job got and
 * `api.job(id)` says what it did. Neither carries a duel log: `api.job(id)` names
 * the duels a job kept and `api.replay(id, i)` is the one way to read one.
 */
export interface JobSummary {
  id: string
  kind: 'refine' | 'test'
  state: JobState
  created_at: number
  started_at: number | null
  finished_at: number | null
  queue_position: number | null
  progress: Progress
  error: string | null
  /** How many kept duels its result carries. Counted server-side. */
  replays: number
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

/**
 * A refusal from the API, with the body it refused with.
 *
 * Both refusals this app makes on purpose — an illegal deck, an unsatisfiable
 * Constraint — answer 422 with the same report the screen was already showing. So
 * the parsed `detail` is kept beside the message: the caller can render the
 * reasons where the user was reading rather than a wall of JSON.
 */
export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(status: number, message: string, detail: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { 'content-type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    let detail: unknown = null
    try {
      detail = (JSON.parse(body) as { detail?: unknown }).detail ?? null
    } catch {
      detail = null
    }
    throw new ApiError(
      res.status,
      `${res.status} ${res.statusText}${body ? `: ${body}` : ''}`,
      detail,
    )
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<Health>('/health'),
  /** All 864 at once. The pool never changes at runtime, so the editor holds it. */
  pool: () => request<Card[]>('/pool'),
  jobs: () => request<JobSummary[]>('/jobs'),
  job: (id: string) => request<Job>(`/jobs/${id}`),
  /** Every value a Constraint may name, with the ceiling the pool sets on it. */
  facets: () => request<Facets>('/constraints/facets'),
  submitRefine: (body: {
    deck?: Deck | null
    mutations: number
    screening_duels: number
    constraint?: Constraint | null
  }) => request<Job>('/jobs/refine', { method: 'POST', body: JSON.stringify(body) }),
  /** Gate-evaluate a deck against the Gauntlet. 500 duels is the floor, not a default. */
  submitTest: (body: {
    deck?: Deck | null
    gate_duels: number
    constraint?: Constraint | null
  }) => request<Job>('/jobs/test', { method: 'POST', body: JSON.stringify(body) }),
  searchCards: (q: string, limit = 12) =>
    request<Card[]>(`/cards?q=${encodeURIComponent(q)}&limit=${limit}`),
  parseDeck: (text: string, constraint?: Constraint | null) =>
    request<DeckReport>('/decks/parse', {
      method: 'POST',
      body: JSON.stringify({ text, constraint: constraint ?? null }),
    }),
  /** Build a deck under a Constraint. Comes back as a full report, like a paste. */
  buildDeck: (constraint: Constraint, seed?: number | null) =>
    request<DeckReport>('/decks/build', {
      method: 'POST',
      body: JSON.stringify({ constraint, seed: seed ?? null }),
    }),
  cancel: (id: string) => request<Job>(`/jobs/${id}/cancel`, { method: 'POST' }),
  /** Every saved deck and every version, with the Gate result each one carries. */
  library: () => request<LibraryDeck[]>('/library'),
  /** Save under a name. The name is the identity: an existing one gets a version. */
  saveDeck: (body: {
    name: string
    main: number[]
    extra: number[]
    note?: string | null
  }) =>
    request<DeckSaved>('/library/decks', {
      method: 'POST',
      body: JSON.stringify({ ...body, note: body.note ?? null }),
    }),
  deleteDeck: (id: string) =>
    request<void>(`/library/decks/${id}`, { method: 'DELETE' }),
  /** The diff and the Gate verdict, both answered server-side so one exists. */
  compareDecks: (left: DeckRef, right: DeckRef) =>
    request<DeckComparison>('/library/compare', {
      method: 'POST',
      body: JSON.stringify({ left, right }),
    }),

  replays: (jobId: string) => request<DuelReplaySummary[]>(`/jobs/${jobId}/replays`),
  replay: (jobId: string, index: number) =>
    request<DuelReplay>(`/jobs/${jobId}/replays/${index}`),
}
