/** Where a walk starts: the GPS fix when it is inside coverage, otherwise a friendly ask. */

import type { Place } from '../state/urlState'
import { inBbox } from './places'

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
