/** Share my walk: follow-link paths, route thinning for upload, and "updated 12 s ago" text. */

import { withBase } from '../api/demo'

/** The server accepts at most this many route points. */
export const MAX_ROUTE_POINTS = 2000
const FOLLOW_PATH = /\/follow\/([A-Za-z0-9_-]+)\/?$/
const JUST_NOW_MS = 5_000
const MS_PER_S = 1000
const S_PER_MIN = 60
const MIN_PER_H = 60

/** The walk id in a /follow/<id> path (any deploy base), or null for every other page. */
export function followIdFromPath(pathname: string): string | null {
  return FOLLOW_PATH.exec(pathname)?.[1] ?? null
}

/** The link a friend opens; demo links stay in demo mode so they never touch the network. */
export function followUrl(origin: string, walkId: string, demo: boolean): string {
  return `${origin}${withBase(`/follow/${walkId}`)}${demo ? '?demo=1' : ''}`
}

/** Evenly thin a long route to the upload limit, always keeping the first and last points. */
export function downsampleRoute(
  coords: ReadonlyArray<[number, number]>,
  max: number = MAX_ROUTE_POINTS,
): [number, number][] {
  if (coords.length <= max) return [...coords]
  const step = (coords.length - 1) / (max - 1)
  return Array.from({ length: max }, (_, i) => coords[Math.round(i * step)])
}

export function formatAgo(ms: number): string {
  if (ms < JUST_NOW_MS) return 'just now'
  const s = Math.floor(ms / MS_PER_S)
  if (s < S_PER_MIN) return `${s} s ago`
  const min = Math.floor(s / S_PER_MIN)
  if (min < MIN_PER_H) return `${min} min ago`
  return `${Math.floor(min / MIN_PER_H)} h ago`
}
