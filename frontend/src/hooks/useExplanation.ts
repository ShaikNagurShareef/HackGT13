import { useEffect, useState } from 'react'
import type { Explanation } from '../api/schemas'

export interface ExplanationState {
  result: Explanation | null
  failed: boolean
}

/** Fetch an explanation for `key`; on failure the caller shows a local summary instead. */
export function useExplanation(key: string | null, load: () => Promise<Explanation>): ExplanationState {
  const [state, setState] = useState<ExplanationState>({ result: null, failed: false })

  useEffect(() => {
    setState({ result: null, failed: false })
    if (key == null) return
    let cancelled = false
    load()
      .then((r) => !cancelled && setState({ result: r, failed: false }))
      .catch(() => !cancelled && setState({ result: null, failed: true }))
    return () => {
      cancelled = true
    }
    // `load` closes over the same inputs that make up `key`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  return state
}
