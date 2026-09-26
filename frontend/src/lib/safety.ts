/**
 * Personal-safety copy and formatting. Wording rules: "reported crimes against persons",
 * "well-lit", "busier streets", "help points" — never words that label a place as good or bad.
 */

import type { ActivityBand, CrimeBand, DayPart, HelpPoint, HelpPointKind, RouteSafety, SafetyHex } from '../api/safetySchemas'
import { hourLabel } from './time'

export type RGB = [number, number, number]

const HOURS_PER_DAY = 24
const PERCENT = 100
/** A route counts as "busier streets" when at least half of it runs along busier streets. */
export const BUSY_SHARE_MIN = 0.5

export const FAIRNESS_NOTE =
  'Reported incidents, grouped by area and time of day. Reports reflect where police record incidents, not how people should feel about a neighborhood. PathPro never routes around neighborhoods based on crime.'

export const CRIME_LAYER_NAME = 'Reported crimes against persons'

/**
 * Calm indigo tints, lighter as reports rise. Deliberately outside the traffic-risk ramp
 * (blue → amber → pink) and never red, so the layer informs without alarming.
 */
export const CRIME_BAND_INFO: Record<CrimeBand, { label: string; phrase: string; rgb: RGB; alpha: number }> = {
  lower: { label: 'Fewer reports', phrase: 'fewer reports than typical', rgb: [92, 104, 170], alpha: 70 },
  typical: { label: 'Typical', phrase: 'typical for the city', rgb: [124, 130, 208], alpha: 115 },
  higher: { label: 'More reports', phrase: 'more reports than typical', rgb: [172, 166, 240], alpha: 165 },
}

export const HELP_POINT_INFO: Record<HelpPointKind, { label: string; rgb: RGB }> = {
  blue_light: { label: 'Blue-light emergency phone', rgb: [58, 136, 255] },
  police: { label: 'Police station', rgb: [150, 170, 230] },
  fire: { label: 'Fire station', rgb: [240, 172, 112] },
  hospital: { label: 'Hospital', rgb: [112, 212, 172] },
  marta: { label: 'MARTA station', rgb: [246, 190, 72] },
}

export const ACTIVITY_LABEL: Record<ActivityBand, string> = {
  quiet: 'Quieter streets',
  moderate: 'Moderate foot traffic',
  busy: 'Busier streets',
}

export function rgbCss([r, g, b]: RGB, alpha = 1): string {
  return `rgb(${r} ${g} ${b} / ${alpha})`
}

function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`
}

function percent(share: number): string {
  return `${Math.round(share * PERCENT)}%`
}

/** Compact route-row line, e.g. "82% well-lit · 3 help points nearby · busier streets". Never mentions crime. */
export function formatRouteSafety(safety: RouteSafety | null): string | null {
  if (!safety) return null
  const parts = [
    safety.lit_share != null ? `${percent(safety.lit_share)} well-lit` : null,
    safety.help_points_within_100m > 0 ? `${plural(safety.help_points_within_100m, 'help point', 'help points')} nearby` : null,
    safety.busy_share != null && safety.busy_share >= BUSY_SHARE_MIN ? 'busier streets' : null,
  ].filter((p): p is string => p != null)
  return parts.length ? parts.join(' · ') : null
}

/** Expanded panel only: "4 reported crimes against persons nearby (evening, last 12 months)". */
export function formatRouteCrimes(safety: RouteSafety | null, parts: ReadonlyArray<DayPart>): string | null {
  if (!safety) return null
  const when = `(${dayPartName(safety.day_part, parts).toLowerCase()}, last 12 months)`
  const n = safety.crimes_persons_nearby
  if (n === 0) return `No reported crimes against persons nearby ${when}`
  return `${plural(n, 'reported crime', 'reported crimes')} against persons nearby ${when}`
}

function wrapRange(start: number, end: number): number[] {
  const length = (end - start + HOURS_PER_DAY) % HOURS_PER_DAY
  return Array.from({ length }, (_, i) => (start + i) % HOURS_PER_DAY)
}

const HOUR_RANGE = /^(\d{1,2})\s*[-–]\s*(\d{1,2})$/

/** The hours a day part covers, whatever shape the API used. */
function partHours(part: DayPart): number[] {
  if (typeof part.hours === 'string') {
    const m = part.hours.trim().match(HOUR_RANGE)
    return m ? wrapRange(Number(m[1]) % HOURS_PER_DAY, Number(m[2]) % HOURS_PER_DAY) : []
  }
  const [a, b] = part.hours
  const isPair = part.hours.length === 2 && (b - a + HOURS_PER_DAY) % HOURS_PER_DAY > 1
  return isPair ? wrapRange(a, b) : [...part.hours]
}

export function dayPartFor(hour: number, parts: ReadonlyArray<DayPart>): DayPart | null {
  return parts.find((p) => partHours(p).includes(hour)) ?? null
}

export function dayPartName(key: string, parts: ReadonlyArray<DayPart>): string {
  return parts.find((p) => p.key === key)?.label ?? key
}

/** "5 PM–10 PM" for a contiguous day part (wrapping past midnight); '' when it can't be read. */
export function hoursLabel(part: DayPart): string {
  const hours = new Set(partHours(part))
  const start = [...hours].find((h) => !hours.has((h - 1 + HOURS_PER_DAY) % HOURS_PER_DAY))
  if (start == null) return ''
  let end = start
  while (hours.has(end % HOURS_PER_DAY)) end += 1
  return `${hourLabel(start)}–${hourLabel(end % HOURS_PER_DAY)}`
}

/** Tap card / tooltip content for one hex. */
export function hexSummary(hex: SafetyHex, dayLabel: string | null): { title: string; lines: string[] } {
  const crimes = plural(hex.crimes_persons_12mo, 'reported crime', 'reported crimes')
  const lines = [
    `${crimes} against persons in the last 12 months (${CRIME_BAND_INFO[hex.crime_band].phrase})`,
    hex.lit_share != null ? `${percent(hex.lit_share)} well-lit` : null,
    hex.activity_band ? ACTIVITY_LABEL[hex.activity_band] : null,
    hex.help_points > 0 ? plural(hex.help_points, 'help point', 'help points') : null,
  ].filter((l): l is string => l != null)
  return { title: dayLabel ? `This area · ${dayLabel}` : 'This area', lines }
}

export function helpPointLabel(point: HelpPoint): string {
  const kind = HELP_POINT_INFO[point.kind].label
  return point.name ? `${kind} · ${point.name}` : kind
}

/** One-line scope statement for the welcome, search, and sidebar. Honest when the layer is absent. */
export function scopeLine(safetyAvailable: boolean): string {
  return safetyAvailable
    ? 'Traffic risk, plus personal-safety signals: lighting, foot traffic, help points, and reported crimes against persons.'
    : 'Traffic risk from crash history.'
}

/** Only http(s) source links are rendered. */
export function safeHref(url: string): string | null {
  return /^https?:\/\//i.test(url) ? url : null
}
