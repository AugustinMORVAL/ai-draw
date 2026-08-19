import { useEffect, useState } from 'react'
import { api, type DeckReport } from '@/lib/api'

const DEBOUNCE_MS = 300

interface Parsed {
  text: string
  report: DeckReport | null
  error: string | null
}

const NOTHING: Parsed = { text: '', report: null, error: null }

/**
 * Parses the paste box server-side, debounced.
 *
 * Legality lives on the server and only on the server: the same rules gate the job
 * queue, and a second copy here would be a second answer to "is this deck legal?".
 *
 * The result carries the text it was parsed from, so "still typing" is derived by
 * comparing it with the current text rather than tracked as its own state.
 */
export function useDeckReport(text: string) {
  const [parsed, setParsed] = useState<Parsed>(NOTHING)
  const trimmed = text.trim()

  useEffect(() => {
    if (!trimmed) return
    let cancelled = false
    const timer = setTimeout(async () => {
      try {
        const report = await api.parseDeck(text)
        if (!cancelled) setParsed({ text, report, error: null })
      } catch (e) {
        if (!cancelled) {
          setParsed({
            text,
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
  }, [text, trimmed])

  if (!trimmed) return { report: null, pending: false, error: null }
  const fresh = parsed.text === text
  return {
    // The previous report stays on screen while the next one is in flight, dimmed,
    // so the panel does not blank out on every keystroke.
    report: parsed.report,
    pending: !fresh,
    error: fresh ? parsed.error : null,
  }
}
