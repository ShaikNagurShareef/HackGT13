import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import { isDemoMode } from '../api/demo'
import { prefetchClips, type AlertKind } from '../lib/alertClips'

export interface AlertClipsInput {
  routeKey: string | null | undefined
  kind: AlertKind
  /** Number of alert stretches on the followed route. */
  count: number
  /** Navigation (or its preview) is running: the first start fetches the clips. */
  active: boolean
}

/**
 * Grok Voice clips for a route's alerts, fetched once when navigation first starts on that route
 * and kept as Blob URLs until the route changes or the component unmounts (then revoked).
 * Returns a lookup: the clip URL for an alert index, or null so the device voice speaks it.
 * Demo mode never fetches.
 */
export function useAlertClips({ routeKey, kind, count, active }: AlertClipsInput): (index: number) => string | null {
  const clips = useRef<ReadonlyMap<number, string>>(new Map())
  const target = routeKey && count > 0 ? `${routeKey}:${kind}:${count}` : null
  const [armed, setArmed] = useState<string | null>(null)
  // Arming is sticky per route so ending and restarting navigation does not fetch again.
  // Adjusting state during render (not in an effect) is React's pattern for this.
  if (active && target && armed !== target && !isDemoMode()) setArmed(target)

  useEffect(() => {
    if (!routeKey || armed !== target) return
    const controller = new AbortController()
    const urls = new Map<number, string>()
    clips.current = urls
    void prefetchClips(
      count,
      (index, signal) => api.ttsAlert(routeKey, index, kind, signal),
      controller.signal,
      (index, clip) => urls.set(index, URL.createObjectURL(clip)),
    )
    return () => {
      controller.abort()
      urls.forEach((url) => URL.revokeObjectURL(url))
      if (clips.current === urls) clips.current = new Map()
    }
  }, [armed, target, routeKey, kind, count])

  return useCallback((index: number) => clips.current.get(index) ?? null, [])
}
