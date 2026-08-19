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
  jobs: () => request<Job[]>('/jobs'),
  job: (id: string) => request<Job>(`/jobs/${id}`),
  submitRefine: (body: { mutations: number; screening_duels: number }) =>
    request<Job>('/jobs/refine', { method: 'POST', body: JSON.stringify(body) }),
  cancel: (id: string) => request<Job>(`/jobs/${id}/cancel`, { method: 'POST' }),
}
