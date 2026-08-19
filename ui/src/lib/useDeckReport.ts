import { useEffect, useState } from 'react'
import { api, type Constraint, type DeckReport } from '@/lib/api'

const DEBOUNCE_MS = 300

interface Parsed {
  text: string
  /** The Constraint the report was judged against, as JSON, or null for none. */
  asked: string | null
  report: DeckReport | null
  error: string | null
}

const NOTHING: Parsed = { text: '', asked: null, report: null, error: null }

/**
 * Parses the paste box server-side, debounced.
 *
 * Legality lives on the server and only on the server: the same rules gate the job
 * queue, and a second copy here would be a second answer to "is this deck legal?".
 *
 * The result carries the text it was parsed from, so "still typing" is derived by
 * comparing it with the current text rather than tracked as its own state.
 *
 * The Constraint goes with it. Conformance is judged next to legality by the same
 * server call, so editing an interest re-reads the deck rather than leaving a stale
 * verdict beside a changed question.
 */
export function useDeckReport(text: string, constraint: Constraint | null = null) {
  const [parsed, setParsed] = useState<Parsed>(NOTHING)
  const trimmed = text.trim()
  // JSON, so the effect keys on the Constraint's value rather than its identity:
  // the form hands over a fresh object on every keystroke.
  const asked = constraint === null ? null : JSON.stringify(constraint)

  useEffect(() => {
    if (!trimmed) return
    let cancelled = false
    const timer = setTimeout(async () => {
      try {
        const report = await api.parseDeck(
          text,
          asked === null ? null : (JSON.parse(asked) as Constraint),
        )
        if (!cancelled) setParsed({ text, asked, report, error: null })
      } catch (e) {
        if (!cancelled) {
          setParsed({
            text,
            asked,
            report: null,
            error: e instanceof Error ? e.message : String(e),
          })
        }
      }
    }, DEBOUNCE_MS)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [text, trimmed, asked])

  if (!trimmed) return { report: null, pending: false, error: null }
  const fresh = parsed.text === text && parsed.asked === asked
  return {
    // The previous report stays on screen while the next one is in flight, dimmed,
    // so the panel does not blank out on every keystroke.
    report: parsed.report,
    pending: !fresh,
    error: fresh ? parsed.error : null,
  }
}
