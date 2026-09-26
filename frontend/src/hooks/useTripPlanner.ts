import { useCallback, useEffect } from 'react'
import { resolveOrigin, type ResolvedOrigin } from '../lib/origin'
import type { Place, ViewState } from '../state/urlState'
import type { Geolocation } from './useGeolocation'

export interface TripPlannerInput {
  view: ViewState
  update: (patch: Partial<ViewState>) => void
  geo: Geolocation
  bbox: ReadonlyArray<number>
}

export interface TripPlanner {
  origin: ResolvedOrigin
  pickDestination: (place: Place) => void
  pickOrigin: (place: Place) => void
  swap: () => void
  clear: () => void
}

/** Google-Maps-style trip entry: pick a destination and the start defaults to "Your location". */
export function useTripPlanner({ view, update, geo, bbox }: TripPlannerInput): TripPlanner {
  const origin = resolveOrigin(geo, bbox)
  const gpsStart = origin.place
  const { request } = geo

  const pickDestination = useCallback(
    (place: Place) => {
      if (view.from) return update({ to: place, seg: null })
      if (gpsStart) return update({ from: gpsStart, to: place, seg: null })
      update({ to: place, seg: null })
      request()
    },
    [view.from, gpsStart, update, request],
  )

  // The first GPS fix can arrive after the destination was picked: start from it then.
  useEffect(() => {
    if (view.to && !view.from && gpsStart) update({ from: gpsStart })
  }, [view.to, view.from, gpsStart, update])

  const pickOrigin = useCallback((place: Place) => update({ from: place, seg: null }), [update])
  const swap = useCallback(() => update({ from: view.to, to: view.from, seg: null }), [update, view.from, view.to])
  const clear = useCallback(() => update({ from: null, to: null, seg: null }), [update])

  return { origin, pickDestination, pickOrigin, swap, clear }
}
