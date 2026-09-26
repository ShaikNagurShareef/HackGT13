/** Turn-by-turn helpers for navigation mode: where the walker is on the route and what comes next. */

import { continueHeadline, tripNoun, type TravelMode } from './modes'
import { cumulativeDistances, haversine, type WalkAlert } from './walk'

export interface LatLon {
  lat: number
  lon: number
}

export const ARRIVAL_RADIUS_M = 30
/** Within this distance of the route, Start follows GPS; farther away it previews the walk. */
export const NEAR_ROUTE_M = 150
/** How far ahead the banner warns about the next high-risk stretch. */
export const ALERT_LOOKAHEAD_M = 400
/** Remaining distance at which the banner switches to the destination. */
export const ARRIVING_M = 60

const EARTH_M_PER_DEG = (6_371_000 * Math.PI) / 180
const ROUND_TO_M = 10

export function distanceM(a: LatLon, b: LatLon): number {
  return haversine([a.lon, a.lat], [b.lon, b.lat])
}

export interface Projection {
  alongM: number
  offsetM: number
}

/** Local metric frame centred on `p`, accurate to well under a metre across a walk. */
function toLocal(p: LatLon): (c: [number, number]) => [number, number] {
  const kx = EARTH_M_PER_DEG * Math.cos((p.lat * Math.PI) / 180)
  return ([lon, lat]) => [(lon - p.lon) * kx, (lat - p.lat) * EARTH_M_PER_DEG]
}

/** Closest point on segment AB to the origin: parameter t in [0, 1] and its distance. */
function closestOnSegment([ax, ay]: [number, number], [bx, by]: [number, number]): { t: number; d: number } {
  const dx = bx - ax
  const dy = by - ay
  const len2 = dx * dx + dy * dy
  const t = len2 === 0 ? 0 : Math.max(0, Math.min(1, -(ax * dx + ay * dy) / len2))
  return { t, d: Math.hypot(ax + t * dx, ay + t * dy) }
}

/** Project a position onto a [lon, lat] polyline: metres walked along it and metres off it. */
export function projectOnRoute(
  coords: ReadonlyArray<[number, number]>,
  cum: ReadonlyArray<number>,
  p: LatLon,
): Projection {
  const local = toLocal(p)
  if (coords.length < 2) {
    return { alongM: 0, offsetM: coords.length ? Math.hypot(...local(coords[0])) : 0 }
  }
  let best: Projection = { alongM: 0, offsetM: Number.POSITIVE_INFINITY }
  for (let i = 1; i < coords.length; i++) {
    const { t, d } = closestOnSegment(local(coords[i - 1]), local(coords[i]))
    if (d < best.offsetM) best = { alongM: cum[i - 1] + t * (cum[i] - cum[i - 1]), offsetM: d }
  }
  return best
}

export function formatDistance(m: number): string {
  if (m >= 1000) return `${(m / 1000).toFixed(1)} km`
  return `${Math.max(ROUND_TO_M, Math.round(m / ROUND_TO_M) * ROUND_TO_M)} m`
}

export function remainingSeconds(durationS: number, totalM: number, alongM: number): number {
  if (totalM <= 0) return 0
  return Math.max(0, durationS * (1 - alongM / totalM))
}

export function hasArrived(p: LatLon, destination: LatLon, radiusM = ARRIVAL_RADIUS_M): boolean {
  return distanceM(p, destination) <= radiusM
}

export interface NavInstruction {
  tone: 'alert' | 'info' | 'arrive'
  headline: string
  detail: string
}

export interface InstructionInput {
  alerts: ReadonlyArray<WalkAlert>
  alongM: number
  totalM: number
  durationS: number
  street: string | null
  destination: string
  /** Travel mode: ride modes get ride wording on the street banner (alerts read the same). */
  mode?: TravelMode
}

function joinNames(names: ReadonlyArray<string>): string {
  return names.join(' and ')
}

/** Calm, single-action banner copy (PRD §7.4): traffic risk only, never "safe" or "danger". */
export function nextInstruction(input: InstructionInput): NavInstruction {
  const { alerts, alongM, totalM } = input
  const next = alerts.find((a) => alongM < a.end_m)
  if (next && alongM >= next.start_m) {
    return { tone: 'alert', headline: 'High traffic risk here', detail: `${joinNames(next.names)} · take extra care crossing` }
  }
  if (next && next.start_m - alongM <= ALERT_LOOKAHEAD_M) {
    return {
      tone: 'alert',
      headline: 'High traffic risk ahead',
      detail: `${joinNames(next.names)} in ${formatDistance(next.start_m - alongM)}`,
    }
  }
  const leftM = Math.max(0, totalM - alongM)
  if (leftM <= ARRIVING_M) {
    return { tone: 'arrive', headline: 'Almost there', detail: `${input.destination} in ${formatDistance(leftM)}` }
  }
  const minutes = Math.max(1, Math.round(remainingSeconds(input.durationS, totalM, alongM) / 60))
  return {
    tone: 'info',
    headline: continueHeadline(input.street, input.mode ?? 'walk'),
    detail: `${minutes} min to go`,
  }
}

export interface NamedPath {
  path: ReadonlyArray<[number, number]>
  name: string
}

/** Name of the street closest to `p` (the route's own segments are passed in). */
export function nearestStreet(p: LatLon, streets: ReadonlyArray<NamedPath>): string | null {
  const local = toLocal(p)
  let best: { name: string; d: number } | null = null
  for (const s of streets) {
    for (let i = 1; i < s.path.length; i++) {
      const { d } = closestOnSegment(local(s.path[i - 1]), local(s.path[i]))
      if (!best || d < best.d) best = { name: s.name, d }
    }
  }
  return best?.name ?? null
}

export interface StartChoice {
  mode: 'gps' | 'preview'
  note: string | null
}

/** Start follows GPS on or near the route; otherwise (GPS off, or at the expo) it previews the walk or ride. */
export function startMode(coords: ReadonlyArray<[number, number]>, gps: LatLon | null, travel: TravelMode = 'walk'): StartChoice {
  const noun = tripNoun(travel)
  if (!gps) return { mode: 'preview', note: `Location is off, so Start previews the ${noun}.` }
  const { offsetM } = projectOnRoute(coords, cumulativeDistances(coords), gps)
  if (offsetM <= NEAR_ROUTE_M) return { mode: 'gps', note: null }
  return { mode: 'preview', note: `You're ${formatDistance(offsetM)} from this route, so Start previews the ${noun}.` }
}
