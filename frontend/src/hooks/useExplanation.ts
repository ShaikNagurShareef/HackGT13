import { useEffect, useState } from 'react'
import type { Explanation } from '../api/schemas'

/** Fetch an explanation for `key`; null while loading, or if the request fails (template shows). */
export function useExplanation(key: string | null, load: () => Promise<Explanation>): Explanation | null {
  const [result, setResult] = useState<Explanation | null>(null)

  useEffect(() => {
    setResult(null)
    if (key == null) return
    let cancelled = false
    load()
      .then((r) => !cancelled && setResult(r))
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
    // `load` closes over the same inputs that make up `key`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  return result
}
