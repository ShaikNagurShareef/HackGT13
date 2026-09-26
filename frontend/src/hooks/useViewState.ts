import { useCallback, useEffect, useState } from 'react'
import { parseState, serializeState, type ViewState } from '../state/urlState'

/** View state mirrored into the URL so every view is shareable and refresh-safe. */
export function useViewState(): [ViewState, (patch: Partial<ViewState>) => void] {
  const [state, setState] = useState<ViewState>(() => parseState(window.location.search))

  useEffect(() => {
    const next = `${window.location.pathname}${serializeState(state)}`
    if (next !== `${window.location.pathname}${window.location.search}`) {
      window.history.replaceState(null, '', next)
    }
  }, [state])

  const update = useCallback((patch: Partial<ViewState>) => setState((s) => ({ ...s, ...patch })), [])
  return [state, update]
}
