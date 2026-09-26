/**
 * On-device routine learning: remembers past walks in localStorage and suggests the next one
 * ("You usually walk here on Fridays around 10 PM", "Heading back?", Home / Work).
 *
 * Privacy: nothing here touches the network; history lives only in this browser.
 * Resilience: every storage read/write is try/catch + zod-validated, so corrupt or blocked
 * storage degrades to "no history" and never throws into the UI.
 */

import { z } from 'zod'
import { atlantaParts, hourLabel } from './time'

export interface Place {
  label: string
  lat: number
  lon: number
}
export interface TripRecord {
  from: Place
  to: Place
  at: string // ISO timestamp when the walk started
}
export type SavedKind = 'home' | 'work'
export interface RoutineSuggestion {
  from: Place | null // null = "from your current location"
  to: Place
  reason: string
  kind: 'routine' | 'return' | 'saved'
  score: number // higher = better
}
type LatLon = { lat: number; lon: number }
type Saved = Partial<Record<SavedKind, Place>>

export const ROUTINES_STORAGE_KEY = 'pathpro:routines:v1'

const MAX_TRIPS = 200
const MAX_LABEL_CHARS = 200
const DEFAULT_SUGGESTIONS = 3
const DEFAULT_RECENTS = 5
const CLUSTER_RADIUS_M = 150 // points this close are the same place
const NEAR_M = 300 // "you are at the origin / destination"
const HERE_EXCLUSION_M = 200 // never suggest where you already are
const FAR_ORIGIN_M = 1500
const NEAR_ORIGIN_BOOST = 3
const FAR_ORIGIN_FACTOR = 0.25
const MIN_OCCURRENCES = 2
const MIN_ROUTINE_SCORE = 0.15
const FULL_HOUR_WINDOW = 1 // hours of full time-similarity weight
const ZERO_HOUR_WINDOW = 3 // similarity tapers to 0 here
const SAME_WEEKDAY = 1
const SAME_DAY_TYPE = 0.6
const OTHER_DAY = 0.2
const HALF_LIFE_DAYS = 14
const DAY_MS = 86_400_000
const HOUR_MS = 3_600_000
const RETURN_WINDOW_MS = 12 * HOUR_MS
const RETURN_SCORE = 2
const SAVED_SCORE = 0.5
const EVENING_FROM_HOUR = 17
const LATE_NIGHT_UNTIL_HOUR = 4
const WORK_MORNING = { from: 6, until: 11 }
const EARTH_RADIUS_M = 6_371_000

const WEEKDAY_SHORT = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'] as const
const WEEKDAY_LONG = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'] as const

// ---------- validation + storage ----------

const placeSchema = z.object({
  label: z.string().transform((s) => s.slice(0, MAX_LABEL_CHARS)),
  lat: z.number().min(-90).max(90),
  lon: z.number().min(-180).max(180),
})
const tripSchema = z.object({
  from: placeSchema,
  to: placeSchema,
  at: z.string().refine((s) => Number.isFinite(Date.parse(s)), 'invalid timestamp'),
})
const rawStoreSchema = z.object({
  trips: z.array(z.unknown()).catch([]),
  saved: z
    .object({ home: placeSchema.optional().catch(undefined), work: placeSchema.optional().catch(undefined) })
    .catch({}),
})

interface Store {
  trips: ReadonlyArray<TripRecord>
  saved: Saved
}
const EMPTY_STORE: Store = { trips: [], saved: {} }

function resolveStorage(storage?: Storage): Storage | null {
  if (storage) return storage
  try {
    return typeof window === 'undefined' ? null : window.localStorage
  } catch {
    return null // storage blocked (privacy mode / sandboxed iframe)
  }
}

function compactSaved(saved: Saved): Saved {
  return Object.fromEntries(Object.entries(saved).filter(([, p]) => p != null)) as Saved
}

function readStore(storage: Storage | null): Store {
  if (!storage) return EMPTY_STORE
  try {
    const raw = storage.getItem(ROUTINES_STORAGE_KEY)
    if (raw == null) return EMPTY_STORE
    const parsed = rawStoreSchema.safeParse(JSON.parse(raw))
    if (!parsed.success) return EMPTY_STORE
    const trips = parsed.data.trips.flatMap((t) => {
      const r = tripSchema.safeParse(t)
      return r.success ? [r.data] : []
    })
    return { trips, saved: compactSaved(parsed.data.saved) }
  } catch {
    return EMPTY_STORE // unreadable or corrupt JSON: behave as if there is no history
  }
}

function writeStore(storage: Storage | null, store: Store): void {
  if (!storage) return
  try {
    storage.setItem(ROUTINES_STORAGE_KEY, JSON.stringify(store))
  } catch {
    // Quota exceeded or storage blocked: routines are a convenience, the walk still works.
  }
}

function updateStore(storage: Storage | undefined, update: (store: Store) => Store): void {
  const resolved = resolveStorage(storage)
  writeStore(resolved, update(readStore(resolved)))
}

// ---------- public storage API ----------

export function recordTrip(trip: TripRecord, storage?: Storage): void {
  const parsed = tripSchema.safeParse(trip)
  if (!parsed.success) return
  updateStore(storage, (store) => ({
    ...store,
    trips: [...store.trips, parsed.data].sort((a, b) => Date.parse(a.at) - Date.parse(b.at)).slice(-MAX_TRIPS),
  }))
}

/** All stored trips, oldest first. */
export function tripHistory(storage?: Storage): TripRecord[] {
  return [...readStore(resolveStorage(storage)).trips]
}

export function savedPlaces(storage?: Storage): Partial<Record<SavedKind, Place>> {
  return { ...readStore(resolveStorage(storage)).saved }
}

export function setSavedPlace(kind: SavedKind, place: Place | null, storage?: Storage): void {
  const parsed = place ? placeSchema.safeParse(place) : null
  if (parsed && !parsed.success) return
  updateStore(storage, (store) => ({ ...store, saved: compactSaved({ ...store.saved, [kind]: parsed?.data }) }))
}

/** Clears trip history but keeps saved Home / Work. */
export function clearHistory(storage?: Storage): void {
  updateStore(storage, (store) => ({ ...store, trips: [] }))
}

// ---------- geometry + clustering ----------

function distanceM(a: LatLon, b: LatLon): number {
  const toRad = (d: number) => (d * Math.PI) / 180
  const dLat = toRad(b.lat - a.lat)
  const dLon = toRad(b.lon - a.lon)
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLon / 2) ** 2
  return 2 * EARTH_RADIUS_M * Math.asin(Math.sqrt(h))
}

interface Cluster {
  id: number
  place: Place // most recent point (and label) seen in this cluster
}

function newestFirst(trips: ReadonlyArray<TripRecord>): TripRecord[] {
  return [...trips].sort((a, b) => Date.parse(b.at) - Date.parse(a.at))
}

function findCluster(clusters: ReadonlyArray<Cluster>, p: LatLon): Cluster | undefined {
  return clusters.find((c) => distanceM(c.place, p) <= CLUSTER_RADIUS_M)
}

/** Greedy ~150 m clustering anchored on the newest point, so the newest label wins. */
function buildClusters(trips: ReadonlyArray<TripRecord>): Cluster[] {
  return newestFirst(trips)
    .flatMap((t) => [t.to, t.from])
    .reduce<Cluster[]>((acc, p) => (findCluster(acc, p) ? acc : [...acc, { id: acc.length, place: p }]), [])
}

export function recentPlaces(storage?: Storage, limit = DEFAULT_RECENTS): Place[] {
  const { trips } = readStore(resolveStorage(storage))
  const clusters = buildClusters(trips)
  const ids = newestFirst(trips).map((t) => findCluster(clusters, t.to)?.id ?? -1)
  return [...new Set(ids)]
    .filter((id) => id >= 0)
    .slice(0, Math.max(0, limit))
    .map((id) => clusters[id].place)
}

// ---------- time similarity ----------

interface TimeCtx {
  day: number // 0 = Sunday, Atlanta local
  hour: number // fractional hour, Atlanta local
}

function timeCtx(d: Date): TimeCtx {
  const { weekday, hour, minute } = atlantaParts(d)
  return { day: WEEKDAY_SHORT.indexOf(weekday as (typeof WEEKDAY_SHORT)[number]), hour: hour + minute / 60 }
}

const isWeekend = (day: number) => day === 0 || day === 6

function hourSimilarity(a: number, b: number): number {
  const raw = Math.abs(a - b)
  const d = Math.min(raw, 24 - raw)
  if (d <= FULL_HOUR_WINDOW) return 1
  if (d >= ZERO_HOUR_WINDOW) return 0
  return (ZERO_HOUR_WINDOW - d) / (ZERO_HOUR_WINDOW - FULL_HOUR_WINDOW)
}

function daySimilarity(a: number, b: number): number {
  if (a === b) return SAME_WEEKDAY
  return isWeekend(a) === isWeekend(b) ? SAME_DAY_TYPE : OTHER_DAY
}

function recencyWeight(ageMs: number): number {
  return 0.5 ** (Math.max(0, ageMs) / DAY_MS / HALF_LIFE_DAYS)
}

function circularMeanHour(hours: ReadonlyArray<number>): number {
  const angles = hours.map((h) => (h / 24) * 2 * Math.PI)
  const x = angles.reduce((s, a) => s + Math.cos(a), 0)
  const y = angles.reduce((s, a) => s + Math.sin(a), 0)
  const mean = (Math.atan2(y, x) / (2 * Math.PI)) * 24
  return (mean + 24) % 24
}

function partOfDay(hour: number): string {
  if (hour >= 5 && hour < 12) return 'morning'
  if (hour >= 12 && hour < 17) return 'afternoon'
  if (hour >= 17 && hour < 21) return 'evening'
  return 'night'
}

/** "You usually walk here on Fridays around 10 PM" / "... on weekday mornings" / "... around 2 PM". */
function routineReason(times: ReadonlyArray<TimeCtx>): string {
  const hour = Math.round(circularMeanHour(times.map((t) => t.hour))) % 24
  const days = new Set(times.map((t) => t.day))
  const [firstDay] = days
  if (days.size === 1) return `You usually walk here on ${WEEKDAY_LONG[firstDay]}s around ${hourLabel(hour)}`
  const weekend = [...days].map(isWeekend)
  if (weekend.every((w) => !w)) return `You usually walk here on weekday ${partOfDay(hour)}s`
  if (weekend.every((w) => w)) return `You usually walk here on weekend ${partOfDay(hour)}s`
  return `You usually walk here around ${hourLabel(hour)}`
}

// ---------- suggestion sources ----------

interface PairMatch {
  from: Cluster
  to: Cluster
  weight: number
  time: TimeCtx
}

function matchTrips(trips: ReadonlyArray<TripRecord>, now: Date): PairMatch[] {
  const clusters = buildClusters(trips)
  const nowCtx = timeCtx(now)
  return trips.flatMap((t) => {
    const at = new Date(t.at)
    const time = timeCtx(at)
    const from = findCluster(clusters, t.from)
    const to = findCluster(clusters, t.to)
    const hourSim = hourSimilarity(nowCtx.hour, time.hour)
    if (!from || !to || from.id === to.id || hourSim === 0) return []
    const weight = hourSim * daySimilarity(nowCtx.day, time.day) * recencyWeight(now.getTime() - at.getTime())
    return [{ from, to, weight, time }]
  })
}

/** Stable grouping (Map.groupBy is ES2024; the app targets ES2023). */
function groupBy<T>(items: ReadonlyArray<T>, keyOf: (item: T) => string): T[][] {
  const keys = [...new Set(items.map(keyOf))]
  return keys.map((k) => items.filter((item) => keyOf(item) === k))
}

function originFactor(here: LatLon | null, origin: Place): { factor: number; from: Place | null } {
  if (!here) return { factor: 1, from: origin }
  const d = distanceM(here, origin)
  if (d <= NEAR_M) return { factor: NEAR_ORIGIN_BOOST, from: null }
  return { factor: d > FAR_ORIGIN_M ? FAR_ORIGIN_FACTOR : 1, from: origin }
}

function routineSuggestions(trips: ReadonlyArray<TripRecord>, now: Date, here: LatLon | null): RoutineSuggestion[] {
  const groups = groupBy(matchTrips(trips, now), (m) => `${m.from.id}>${m.to.id}`)
  return groups.flatMap((matches) => {
    const base = matches.reduce((s, m) => s + m.weight, 0)
    if (matches.length < MIN_OCCURRENCES || base < MIN_ROUTINE_SCORE) return []
    const { from: origin, to } = matches[0]
    const { factor, from } = originFactor(here, origin.place)
    const reason = routineReason(matches.map((m) => m.time))
    return [{ from, to: to.place, reason, kind: 'routine' as const, score: base * factor }]
  })
}

function returnSuggestion(trips: ReadonlyArray<TripRecord>, now: Date, here: LatLon | null): RoutineSuggestion[] {
  const last = newestFirst(trips).find((t) => Date.parse(t.at) <= now.getTime())
  if (!last || now.getTime() - Date.parse(last.at) > RETURN_WINDOW_MS) return []
  if (here && distanceM(here, last.to) > NEAR_M) return []
  return [{ from: here ? null : last.to, to: last.from, reason: 'Heading back?', kind: 'return', score: RETURN_SCORE }]
}

function savedSuggestions(saved: Saved, now: Date, here: LatLon | null): RoutineSuggestion[] {
  const { day, hour } = timeCtx(now)
  const evening = hour >= EVENING_FROM_HOUR || hour < LATE_NIGHT_UNTIL_HOUR
  const workMorning = !isWeekend(day) && hour >= WORK_MORNING.from && hour < WORK_MORNING.until
  const wanted: ReadonlyArray<[Place | undefined, boolean, string]> = [
    [saved.home, evening, 'Home'],
    [saved.work, workMorning, 'Work'],
  ]
  return wanted.flatMap(([place, active, reason]) => {
    if (!place || !active || (here && distanceM(here, place) <= NEAR_M)) return []
    return [{ from: null, to: place, reason, kind: 'saved' as const, score: SAVED_SCORE }]
  })
}

function rankAndDedupe(
  candidates: ReadonlyArray<RoutineSuggestion>,
  here: LatLon | null,
  limit: number,
): RoutineSuggestion[] {
  return candidates
    .filter((c) => !here || distanceM(here, c.to) > HERE_EXCLUSION_M)
    .toSorted((a, b) => b.score - a.score)
    .reduce<RoutineSuggestion[]>(
      (kept, c) => (kept.some((k) => distanceM(k.to, c.to) <= CLUSTER_RADIUS_M) ? kept : [...kept, c]),
      [],
    )
    .slice(0, Math.max(0, limit))
}

function validHere(here: LatLon | null): LatLon | null {
  return here && Number.isFinite(here.lat) && Number.isFinite(here.lon) ? here : null
}

/** Ranked next-walk suggestions for this moment and (optional) GPS fix. */
export function suggestTrips(
  now: Date,
  here: { lat: number; lon: number } | null,
  storage?: Storage,
  limit = DEFAULT_SUGGESTIONS,
): RoutineSuggestion[] {
  if (!Number.isFinite(now.getTime())) return []
  const { trips, saved } = readStore(resolveStorage(storage))
  const at = validHere(here)
  const candidates = [
    ...routineSuggestions(trips, now, at),
    ...returnSuggestion(trips, now, at),
    ...savedSuggestions(saved, now, at),
  ]
  return rankAndDedupe(candidates, at, limit)
}
