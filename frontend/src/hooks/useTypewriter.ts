import { useEffect, useState } from 'react'

const CHARS_PER_TICK = 3
const TICK_MS = 16

/** Reveal validated text progressively (GEN-05) — instant under reduced motion. */
export function useTypewriter(text: string | null): string | null {
  const [shown, setShown] = useState<string | null>(text)

  useEffect(() => {
    if (text == null) {
      setShown(null)
      return
    }
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (reduced) {
      setShown(text)
      return
    }
    let i = 0
    setShown('')
    const id = window.setInterval(() => {
      i += CHARS_PER_TICK
      setShown(text.slice(0, i))
      if (i >= text.length) window.clearInterval(id)
    }, TICK_MS)
    return () => window.clearInterval(id)
  }, [text])

  return shown
}
