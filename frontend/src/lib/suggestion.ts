/** Wording and strength of learned-routine suggestions for the home card. */

import type { RoutineSuggestion } from './routines'
import { WALK_SPEED_MPS, haversine } from './walk'

/** A routine needs this score (≈ a regular trip from where you stand) to earn the home card. */
export const STRONG_ROUTINE_SCORE = 1

export function isStrongSuggestion(s: RoutineSuggestion | undefined): s is RoutineSuggestion {
  if (!s) return false
  return s.kind === 'return' || (s.kind === 'routine' && s.score >= STRONG_ROUTINE_SCORE)
}

export function suggestionHeadline(s: RoutineSuggestion): string {
  if (s.kind === 'return') return `Heading back to ${s.to.label}?`
  if (s.kind === 'routine') return `Heading to ${s.to.label}?`
  return `Go to ${s.to.label}?`
}

/** Straight-line walks bend around blocks; this keeps the estimate close to routed times. */
const DETOUR_FACTOR = 1.3
const SECONDS_PER_MIN = 60

/** Rough walking minutes between two points, for the suggestion card before routes are fetched. */
export function estimateWalkMin(from: { lat: number; lon: number }, to: { lat: number; lon: number }): number {
  const metres = haversine([from.lon, from.lat], [to.lon, to.lat]) * DETOUR_FACTOR
  return Math.max(1, Math.round(metres / WALK_SPEED_MPS / SECONDS_PER_MIN))
}
