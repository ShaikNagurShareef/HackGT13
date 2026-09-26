/** Travel modes (Walk · Bike · E-bike · Scooter): labels, speeds, and mode-aware copy. */

import { travelModeSchema, type ModeInfo, type TravelMode } from '../api/schemas'
import { WALK_SPEED_MPS } from './walk'

export type { ModeInfo, TravelMode } from '../api/schemas'

export const TRAVEL_MODES: ReadonlyArray<TravelMode> = travelModeSchema.options
export const DEFAULT_MODE: TravelMode = 'walk'
export const UNAVAILABLE_NOTE = 'Coming soon in this area'

export const MODE_LABELS: Record<TravelMode, string> = {
  walk: 'Walk',
  bike: 'Bike',
  ebike: 'E-bike',
  scooter: 'Scooter',
}

const KMH_PER_MPS = 3.6
const SECONDS_PER_MIN = 60
/** Used only when the server does not list a mode's speed. */
export const FALLBACK_SPEED_KMH: Record<TravelMode, number> = {
  walk: WALK_SPEED_MPS * KMH_PER_MPS,
  bike: 15,
  ebike: 20,
  scooter: 15,
}

const WALK_ARRIVAL_M = 30
const RIDE_ARRIVAL_M = 40
const RIDE_PREFIX = 'ride_'

export function isTravelMode(value: unknown): value is TravelMode {
  return travelModeSchema.safeParse(value).success
}

export function isRideMode(mode: TravelMode): boolean {
  return mode !== 'walk'
}

/** "walk" or "ride": the noun in durations and copy ("12 min ride", "previews the ride"). */
export function tripNoun(mode: TravelMode): 'walk' | 'ride' {
  return isRideMode(mode) ? 'ride' : 'walk'
}

function fallbackInfo(key: TravelMode): ModeInfo {
  const ride = isRideMode(key)
  return {
    key,
    label: MODE_LABELS[key],
    available: !ride,
    speed_kmh: FALLBACK_SPEED_KMH[key],
    network: ride ? 'ride' : 'walk',
    static_prefix: ride ? RIDE_PREFIX : '',
  }
}

/** All four tabs in order. Modes the server doesn't list show as unavailable; walk is always available. */
export function modeOptions(modes: ReadonlyArray<ModeInfo>): ModeInfo[] {
  return TRAVEL_MODES.map((key) => {
    const listed = modes.find((m) => m.key === key)
    if (!listed) return fallbackInfo(key)
    return key === 'walk' && !listed.available ? { ...listed, available: true } : listed
  })
}

export function modeInfo(mode: TravelMode, options: ReadonlyArray<ModeInfo>): ModeInfo {
  return options.find((o) => o.key === mode) ?? fallbackInfo(mode)
}

/** The requested mode when it is available here, otherwise Walk. */
export function resolveMode(requested: TravelMode, options: ReadonlyArray<ModeInfo>): TravelMode {
  return modeInfo(requested, options).available ? requested : DEFAULT_MODE
}

export function modeUnavailableMessage(mode: TravelMode): string {
  return `${MODE_LABELS[mode]} routes aren't available in this area yet. Showing the walk instead.`
}

export function speedMps(mode: TravelMode, options: ReadonlyArray<ModeInfo>): number {
  const listed = options.find((o) => o.key === mode)
  return (listed?.speed_kmh ?? FALLBACK_SPEED_KMH[mode]) / KMH_PER_MPS
}

function minutes(seconds: number): number {
  return Math.max(1, Math.round(seconds / SECONDS_PER_MIN))
}

/** "12 min ride" / "12 min walk". */
export function formatTripMinutes(seconds: number, mode: TravelMode): string {
  return `${minutes(seconds)} min ${tripNoun(mode)}`
}

/** Rough minutes for a routed distance at the mode's speed (tabs and chips before a fetch). */
export function estimateMinutes(distanceM: number, mode: TravelMode, options: ReadonlyArray<ModeInfo>): number {
  return minutes(distanceM / speedMps(mode, options))
}

export function continueHeadline(street: string | null, mode: TravelMode): string {
  const name = street ?? 'the PathPro route'
  return isRideMode(mode) ? `Keep riding on ${name}` : `Continue on ${name}`
}

export function arrivalRadiusM(mode: TravelMode): number {
  return isRideMode(mode) ? RIDE_ARRIVAL_M : WALK_ARRIVAL_M
}

export function travelingTo(mode: TravelMode, destination: string): string {
  return `${isRideMode(mode) ? 'Riding' : 'Walking'} to ${destination}`
}

export function networkLegendTitle(mode: TravelMode): string {
  return isRideMode(mode) ? 'Traffic risk to people on bikes & scooters' : 'Traffic risk to pedestrians'
}

export interface TabDuration {
  minutes: number
  /** True for a distance-based estimate (the mode has not been routed yet). */
  estimated: boolean
}

/** Per-tab duration: the routed time when fetched, an estimate when available, nothing when unavailable. */
export function tabDurations(
  options: ReadonlyArray<ModeInfo>,
  fetched: Partial<Record<TravelMode, number>>,
  distanceM: number | null,
): Record<TravelMode, TabDuration | null> {
  const entry = (info: ModeInfo): TabDuration | null => {
    if (!info.available) return null
    const seconds = fetched[info.key]
    if (seconds != null) return { minutes: minutes(seconds), estimated: false }
    return distanceM == null ? null : { minutes: estimateMinutes(distanceM, info.key, options), estimated: true }
  }
  return Object.fromEntries(options.map((o) => [o.key, entry(o)])) as Record<TravelMode, TabDuration | null>
}
