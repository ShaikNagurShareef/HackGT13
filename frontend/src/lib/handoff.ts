/** MARTA hand-off and "try a ride" suggestions for long walks (pure logic for the route sheet). */

import type { ModeInfo, TransitStation, TravelMode } from '../api/schemas'
import type { Place } from '../state/urlState'
import { MODE_LABELS, TRAVEL_MODES, estimateMinutes, isRideMode } from './modes'
import { estimateWalkMin } from './suggestion'
import { distanceM, type LatLon } from './navigation'

/** Walks longer than this (fastest route) get the MARTA card and the ride chip. */
export const HANDOFF_MIN_S = 25 * 60

export interface NearestStation {
  station: TransitStation
  walkMin: number
}

export interface MartaHandoff {
  /** Station to walk to from the start. */
  board: NearestStation
  /** Station nearest the destination, and the walk from it. */
  alight: NearestStation | null
}

export function nearestStation(p: LatLon, stations: ReadonlyArray<TransitStation>): NearestStation | null {
  let best: TransitStation | null = null
  let bestM = Number.POSITIVE_INFINITY
  for (const s of stations) {
    const d = distanceM(p, s)
    if (d < bestM) {
      best = s
      bestM = d
    }
  }
  return best ? { station: best, walkMin: estimateWalkMin(p, best) } : null
}

export interface HandoffInput {
  from: LatLon | null
  to: LatLon | null
  /** The walk's fastest-route duration. */
  walkDurationS: number | null
  stations: ReadonlyArray<TransitStation>
}

/** Rail helps only when both ends have different stations and walking to them beats walking the trip. */
export function martaHandoff({ from, to, walkDurationS, stations }: HandoffInput): MartaHandoff | null {
  if (!from || !to || walkDurationS == null || walkDurationS <= HANDOFF_MIN_S) return null
  const board = nearestStation(from, stations)
  const alight = nearestStation(to, stations)
  if (!board || !alight || board.station.name === alight.station.name) return null
  if (board.walkMin + alight.walkMin >= walkDurationS / 60) return null
  return { board, alight }
}

export function stationLabel(name: string): string {
  return /station$/i.test(name) ? name : `${name} station`
}

export function stationPlace(station: TransitStation): Place {
  return { lat: station.lat, lon: station.lon, label: stationLabel(station.name) }
}

export function handoffTitle(h: MartaHandoff): string {
  return `Faster with MARTA: walk ${h.board.walkMin} min to ${stationLabel(h.board.station.name)}`
}

export function handoffFollowUp(h: MartaHandoff): string | null {
  return h.alight ? `…then from ${stationLabel(h.alight.station.name)}, ${h.alight.walkMin} min walk` : null
}

export interface RideSuggestion {
  mode: TravelMode
  minutes: number
}

export interface RideSuggestionInput {
  walkDurationS: number | null
  distanceM: number
  options: ReadonlyArray<ModeInfo>
}

/** "Try Bike: ~14 min" when the walk is long and a ride mode is available here. */
export function rideSuggestion({ walkDurationS, distanceM, options }: RideSuggestionInput): RideSuggestion | null {
  if (walkDurationS == null || walkDurationS <= HANDOFF_MIN_S) return null
  const mode = TRAVEL_MODES.find((m) => isRideMode(m) && options.some((o) => o.key === m && o.available))
  return mode ? { mode, minutes: estimateMinutes(distanceM, mode, options) } : null
}

export function rideChipLabel(s: RideSuggestion): string {
  return `Try ${MODE_LABELS[s.mode]}: ~${s.minutes} min`
}
