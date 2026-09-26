import { useEffect, useRef, useState } from 'react'
import { ApiError, api, type Condition } from '../api/client'
import type { Route, Routes, TravelMode } from '../api/schemas'
import { DEFAULT_PREFERENCE, type RoutePreference } from '../api/safetySchemas'
import { TRAVEL_MODES } from '../lib/modes'
import type { Place } from '../state/urlState'
import { useLatest } from './useLatest'

export interface TripQuery {
  from: Place | null
  to: Place | null
  depart: string
  cond: Condition
  prefer?: RoutePreference
  mode?: TravelMode
}

export interface RouteHandlers {
  onError: (message: string | null) => void
  /** Destination outside street routing: the caller can show an area score instead (CITY-03). */
  onOutside: (to: Place) => void
  onLoaded: (routes: Routes) => void
  /** The server has no routing for this ride mode here: the caller falls back to Walk. */
  onModeUnavailable?: (mode: TravelMode) => void
}

export interface RoutesResult {
  routes: Routes | null
  loading: boolean
  /** Headline duration (seconds) per mode already routed for this trip, for the mode tabs. */
  durations: Partial<Record<TravelMode, number>>
}

interface RouteState {
  results: Readonly<Record<string, Routes>>
  failedKey: string | null
}

/** Switching modes back and forth reuses these; older trips fall out first. */
const MAX_CACHED = 8

function tripKey(q: TripQuery, mode: TravelMode = q.mode ?? 'walk'): string | null {
  if (!q.from || !q.to) return null
  // The preference applies to walks only, so rides share one key whatever it is.
  const prefer = mode === 'walk' ? (q.prefer ?? DEFAULT_PREFERENCE) : DEFAULT_PREFERENCE
  return [q.from.lat, q.from.lon, q.to.lat, q.to.lon, q.depart, q.cond, prefer, mode].join('|')
}

function headline(r: Routes): Route {
  return r.pathpro ?? r.fastest
}

function remember(results: Readonly<Record<string, Routes>>, key: string, routes: Routes): Record<string, Routes> {
  const kept = Object.entries(results).filter(([k]) => k !== key).slice(-(MAX_CACHED - 1))
  return { ...Object.fromEntries(kept), [key]: routes }
}

/** Fetches the fastest + PathPro routes for the current trip and mode; never shows a previous trip's routes. */
export function useRoutes(query: TripQuery, handlers: RouteHandlers): RoutesResult {
  const [state, setState] = useState<RouteState>({ results: {}, failedKey: null })
  const cache = useRef(state.results)
  const latest = useLatest(handlers)
  const { from, to, depart, cond } = query
  const prefer = query.prefer ?? DEFAULT_PREFERENCE
  const mode = query.mode ?? 'walk'
  const key = tripKey(query)

  useEffect(() => {
    if (!from || !to) return
    const requestKey = tripKey({ from, to, depart, cond, prefer, mode })
    if (requestKey == null) return
    const cached = cache.current[requestKey]
    if (cached) {
      latest.current.onLoaded(cached)
      return
    }
    let cancelled = false
    latest.current.onError(null)
    api
      .routes(from, to, depart, cond, prefer, mode)
      .then((r) => {
        if (cancelled) return
        const results = remember(cache.current, requestKey, r)
        cache.current = results
        setState((s) => ({ results, failedKey: s.failedKey === requestKey ? null : s.failedKey }))
        latest.current.onLoaded(r)
      })
      .catch((e: unknown) => {
        if (cancelled) return
        setState((s) => ({ ...s, failedKey: requestKey }))
        const code = e instanceof ApiError ? e.code : null
        if (code === 'MODE_UNAVAILABLE' && mode !== 'walk' && latest.current.onModeUnavailable) {
          latest.current.onModeUnavailable(mode)
          return
        }
        latest.current.onError(e instanceof ApiError ? e.message : 'Could not compute routes.')
        if (code === 'OUT_OF_COVERAGE') latest.current.onOutside(to)
      })
    return () => {
      cancelled = true
    }
  }, [from, to, depart, cond, prefer, mode, latest])

  const routes = key != null ? (state.results[key] ?? null) : null
  const durations: Partial<Record<TravelMode, number>> = Object.fromEntries(
    TRAVEL_MODES.flatMap((m) => {
      const k = tripKey(query, m)
      const found = k != null ? state.results[k] : undefined
      return found ? [[m, headline(found).duration_s]] : []
    }),
  )
  return { routes, loading: key != null && routes == null && state.failedKey !== key, durations }
}
