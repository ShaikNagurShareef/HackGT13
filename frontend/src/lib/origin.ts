/** Where a walk starts: the GPS fix when it is inside coverage, otherwise a friendly ask. */

import type { Place } from '../state/urlState'
import { distanceM } from './navigation'
import { PLACES, inBbox } from './places'

export const YOUR_LOCATION = 'Your location'

export type GeoStatus = 'prompt' | 'locating' | 'granted' | 'denied' | 'unavailable'

export interface GeoFix {
  lat: number
  lon: number
  accuracy: number
  heading: number | null
  at: number
}

export type OriginStatus = 'ready' | 'ask' | 'locating' | 'outside' | 'denied' | 'unavailable'

export interface ResolvedOrigin {
  place: Place | null
  status: OriginStatus
}

export function resolveOrigin(
  geo: { status: GeoStatus; position: GeoFix | null },
  bbox: ReadonlyArray<number>,
): ResolvedOrigin {
  const { position } = geo
  if (position) {
    return inBbox(bbox, position)
      ? { place: { lat: position.lat, lon: position.lon, label: YOUR_LOCATION }, status: 'ready' }
      : { place: null, status: 'outside' }
  }
  if (geo.status === 'denied' || geo.status === 'unavailable') return { place: null, status: geo.status }
  if (geo.status === 'prompt') return { place: null, status: 'ask' }
  return { place: null, status: 'locating' }
}

const MESSAGES: Record<OriginStatus, string | null> = {
  ready: null,
  locating: 'Finding your location…',
  ask: 'Pick a starting point, or tap the locate button to start from where you are.',
  outside: "You're outside Atlanta — PathPro covers the City of Atlanta. Pick a starting point.",
  denied: "Location is off, so PathPro can't start from where you are. Pick a starting point.",
  unavailable: "This device isn't sharing a location right now. Pick a starting point.",
}

export function originMessage(status: OriginStatus): string | null {
  return MESSAGES[status]
}

/** A GPS start this close to a curated place is recorded under that place's name. */
const NAMED_START_RADIUS_M = 200
const UNNAMED_START = 'Start point'

/** Trip history never stores "Your location" (it would read "Heading back to Your location?"). */
export function describeStart(place: Place): Place {
  if (place.label !== YOUR_LOCATION) return place
  let best: { label: string; d: number } | null = null
  for (const p of PLACES) {
    const d = distanceM(place, p)
    if (d <= NAMED_START_RADIUS_M && (!best || d < best.d)) best = { label: p.label, d }
  }
  return { ...place, label: best?.label ?? UNNAMED_START }
}
