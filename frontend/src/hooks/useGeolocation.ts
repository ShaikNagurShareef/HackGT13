import { useCallback, useEffect, useRef, useState } from 'react'
import type { GeoFix, GeoStatus } from '../lib/origin'

export interface Geolocation {
  status: GeoStatus
  position: GeoFix | null
  error: string | null
  /** Ask for location (shows the browser prompt the first time). Call only from a user gesture. */
  request: () => void
}

interface GeoState {
  status: GeoStatus
  position: GeoFix | null
  error: string | null
}

const WATCH_OPTIONS: PositionOptions = { enableHighAccuracy: true, maximumAge: 5_000, timeout: 15_000 }
const PERMISSION_DENIED = 1
const POSITION_UNAVAILABLE = 2
const TIMEOUT_MESSAGE = 'Still looking for a GPS signal…'
const UNAVAILABLE_MESSAGE = "Your location isn't available right now."

function geolocationApi(): globalThis.Geolocation | undefined {
  return typeof navigator === 'undefined' ? undefined : navigator.geolocation
}

function toFix(p: GeolocationPosition): GeoFix {
  const { latitude, longitude, accuracy, heading } = p.coords
  return {
    lat: latitude,
    lon: longitude,
    accuracy,
    heading: heading == null || Number.isNaN(heading) ? null : heading,
    at: p.timestamp,
  }
}

/**
 * Watches the device position. Never prompts on its own: it only starts watching after
 * `request()` (a user tap) or when the browser reports permission was already granted.
 */
export function useGeolocation(): Geolocation {
  const [state, setState] = useState<GeoState>(() => ({
    status: geolocationApi() ? 'prompt' : 'unavailable',
    position: null,
    error: null,
  }))
  const watchId = useRef<number | null>(null)

  const stopWatching = useCallback(() => {
    if (watchId.current != null) geolocationApi()?.clearWatch(watchId.current)
    watchId.current = null
  }, [])

  const request = useCallback(() => {
    const geo = geolocationApi()
    if (!geo || watchId.current != null) return
    setState((s) => (s.position ? s : { ...s, status: 'locating', error: null }))
    watchId.current = geo.watchPosition(
      (p) => setState({ status: 'granted', position: toFix(p), error: null }),
      (e) => {
        if (e.code === PERMISSION_DENIED) {
          stopWatching()
          setState((s) => ({ ...s, status: 'denied', error: null }))
          return
        }
        // Signal loss and timeouts are transient (tunnels, trees, emulator jumps): keep watching,
        // keep the last fix, and say what's happening.
        const message = e.code === POSITION_UNAVAILABLE ? UNAVAILABLE_MESSAGE : TIMEOUT_MESSAGE
        const lost = e.code === POSITION_UNAVAILABLE
        setState((s) => ({ ...s, status: s.position || !lost ? s.status : 'unavailable', error: message }))
      },
      WATCH_OPTIONS,
    )
  }, [stopWatching])

  useEffect(() => {
    if (!geolocationApi()) return
    let cancelled = false
    navigator.permissions
      ?.query({ name: 'geolocation' })
      .then((p) => {
        if (cancelled) return
        if (p.state === 'granted') request()
        else if (p.state === 'denied') setState((s) => ({ ...s, status: 'denied' }))
      })
      .catch(() => {
        // Permissions API unsupported (older Safari): stay in 'prompt' until the user taps locate.
      })
    return () => {
      cancelled = true
      stopWatching()
    }
  }, [request, stopWatching])

  return { ...state, request }
}
