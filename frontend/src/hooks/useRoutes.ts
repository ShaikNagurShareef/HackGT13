import { useEffect, useState } from 'react'
import { ApiError, api, type Condition } from '../api/client'
import type { Routes } from '../api/schemas'
import type { Place } from '../state/urlState'
import { useLatest } from './useLatest'

export interface TripQuery {
  from: Place | null
  to: Place | null
  depart: string
  cond: Condition
}

export interface RouteHandlers {
  onError: (message: string | null) => void
  /** Destination outside street routing: the caller can show an area score instead (CITY-03). */
  onOutside: (to: Place) => void
  onLoaded: (routes: Routes) => void
}

interface RouteState {
  key: string | null
  routes: Routes | null
  failed: boolean
}

function tripKey(q: TripQuery): string | null {
  if (!q.from || !q.to) return null
  return [q.from.lat, q.from.lon, q.to.lat, q.to.lon, q.depart, q.cond].join('|')
}

/** Fetches the fastest + PathPro routes for the current trip; never shows a previous trip's routes. */
export function useRoutes(query: TripQuery, handlers: RouteHandlers): { routes: Routes | null; loading: boolean } {
  const [state, setState] = useState<RouteState>({ key: null, routes: null, failed: false })
  const latest = useLatest(handlers)
  const { from, to, depart, cond } = query
  const key = tripKey(query)

  useEffect(() => {
    if (!from || !to) return
    let cancelled = false
    const requestKey = tripKey({ from, to, depart, cond })
    latest.current.onError(null)
    api
      .routes(from, to, depart, cond)
      .then((r) => {
        if (cancelled) return
        setState({ key: requestKey, routes: r, failed: false })
        latest.current.onLoaded(r)
      })
      .catch((e: unknown) => {
        if (cancelled) return
        setState({ key: requestKey, routes: null, failed: true })
        latest.current.onError(e instanceof ApiError ? e.message : 'Could not compute routes.')
        if (e instanceof ApiError && e.code === 'OUT_OF_COVERAGE') latest.current.onOutside(to)
      })
    return () => {
      cancelled = true
    }
  }, [from, to, depart, cond, latest])

  const current = key != null && state.key === key
  return { routes: current ? state.routes : null, loading: key != null && !current }
}
