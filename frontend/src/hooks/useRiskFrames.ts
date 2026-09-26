import { useEffect, useState } from 'react'
import type { Cond, FrameSet } from '../frames/frameStore'
import type { DayGroup } from '../lib/time'
import { useLatest } from './useLatest'

export interface FrameSource {
  get: (day: DayGroup, cond: Cond) => Promise<FrameSet>
  prefetch: (day: DayGroup) => void
}

/**
 * Risk Tides (or City Pulse) frames for a day group and condition. Frames from a previous store
 * (the walk network, before switching to the ride network) are never returned for the new one.
 */
export function useRiskFrames(
  store: FrameSource | null,
  day: DayGroup,
  cond: Cond,
  enabled: boolean,
  onError: (message: string) => void,
  errorMessage: string,
): FrameSet | null {
  const [loaded, setLoaded] = useState<{ store: FrameSource; frames: FrameSet } | null>(null)
  const latest = useLatest({ onError, errorMessage })

  useEffect(() => {
    if (!store || !enabled) return
    let cancelled = false
    store.prefetch(day)
    store
      .get(day, cond)
      .then((frames) => !cancelled && setLoaded({ store, frames }))
      .catch(() => !cancelled && latest.current.onError(latest.current.errorMessage))
    return () => {
      cancelled = true
    }
  }, [store, day, cond, enabled, latest])

  return loaded != null && loaded.store === store ? loaded.frames : null
}
